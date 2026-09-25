from __future__ import annotations

import hashlib
import os
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from .adapters import ModelAdapter, adapter_from_environment
from .policy import Policy
from .storage import ReceiptStore


@dataclass(frozen=True)
class Receipt:
    receipt_id: str
    created_at: str
    request_hash: str
    decision: str
    response: str
    response_hash: str
    policy_id: str
    policy_hash: str
    adapter: str
    model: str
    corpus_hash: str | None = None
    runtime: str = "holbrook-os/0.2.0"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class HolbrookRuntime:
    def __init__(
        self,
        adapter: ModelAdapter | None = None,
        policy: Policy | None = None,
        store: ReceiptStore | None = None,
    ):
        self.adapter = adapter or adapter_from_environment()
        self.policy = policy or Policy()
        self.store = store

    @staticmethod
    def _hash(value: str) -> str:
        return hashlib.sha256(value.encode()).hexdigest()

    def run(self, prompt: str) -> Receipt:
        if not prompt.strip():
            raise ValueError("prompt must not be empty")

        decision = self.policy.decide(prompt)
        request_hash = self._hash(prompt)

        if decision.decision == "veto":
            response = f"Request vetoed by policy (${decision.reason})."
        else:
            response = self.adapter.generate(prompt)

        receipt = Receipt(
            receipt_id=str(uuid.uuid4()),
            created_at=datetime.now(timezone.utc).isoformat(),
            request_hash=request_hash,
            decision=decision.decision,
            response=response,
            response_hash=self._hash(response),
            policy_id=decision.policy_id,
            policy_hash=decision.policy_hash,
            adapter=getattr(self.adapter, "name", type(self.adapter).__name__),
            model=os.getenv("HOLBROOK_MODEL", "default"),
            corpus_hash=os.getenv("HOLBROOK_CORPUS_HASH"),
        )
        if self.store:
            self.store.save(receipt.to_dict())
        return receipt

    @staticmethod
    def verify(receipt: dict[str, Any]) -> bool:
        response = str(receipt.get("response", ""))
        if receipt.get("response_hash") != hashlib.sha256(response.encode()).hexdigest():
            return False
        return bool(receipt.get("receipt_id") and receipt.get("request_hash"))
