"""Ledger backends for a settled Moltbook bounty.

The simulated backend is the default. It signs an in-toto Statement v1 inside a
DSSE envelope (the Sigstore payload layout) with HMAC-SHA256. That HMAC mode is
labeled SIMULATED. Ed25519 attribution is checked with public keys only. This
module does not call Fulcio, Rekor, or any chain, and it does not mint a token.

The on-chain backend is a locked adapter. Constructing it is allowed so callers
can see the interface; every method refuses before any network call.

Merkle pairing matches scripts/build-merkle.py: odd levels duplicate the last
leaf, and a parent is sha256 of the UTF-8 concatenation of the two child hex
digests.

License of this file: MIT, same as the repository. The statement and DSSE
layouts are used as specifications, not copied code. See README.md.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from typing import Protocol

PAYLOAD_TYPE = "application/vnd.in-toto+json"
KEY_ID = "moltbook-simulated-receipt"
SIGNATURE_SCHEME = "dsse-simulated-hmac-sha256"
HMAC_MODE = "SIMULATED"
ATTRIBUTION_SCHEME = "ed25519"
PREDICATE_SETTLEMENT = (
    "https://github.com/dbottrader/Holbrook-CP8-HHC/moltbook/ledger/bounty-settlement/v1"
)
PREDICATE_PROMOTION = (
    "https://github.com/dbottrader/Holbrook-CP8-HHC/moltbook/ledger/bounty-promotion/v1"
)
WALLET_CLASS = "SIMULATED_ONLY_NO_MONETARY_AUTHORITY"
CURRENCY = "HHC-SIM"
EIP712_DOMAIN = {
    "name": "ASIN-HHC Settlement",
    "version": "1",
    "chainId": 0,
    "verifyingContract": "0x0000000000000000000000000000000000000000",
}
WORKER_SHARE_BPS = 9000
VERIFIER_POOL_BPS = 1000


class OnchainDisabled(RuntimeError):
    """Raised when the locked chain adapter is asked to sign, anchor, or mint."""


class LedgerBackend(Protocol):
    name: str

    def sign_settlement(self, statement: dict, key: bytes) -> str:
        """Return the canonical DSSE envelope JSON."""

    def verify_envelope(self, envelope_json: str, key: bytes) -> bool:
        """Return whether the envelope signature matches the payload."""

    def anchor(self, receipt_hashes: list[str]) -> str:
        """Return a Merkle root over receipt hashes. No chain transaction."""


def canonical_json(document: dict) -> str:
    return json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_hex(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def split_minor(price_minor: int, worker_bps: int = WORKER_SHARE_BPS) -> tuple[int, int]:
    """Integer floor split.

    worker_minor = price_minor * worker_bps // 10000
    pool_minor = price_minor - worker_minor

    The floor remainder of the 90% calculation stays in the verifier pool.
    worker_minor + pool_minor = price_minor. The platform retains nothing.
    """

    if price_minor <= 0:
        raise ValueError("price_minor must be positive")
    worker_minor = (price_minor * worker_bps) // 10000
    return worker_minor, price_minor - worker_minor


def verifier_payouts(pool_minor: int, verifier_ids: list[str]) -> list[tuple[str, int]]:
    """Split the pool across verifiers ordered by id.

    The first n-1 verifiers receive pool // n. The last id receives that share
    plus pool % n. The shares sum to pool_minor.
    """

    ordered = sorted(verifier_ids)
    count = len(ordered)
    if count < 1:
        raise ValueError("at least one verifier")
    if pool_minor < count:
        raise ValueError("pool smaller than verifier count")
    base = pool_minor // count
    remainder = pool_minor % count
    payouts = [(verifier_id, base) for verifier_id in ordered]
    last_id, last_amount = payouts[-1]
    payouts[-1] = (last_id, last_amount + remainder)
    return payouts


def settlement_statement(
    *,
    bounty_id: str,
    settlement_id: str,
    artifact_hash: str,
    worker_id: str,
    worker_minor: int,
    verifier_pool_minor: int,
    price_minor: int,
    pending_transfer_id: str,
    post_transfer_ids: list[str],
    verifiers: list[dict],
    prev_receipt_hash: str,
) -> dict:
    return {
        "_type": "https://in-toto.io/Statement/v1",
        "predicate": {
            "backend": "simulated",
            "bountyId": bounty_id,
            "currency": CURRENCY,
            "pendingTransferId": pending_transfer_id,
            "postTransferIds": sorted(post_transfer_ids),
            "prevReceiptHash": prev_receipt_hash,
            "priceMinor": price_minor,
            "settlementId": settlement_id,
            "verifierPoolMinor": verifier_pool_minor,
            "verifiers": sorted(verifiers, key=lambda row: row["id"]),
            "walletClass": WALLET_CLASS,
            "worker": {"amountMinor": worker_minor, "id": worker_id},
        },
        "predicateType": PREDICATE_SETTLEMENT,
        "subject": [
            {
                "digest": {"sha256": artifact_hash},
                "name": f"bounty:{bounty_id}",
            }
        ],
    }


def promotion_statement(
    *,
    bounty_id: str,
    settlement_id: str,
    artifact_hash: str,
    promoter_id: str,
    prev_receipt_hash: str,
) -> dict:
    return {
        "_type": "https://in-toto.io/Statement/v1",
        "predicate": {
            "artifactHash": artifact_hash,
            "backend": "simulated",
            "bountyId": bounty_id,
            "fromPromotion": "HOLD",
            "prevReceiptHash": prev_receipt_hash,
            "promoterId": promoter_id,
            "settlementId": settlement_id,
            "toPromotion": "SIM_ACCEPTED",
            "walletClass": WALLET_CLASS,
        },
        "predicateType": PREDICATE_PROMOTION,
        "subject": [
            {
                "digest": {"sha256": artifact_hash},
                "name": f"bounty:{bounty_id}",
            }
        ],
    }


def eip712_preview(statement: dict) -> dict:
    """Typed-data preview for a later chain signer. chainId 0 is not a network.

    This object is stored beside the receipt. The simulated backend does not
    secp256k1-sign it and does not broadcast it.
    """

    predicate = statement["predicate"]
    return {
        "domain": dict(EIP712_DOMAIN),
        "message": {
            "priceMinor": predicate.get("priceMinor", 0),
            "settlementId": predicate.get("settlementId", ""),
            "workerAmount": predicate.get("worker", {}).get("amountMinor", 0),
        },
        "primaryType": "Settlement",
        "types": {
            "EIP712Domain": [
                {"name": "name", "type": "string"},
                {"name": "version", "type": "string"},
                {"name": "chainId", "type": "uint256"},
                {"name": "verifyingContract", "type": "address"},
            ],
            "Settlement": [
                {"name": "settlementId", "type": "string"},
                {"name": "workerAmount", "type": "uint256"},
                {"name": "priceMinor", "type": "uint256"},
            ],
        },
    }


def pae(payload_type: str, payload: bytes) -> bytes:
    """DSSE Pre-Authentication Encoding v1. See secure-systems-lab/dsse."""

    prefix = f"DSSEv1 {len(payload_type)} {payload_type} {len(payload)} ".encode("ascii")
    return prefix + payload


def sign_envelope(statement_json: str, key: bytes) -> str:
    payload = statement_json.encode("utf-8")
    signature = hmac.new(key, pae(PAYLOAD_TYPE, payload), hashlib.sha256).digest()
    envelope = {
        "payload": base64.b64encode(payload).decode("ascii"),
        "payloadType": PAYLOAD_TYPE,
        "signatures": [
            {
                "keyid": KEY_ID,
                "sig": base64.b64encode(signature).decode("ascii"),
            }
        ],
    }
    return canonical_json(envelope)


class ReceiptVerificationError(ValueError):
    """An attributable receipt failed a public-key check."""


def verify_ed25519_envelope(
    envelope_json: str,
    public_keys: dict[str, bytes],
    revoked_key_ids: set[str] | None = None,
) -> str:
    """Verify one DSSE envelope with Ed25519 public keys. Return the key id.

    Rotated keys verify when their public key is still in ``public_keys`` and
    the id is not in ``revoked_key_ids``. A revoked id fails closed.
    """

    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    envelope = json.loads(envelope_json)
    if envelope.get("payloadType") != PAYLOAD_TYPE:
        raise ReceiptVerificationError("payload type")
    signatures = envelope.get("signatures") or []
    if len(signatures) != 1:
        raise ReceiptVerificationError("signature count")
    key_id = signatures[0].get("keyid")
    if not isinstance(key_id, str) or not key_id:
        raise ReceiptVerificationError("missing key id")
    if revoked_key_ids and key_id in revoked_key_ids:
        raise ReceiptVerificationError(f"revoked key {key_id}")
    public = public_keys.get(key_id)
    if public is None:
        raise ReceiptVerificationError(f"unknown key {key_id}")
    if len(public) != 32:
        raise ReceiptVerificationError(f"public key length {key_id}")
    payload = base64.b64decode(envelope["payload"])
    signature = base64.b64decode(signatures[0]["sig"])
    if len(signature) != 64:
        raise ReceiptVerificationError("signature length")
    try:
        Ed25519PublicKey.from_public_bytes(public).verify(signature, pae(PAYLOAD_TYPE, payload))
    except InvalidSignature as exc:
        raise ReceiptVerificationError("ed25519 signature mismatch") from exc
    return key_id


def verify_envelope(envelope_json: str, key: bytes) -> bool:
    envelope = json.loads(envelope_json)
    if envelope.get("payloadType") != PAYLOAD_TYPE:
        return False
    signatures = envelope.get("signatures") or []
    if len(signatures) != 1 or signatures[0].get("keyid") != KEY_ID:
        return False
    payload = base64.b64decode(envelope["payload"])
    expected = hmac.new(key, pae(PAYLOAD_TYPE, payload), hashlib.sha256).digest()
    actual = base64.b64decode(signatures[0]["sig"])
    return hmac.compare_digest(expected, actual)


def merkle_root(leaves: list[str]) -> str:
    """Same pairing rule as scripts/build-merkle.py build_merkle_tree."""

    if not leaves:
        return sha256_hex("")
    level = list(leaves)
    if len(level) % 2 == 1:
        level.append(level[-1])
    while len(level) > 1:
        nxt = []
        for index in range(0, len(level), 2):
            left = level[index]
            right = level[index + 1] if index + 1 < len(level) else left
            nxt.append(sha256_hex(left + right))
        level = nxt
    return level[0]


class SimulatedLedger:
    name = "simulated"

    def sign_settlement(self, statement: dict, key: bytes) -> str:
        return sign_envelope(canonical_json(statement), key)

    def verify_envelope(self, envelope_json: str, key: bytes) -> bool:
        return verify_envelope(envelope_json, key)

    def anchor(self, receipt_hashes: list[str]) -> str:
        return merkle_root(receipt_hashes)


class OnchainLedger:
    name = "onchain"

    def sign_settlement(self, statement: dict, key: bytes) -> str:
        raise OnchainDisabled("onchain backend is off; no chain calls and no minting")

    def verify_envelope(self, envelope_json: str, key: bytes) -> bool:
        raise OnchainDisabled("onchain backend is off; no chain calls and no minting")

    def anchor(self, receipt_hashes: list[str]) -> str:
        raise OnchainDisabled("onchain backend is off; no chain calls and no minting")


def get_backend(name: str = "simulated") -> LedgerBackend:
    if name == "simulated":
        return SimulatedLedger()
    if name == "onchain":
        return OnchainLedger()
    raise ValueError(f"unknown ledger backend: {name}")
