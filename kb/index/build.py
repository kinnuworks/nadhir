"""Build the clause-level retrieval corpus.

Inputs:
  kb/sources.yaml            project sources (metadata, hashes, quotes)
  kb/cache/                  raw bytes of fetched project sources (filled by --fetch)
  <dataset>                  the organiser's UAE PolicyData folder (CLI arg)

Outputs:
  kb/index/clauses.jsonl     one clause per line
  kb/index/documents.json    one record per document
  kb/cache/manifest.json     fetch results (with --fetch)

Usage:
  python kb/index/build.py --fetch --dataset /path/to/Dataset/UAE/PolicyData
"""

import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
import zipfile
from collections import Counter
from pathlib import Path

import lxml.etree
import lxml.html
import yaml

ROOT = Path(__file__).resolve().parents[2]
KB = ROOT / "kb"
OUT = KB / "index"
UA = "Mozilla/5.0 (research KB build)"
PDFTOTEXT = "/opt/homebrew/bin/pdftotext"
REPO_BLOB = ("https://github.com/CrashingGuru/Sandbox_Training/blob/"
             "b4f5073346e4bc661070f53c8e005b229ee1d6bc/Dataset/UAE/PolicyData/")
FOLDERS = ["01", "02", "03", "04", "05", "06"]
MIN_WORDS, MAX_WORDS = 30, 220
MAX_BYTES = 15 * 1024 * 1024
# Dropped first, in this order, if the corpus is over MAX_BYTES.
LOW_RELEVANCE = re.compile(r"space|virtual asset|autonomous", re.I)

BLOCK_TAGS = {
    "p", "div", "li", "ul", "ol", "table", "tr", "td", "th", "section", "article",
    "blockquote", "dd", "dt", "dl", "pre", "br", "main", "header", "aside", "figure",
    "figcaption", "caption", "tbody", "thead", "form", "center",
}
HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
DROP_TAGS = ["script", "style", "nav", "footer", "noscript", "template", "svg", "iframe", "head"]


# ---------------------------------------------------------------- text helpers

# zero-width, soft hyphen and bidi control characters
ZERO_WIDTH = dict.fromkeys(
    [0x200B, 0x200C, 0x200D, 0x2060, 0xFEFF, 0x00AD, 0x200E, 0x200F,
     0x202A, 0x202B, 0x202C, 0x202D, 0x202E, 0x2066, 0x2067, 0x2068, 0x2069], None)


def fix_ligatures(text):
    # pdftotext writes U+FFFD for some unmapped Latin ligature glyphs ("Th", "ff")
    text = re.sub(r"\ufffd{3,}", " ", text)
    text = re.sub(r"(?<![A-Za-z\ufffd])\ufffd(?=[a-z])", "Th", text)
    return re.sub(r"(?<=[a-z])\ufffd(?=[a-z])", "ff", text)


def clean(text):
    text = unicodedata.normalize("NFKC", text).translate(ZERO_WIDTH)
    text = fix_ligatures(text)
    text = re.sub(r"(?:\s?\.){4,}", " ", text)  # table-of-contents dot leaders
    return re.sub(r"\s+", " ", text).strip()


def dehyphenate(text):
    return re.sub(r"(\w)-\n\s*([a-z])", r"\1\2", text)


def words(text):
    return len(text.split())


def lang_of(text):
    ar = len(re.findall(r"[\u0600-\u06ff\u0750-\u077f\ufb50-\ufdff\ufe70-\ufeff]", text))
    lat = len(re.findall(r"[A-Za-z]", text))
    return "ar" if ar > lat else "en"


SENT_END = re.compile(r"(?<=[.!?;:\u061f\u06d4])\s+")


def split_long(text):
    """Split text over MAX_WORDS at sentence ends; hard-split as last resort."""
    if words(text) <= MAX_WORDS:
        return [text]
    out, cur = [], []
    for sent in SENT_END.split(text):
        sw = sent.split()
        if cur and words(" ".join(cur)) + len(sw) > MAX_WORDS:
            out.append(" ".join(cur))
            cur = []
        while len(sw) > MAX_WORDS:
            out.append(" ".join(sw[:MAX_WORDS]))
            sw = sw[MAX_WORDS:]
        cur.extend(sw)
    if cur:
        out.append(" ".join(cur))
    return out


def chunk(paras):
    """paras: list of (locator, text). Merge short neighbours with the same
    locator, split long ones. Returns list of (locator, text)."""
    pieces = []
    for loc, text in paras:
        for p in split_long(text):
            if p:
                pieces.append((loc, p))
    out = []
    buf_loc, buf = None, ""
    for loc, text in pieces:
        if buf and (loc != buf_loc or words(buf) >= MIN_WORDS
                    or words(buf) + words(text) > MAX_WORDS):
            out.append((buf_loc, buf))
            buf = ""
        if not buf:
            buf_loc, buf = loc, text
        else:
            buf = buf + " " + text
    if buf:
        out.append((buf_loc, buf))
    # fold a short tail into the previous clause when it fits
    merged = []
    for loc, text in out:
        if (merged and words(text) < MIN_WORDS and merged[-1][0] == loc
                and words(merged[-1][1]) + words(text) <= MAX_WORDS):
            merged[-1] = (loc, merged[-1][1] + " " + text)
        else:
            merged.append((loc, text))
    return [(l, t) for l, t in merged if words(t) >= 4 or re.search(r"[\u0600-\u06ff]", t)]


# ---------------------------------------------------------------- extractors

def pdf_pages(path):
    res = subprocess.run([PDFTOTEXT, "-q", "-enc", "UTF-8", str(path), "-"],
                         capture_output=True, timeout=600)
    text = res.stdout.decode("utf-8", "replace")
    pages = text.split("\f")
    if pages and not pages[-1].strip():
        pages = pages[:-1]
    return pages


def edge_key(line):
    return re.sub(r"\d+", "#", line.strip().lower())


def pdf_paragraphs(path):
    pages = pdf_pages(path)
    # repeated header/footer lines: first/last 2 non-empty lines seen on most pages
    edge = Counter()
    page_lines = []
    for pg in pages:
        lines = pg.split("\n")
        page_lines.append(lines)
        nz = [l for l in lines if l.strip()]
        for l in set(map(edge_key, nz[:2] + nz[-2:])):
            edge[l] += 1
    repeated = set()
    if len(pages) >= 4:
        repeated = {k for k, n in edge.items() if n >= 0.5 * len(pages) and k.strip("# ")}
        repeated |= {"#", "# / #", "page #", "page # of #", "- # -"}
    paras = []
    for i, lines in enumerate(page_lines, 1):
        nz_idx = [j for j, l in enumerate(lines) if l.strip()]
        edges = set(nz_idx[:2] + nz_idx[-2:])
        kept = [l for j, l in enumerate(lines)
                if not (j in edges and edge_key(l) in repeated)]
        body = dehyphenate("\n".join(kept))
        for block in re.split(r"\n\s*\n", body):
            t = clean(block)
            if t:
                paras.append((f"p.{i}", t))
    return paras, len(pages)


def heading_text(el):
    return clean(el.text_content())[:160]


def is_heading(el):
    if el.tag in HEADING_TAGS:
        return True
    if el.tag not in ("p", "div"):
        return False
    for c in (el.get("class") or "").lower().split():
        if re.match(r"^(oj-)?(ti-|sti-|doc-ti)|^msoheading|^heading\d?$", c):
            return True
    return False


def html_paragraphs(raw):
    doc = lxml.html.document_fromstring(raw)
    title = clean(doc.findtext(".//title") or "")
    for el in doc.xpath("|".join("//" + t for t in DROP_TAGS)):
        el.drop_tree()
    for el in doc.xpath("//*[@role='navigation' or @aria-hidden='true']"):
        el.drop_tree()
    body = doc.find("body") if doc.find("body") is not None else doc
    paras = []
    state = {"loc": title or "top", "buf": []}

    def flush():
        t = clean("".join(state["buf"]))
        state["buf"] = []
        if t:
            paras.append((state["loc"], t))

    def pre_blocks(text):
        # plain-text pages such as the Federal Register: use [[Page N]] markers as locators
        for b in re.split(r"\n\s*\n", dehyphenate(text)):
            m = re.fullmatch(r"\s*\[\[Page (\d+)\]\]\s*", b)
            if m:
                state["loc"] = f"FR p.{m.group(1)}"
                continue
            t = clean(b)
            if t:
                paras.append((state["loc"], t))

    def walk(el):
        if not isinstance(el.tag, str):
            if el.tail:
                state["buf"].append(el.tail)
            return
        tag = el.tag.lower() if isinstance(el.tag, str) else ""
        if is_heading(el):
            flush()
            h = heading_text(el)
            if h:
                # "Article 110" followed straight by its subtitle: keep both
                if paras and paras[-1] == (state["loc"], state["loc"]) and len(state["loc"]) <= 40:
                    paras.pop()
                    h = f"{state['loc']} - {h}"[:160]
                state["loc"] = h
                paras.append((h, h))
        elif tag == "pre":
            flush()
            pre_blocks(el.text_content())
        else:
            block = tag in BLOCK_TAGS
            if block:
                flush()
            if el.text:
                state["buf"].append(el.text)
            for child in el:
                walk(child)
            if block:
                flush()
        if el.tail:
            state["buf"].append(el.tail)

    walk(body)
    flush()
    # a heading paragraph merges with the text below it in chunk()
    return paras, title


def docx_paragraphs(path):
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    with zipfile.ZipFile(path) as z:
        root = lxml.etree.fromstring(z.read("word/document.xml"))
    paras, loc = [], "top"
    for p in root.iter("{%s}p" % ns["w"]):
        t = clean("".join(p.itertext()))
        if not t:
            continue
        style = p.find("w:pPr/w:pStyle", ns)
        sval = style.get("{%s}val" % ns["w"]) if style is not None else ""
        if sval and re.match(r"(heading|title)", sval, re.I):
            loc = t[:160]
        paras.append((loc, t))
    return paras


def looks_like_junk_html(text_words, title):
    return text_words < 60 or re.search(r"redirect|not found|access denied|just a moment", title, re.I)


# ---------------------------------------------------------------- fetching

def sniff_ext(data, ctype):
    if data[:5] == b"%PDF-":
        return "pdf"
    head = data[:2048].lower()
    if b"<html" in head or b"<!doctype html" in head or "html" in (ctype or ""):
        return "html"
    if "xml" in (ctype or "") or head.lstrip().startswith(b"<?xml"):
        return "xml"
    return "bin"


def fetchable(src):
    url = src["url"].lower()
    if "/api/" in url or url.endswith("rss.xml") or url.endswith(".xsd"):
        return False
    return src["status"] == "verified-primary"


def fetch_one(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return r.read(), r.headers.get("Content-Type", "")


def fetch_all(sources, cache):
    cache.mkdir(parents=True, exist_ok=True)
    manifest_path = cache / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    for src in sources:
        if not fetchable(src):
            continue
        sid = src["id"]
        old = manifest.get(sid)
        if old and old.get("ok") and (cache / old["file"]).exists():
            continue
        err = None
        for attempt in range(2):
            try:
                data, ctype = fetch_one(src["url"])
                break
            except Exception as e:  # noqa: BLE001
                err = f"{type(e).__name__}: {e}"
                data = None
                time.sleep(3)
        if data is None:
            manifest[sid] = {"ok": False, "url": src["url"], "error": err}
            print(f"fetch failed {sid}: {err}", file=sys.stderr)
            continue
        ext = sniff_ext(data, ctype)
        fname = f"{sid}.{ext}"
        (cache / fname).write_bytes(data)
        sha = hashlib.sha256(data).hexdigest()
        manifest[sid] = {"ok": ext in ("pdf", "html"), "url": src["url"], "file": fname,
                         "content_type": ctype, "bytes": len(data), "sha256": sha,
                         "sha256_matches": sha == src.get("sha256"),
                         "error": None if ext in ("pdf", "html") else f"not a document ({ext})"}
        print(f"fetched {sid}: {ext} {len(data)} bytes, sha match={sha == src.get('sha256')}")
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


# ---------------------------------------------------------------- collections

def project_docs(sources, cache):
    manifest_path = cache / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    docs = []
    for src in sources:
        sid = src["id"]
        m = manifest.get(sid) or {}
        paras, kind_text = None, "quote"
        if src["status"] == "verified-primary" and m.get("ok"):
            path = cache / m["file"]
            if m["file"].endswith(".pdf"):
                paras, _ = pdf_paragraphs(path)
            else:
                paras, _ = html_paragraphs(path.read_bytes())
            if paras and sum(words(t) for _, t in paras) >= 60:
                kind_text = "text"
            else:
                paras = None
        if paras:
            clauses = [(l, t, "text") for l, t in chunk(paras)]
        else:
            clauses = [(q.get("locator", ""), clean(q["text"]), "quote")
                       for q in (src.get("quotes") or [])]
        docs.append({
            "meta": {
                "id": sid, "title": src["title"], "publisher": src.get("publisher", ""),
                "url": src["url"], "collection": "project", "status": src["status"],
                "kind": src.get("kind", ""),
                "sha256": m.get("sha256") if kind_text == "text" else src.get("sha256"),
            },
            "clauses": clauses, "fulltext": kind_text == "text", "size": 0,
        })
    return docs


def md_meta(path):
    text = path.read_text(encoding="utf-8", errors="replace")
    title = ""
    m = re.search(r"^#\s+(.+)$", text, re.M)
    if m:
        title = m.group(1).strip()
    pub = ""
    m = re.search(r"\*\*Issuing body:\*\*\s*(.+)", text)
    if m:
        pub = m.group(1).strip()
    abstract = ""
    m = re.search(r"^##\s+Abstract\s*\n(.*?)(?=^##\s|\Z)", text, re.M | re.S)
    if m:
        abstract = clean(m.group(1))
    return title, pub, abstract


def is_dup_name(name):
    stem = name.rsplit(".", 1)[0]
    return stem.endswith(" (1)") or stem.endswith("(1)")


def organiser_docs(dataset):
    docs, seen_sha, skipped = [], {}, []
    for folder in sorted(p for p in dataset.iterdir() if p.is_dir() and p.name[:2] in FOLDERS):
        files = sorted(f for f in folder.iterdir() if f.is_file() and not is_dup_name(f.name))
        by_stem = {}
        for f in files:
            by_stem.setdefault(f.stem, {})[f.suffix.lower()] = f
        for stem, variants in sorted(by_stem.items()):
            title, pub, abstract = ("", "", "")
            if ".md" in variants:
                title, pub, abstract = md_meta(variants[".md"])
            chosen, paras, ftype = None, None, None
            for ext in (".pdf", ".html", ".docx"):
                f = variants.get(ext)
                if not f:
                    continue
                data = f.read_bytes()
                sha = hashlib.sha256(data).hexdigest()
                if sha in seen_sha:
                    skipped.append(f"{folder.name}/{f.name} (same bytes as {seen_sha[sha]})")
                    chosen = "dup"
                    break
                if ext == ".pdf":
                    p, _ = pdf_paragraphs(f)
                elif ext == ".html":
                    p, html_title = html_paragraphs(data)
                    if looks_like_junk_html(sum(words(t) for _, t in p), html_title):
                        skipped.append(f"{folder.name}/{f.name} (placeholder page, not the document)")
                        continue
                else:
                    p = docx_paragraphs(f)
                if not p or sum(words(t) for _, t in p) < 30:
                    skipped.append(f"{folder.name}/{f.name} (no extractable text)")
                    continue
                seen_sha[sha] = f"{folder.name}/{f.name}"
                chosen, paras, ftype = f, p, ext[1:]
                break
            if chosen == "dup":
                continue
            if chosen is None:
                if not abstract:
                    continue
                chosen = variants[".md"]
                clauses = [("Abstract", abstract, "abstract")]
                ftype = "abstract"
                sha = hashlib.sha256(chosen.read_bytes()).hexdigest()
            else:
                clauses = [(l, t, "text") for l, t in chunk(paras)]
            doc_id = f"ITU-UAE:{folder.name}/{stem}".replace(" ", "_")
            url = REPO_BLOB + urllib.parse.quote(f"{folder.name}/{chosen.name}")
            docs.append({
                "meta": {
                    "id": doc_id, "title": title or stem.replace("_", " "),
                    "publisher": pub, "url": url, "collection": "itu-sandbox-uae",
                    "status": "organiser-dataset", "kind": ftype, "sha256": sha,
                },
                "clauses": clauses, "fulltext": ftype != "abstract",
                "file_bytes": chosen.stat().st_size, "folder": folder.name,
            })
    return docs, skipped


# ---------------------------------------------------------------- output

def render(doc):
    lines = []
    did = doc["meta"]["id"]
    for n, (loc, text, kind) in enumerate(doc["clauses"], 1):
        lines.append(json.dumps({
            "id": f"{did}#{n:04d}", "doc": did, "locator": loc, "text": text,
            "lang": lang_of(text), "kind": kind,
        }, ensure_ascii=False))
    return lines


def doc_lang(lines):
    langs = Counter(json.loads(l)["lang"] for l in lines)
    return langs.most_common(1)[0][0] if langs else "en"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True, help="path to Dataset/UAE/PolicyData")
    ap.add_argument("--cache", default=str(KB / "cache"))
    ap.add_argument("--fetch", action="store_true", help="download missing project sources")
    args = ap.parse_args()

    sources = yaml.safe_load((KB / "sources.yaml").read_text())["sources"]
    cache = Path(args.cache)
    if args.fetch:
        fetch_all(sources, cache)

    proj = project_docs(sources, cache)
    org, skipped = organiser_docs(Path(args.dataset))
    all_docs = proj + org
    for d in all_docs:
        d["lines"] = render(d)
        d["size"] = sum(len(l.encode()) + 1 for l in d["lines"])

    dropped = []
    total = sum(d["size"] for d in all_docs)
    if total > MAX_BYTES:
        order = [d for d in org if d.get("folder", "").startswith("06")]
        order += sorted((d for d in org if not d.get("folder", "").startswith("06")
                         and LOW_RELEVANCE.search(d["meta"]["title"] + d["meta"]["id"])),
                        key=lambda d: -d["size"])
        for d in order:
            if total <= MAX_BYTES:
                break
            all_docs.remove(d)
            total -= d["size"]
            dropped.append(d["meta"]["id"])

    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "clauses.jsonl", "w", encoding="utf-8") as fh:
        for d in all_docs:
            for l in d["lines"]:
                fh.write(l + "\n")
    meta = []
    for d in all_docs:
        m = dict(d["meta"])
        m["clauses"] = len(d["lines"])
        m["lang"] = doc_lang(d["lines"])
        meta.append(m)
    (OUT / "documents.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False) + "\n",
                                        encoding="utf-8")

    for coll in ("project", "itu-sandbox-uae"):
        ds = [d for d in all_docs if d["meta"]["collection"] == coll]
        print(f"{coll}: {len(ds)} docs, {sum(len(d['lines']) for d in ds)} clauses, "
              f"{sum(1 for d in ds if d['fulltext'])} with full text")
    print(f"clauses.jsonl: {total} bytes")
    for s in skipped:
        print(f"skipped: {s}")
    for d in dropped:
        print(f"dropped for size: {d}")


if __name__ == "__main__":
    main()
