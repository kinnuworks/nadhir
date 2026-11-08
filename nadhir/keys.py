"""Demo signing keys for registered originators.

These are throwaway demo keys committed on purpose so anyone can rerun the replays.
They protect nothing. A real deployment would use the authority's own certificates.
"""
from __future__ import annotations

import datetime
import re
from pathlib import Path

KEY_DIR = Path(__file__).parent / "keys" / "demo"


def _safe(sender: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", sender)


def ensure(sender: str) -> tuple[bytes, bytes]:
    key_path, cert_path = KEY_DIR / f"{_safe(sender)}.key.pem", KEY_DIR / f"{_safe(sender)}.crt.pem"
    if key_path.exists() and cert_path.exists():
        return key_path.read_bytes(), cert_path.read_bytes()
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, f"DEMO ONLY {sender}"[:64])])
    now = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now)
            .not_valid_after(now + datetime.timedelta(days=3650))
            .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
            .sign(key, hashes.SHA256()))
    KEY_DIR.mkdir(parents=True, exist_ok=True)
    key_pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                serialization.NoEncryption())
    cert_pem = cert.public_bytes(serialization.Encoding.PEM)
    key_path.write_bytes(key_pem)
    cert_path.write_bytes(cert_pem)
    return key_pem, cert_pem


def cert(sender: str) -> bytes | None:
    p = KEY_DIR / f"{_safe(sender)}.crt.pem"
    return p.read_bytes() if p.exists() else None
