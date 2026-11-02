"""Agent Mesh receipt format (GPU-MESH canon v1).

The hash and the EIP-712-style digest match `gpu-mesh/gpumesh/canon.py`,
`typed.py`, and `ledger.py` on main. SHA-256 stands in for keccak256 and
`chainId` 0, so the mesh signature is not a transaction. HHCW settlement
uses a separate secp256k1 EIP-712 attestation after this receipt verifies.

HHCW is a work token for verified contribution.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

GENESIS_PREV = "0" * 64
CANON = "v1"
DOMAIN_TYPE = "EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)"
CLAIM_TYPE = (
    "WorkClaim(string actor,int256 amount,string kind,uint256 ledgerSeq,"
    "bytes32 payloadHash,bytes32 prevHash,string settlementId,uint256 ts,"
    "string verifierIds,string workerId)"
)
ZERO_ADDRESS = "0x" + "00" * 20
WORKER_BPS = 9000
VERIFIER_BPS = 500
BPS_DENOM = 10000


class MeshReceiptError(ValueError):
    """A mesh receipt failed the canonical check."""


def canon_dumps(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _u256(value: int) -> bytes:
    if value < 0 or value >= 2**256:
        raise MeshReceiptError("uint256 out of range")
    return value.to_bytes(32, "big")


def _i256(value: int) -> bytes:
    if value < -(2**255) or value >= 2**255:
        raise MeshReceiptError("int256 out of range")
    return value.to_bytes(32, "big", signed=True)


def _bytes32_hex(value: str) -> bytes:
    raw = bytes.fromhex(value.removeprefix("0x"))
    if len(raw) != 32:
        raise MeshReceiptError("expected 32 bytes")
    return raw


def _sha256(raw: bytes) -> bytes:
    return hashlib.sha256(raw).digest()


def _encode_address(value: str) -> bytes:
    raw = bytes.fromhex(value.removeprefix("0x"))
    if len(raw) != 20:
        raise MeshReceiptError("address must be 20 bytes")
    return b"\x00" * 12 + raw


def domain_separator() -> bytes:
    type_hash = _sha256(DOMAIN_TYPE.encode("utf-8"))
    return _sha256(
        type_hash + _sha256(b"GPU-MESH") + _sha256(b"1") + _u256(0) + _encode_address(ZERO_ADDRESS)
    )


def claim_struct_hash(
    *,
    actor: str,
    amount: int,
    kind: str,
    ledger_seq: int,
    payload_hash: str,
    prev_hash: str,
    settlement_id: str,
    ts: int,
    verifier_ids: str,
    worker_id: str,
) -> bytes:
    type_hash = _sha256(CLAIM_TYPE.encode("utf-8"))
    return _sha256(
        type_hash
        + _sha256(actor.encode("utf-8"))
        + _i256(amount)
        + _sha256(kind.encode("utf-8"))
        + _u256(ledger_seq)
        + _bytes32_hex(payload_hash)
        + _bytes32_hex(prev_hash)
        + _sha256(settlement_id.encode("utf-8"))
        + _u256(ts)
        + _sha256(verifier_ids.encode("utf-8"))
        + _sha256(worker_id.encode("utf-8"))
    )


def typed_digest(struct_hash: bytes) -> bytes:
    return _sha256(b"\x19\x01" + domain_separator() + struct_hash)


def digest_for(**fields: Any) -> bytes:
    return typed_digest(claim_struct_hash(**fields))


def work_claim_document(**fields: Any) -> dict[str, Any]:
    return {
        "types": {
            "EIP712Domain": [
                {"name": "name", "type": "string"},
                {"name": "version", "type": "string"},
                {"name": "chainId", "type": "uint256"},
                {"name": "verifyingContract", "type": "address"},
            ],
            "WorkClaim": [
                {"name": "actor", "type": "string"},
                {"name": "amount", "type": "int256"},
                {"name": "kind", "type": "string"},
                {"name": "ledgerSeq", "type": "uint256"},
                {"name": "payloadHash", "type": "bytes32"},
                {"name": "prevHash", "type": "bytes32"},
                {"name": "settlementId", "type": "string"},
                {"name": "ts", "type": "uint256"},
                {"name": "verifierIds", "type": "string"},
                {"name": "workerId", "type": "string"},
            ],
        },
        "primaryType": "WorkClaim",
        "domain": {
            "name": "GPU-MESH",
            "version": "1",
            "chainId": 0,
            "verifyingContract": ZERO_ADDRESS,
        },
        "message": {
            "actor": fields["actor"],
            "amount": fields["amount"],
            "kind": fields["kind"],
            "ledgerSeq": fields["ledger_seq"],
            "payloadHash": fields["payload_hash"],
            "prevHash": fields["prev_hash"],
            "settlementId": fields["settlement_id"],
            "ts": fields["ts"],
            "verifierIds": fields["verifier_ids"],
            "workerId": fields["worker_id"],
        },
        "hash": "sha256",
        "note": "EIP-712-style typed data. SHA-256 stands in for keccak256. chainId 0 is not a network.",
    }


def mesh_merkle_root(leaves_hex: list[str]) -> str:
    """Pairwise SHA-256 over receipt hashes. Odd levels duplicate the last leaf."""

    if not leaves_hex:
        return _sha256(b"").hex()
    level = [bytes.fromhex(item.removeprefix("0x")) for item in leaves_hex]
    while len(level) > 1:
        if len(level) % 2 == 1:
            level.append(level[-1])
        level = [_sha256(level[index] + level[index + 1]) for index in range(0, len(level), 2)]
    return level[0].hex()


def split_contribution(total: int) -> tuple[int, int, int]:
    """Exact 9000 / 500 / 500. Dust raises instead of being reassigned."""

    if isinstance(total, bool) or not isinstance(total, int) or total <= 0:
        raise MeshReceiptError("contribution must be a positive integer")
    worker = (total * WORKER_BPS) // BPS_DENOM
    each = (total * VERIFIER_BPS) // BPS_DENOM
    if worker + each + each != total:
        raise MeshReceiptError("contribution does not divide into 9000/500/500")
    return worker, each, each


def _claim_from_entry(entry: Mapping[str, Any], payload_s: str, amount: int) -> dict[str, Any]:
    typed = entry.get("typed_data") or entry.get("typed")
    if not isinstance(typed, dict):
        raise MeshReceiptError("typed_data missing")
    message = typed.get("message")
    if not isinstance(message, dict):
        raise MeshReceiptError("typed message missing")
    return {
        "actor": str(entry["actor"]),
        "amount": amount,
        "kind": str(entry["kind"]),
        "ledger_seq": int(entry["seq"]),
        "payload_hash": sha256_text(payload_s),
        "prev_hash": str(entry["prev_hash"]),
        "settlement_id": str(message.get("settlementId") or ""),
        "ts": int(entry["ts"]),
        "verifier_ids": str(message.get("verifierIds") or ""),
        "worker_id": str(message.get("workerId") or entry["actor"]),
        "message": message,
    }


def verify_mesh_receipt(entry: Mapping[str, Any]) -> dict[str, Any]:
    """Check canon v1, the hash, and the Ed25519 mesh signature. Return the claim."""

    if entry.get("canon") != CANON:
        raise MeshReceiptError("canon must be v1")
    payload_s = entry.get("payload")
    if not isinstance(payload_s, str):
        raise MeshReceiptError("payload must be the canonical JSON string")
    amount = entry.get("amount")
    if isinstance(amount, bool) or not isinstance(amount, int):
        raise MeshReceiptError("amount must be an integer")
    body = {
        "actor": entry["actor"],
        "kind": entry["kind"],
        "payload": payload_s,
        "prev_hash": entry["prev_hash"],
        "seq": entry["seq"],
        "ts": entry["ts"],
    }
    digest_hex = sha256_text(canon_dumps(body))
    if digest_hex != str(entry.get("hash")):
        raise MeshReceiptError("receipt hash mismatch")
    claim = _claim_from_entry(entry, payload_s, amount)
    message = claim.pop("message")
    if message.get("amount") != amount or message.get("ledgerSeq") != int(entry["seq"]):
        raise MeshReceiptError("typed message does not match the entry")
    if message.get("actor") != entry["actor"] or message.get("kind") != entry["kind"]:
        raise MeshReceiptError("typed actor or kind mismatch")
    if str(message.get("prevHash")) != str(entry["prev_hash"]):
        raise MeshReceiptError("typed prevHash mismatch")
    if str(message.get("payloadHash")) != claim["payload_hash"]:
        raise MeshReceiptError("typed payloadHash mismatch")
    signer = str(entry.get("signer") or "")
    signature = str(entry.get("signature") or "")
    try:
        key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(signer))
        key.verify(bytes.fromhex(signature), digest_for(**claim))
    except (InvalidSignature, ValueError) as exc:
        raise MeshReceiptError("mesh signature mismatch") from exc
    claim["payload"] = json.loads(payload_s)
    return claim


def receipt_is_verified(claim: Mapping[str, Any]) -> bool:
    payload = claim.get("payload")
    if not isinstance(payload, dict):
        return False
    status = str(payload.get("status") or payload.get("state") or "").lower()
    kind = str(claim.get("kind") or "").lower()
    if status in {"verified", "pass"}:
        return True
    return kind == "verified" and status in {"", "completed"}


def verifier_ids_of(claim: Mapping[str, Any]) -> list[str]:
    raw = str(claim.get("verifier_ids") or "")
    return [part.strip() for part in raw.split(",") if part.strip()]


def sign_mesh_receipt(
    *,
    actor: str,
    kind: str,
    payload: dict[str, Any],
    prev_hash: str,
    seq: int,
    ts: int,
    private_key: Any,
) -> dict[str, Any]:
    """Build one canon-v1 entry. `private_key` is an Ed25519 private key object."""

    from cryptography.hazmat.primitives import serialization

    body_payload = dict(payload)
    amount = int(body_payload["amount"])
    body_payload["credits"] = amount
    payload_s = canon_dumps(body_payload)
    hashed = {
        "actor": actor,
        "kind": kind,
        "payload": payload_s,
        "prev_hash": prev_hash,
        "seq": seq,
        "ts": ts,
    }
    verifiers = body_payload.get("verifier_ids", body_payload.get("verifier_id", ""))
    if isinstance(verifiers, list):
        verifiers = ",".join(str(item) for item in verifiers)
    worker = str(body_payload.get("worker_id") or body_payload.get("node_id") or actor)
    claim = {
        "actor": actor,
        "amount": amount,
        "kind": kind,
        "ledger_seq": seq,
        "payload_hash": sha256_text(payload_s),
        "prev_hash": prev_hash,
        "settlement_id": str(body_payload.get("settlement_id") or ""),
        "ts": ts,
        "verifier_ids": str(verifiers or ""),
        "worker_id": worker,
    }
    public = private_key.public_key().public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )
    return {
        "seq": seq,
        "ts": ts,
        "actor": actor,
        "kind": kind,
        "payload": payload_s,
        "prev_hash": prev_hash,
        "hash": sha256_text(canon_dumps(hashed)),
        "canon": CANON,
        "amount": amount,
        "signature": private_key.sign(digest_for(**claim)).hex(),
        "signer": public.hex(),
        "typed_data": work_claim_document(**claim),
    }
