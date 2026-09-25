from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable

import gradio as gr
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

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

HHC_NAMESPACE = {
    "core_hz": 428,
    "value_hz": 528,
    "energy_hz": 741,
    "form_hz": 963,
}


def canonical(obj: Any) -> str:
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_json(obj: Any) -> str:
    return sha256(canonical(obj).encode("utf-8"))


def merkle_root(hex_hashes: Iterable[str]) -> str:
    level = [bytes.fromhex(value) for value in hex_hashes]
    if not level:
        return "0" * 64
    while len(level) > 1:
        if len(level) % 2:
            level.append(level[-1])
        level = [
            hashlib.sha256(level[index] + level[index + 1]).digest()
            for index in range(0, len(level), 2)
        ]
    return level[0].hex()


def derive_key() -> bytes:
    seed_basis = canonical(
        {"artifact": ARTIFACT, "bundle": LOCAL_BUNDLE, "hhc": HHC_NAMESPACE}
    )
    salt = hashlib.sha256(("ASIN-NCEA salt:" + seed_basis).encode()).digest()
    ikm = hashlib.sha256(("ASIN-NCEA ikm:" + seed_basis).encode()).digest()
    return HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        info=b"ASIN-NCEA/HHC/AEAD/huggingface-space-smoke-test-only",
    ).derive(ikm)


def run_harness() -> tuple[str, dict[str, Any]]:
    key = derive_key()
    aead = ChaCha20Poly1305(key)
    aad = canonical({"artifact": ARTIFACT, "hhc": HHC_NAMESPACE}).encode()
    plaintext_obj = {
        "architecture": "PoWP-PAL-PoG-NCEA-Fusion",
        "bundle_sha256": LOCAL_BUNDLE["bundle_sha256"],
        "claim_boundary": [
            "AEAD check is a public smoke test",
            "HHC constants are namespace metadata, not security amplification",
            "HHC-SIM has no monetary authority",
            "promotion remains HOLD",
        ],
    }
    plaintext = canonical(plaintext_obj).encode()
    nonce = hashlib.sha256(
        b"ASIN-NCEA huggingface smoke nonce" + plaintext
    ).digest()[:12]
    ciphertext = aead.encrypt(nonce, plaintext, aad)
    roundtrip_ok = aead.decrypt(nonce, ciphertext, aad) == plaintext

    tampered = bytearray(ciphertext)
    tampered[0] ^= 1
    try:
        aead.decrypt(nonce, bytes(tampered), aad)
        tamper_rejected = False
    except InvalidTag:
        tamper_rejected = True

    signing_seed = hashlib.sha256(
        ("public demo receipt key:" + LOCAL_BUNDLE["bundle_sha256"]).encode()
    ).digest()
    private_key = ed25519.Ed25519PrivateKey.from_private_bytes(signing_seed)
    public_key = private_key.public_key()

    event = {
        "event_type": "ASIN_NCEA_HUGGINGFACE_SPACE_RUN",
        "artifact": ARTIFACT,
        "bundle_sha256": LOCAL_BUNDLE["bundle_sha256"],
        "aead": "ChaCha20-Poly1305",
        "key_derivation": "HKDF-SHA256",
        "signature": "Ed25519 test receipt",
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
        {
            "append_seq": 0,
            "event_type": "LOCAL_BUNDLE_ANCHOR",
            "event_hash": sha256_json(LOCAL_BUNDLE),
            "previous_hash": "0" * 64,
        },
        {
            "append_seq": 1,
            "event_type": "HUGGINGFACE_SPACE_RUN",
            "event_hash": event_hash,
            "previous_hash": sha256_json(LOCAL_BUNDLE),
        },
    ]
    ledger_root = merkle_root([sha256_json(row) for row in ledger])
    pass_fail = "PASS_WITH_HOLD" if roundtrip_ok and tamper_rejected else "FAIL"

    result = {
        "artifact": ARTIFACT,
        "pass_fail": pass_fail,
        "evidence_level": EVIDENCE_LEVEL,
        "promotion_verdict": PROMOTION_VERDICT,
        "witness_class": WITNESS_CLASS,
        "runtime_scope": "PUBLIC_DEMO_SMOKE_TEST_ONLY",
        "local_bundle_anchor": LOCAL_BUNDLE,
        "space_run": {
            "roundtrip_ok": roundtrip_ok,
            "tamper_rejected": tamper_rejected,
            "event_hash": event_hash,
            "signature_hex": signature.hex(),
            "public_key_hex": public_key_hex,
            "ledger_merkle_root": ledger_root,
            "wallet_class": "SIMULATED_ONLY_NO_MONETARY_AUTHORITY",
            "simulated_reward_display": (
                "10.000 HHC-SIM" if pass_fail == "PASS_WITH_HOLD" else "0.000 HHC-SIM"
            ),
        },
    }

    summary = f"""
### `{pass_fail}`

- **Evidence:** `{EVIDENCE_LEVEL}`
- **Promotion:** `{PROMOTION_VERDICT}`
- **Witness:** `{WITNESS_CLASS}`
- **AEAD roundtrip:** `{str(roundtrip_ok).lower()}`
- **Tamper rejected:** `{str(tamper_rejected).lower()}`
- **Wallet:** `SIMULATED_ONLY_NO_MONETARY_AUTHORITY`

This run is a public machine-executed demonstration. It is not independent reproduction, production cryptographic certification, token issuance, or kernel promotion.
"""
    return summary, result


with gr.Blocks(title="ASIN-NCEA Evidence Harness v0.1") as demo:
    gr.Markdown(
        """
# ASIN-NCEA Evidence Harness v0.1 🐍

A receipt-first public demonstration of the integrated AEAD, tamper rejection, signed test receipt, hash-linked ledger, and simulated PoWP gate.

> **Authority boundary:** `E3_LOCAL_INTEGRATION / HOLD / MACHINE_EXECUTION_UNATTESTED`
"""
    )
    run_button = gr.Button("Run evidence-bound smoke test", variant="primary")
    summary_output = gr.Markdown()
    json_output = gr.JSON(label="Machine-readable receipt")
    run_button.click(run_harness, outputs=[summary_output, json_output])
    gr.Markdown(
        """
### Claim boundary

HHC constants are namespace/domain-separation metadata only. The deterministic signing material is public and test-only. `HHC-SIM` has no monetary value, network consensus, or production authority.
"""
    )


if __name__ == "__main__":
    demo.launch()
