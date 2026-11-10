"""Build the submission report (docx) from docs/report.md on the organisers' template.

Usage: python scripts/build_report.py [--team NAME] [--leader NAME] [--members TEXT]
                                      [--contact TEXT] [--repo URL] [--out docs/report.docx]
Fields left out stay as highlighted placeholders. Body text keeps the template's look
(Times New Roman, justified, numbered section headings, the template's node table).
"""
from __future__ import annotations

import argparse
import copy
import re
from pathlib import Path

import docx
from docx.enum.text import WD_COLOR_INDEX
from docx.oxml.ns import qn
from docx.shared import Cm, Pt

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "research" / "report" / "ITU-submission-template.docx"
SOURCE = ROOT / "docs" / "report.md"
LIVE = "https://nadhir-gilt.vercel.app"
BODY_PT = 11
TABLE_PT = 9


def _run(p, text, bold=False, italic=False, size=BODY_PT, highlight=False):
    r = p.add_run(text)
    r.font.name = "Times New Roman"
    r._r.get_or_add_rPr().get_or_add_rFonts().set(qn("w:eastAsia"), "Times New Roman")
    r.font.size = Pt(size)
    r.bold, r.italic = bold or None, italic or None
    if highlight:
        r.font.highlight_color = WD_COLOR_INDEX.YELLOW
    return r


def _inline(p, text, size=BODY_PT):
    """**bold**, *italic*, `code` and {{PLACEHOLDER}} inside one paragraph."""
    for part in re.split(r"(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`|\[[A-Z ]+\])", text):
        if not part:
            continue
        if part.startswith("**"):
            _run(p, part[2:-2], bold=True, size=size)
        elif part.startswith("*"):
            _run(p, part[1:-1], italic=True, size=size)
        elif part.startswith("`"):
            _run(p, part[1:-1], size=size)
        elif re.fullmatch(r"\[[A-Z ]+\]", part):
            _run(p, part, size=size, highlight=True)
        else:
            _run(p, part, size=size)


def _fmt(p, after=4, indent=None):
    pf = p.paragraph_format
    pf.space_after = Pt(after)
    pf.space_before = Pt(0)
    pf.line_spacing = 1.0
    if indent is not None:
        pf.left_indent = Pt(indent)
    p.alignment = 3  # justify


def build(a):
    d = docx.Document(TEMPLATE)
    body = d.element.body
    paras = d.paragraphs
    heading_tpl = copy.deepcopy(paras[5]._p)  # "Introduction": numbered List Paragraph
    table_tpl = copy.deepcopy(d.tables[0]._tbl)

    md = SOURCE.read_text(encoding="utf-8")
    title = md.splitlines()[0].lstrip("# ").replace("{{TEAM}}", a.team or "[TEAM NAME]")

    # Header block: title and the four detail lines, rewritten in place
    for r in paras[0].runs[1:]:
        r._r.getparent().remove(r._r)
    paras[0].runs[0].text = title
    paras[0].runs[0].font.size = Pt(13)

    def detail(p, pairs):
        for r in list(p.runs):
            r._r.getparent().remove(r._r)
        p.alignment = 0  # left: justified label lines spread out
        for k, (label, value) in enumerate(pairs):
            if k:
                p.add_run().add_break()
            _run(p, label + " ", size=BODY_PT)
            _run(p, value, size=BODY_PT, highlight=value.startswith("["))

    detail(paras[1], [("Team leader:", a.leader or "[TEAM LEADER]")])
    detail(paras[2], [("Team members:", a.members or "[TEAM MEMBERS]"),
                      ("Contact details:", a.contact or "[CONTACT]")])
    detail(paras[3], [("Github link:", a.repo or "[GITHUB LINK]"), ("Live demo:", LIVE)])

    # Drop everything after the header block (keep the section properties)
    keep = {paras[i]._p for i in range(4)}
    for el in list(body):
        if el.tag == qn("w:sectPr") or el in keep:
            continue
        body.remove(el)
    sect = body.find(qn("w:sectPr"))

    def add_para():
        p = d.add_paragraph()
        body.remove(p._p)
        sect.addprevious(p._p)
        return p

    def add_heading(text):
        h = copy.deepcopy(heading_tpl)
        for r in h.findall(qn("w:r")):
            h.remove(r)
        for pe in h.findall(qn("w:proofErr")):
            h.remove(pe)
        sect.addprevious(h)
        p = docx.text.paragraph.Paragraph(h, d._body)
        _run(p, text, bold=True, size=11.5)
        p.paragraph_format.space_before = Pt(6)
        p.paragraph_format.space_after = Pt(3)
        p.paragraph_format.keep_with_next = True

    def add_table(rows, widths=None):
        t = copy.deepcopy(table_tpl)
        if widths:  # column shares, set by a "<!-- widths: a b c d -->" line above the table
            pr = t.find(qn("w:tblPr"))
            total = int(pr.find(qn("w:tblW")).get(qn("w:w")))
            dxa = [round(total * w / sum(widths)) for w in widths]
            for gc, w in zip(t.find(qn("w:tblGrid")).findall(qn("w:gridCol")), dxa):
                gc.set(qn("w:w"), str(w))
            for tr in t.findall(qn("w:tr")):
                for tc, w in zip(tr.findall(qn("w:tc")), dxa):
                    tc.find(qn("w:tcPr")).find(qn("w:tcW")).set(qn("w:w"), str(w))
            layout = pr.makeelement(qn("w:tblLayout"), {qn("w:type"): "fixed"})
            pr.find(qn("w:tblLook")).addprevious(layout)
        trs = t.findall(qn("w:tr"))
        while len(trs) < len(rows):
            new = copy.deepcopy(trs[-1])
            trs[-1].addnext(new)
            trs = t.findall(qn("w:tr"))
        for extra in trs[len(rows):]:
            t.remove(extra)
        sect.addprevious(t)
        table = docx.table.Table(t, d._body)
        for i, row in enumerate(rows):
            for j, text in enumerate(row):
                cell = table.rows[i].cells[j]
                for cp in cell.paragraphs[1:]:
                    cp._p.getparent().remove(cp._p)
                cp = cell.paragraphs[0]
                for r in list(cp._p):
                    if r.tag != qn("w:pPr"):
                        cp._p.remove(r)
                cp.paragraph_format.space_after = Pt(0)
                cp.paragraph_format.line_spacing = 1.0
                if i == 0 or j == 0:
                    _run(cp, text.replace("**", ""), bold=True, size=TABLE_PT)
                else:
                    _inline(cp, text, size=TABLE_PT)
        sp = add_para()
        sp.paragraph_format.space_after = Pt(2)

    lines = md.splitlines()[1:]
    i = 0
    widths = None
    while i < len(lines):
        ln = lines[i].rstrip()
        if not ln or ln.startswith("Team leader:"):
            i += 1
            continue
        m = re.fullmatch(r"<!-- widths: ([\d ]+) -->", ln)
        if m:
            widths = [int(w) for w in m.group(1).split()]
            i += 1
            continue
        if ln.startswith("## "):
            add_heading(re.sub(r"^\d+\.\s*", "", ln[3:]))
        elif ln.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-+:?", c) for c in cells):
                    rows.append(cells)
                i += 1
            add_table(rows, widths)
            widths = None
            continue
        elif ln.startswith("!["):
            m = re.match(r"!\[(.*)\]\((.*)\)", ln)
            p = add_para()
            p.alignment = 1
            p.paragraph_format.space_after = Pt(1)
            p.paragraph_format.keep_with_next = True
            p.add_run().add_picture(str(ROOT / m.group(2)), width=Cm(16.5))
            cap = add_para()
            _fmt(cap, after=4)
            _run(cap, m.group(1), italic=True, size=TABLE_PT)
        elif ln.startswith("- "):
            p = add_para()
            _fmt(p, after=2, indent=18)
            p.paragraph_format.first_line_indent = Pt(-9)
            _inline(p, "• " + ln[2:])
        elif re.match(r"^\d+\. ", ln):
            p = add_para()
            _fmt(p, after=3, indent=18)
            p.paragraph_format.first_line_indent = Pt(-12)
            _inline(p, ln)
        else:
            p = add_para()
            _fmt(p, after=4)
            _inline(p, ln)
        i += 1

    out = ROOT / a.out
    d.save(out)
    print("wrote", out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--team")
    ap.add_argument("--leader")
    ap.add_argument("--members")
    ap.add_argument("--contact")
    ap.add_argument("--repo")
    ap.add_argument("--out", default="docs/report.docx")
    build(ap.parse_args())
