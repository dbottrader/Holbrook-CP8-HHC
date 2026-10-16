from __future__ import annotations

from typing import Any, Dict, Tuple

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from cp8_runtime.governance import GovernanceRuntime
from dar_p.gate_validator import GateValidator


def _keypair() -> Tuple[Ed25519PrivateKey, str]:
    private_key = Ed25519PrivateKey.generate()
    public_key_hex = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    ).hex()
    return private_key, public_key_hex


def _body(request_id: str = "req-001") -> Dict[str, Any]:
    return {
        "packet_type": "asin_runtime_action_request",
        "version": "0.1",
        "anchor": {"actor": "agent", "source": "test", "environment": "local"},
        "shape": {"action_type": "file_write", "target": "fixture"},
        "intention": {"goal": "test", "why": "verify runtime", "expected_effect": "receipt"},
        "number": {"request_id": request_id, "evidence_tier": "E2"},
    }


def _signed(body: Dict[str, Any], private_key: Ed25519PrivateKey) -> Dict[str, Any]:
    canonical = GateValidator.canonicalize(body)
    return {
        "unsigned_body": body,
        "signature": {
            "key_id": "key_01",
            "algorithm": "Ed25519",
            "encoding": "hex",
            "signature": private_key.sign(canonical).hex(),
            "canonical_signing_data": canonical.decode("utf-8"),
        },
        "gate_pipeline": [{"id": "packet_shape", "status": "REQUIRED"}],
    }


def _packet_shape(body: Dict[str, Any]) -> bool:
    return body.get("packet_type") == "asin_runtime_action_request" and all(
        key in body for key in ("anchor", "shape", "intention", "number")
    )


def _runtime(public_key_hex: str, decision: str) -> GovernanceRuntime:
    return GovernanceRuntime(
        {"key_01": public_key_hex},
        {"packet_shape": _packet_shape},
        lambda body: {"decision": decision, "reason": f"fixture:{decision.lower()}"},
    )


def test_approve_produces_receipt_and_replay() -> None:
    private_key, public_key_hex = _keypair()
    runtime = _runtime(public_key_hex, "APPROVE")

    result = runtime.process(_signed(_body(), private_key))

    assert result["state"] == "APPROVED"
    assert result["decision"] == "APPROVE"
    assert result["receipt"]["request_id"] == "req-001"
    assert runtime.replay(result["receipt"]["replay_ref"]) == result["replay"]


def test_block_is_terminal_and_receipted() -> None:
    private_key, public_key_hex = _keypair()
    result = _runtime(public_key_hex, "BLOCK").process(_signed(_body(), private_key))

    assert result["state"] == "BLOCKED"
    assert result["decision"] == "BLOCK"
    assert result["receipt"]["receipt_hash"]


def test_escalate_maps_to_escalated_state() -> None:
    private_key, public_key_hex = _keypair()
    result = _runtime(public_key_hex, "ESCALATE").process(_signed(_body(), private_key))

    assert result["state"] == "ESCALATED"
    assert result["decision"] == "ESCALATE"


def test_require_more_context_maps_to_context_required() -> None:
    private_key, public_key_hex = _keypair()
    result = _runtime(public_key_hex, "REQUIRE_MORE_CONTEXT").process(
        _signed(_body(), private_key)
    )

    assert result["state"] == "CONTEXT_REQUIRED"
    assert result["decision"] == "REQUIRE_MORE_CONTEXT"


def test_invalid_signature_never_reaches_policy_gate() -> None:
    private_key, public_key_hex = _keypair()
    calls = []
    runtime = GovernanceRuntime(
        {"key_01": public_key_hex},
        {"packet_shape": _packet_shape},
        lambda body: calls.append(body) or {"decision": "APPROVE"},
    )
    artifact = _signed(_body(), private_key)
    artifact["unsigned_body"]["number"]["request_id"] = "tampered"

    result = runtime.process(artifact)

    assert result["state"] == "REJECTED"
    assert result["decision"] == "BLOCK"
    assert calls == []


def test_unknown_policy_decision_fails_closed() -> None:
    private_key, public_key_hex = _keypair()
    result = _runtime(public_key_hex, "SURPRISE").process(_signed(_body(), private_key))

    assert result["state"] == "BLOCKED"
    assert result["decision"] == "BLOCK"
    assert "fail closed" in result["receipt"]["reason"]


def test_replay_records_are_isolated_by_receipt_hash() -> None:
    private_key, public_key_hex = _keypair()
    runtime = _runtime(public_key_hex, "APPROVE")

    first = runtime.process(_signed(_body("branch-a"), private_key))
    second = runtime.process(_signed(_body("branch-b"), private_key))

    assert first["receipt"]["replay_ref"] != second["receipt"]["replay_ref"]
    assert runtime.replay(first["receipt"]["replay_ref"])["request_id"] == "branch-a"
    assert runtime.replay(second["receipt"]["replay_ref"])["request_id"] == "branch-b"
