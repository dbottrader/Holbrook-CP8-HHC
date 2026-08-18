#!/usr/bin/env python3
"""
ASIN-NCEA integrated architecture smoke harness.

This is the GitHub-portable smoke test for the v0.1 integration branch.
It does not replace the sealed local bundle. The sealed local bundle contains
all source snapshots and produced the recorded local anchors below.

Boundary:
- evidence level remains E3_LOCAL_INTEGRATION
- promotion verdict remains HOLD
- wallet output is HHC-SIM only, not monetary issuance
"""
from __future__ import annotations

import hashlib
import json
import sys
from typing import Any, Iterable

try:
    from cryptography.exceptions import InvalidTag
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ed25519
    from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
except Exception as exc:
    print(json.dumps({
        "pass_fail": "FAIL",
        "failure": "cryptography_dependency_missing",
        "detail": repr(exc),
        "remediation": "pip install cryptography",
    }, indent=2))
    raise SystemExit(2)

ARTIFACT = "ASIN-NCEA_INTEGRATED_HARNESS_v0.1"
EVIDENCE_LEVEL = "E3_LOCAL_INTEGRATION"
PROMOTION_VERDICT = "HOLD"
WITNESS_CLASS = "MACHINE_EXECUTION_UNATTESTED"

LOCAL_BUNDLE = {
    "bundle_sha256": "14e3eaaf71461e35d31f185ed3c84083c516539a057e66c1bb3f5485da7c9807",
    "source_entries": 13,
    "source_hashes_ok": True,
    "source_syntax_ok": True,
    "raw_v2_runtime_ready": False,
    "local_deterministic_core_hash": "ee93c43c62eccb6dd9eaf14787bdfe6af2965f66763216221f504af282447274",
    "local_ledger_merkle_root": "ffc27df9d1d33a454e858284b19694c5c7513a9833e25113550f0acd8ec68405",
}

HHC_NAMESPACE = {"core_hz": 428, "value_hz": 528, "energy_hz": 741, "form_hz": 963}


def canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_json(obj: Any) -> str:
    return sha256(canonical(obj).encode("utf-8"))


def merkle_root(hex_hashes: Iterable[str]) -> str:
    level = [bytes.fromhex(h) for h in hex_hashes]
    if not level:
        return "0" * 64
    while len(level) > 1:
        if len(level) % 2:
            level.append(level[-1])
        level = [hashlib.sha256(level[i] + level[i + 1]).digest() for i in range(0, len(level), 2)]
    return level[0].hex()


def derive_key() -> bytes:
    seed_basis = canonical({"artifact": ARTIFACT, "bundle": LOCAL_BUNDLE, "hhc": HHC_NAMESPACE})
    salt = hashlib.sha256(("ASIN-NCEA salt:" + seed_basis).encode()).digest()
    ikm = hashlib.sha256(("ASIN-NCEA ikm:" + seed_basis).encode()).digest()
    return HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        info=b"ASIN-NCEA/HHC/AEAD/github-smoke-test-only",
    ).derive(ikm)


def main() -> int:
    key = derive_key()
    aead = ChaCha20Poly1305(key)
    aad = canonical({"artifact": ARTIFACT, "hhc": HHC_NAMESPACE}).encode()
    plaintext_obj = {
        "architecture": "PoWP-PAL-PoG-NCEA-Fusion",
        "bundle_sha256": LOCAL_BUNDLE["bundle_sha256"],
        "claim_boundary": [
            "AEAD check is a smoke test",
            "HHC constants are namespace metadata, not security amplification",
            "HHC-SIM has no monetary authority",
            "promotion remains HOLD",
        ],
    }
    plaintext = canonical(plaintext_obj).encode()
    nonce = hashlib.sha256(b"ASIN-NCEA github smoke nonce" + plaintext).digest()[:12]
    ciphertext = aead.encrypt(nonce, plaintext, aad)
    roundtrip_ok = aead.decrypt(nonce, ciphertext, aad) == plaintext

    tampered = bytearray(ciphertext)
    tampered[0] ^= 1
    try:
        aead.decrypt(nonce, bytes(tampered), aad)
        tamper_rejected = False
    except InvalidTag:
        tamper_rejected = True

    signing_seed = hashlib.sha256(("receipt key:" + LOCAL_BUNDLE["bundle_sha256"]).encode()).digest()
    private_key = ed25519.Ed25519PrivateKey.from_private_bytes(signing_seed)
    public_key = private_key.public_key()

    event = {
        "event_type": "ASIN_NCEA_GITHUB_SMOKE_RUN",
        "artifact": ARTIFACT,
        "bundle_sha256": LOCAL_BUNDLE["bundle_sha256"],
        "aead": "ChaCha20-Poly1305",
        "key_derivation": "HKDF-SHA256",
        "signature": "Ed25519",
        "ciphertext_sha256": sha256(ciphertext),
        "roundtrip_ok": roundtrip_ok,
        "tamper_rejected": tamper_rejected,
        "promotion_verdict": PROMOTION_VERDICT,
    }
    event_hash = sha256_json(event)
    signature = private_key.sign(bytes.fromhex(event_hash))
    public_key.verify(signature, bytes.fromhex(event_hash))
    public_key_hex = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    ).hex()

    ledger = [
        {"append_seq": 0, "event_type": "LOCAL_BUNDLE_ANCHOR", "event_hash": sha256_json(LOCAL_BUNDLE), "previous_hash": "0" * 64},
        {"append_seq": 1, "event_type": "GITHUB_SMOKE_RUN", "event_hash": event_hash, "previous_hash": sha256_json(LOCAL_BUNDLE)},
    ]
    ledger_root = merkle_root([sha256_json(row) for row in ledger])
    pass_fail = "PASS_WITH_HOLD" if roundtrip_ok and tamper_rejected else "FAIL"

    result = {
        "artifact": ARTIFACT,
        "pass_fail": pass_fail,
        "evidence_level": EVIDENCE_LEVEL,
        "promotion_verdict": PROMOTION_VERDICT,
        "witness_class": WITNESS_CLASS,
        "local_bundle_anchor": LOCAL_BUNDLE,
        "github_smoke": {
            "roundtrip_ok": roundtrip_ok,
            "tamper_rejected": tamper_rejected,
            "event_hash": event_hash,
            "signature_hex": signature.hex(),
            "public_key_hex": public_key_hex,
            "ledger_merkle_root": ledger_root,
            "wallet_class": "SIMULATED_ONLY_NO_MONETARY_AUTHORITY",
            "simulated_reward_display": "10.000 HHC-SIM" if pass_fail == "PASS_WITH_HOLD" else "0.000 HHC-SIM",
        },
    }
    print(json.dumps(result, indent=2))
    return 0 if pass_fail == "PASS_WITH_HOLD" else 1


if __name__ == "__main__":
    raise SystemExit(main())
