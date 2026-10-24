"""Coordinator signing key for receipt claims.

The key is Ed25519 and lives on disk. It signs the EIP-712-style digest of a
receipt. It is not a chain account and it cannot mint anything.
"""

from __future__ import annotations

import os
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

_private: Ed25519PrivateKey | None = None
_public_hex: str = ""


def configure_signer(path: Path) -> str:
    """Load or create the signing key. Returns the public key as hex."""
    global _private, _public_hex
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raw = bytes.fromhex(path.read_text(encoding="utf-8").strip())
        _private = Ed25519PrivateKey.from_private_bytes(raw)
    else:
        _private = Ed25519PrivateKey.generate()
        secret = _private.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption(),
        )
        path.write_text(secret.hex() + "\n", encoding="utf-8")
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    public = _private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    _public_hex = public.hex()
    return _public_hex


def signer_public_hex() -> str:
    if not _public_hex:
        raise RuntimeError("ledger signer is not configured")
    return _public_hex


def sign_digest(digest: bytes) -> str:
    if _private is None:
        raise RuntimeError("ledger signer is not configured")
    return _private.sign(digest).hex()


def verify_digest(public_hex: str, digest: bytes, signature_hex: str) -> bool:
    try:
        key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_hex))
        key.verify(bytes.fromhex(signature_hex), digest)
        return True
    except (InvalidSignature, ValueError):
        return False
