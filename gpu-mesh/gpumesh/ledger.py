"""Hash-chained receipt ledger.

An entry stores the exact canonical JSON that was hashed (``body_json``).
Replay hashes those bytes and checks ``prev_hash``. ``hash`` and ``canon``
sit beside the preimage and are not inside it, matching ASIN-HHC canon v1.
"""

from __future__ import annotations

import json
import time
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from gpumesh.canon import (
    ALGORITHM,
    CANON,
    GENESIS_PREV,
    HASHED_FIELDS,
    canon_dumps,
    canon_sha256,
    sha256_text,
)
from gpumesh.db import LedgerEntry, postgres_ledger_lock
from gpumesh.errors import MeshError
from gpumesh.signing import sign_digest, signer_public_hex, verify_digest
from gpumesh.typed import digest_for, work_claim_document


def normalize_amount(payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
    """Credits are integers. ``amount`` is the token-ready field; ``credits`` mirrors it."""
    body = dict(payload)
    if "amount" in body:
        amount = body["amount"]
    elif "credits" in body:
        amount = body["credits"]
    else:
        amount = 0
    if isinstance(amount, bool) or not isinstance(amount, int):
        raise MeshError(400, "amount must be an integer", code="amount_not_integer")
    if "credits" in body:
        credits = body["credits"]
        if isinstance(credits, bool) or not isinstance(credits, int):
            raise MeshError(400, "credits must be an integer", code="amount_not_integer")
        if credits != amount:
            raise MeshError(400, "credits and amount must match", code="amount_mismatch")
    body["amount"] = amount
    body["credits"] = amount
    return body, amount


def _claim_fields(actor: str, kind: str, payload: dict[str, Any], amount: int) -> dict[str, Any]:
    verifiers = payload.get("verifier_ids", payload.get("verifier_id", ""))
    if isinstance(verifiers, list):
        verifiers = ",".join(str(item) for item in verifiers)
    worker = str(payload.get("worker_id") or payload.get("node_id") or actor)
    return {
        "worker_id": worker,
        "verifier_ids": str(verifiers or ""),
        "settlement_id": str(payload.get("settlement_id") or ""),
        "amount": amount,
        "actor": actor,
        "kind": kind,
    }


def append(session: Session, *, actor: str, kind: str, payload: dict[str, Any]) -> LedgerEntry:
    postgres_ledger_lock(session)
    payload, amount = normalize_amount(payload)
    payload_s = canon_dumps(payload)
    last = session.scalar(select(LedgerEntry).order_by(LedgerEntry.seq.desc()).limit(1))
    prev = GENESIS_PREV if last is None else last.hash
    seq = 1 if last is None else last.seq + 1
    ts = int(time.time() * 1000)
    body = {
        "actor": actor,
        "kind": kind,
        "payload": payload_s,
        "prev_hash": prev,
        "seq": seq,
        "ts": ts,
    }
    body_json = canon_dumps(body)
    digest = sha256_text(body_json)
    fields = _claim_fields(actor, kind, payload, amount)
    claim = {
        "actor": actor,
        "amount": amount,
        "kind": kind,
        "ledger_seq": seq,
        "payload_hash": sha256_text(payload_s),
        "prev_hash": prev,
        "settlement_id": fields["settlement_id"],
        "ts": ts,
        "verifier_ids": fields["verifier_ids"],
        "worker_id": fields["worker_id"],
    }
    typed = work_claim_document(**claim)
    signature = sign_digest(digest_for(**claim))
    entry = LedgerEntry(
        seq=seq,
        ts=ts,
        actor=actor,
        kind=kind,
        payload=payload_s,
        prev_hash=prev,
        hash=digest,
        canon=CANON,
        body_json=body_json,
        signature=signature,
        signer=signer_public_hex(),
        typed_json=canon_dumps(typed),
        amount=amount,
    )
    session.add(entry)
    session.flush()
    return entry


def append_genesis(session: Session) -> LedgerEntry:
    return append(
        session,
        actor="genesis",
        kind="genesis",
        payload={
            "network": "GPU-MESH",
            "mesh": "0.1.0",
            "signer": signer_public_hex(),
            "ledger_backend": "simulated",
            "note": "Integer simulated utility credits. Nothing is minted.",
            "amount": 0,
            "credits": 0,
        },
    )


def entry_public(entry: LedgerEntry) -> dict[str, Any]:
    return {
        "seq": entry.seq,
        "ts": entry.ts,
        "actor": entry.actor,
        "kind": entry.kind,
        "payload": entry.payload,
        "prev_hash": entry.prev_hash,
        "hash": entry.hash,
        "canon": entry.canon,
        "amount": entry.amount,
        "signature": entry.signature,
        "signer": entry.signer,
        "typed_data": json.loads(entry.typed_json) if entry.typed_json else None,
    }


def _signature_ok(entry_hash: str, payload: str, prev: str, seq: int, ts: int, actor: str, kind: str, amount: int, signature: str, signer: str, typed: dict | None) -> bool:
    if not signature or not signer or not isinstance(typed, dict):
        return False
    message = typed.get("message") if isinstance(typed, dict) else None
    if not isinstance(message, dict):
        return False
    try:
        claim = {
            "actor": actor,
            "amount": amount,
            "kind": kind,
            "ledger_seq": seq,
            "payload_hash": sha256_text(payload),
            "prev_hash": prev,
            "settlement_id": str(message.get("settlementId") or ""),
            "ts": ts,
            "verifier_ids": str(message.get("verifierIds") or ""),
            "worker_id": str(message.get("workerId") or actor),
        }
        if message.get("amount") != amount or message.get("ledgerSeq") != seq:
            return False
        return verify_digest(signer, digest_for(**claim), signature)
    except (TypeError, ValueError):
        return False


def verify_entries(entries: list[LedgerEntry]) -> dict[str, Any]:
    errors: list[str] = []
    prev = GENESIS_PREV
    for index, entry in enumerate(entries, start=1):
        if entry.seq != index:
            errors.append(f"seq gap at {entry.seq}, expected {index}")
        if entry.prev_hash != prev:
            errors.append(f"link break at seq {entry.seq}")
        if sha256_text(entry.body_json) != entry.hash:
            errors.append(f"hash mismatch at seq {entry.seq}")
        try:
            parsed = json.loads(entry.body_json)
        except json.JSONDecodeError:
            errors.append(f"body is not json at seq {entry.seq}")
            prev = entry.hash
            continue
        if canon_dumps(parsed) != entry.body_json:
            errors.append(f"canon unstable at seq {entry.seq}")
        for field in HASHED_FIELDS:
            if parsed.get(field) != getattr(entry, field):
                errors.append(f"column {field} diverges at seq {entry.seq}")
        if not _signature_ok(
            entry.hash,
            entry.payload,
            entry.prev_hash,
            entry.seq,
            entry.ts,
            entry.actor,
            entry.kind,
            entry.amount,
            entry.signature,
            entry.signer,
            json.loads(entry.typed_json) if entry.typed_json else None,
        ):
            errors.append(f"signature mismatch at seq {entry.seq}")
        prev = entry.hash
    tip = entries[-1].hash if entries else None
    return {
        "ok": not errors and bool(entries),
        "length": len(entries),
        "tip": tip,
        "errors": errors,
        "canon": CANON,
        "algorithm": ALGORITHM,
    }


def verify_session(session: Session) -> dict[str, Any]:
    rows = list(session.scalars(select(LedgerEntry).order_by(LedgerEntry.seq.asc())))
    return verify_entries(rows)


def verify_export(entries: list[dict[str, Any]]) -> dict[str, Any]:
    """Replay a public ledger export. This is the offline check anyone can run."""
    errors: list[str] = []
    prev = GENESIS_PREV
    for index, entry in enumerate(entries, start=1):
        if entry.get("seq") != index:
            errors.append(f"seq gap at {entry.get('seq')}, expected {index}")
        if entry.get("prev_hash") != prev:
            errors.append(f"link break at seq {entry.get('seq')}")
        try:
            body = {field: entry[field] for field in HASHED_FIELDS}
        except KeyError as exc:
            errors.append(f"missing {exc} at seq {entry.get('seq')}")
            prev = str(entry.get("hash") or "")
            continue
        if canon_sha256(body) != entry.get("hash"):
            errors.append(f"hash mismatch at seq {entry.get('seq')}")
        amount = entry.get("amount")
        if isinstance(amount, bool) or not isinstance(amount, int):
            errors.append(f"amount is not an integer at seq {entry.get('seq')}")
            amount = 0
        if not _signature_ok(
            str(entry.get("hash") or ""),
            str(entry.get("payload") or ""),
            str(entry.get("prev_hash") or ""),
            int(entry.get("seq") or 0),
            int(entry.get("ts") or 0),
            str(entry.get("actor") or ""),
            str(entry.get("kind") or ""),
            int(amount),
            str(entry.get("signature") or ""),
            str(entry.get("signer") or ""),
            entry.get("typed_data") if isinstance(entry.get("typed_data"), dict) else None,
        ):
            errors.append(f"signature mismatch at seq {entry.get('seq')}")
        prev = str(entry.get("hash") or "")
    return {
        "ok": not errors and bool(entries),
        "length": len(entries),
        "tip": entries[-1].get("hash") if entries else None,
        "errors": errors,
        "canon": CANON,
        "algorithm": ALGORITHM,
    }


def tip_status(session: Session) -> dict[str, Any]:
    """Cheap check for the dashboard poll: length, tip, and the last link."""
    rows = list(
        session.scalars(select(LedgerEntry).order_by(LedgerEntry.seq.desc()).limit(2))
    )
    if not rows:
        return {"ok": False, "length": 0, "tip": None, "error": "empty"}
    last = rows[0]
    length = session.query(LedgerEntry).count()
    errors: list[str] = []
    if sha256_text(last.body_json) != last.hash:
        errors.append("tip hash mismatch")
    if len(rows) == 2 and last.prev_hash != rows[1].hash:
        errors.append("tip link break")
    if length == 1 and last.prev_hash != GENESIS_PREV:
        errors.append("genesis link break")
    return {"ok": not errors, "length": length, "tip": last.hash, "errors": errors, "canon": CANON}
