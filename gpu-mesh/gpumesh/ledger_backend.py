"""Ledger backends.

``simulated`` is the default for this process: append-only integer claims in
the local database, signed, with a Merkle root that is not published.
``onchain`` is the name of the seam. This process still does not submit a
transaction and does not open a socket. Live HHCW settlement on Base Sepolia
is the box-side settler (``gpu-mesh/settler``), which holds the key.
Settlement ``0xdfFE664d23E30Baff7Ad4d16831aD625Cc90bcCA``, token
``0x24a7B22fC54DbFD117023535eBeCf660B76fdb5d``, after two distinct verifiers.
Switching the local name is ``GPU_MESH_LEDGER_BACKEND``.
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
            "This process does not submit a Base transaction and does not open a socket. "
            "The public GPU mesh settles HHCW on Base Sepolia via the box-side settler "
            "(Settlement 0xdfFE664d23E30Baff7Ad4d16831aD625Cc90bcCA, "
            "token 0x24a7B22fC54DbFD117023535eBeCf660B76fdb5d) after two distinct verifiers.",
            "server_error",
            "onchain_disabled",
        )

    def anchor(self, session: Session) -> dict[str, Any]:
        del session
        raise MeshError(
            501,
            "This process does not anchor on Base and does not open a socket. "
            "The public GPU mesh settles HHCW on Base Sepolia via the box-side settler "
            "(Settlement 0xdfFE664d23E30Baff7Ad4d16831aD625Cc90bcCA, "
            "token 0x24a7B22fC54DbFD117023535eBeCf660B76fdb5d) after two distinct verifiers.",
            "server_error",
            "onchain_disabled",
        )


_active = "simulated"


def activate(name: str) -> str:
    """Select the process-wide ledger. Called once when the database opens."""
    global _active
    backend = get_backend(name or "simulated")
    _active = backend.name
    return _active


def current_backend() -> str:
    return _active


def append_current(session: Session, *, actor: str, kind: str, payload: dict[str, Any]) -> Any:
    return get_backend(_active).append(session, actor=actor, kind=kind, payload=payload)


def get_backend(name: str) -> LedgerBackend:
    if name in {"", "simulated"}:
        return SimulatedLedger()
    if name == "onchain":
        return OnchainLedger()
    raise MeshError(400, f"unknown ledger backend {name}", code="bad_backend")
