"""Merkle root over the receipt chain.

The root is a local commitment. Nothing here opens a socket, talks to a
chain, or deploys a contract. An on-chain hook exists only so a later
backend can be switched on without rewriting receipts, and it refuses.
"""

from __future__ import annotations

import hashlib
import time
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from gpumesh.db import Anchor, LedgerEntry
from gpumesh.errors import MeshError


def _sha(raw: bytes) -> bytes:
    return hashlib.sha256(raw).digest()


def merkle_root(leaves_hex: list[str]) -> str:
    """Bitcoin-style pairwise SHA-256. Odd levels duplicate the last leaf."""
    if not leaves_hex:
        return _sha(b"").hex()
    level = [bytes.fromhex(item) for item in leaves_hex]
    while len(level) > 1:
        if len(level) % 2 == 1:
            level.append(level[-1])
        level = [_sha(level[i] + level[i + 1]) for i in range(0, len(level), 2)]
    return level[0].hex()


class AnchoringHook(Protocol):
    name: str

    def commit(self, session: Session, commitment: dict[str, Any]) -> dict[str, Any]: ...


class SimulatedAnchor:
    """Store the root in the database and leave it unpublished."""

    name = "simulated"

    def commit(self, session: Session, commitment: dict[str, Any]) -> dict[str, Any]:
        row = Anchor(
            created_at=time.time(),
            from_seq=int(commitment["from_seq"]),
            to_seq=int(commitment["to_seq"]),
            count=int(commitment["count"]),
            root=str(commitment["root"]),
            tip_hash=str(commitment["tip_hash"]),
            backend=self.name,
            published=0,
        )
        session.add(row)
        session.flush()
        body = dict(commitment)
        body["id"] = row.id
        body["backend"] = self.name
        body["published"] = False
        body["chain_called"] = False
        return body


class OnchainAnchor:
    """Refuses. Turning this on is Dennis's decision after legal review."""

    name = "onchain"

    def commit(self, session: Session, commitment: dict[str, Any]) -> dict[str, Any]:
        del session, commitment
        raise MeshError(
            501,
            "on-chain anchoring is disabled. The simulated backend records Merkle roots locally and does not mint or broadcast.",
            "server_error",
            "onchain_disabled",
        )


def hook_for(name: str) -> AnchoringHook:
    if name in {"", "simulated"}:
        return SimulatedAnchor()
    if name == "onchain":
        return OnchainAnchor()
    raise MeshError(400, f"unknown ledger backend {name}", code="bad_backend")


def commitment_for(session: Session) -> dict[str, Any]:
    rows = list(session.scalars(select(LedgerEntry).order_by(LedgerEntry.seq.asc())))
    hashes = [row.hash for row in rows]
    root = merkle_root(hashes)
    return {
        "from_seq": rows[0].seq if rows else 0,
        "to_seq": rows[-1].seq if rows else 0,
        "count": len(rows),
        "root": root,
        "tip_hash": rows[-1].hash if rows else "",
        "published": False,
        "chain_called": False,
    }


def anchor_chain(session: Session, backend_name: str = "simulated") -> dict[str, Any]:
    """Commit the current receipt chain. Repeat calls with the same tip reuse the row."""
    current = commitment_for(session)
    if current["count"] == 0:
        raise MeshError(409, "ledger is empty", code="empty_ledger")
    existing = session.scalar(select(Anchor).where(Anchor.tip_hash == current["tip_hash"]).limit(1))
    if existing is not None and backend_name != "onchain":
        return {
            "id": existing.id,
            "from_seq": existing.from_seq,
            "to_seq": existing.to_seq,
            "count": existing.count,
            "root": existing.root,
            "tip_hash": existing.tip_hash,
            "backend": existing.backend,
            "published": False,
            "chain_called": False,
            "reused": True,
        }
    hook = hook_for(backend_name)
    body = hook.commit(session, current)
    body["reused"] = False
    return body


def latest_anchor(session: Session) -> dict[str, Any] | None:
    row = session.scalar(select(Anchor).order_by(Anchor.id.desc()).limit(1))
    if row is None:
        return None
    return {
        "id": row.id,
        "from_seq": row.from_seq,
        "to_seq": row.to_seq,
        "count": row.count,
        "root": row.root,
        "tip_hash": row.tip_hash,
        "backend": row.backend,
        "published": False,
        "chain_called": False,
    }
