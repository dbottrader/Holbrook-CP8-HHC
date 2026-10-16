"""Runnable CP8 governance bridge built on the existing DAR-P validator.

The runtime deliberately separates cryptographic artifact acceptance from policy
authority. A valid signature proves artifact identity; it never grants authority.
Every terminal policy decision produces a deterministic receipt and replay record.
"""

from __future__ import annotations

import hashlib
from enum import Enum
from typing import Any, Callable, Dict, Mapping, Optional

from dar_p.gate_validator import GateCallable, GateValidator


PolicyCallable = Callable[[Dict[str, Any]], Mapping[str, Any] | str]


class PolicyDecision(str, Enum):
    APPROVE = "APPROVE"
    BLOCK = "BLOCK"
    ESCALATE = "ESCALATE"
    REQUIRE_MORE_CONTEXT = "REQUIRE_MORE_CONTEXT"


class RuntimeState(str, Enum):
    RECEIVED = "RECEIVED"
    VALIDATED = "VALIDATED"
    REJECTED = "REJECTED"
    APPROVED = "APPROVED"
    BLOCKED = "BLOCKED"
    ESCALATED = "ESCALATED"
    CONTEXT_REQUIRED = "CONTEXT_REQUIRED"


_DECISION_TO_STATE = {
    PolicyDecision.APPROVE: RuntimeState.APPROVED,
    PolicyDecision.BLOCK: RuntimeState.BLOCKED,
    PolicyDecision.ESCALATE: RuntimeState.ESCALATED,
    PolicyDecision.REQUIRE_MORE_CONTEXT: RuntimeState.CONTEXT_REQUIRED,
}


class GovernanceRuntime:
    """Validate, govern, receipt, and replay one CP8 action request."""

    def __init__(
        self,
        key_registry: Mapping[str, Any],
        gate_registry: Mapping[str, GateCallable],
        policy_gate: PolicyCallable,
        *,
        policy_snapshot: str = "cp8-policy-v0.1",
    ) -> None:
        self.validator = GateValidator(key_registry)
        self.gate_registry = gate_registry
        self.policy_gate = policy_gate
        self.policy_snapshot = policy_snapshot
        self._replay: Dict[str, Dict[str, Any]] = {}

    def process(self, artifact: Mapping[str, Any]) -> Dict[str, Any]:
        """Process a signed DAR-P action artifact with fail-closed semantics."""
        validation = self.validator.validate(artifact, self.gate_registry)
        validation_status = validation["status"]

        if validation_status == "REJECTED":
            return {
                "state": RuntimeState.REJECTED.value,
                "decision": PolicyDecision.BLOCK.value,
                "validation": validation,
                "receipt": self._receipt(
                    state=RuntimeState.REJECTED,
                    decision=PolicyDecision.BLOCK,
                    artifact_hash=validation["receipt"]["artifact_hash"],
                    request_id=self._request_id(artifact),
                    reason="DAR-P validation rejected the artifact.",
                ),
            }

        body = dict(artifact["unsigned_body"])
        policy_result = self.policy_gate(body)
        decision, reason = self._normalize_policy_result(policy_result)
        state = _DECISION_TO_STATE[decision]
        receipt = self._receipt(
            state=state,
            decision=decision,
            artifact_hash=validation["receipt"]["artifact_hash"],
            request_id=self._request_id(artifact),
            reason=reason,
        )
        replay_ref = receipt["receipt_hash"]
        replay_record = {
            "replay_ref": replay_ref,
            "request_id": receipt["request_id"],
            "artifact_hash": receipt["artifact_hash"],
            "policy_snapshot": self.policy_snapshot,
            "decision": decision.value,
            "state": state.value,
            "reason": reason,
            "validation_hash": validation["receipt"]["validation_hash"],
        }
        self._replay[replay_ref] = replay_record

        return {
            "state": state.value,
            "decision": decision.value,
            "validation": validation,
            "receipt": {**receipt, "replay_ref": replay_ref},
            "replay": replay_record,
        }

    def replay(self, replay_ref: str) -> Optional[Dict[str, Any]]:
        """Return a defensive copy of a prior replay record."""
        record = self._replay.get(replay_ref)
        return dict(record) if record is not None else None

    def _receipt(
        self,
        *,
        state: RuntimeState,
        decision: PolicyDecision,
        artifact_hash: Optional[str],
        request_id: Optional[str],
        reason: str,
    ) -> Dict[str, Any]:
        body = {
            "protocol": "ASINHHCCP8-RUNTIME",
            "receipt_version": "0.1",
            "request_id": request_id,
            "artifact_hash": artifact_hash,
            "policy_snapshot": self.policy_snapshot,
            "state": state.value,
            "decision": decision.value,
            "reason": reason,
        }
        body["receipt_hash"] = hashlib.sha256(
            GateValidator.canonicalize(body)
        ).hexdigest()
        return body

    @staticmethod
    def _request_id(artifact: Mapping[str, Any]) -> Optional[str]:
        body = artifact.get("unsigned_body", {})
        if not isinstance(body, Mapping):
            return None
        number = body.get("number", {})
        if not isinstance(number, Mapping):
            return None
        request_id = number.get("request_id")
        return str(request_id) if request_id is not None else None

    @staticmethod
    def _normalize_policy_result(
        result: Mapping[str, Any] | str,
    ) -> tuple[PolicyDecision, str]:
        if isinstance(result, str):
            raw_decision = result
            reason = "Policy gate returned no reason."
        elif isinstance(result, Mapping):
            raw_decision = str(result.get("decision", "BLOCK"))
            reason = str(result.get("reason", "Policy gate returned no reason."))
        else:
            return PolicyDecision.BLOCK, "Malformed policy result; fail closed."

        try:
            decision = PolicyDecision(raw_decision.upper())
        except ValueError:
            return PolicyDecision.BLOCK, f"Unknown policy decision {raw_decision!r}; fail closed."
        return decision, reason
