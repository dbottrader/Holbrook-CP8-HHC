"""Token-ready bounty receipts.

The simulated backend is the default and does not mint. The on-chain adapter
loads only when get_backend("onchain") sees HHCW_SETTLEMENT_ADDR.
"""

from moltbook.ledger.backend import (
    OnchainDisabled,
    OnchainLedger,
    SimulatedLedger,
    get_backend,
)

__all__ = [
    "OnchainDisabled",
    "OnchainLedger",
    "SimulatedLedger",
    "get_backend",
]
