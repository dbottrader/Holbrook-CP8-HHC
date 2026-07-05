from __future__ import annotations

from typing import Any, Dict, Tuple

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from dar_p.gate_validator import GateValidator


def _keypair() -> Tuple[Ed25519PrivateKey, str]:
    private_key = Ed25519PrivateKey.generate()
    public_key_hex = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    ).hex()
    return private_key, public_key_hex


def _signed_artifact(
    unsigned_body: Dict[str, Any],
    private_key: Ed25519PrivateKey,
    gate_pipeline: list[dict[str, str]] | None = None,
    key_id: str = "key_01",
) -> Dict[str, Any]:
    canonical_body = GateValidator.canonicalize(unsigned_body)
    signature = private_key.sign(canonical_body).hex()
    return {
        "unsigned_body": unsigned_body,
        "signature": {
            "key_id": key_id,
            "algorithm": "Ed25519",
            "encoding": "hex",
            "signature": signature,
            "canonical_signing_data": canonical_body.decode("utf-8"),
        },
        "gate_pipeline": gate_pipeline or [{"id": "known_required", "status": "REQUIRED"}],
    }


def _first_error_code(result: Dict[str, Any]) -> str:
    return result["errors"][0]["code"]


def test_valid_artifact_accepted() -> None:
    private_key, public_key_hex = _keypair()
    validator = GateValidator({"key_01": public_key_hex})
    artifact = _signed_artifact({"data": 1}, private_key)

    result = validator.validate(artifact, {"known_required": lambda body: body["data"] == 1})

    assert result["status"] == "ACCEPTED"
    assert result["errors"] == []
    assert result["receipt"]["artifact_hash"]


def test_bad_signature_rejected() -> None:
    private_key, public_key_hex = _keypair()
    validator = GateValidator({"key_01": public_key_hex})
    artifact = _signed_artifact({"data": 1}, private_key)
    artifact["unsigned_body"] = {"data": 2}

    result = validator.validate(artifact, {"known_required": lambda body: True})

    assert result["status"] == "REJECTED"
    assert _first_error_code(result) == "SIGNATURE_INVALID"


def test_missing_key_rejected() -> None:
    private_key, _public_key_hex = _keypair()
    validator = GateValidator({})
    artifact = _signed_artifact({"data": 1}, private_key)

    result = validator.validate(artifact, {"known_required": lambda body: True})

    assert result["status"] == "REJECTED"
    assert _first_error_code(result) == "KEY_NOT_FOUND"


def test_unknown_required_gate_rejected() -> None:
    private_key, public_key_hex = _keypair()
    validator = GateValidator({"key_01": public_key_hex})
    artifact = _signed_artifact(
        {"data": 1},
        private_key,
        gate_pipeline=[{"id": "missing_required", "status": "REQUIRED"}],
    )

    result = validator.validate(artifact, {})

    assert result["status"] == "REJECTED"
    assert _first_error_code(result) == "UNKNOWN_REQUIRED_GATE"


def test_unknown_optional_gate_accepted_with_warnings() -> None:
    private_key, public_key_hex = _keypair()
    validator = GateValidator({"key_01": public_key_hex})
    artifact = _signed_artifact(
        {"data": 1},
        private_key,
        gate_pipeline=[{"id": "missing_optional", "status": "OPTIONAL"}],
    )

    result = validator.validate(artifact, {})

    assert result["status"] == "ACCEPTED_WITH_WARNINGS"
    assert result["warnings"][0]["code"] == "UNKNOWN_OPTIONAL_GATE"
    assert result["errors"] == []


def test_required_gate_false_rejected() -> None:
    private_key, public_key_hex = _keypair()
    validator = GateValidator({"key_01": public_key_hex})
    artifact = _signed_artifact({"data": 1}, private_key)

    result = validator.validate(artifact, {"known_required": lambda body: False})

    assert result["status"] == "REJECTED"
    assert _first_error_code(result) == "REQUIRED_GATE_FAILED"


def test_malformed_schema_rejected() -> None:
    validator = GateValidator({"key_01": "00" * 32})
    malformed = {
        "unsigned_body": {"data": 1},
        "signature": {"key_id": "key_01", "signature": "00" * 64},
        "gate_pipeline": [{"id": "known_required", "status": "MANDATORY"}],
    }

    result = validator.validate(malformed, {"known_required": lambda body: True})

    assert result["status"] == "REJECTED"
    assert _first_error_code(result) == "SCHEMA_BINDING_FAILURE"


def test_canonicalization_stability_same_hash_across_key_order_changes() -> None:
    private_key, public_key_hex = _keypair()
    validator = GateValidator({"key_01": public_key_hex})

    body_a = {"b": 2, "a": {"d": 4, "c": 3}}
    body_b = {"a": {"c": 3, "d": 4}, "b": 2}
    artifact_a = _signed_artifact(body_a, private_key)
    artifact_b = _signed_artifact(body_b, private_key)

    result_a = validator.validate(artifact_a, {"known_required": lambda body: True})
    result_b = validator.validate(artifact_b, {"known_required": lambda body: True})

    assert result_a["status"] == "ACCEPTED"
    assert result_b["status"] == "ACCEPTED"
    assert result_a["receipt"]["artifact_hash"] == result_b["receipt"]["artifact_hash"]
    assert GateValidator.canonicalize(body_a) == GateValidator.canonicalize(body_b)
