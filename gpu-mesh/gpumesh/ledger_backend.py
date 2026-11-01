"""Ledger backends.

``simulated`` is the default: append-only integer claims of a simulated
utility credit in the local database, signed, with a Merkle root that is
not published. ``onchain`` is a named adapter that refuses. It does not
open a socket, deploy a contract, or mint anything.
"""

from __future__ import annotations

from typing import Any, Protocol

from sqlalchemy.orm import Session

from gpumesh.errors import MeshError
from gpumesh.merkle import anchor_chain


class LedgerBackend(Protocol):
    name: str

    def append(self, session: Session, *, actor: str, kind: str, payload: dict[str, Any]) -> Any: ...

    def anchor(self, session: Session) -> dict[str, Any]: ...


class SimulatedLedger:
    name = "simulated"

    def append(self, session: Session, *, actor: str, kind: str, payload: dict[str, Any]) -> Any:
        from gpumesh.ledger import append

        return append(session, actor=actor, kind=kind, payload=payload)

    def anchor(self, session: Session) -> dict[str, Any]:
        return anchor_chain(session, "simulated")


class OnchainLedger:
    name = "onchain"

    def append(self, session: Session, *, actor: str, kind: str, payload: dict[str, Any]) -> Any:
        del session, actor, kind, payload
        raise MeshError(
            501,
            "the on-chain ledger is disabled. HHC stays a simulated utility credit. Nothing is minted.",
            "server_error",
            "onchain_disabled",
        )

    def anchor(self, session: Session) -> dict[str, Any]:
        del session
        raise MeshError(
            501,
            "on-chain anchoring is disabled. No contract is deployed and nothing is minted.",
            "server_error",
            "onchain_disabled",
        )


def get_backend(name: str) -> LedgerBackend:
    if name in {"", "simulated"}:
        return SimulatedLedger()
    if name == "onchain":
        return OnchainLedger()
    raise MeshError(400, f"unknown ledger backend {name}", code="bad_backend")
