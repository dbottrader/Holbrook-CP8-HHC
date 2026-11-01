"""EIP-712-style typed data for a work claim.

The encoding follows EIP-712 (domain separator, type hash, ``\\x19\\x01``),
with SHA-256 in place of keccak256. ``chainId`` is 0 and ``verifyingContract``
is the zero address, so this digest is not a transaction and cannot be
broadcast. Amounts are integers.
"""

from __future__ import annotations

from typing import Any

DOMAIN_TYPE = "EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)"
CLAIM_TYPE = (
    "WorkClaim(string actor,int256 amount,string kind,uint256 ledgerSeq,"
    "bytes32 payloadHash,bytes32 prevHash,string settlementId,uint256 ts,"
    "string verifierIds,string workerId)"
)
ZERO_ADDRESS = "0x" + "00" * 20


def _u256(value: int) -> bytes:
    if value < 0 or value >= 2**256:
        raise ValueError("uint256 out of range")
    return value.to_bytes(32, "big")


def _i256(value: int) -> bytes:
    if value < -(2**255) or value >= 2**255:
        raise ValueError("int256 out of range")
    return value.to_bytes(32, "big", signed=True)


def _bytes32_hex(value: str) -> bytes:
    raw = bytes.fromhex(value.removeprefix("0x"))
    if len(raw) != 32:
        raise ValueError("expected 32 bytes")
    return raw


def _sha256(raw: bytes) -> bytes:
    import hashlib

    return hashlib.sha256(raw).digest()


def _encode_address(value: str) -> bytes:
    raw = bytes.fromhex(value.removeprefix("0x"))
    if len(raw) != 20:
        raise ValueError("address must be 20 bytes")
    return b"\x00" * 12 + raw


def domain_separator() -> bytes:
    type_hash = _sha256(DOMAIN_TYPE.encode("utf-8"))
    return _sha256(
        type_hash
        + _sha256(b"GPU-MESH")
        + _sha256(b"1")
        + _u256(0)
        + _encode_address(ZERO_ADDRESS)
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


def work_claim_document(
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
) -> dict[str, Any]:
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
            "actor": actor,
            "amount": amount,
            "kind": kind,
            "ledgerSeq": ledger_seq,
            "payloadHash": payload_hash,
            "prevHash": prev_hash,
            "settlementId": settlement_id,
            "ts": ts,
            "verifierIds": verifier_ids,
            "workerId": worker_id,
        },
        "hash": "sha256",
        "note": "EIP-712-style typed data. SHA-256 stands in for keccak256. chainId 0 is not a network.",
    }


def digest_for(**fields: Any) -> bytes:
    return typed_digest(claim_struct_hash(**fields))
