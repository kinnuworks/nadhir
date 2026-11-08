"""Build, parse, validate and sign CAP 1.2 alerts (OASIS CAP 1.2 = ITU-T X.1303bis)."""
from __future__ import annotations

import copy
import re
from pathlib import Path

from lxml import etree

NS = "urn:oasis:names:tc:emergency:cap:1.2"
DS = "http://www.w3.org/2000/09/xmldsig#"
SCHEMA_PATH = Path(__file__).parent / "schema" / "CAP-v1.2.xsd"
_schema = None

ALERT_ORDER = ["identifier", "sender", "sent", "status", "msgType", "source", "scope",
               "restriction", "addresses", "code", "note", "references", "incidents"]
INFO_ORDER = ["language", "category", "event", "responseType", "urgency", "severity", "certainty",
              "audience", "eventCode", "effective", "onset", "expires", "senderName", "headline",
              "description", "instruction", "web", "contact"]


def _q(tag: str) -> str:
    return f"{{{NS}}}{tag}"


def schema() -> etree.XMLSchema:
    global _schema
    if _schema is None:
        _schema = etree.XMLSchema(etree.parse(str(SCHEMA_PATH)))
    return _schema


def build(alert: dict) -> str:
    """Turn an alert dict into CAP 1.2 XML text. Unknown keys are ignored."""
    root = etree.Element(_q("alert"), nsmap={None: NS})
    for key in ALERT_ORDER:
        val = alert.get(key)
        if val in (None, "", []):
            continue
        for v in (val if isinstance(val, list) else [val]):
            etree.SubElement(root, _q(key)).text = str(v)
    for info in alert.get("info", []):
        el = etree.SubElement(root, _q("info"))
        for key in INFO_ORDER:
            val = info.get(key)
            if val in (None, "", []):
                continue
            for v in (val if isinstance(val, list) else [val]):
                etree.SubElement(el, _q(key)).text = str(v)
        for name, value in info.get("parameters", []):
            p = etree.SubElement(el, _q("parameter"))
            etree.SubElement(p, _q("valueName")).text = name
            etree.SubElement(p, _q("value")).text = str(value)
        for area in info.get("areas", []):
            a = etree.SubElement(el, _q("area"))
            etree.SubElement(a, _q("areaDesc")).text = area.get("areaDesc", "")
            for poly in area.get("polygons", []):
                etree.SubElement(a, _q("polygon")).text = poly
            for name, value in area.get("geocodes", []):
                g = etree.SubElement(a, _q("geocode"))
                etree.SubElement(g, _q("valueName")).text = name
                etree.SubElement(g, _q("value")).text = str(value)
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", pretty_print=True).decode()


def _text(el, tag):
    found = el.find(_q(tag))
    return found.text if found is not None else None


def parse(xml: str) -> dict:
    """Parse CAP XML into the same dict shape that build() takes, plus 'signed'."""
    root = etree.fromstring(xml.encode() if isinstance(xml, str) else xml)
    out: dict = {}
    for key in ALERT_ORDER:
        vals = [e.text for e in root.findall(_q(key))]
        if vals:
            out[key] = vals if key == "code" else vals[0]
    out["signed"] = root.find(f"{{{DS}}}Signature") is not None
    out["info"] = []
    for el in root.findall(_q("info")):
        info: dict = {}
        for key in INFO_ORDER:
            vals = [e.text for e in el.findall(_q(key))]
            if vals:
                info[key] = vals if key in ("category", "responseType") else vals[0]
        info["parameters"] = [(_text(p, "valueName"), _text(p, "value")) for p in el.findall(_q("parameter"))]
        info["areas"] = []
        for a in el.findall(_q("area")):
            info["areas"].append({
                "areaDesc": _text(a, "areaDesc"),
                "polygons": [p.text for p in a.findall(_q("polygon"))],
                "geocodes": [(_text(g, "valueName"), _text(g, "value")) for g in a.findall(_q("geocode"))],
            })
        out["info"].append(info)
    return out


def validate(xml: str) -> list[str]:
    """Return schema errors against the official CAP 1.2 XSD (empty list = valid)."""
    try:
        doc = etree.fromstring(xml.encode() if isinstance(xml, str) else xml)
    except etree.XMLSyntaxError as e:
        return [f"not well-formed XML: {e}"]
    sch = schema()
    if sch.validate(doc):
        return []
    return [f"line {e.line}: {e.message}" for e in sch.error_log]


SENT_RE = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d[-+]\d\d:\d\d$")


def with_parameters(xml: str, params: list[tuple[str, str]]) -> str:
    """Add parameters to every <info> block (used for provenance and approval)."""
    root = etree.fromstring(xml.encode())
    for info in root.findall(_q("info")):
        # parameters go before resource/area per the schema sequence
        anchor = info.find(_q("resource"))
        if anchor is None:
            anchor = info.find(_q("area"))
        for name, value in params:
            p = etree.Element(_q("parameter"))
            etree.SubElement(p, _q("valueName")).text = name
            etree.SubElement(p, _q("value")).text = str(value)
            if anchor is not None:
                anchor.addprevious(p)
            else:
                info.append(p)
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", pretty_print=True).decode()


def sign(xml: str, key_pem: bytes, cert_pem: bytes) -> str:
    """Enveloped XML-DSig on <alert>, the only signature form CAP 1.2 section 3.3.4.1 allows."""
    from signxml import XMLSigner, methods
    root = etree.fromstring(xml.encode())
    signed = XMLSigner(method=methods.enveloped, signature_algorithm="rsa-sha256",
                       digest_algorithm="sha256").sign(root, key=key_pem, cert=cert_pem)
    return etree.tostring(signed, xml_declaration=True, encoding="UTF-8").decode()


def verify(xml: str, cert_pems: list[bytes]) -> tuple[bool, str]:
    """Check the enveloped signature against each registered certificate."""
    from signxml import XMLVerifier
    root = etree.fromstring(xml.encode())
    if root.find(f"{{{DS}}}Signature") is None:
        return False, "no signature"
    last = "no registered certificate for this sender"
    for cert in cert_pems:
        try:
            XMLVerifier().verify(copy.deepcopy(root), x509_cert=cert)
            return True, "signature verifies against a registered certificate"
        except Exception as e:  # signxml raises several types
            last = f"signature does not verify: {type(e).__name__}"
    return False, last
