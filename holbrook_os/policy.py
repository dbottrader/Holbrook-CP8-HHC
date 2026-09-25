from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass


@dataclass(frozen=True)
class PolicyDecision:
    decision: str
    reason: str | None
    policy_id: str
    policy_hash: str


class Policy:
    """Deterministic baseline policy. Extend with explicit policy modules."""

    policy_id = "baseline-v1"
    blocked_terms = (
        "steal credentials",
        "exfiltrate secrets",
        "bypass authentication",
    )

    @property
    def policy_hash(self) -> str:
        payload = json.dumps(
            {"policy_id": self.policy_id, "blocked_terms": self.blocked_terms},
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode()).hexdigest()

    def decide(self, prompt: str) -> PolicyDecision:
        normalized = prompt.casefold()
        for term in self.blocked_terms:
            if term in normalized:
                return PolicyDecision(
                    "veto",
                    f"blocked policy term: {term}",
                    self.policy_id,
                    self.policy_hash,
                )
        return PolicyDecision("allow", None, self.policy_id, self.policy_hash)
