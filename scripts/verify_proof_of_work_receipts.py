#!/usr/bin/env python3
"""Check a Proof-of-Work Commons receipt chain with public keys only.

The input is a JSON file. It must not contain a signing seed or an HMAC secret.
The script does not open a database and does not read private.cp8_moltbook_receipt_signing_keys.

    python3 scripts/verify_proof_of_work_receipts.py bundle.json

HMAC envelopes stay labeled SIMULATED and are not checked here. Ed25519
attribution envelopes are checked with the published public keys. A key with
revoked_at set fails closed. A key with only rotated_at set still verifies.
"""

from __future__ import annotations

import base64
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from moltbook.ledger.backend import (  # noqa: E402
    ATTRIBUTION_SCHEME,
    HMAC_MODE,
    WALLET_CLASS,
    ReceiptVerificationError,
    verify_ed25519_envelope,
)

FORBIDDEN_KEYS = {"seed", "secret", "private_key", "signing_seed", "hmac_secret"}


class VerifyFailure(RuntimeError):
    pass


def fail(message):
    raise VerifyFailure(message)


def refuse_secrets(value, path="$"):
    if isinstance(value, dict):
        for key, item in value.items():
            lowered = str(key).lower()
            if lowered in FORBIDDEN_KEYS or "seed" in lowered or lowered.endswith("secret"):
                fail(f"refusing secret field {path}.{key}")
            refuse_secrets(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            refuse_secrets(item, f"{path}[{index}]")


def load_bundle(path):
    document = json.loads(Path(path).read_text())
    refuse_secrets(document)
    if not isinstance(document.get("public_keys"), list):
        fail("public_keys must be a list")
    if not isinstance(document.get("receipts"), list) or not document["receipts"]:
        fail("receipts must be a non-empty list")
    return document


def public_key_map(rows):
    keys = {}
    revoked = set()
    for row in rows:
        if row.get("scheme") != ATTRIBUTION_SCHEME:
            continue
        key_id = row.get("key_id")
        encoded = row.get("public_key_hex")
        if not key_id or not encoded:
            fail("ed25519 key is missing id or public_key_hex")
        raw = bytes.fromhex(encoded)
        if len(raw) != 32:
            fail(f"public key length {key_id}")
        keys[key_id] = raw
        if row.get("revoked_at"):
            revoked.add(key_id)
    if not keys:
        fail("no ed25519 public keys")
    return keys, revoked


def check_receipt(receipt, keys, revoked, previous_hash):
    if receipt.get("hmac_mode") != HMAC_MODE:
        fail(f"hmac_mode must be {HMAC_MODE}")
    if receipt.get("prev_receipt_hash") != previous_hash:
        fail("prev-hash chain break")
    envelope_json = receipt.get("envelope_json") or ""
    digest = hashlib.sha256(envelope_json.encode("utf-8")).hexdigest()
    if digest != receipt.get("receipt_hash"):
        fail("receipt_hash does not match envelope_json")
    payload_text = receipt.get("attribution_payload")
    attribution = receipt.get("attribution_envelope")
    if not payload_text or not attribution:
        fail("missing attribution")
    if receipt.get("attribution_key_id") is None:
        fail("missing attribution key id")
    try:
        key_id = verify_ed25519_envelope(attribution, keys, revoked)
    except ReceiptVerificationError as exc:
        fail(str(exc))
    if key_id != receipt["attribution_key_id"]:
        fail("attribution key id does not match the signature")
    decoded = base64.b64decode(json.loads(attribution)["payload"])
    if decoded.decode("utf-8") != payload_text:
        fail("attribution payload bytes do not match the envelope")
    payload = json.loads(payload_text)
    if payload.get("mode") != "ATTRIBUTABLE":
        fail("attribution mode")
    if payload.get("walletClass") != WALLET_CLASS:
        fail("wallet class")
    statement = payload.get("statement")
    if statement != json.loads(receipt["statement_json"]):
        fail("statement does not match attribution payload")
    if receipt.get("kind") == "settlement":
        verifiers = payload.get("verifiers") or []
        operators = [row.get("operatorId") for row in verifiers]
        if len(operators) < 2 or any(not item for item in operators):
            fail("settlement verifiers")
        if len(set(operators)) != len(operators):
            fail("settlement verifiers share an operator")
    return receipt["receipt_hash"]


def main(argv):
    if len(argv) != 2:
        fail("usage: verify_proof_of_work_receipts.py bundle.json")
    document = load_bundle(argv[1])
    keys, revoked = public_key_map(document["public_keys"])
    previous = ""
    for receipt in document["receipts"]:
        previous = check_receipt(receipt, keys, revoked, previous)
    print(json.dumps({"ok": True, "receipts": len(document["receipts"])}))


if __name__ == "__main__":
    try:
        main(sys.argv)
    except (VerifyFailure, json.JSONDecodeError, ValueError) as exc:
        sys.stderr.write(f"verify failed: {exc}\n")
        raise SystemExit(1) from exc
