"""DAR-P deterministic gate validator.

This module implements the runtime-side closure rule for DAR-P artifacts:
cryptographic identity and gate execution are deterministic runtime duties;
LLMs may only interpret a frozen result after this validator has completed.

The important signing invariant is non-circular canonicalization:
the Ed25519 signature is verified over the canonical bytes of ``unsigned_body``
only. The signature block itself is extracted and never included in the
message being verified.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
from enum import Enum
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple, Union

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from pydantic import BaseModel, Field, ValidationError
from typing_extensions import Literal


GateCallable = Callable[[Dict[str, Any]], Union[bool, Mapping[str, Any]]]
PublicKeyValue = Union[str, bytes, Ed25519PublicKey, Mapping[str, Any]]


class ValidationStatus(str, Enum):
    ACCEPTED = "ACCEPTED"
    ACCEPTED_WITH_WARNINGS = "ACCEPTED_WITH_WARNINGS"
    REJECTED = "REJECTED"


class GateStatus(str, Enum):
    REQUIRED = "REQUIRED"
    OPTIONAL = "OPTIONAL"


class GateConfig(BaseModel):
    """One gate declaration in an artifact pipeline."""

    id: str = Field(..., min_length=1)
    status: GateStatus

    class Config:
        extra = "forbid"


class SignatureBlock(BaseModel):
    """Detached Ed25519 signature metadata.

    ``canonical_signing_data`` is informational only when present. Verification
    always recomputes canonical bytes from ``unsigned_body`` so callers cannot
    smuggle alternate signing bytes through the signature block.
    """

    key_id: str = Field(..., min_length=1)
    signature: str = Field(..., min_length=1)
    algorithm: Literal["Ed25519"] = "Ed25519"
    encoding: Literal["hex", "base64"] = "hex"
    canonical_signing_data: Optional[str] = None

    class Config:
        extra = "forbid"


class Artifact(BaseModel):
    """DAR-P artifact envelope.

    Only ``unsigned_body`` is signed. ``signature`` and ``gate_pipeline`` are
    envelope metadata used by the deterministic wrapper.
    """

    unsigned_body: Dict[str, Any]
    signature: SignatureBlock
    gate_pipeline: List[GateConfig]

    class Config:
        extra = "forbid"


class GateValidator:
    """Validate DAR-P artifacts with deterministic, fail-closed semantics.

    Execution order:
      1. Validate artifact schema with Pydantic.
      2. Extract the detached signature block.
      3. Canonicalize ``unsigned_body`` without the signature field.
      4. Verify Ed25519 over the canonical bytes.
      5. Execute REQUIRED/OPTIONAL gates.
      6. Emit a receipt over the validation result and artifact hash.
    """

    def __init__(self, key_registry: Mapping[str, PublicKeyValue]):
        self.key_registry = key_registry

    @staticmethod
    def canonicalize(data: Any) -> bytes:
        """Return deterministic JSON bytes for signing and receipts.

        This uses the strict JSON subset needed by DAR-P tests: sorted keys,
        compact separators, UTF-8 bytes, and no NaN/Infinity values. It is the
        canonicalization boundary used by both signing and verification.
        """

        return json.dumps(
            data,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")

    def validate(
        self,
        raw_data: Mapping[str, Any],
        gate_registry: Mapping[str, GateCallable],
    ) -> Dict[str, Any]:
        """Validate one DAR-P artifact and return a deterministic result."""

        artifact_hash: Optional[str] = None
        gate_results: List[Dict[str, Any]] = []
        warnings: List[Dict[str, str]] = []
        errors: List[Dict[str, str]] = []

        try:
            artifact = Artifact(**raw_data)
        except ValidationError as exc:
            errors.append(
                {
                    "code": "SCHEMA_BINDING_FAILURE",
                    "message": "Artifact failed Pydantic schema validation.",
                    "detail": exc.errors()[0].get("msg", str(exc)),
                }
            )
            return self._result(
                status=ValidationStatus.REJECTED,
                artifact_hash=artifact_hash,
                warnings=warnings,
                errors=errors,
                gate_results=gate_results,
            )

        body_bytes = self.canonicalize(artifact.unsigned_body)
        artifact_hash = hashlib.sha256(body_bytes).hexdigest()

        signature_ok, signature_error = self._verify_ed25519(
            artifact.signature,
            body_bytes,
        )
        if not signature_ok:
            errors.append(signature_error)
            return self._result(
                status=ValidationStatus.REJECTED,
                artifact_hash=artifact_hash,
                warnings=warnings,
                errors=errors,
                gate_results=gate_results,
            )

        for gate_cfg in artifact.gate_pipeline:
            gate = gate_registry.get(gate_cfg.id)

            if gate is None:
                if gate_cfg.status is GateStatus.REQUIRED:
                    errors.append(
                        {
                            "code": "UNKNOWN_REQUIRED_GATE",
                            "message": f"Required gate is not registered: {gate_cfg.id}",
                        }
                    )
                    gate_results.append(
                        {
                            "id": gate_cfg.id,
                            "status": gate_cfg.status.value,
                            "passed": False,
                            "known": False,
                        }
                    )
                    return self._result(
                        status=ValidationStatus.REJECTED,
                        artifact_hash=artifact_hash,
                        warnings=warnings,
                        errors=errors,
                        gate_results=gate_results,
                    )

                warnings.append(
                    {
                        "code": "UNKNOWN_OPTIONAL_GATE",
                        "message": f"Optional gate is not registered: {gate_cfg.id}",
                    }
                )
                gate_results.append(
                    {
                        "id": gate_cfg.id,
                        "status": gate_cfg.status.value,
                        "passed": None,
                        "known": False,
                    }
                )
                continue

            passed, detail = self._run_gate(gate, artifact.unsigned_body)
            gate_results.append(
                {
                    "id": gate_cfg.id,
                    "status": gate_cfg.status.value,
                    "passed": passed,
                    "known": True,
                    "detail": detail,
                }
            )

            if not passed and gate_cfg.status is GateStatus.REQUIRED:
                errors.append(
                    {
                        "code": "REQUIRED_GATE_FAILED",
                        "message": f"Required gate failed: {gate_cfg.id}",
                    }
                )
                return self._result(
                    status=ValidationStatus.REJECTED,
                    artifact_hash=artifact_hash,
                    warnings=warnings,
                    errors=errors,
                    gate_results=gate_results,
                )

            if not passed and gate_cfg.status is GateStatus.OPTIONAL:
                warnings.append(
                    {
                        "code": "OPTIONAL_GATE_FAILED",
                        "message": f"Optional gate failed: {gate_cfg.id}",
                    }
                )

        status = (
            ValidationStatus.ACCEPTED_WITH_WARNINGS
            if warnings
            else ValidationStatus.ACCEPTED
        )
        return self._result(
            status=status,
            artifact_hash=artifact_hash,
            warnings=warnings,
            errors=errors,
            gate_results=gate_results,
        )

    def _verify_ed25519(
        self,
        sig_block: SignatureBlock,
        data: bytes,
    ) -> Tuple[bool, Dict[str, str]]:
        key_material = self.key_registry.get(sig_block.key_id)
        if key_material is None:
            return False, {
                "code": "KEY_NOT_FOUND",
                "message": f"No public key registered for key_id: {sig_block.key_id}",
            }

        try:
            public_key = self._load_public_key(key_material)
            signature = self._decode_signature(sig_block.signature, sig_block.encoding)
            public_key.verify(signature, data)
        except InvalidSignature:
            return False, {
                "code": "SIGNATURE_INVALID",
                "message": "Ed25519 signature verification failed.",
            }
        except (ValueError, TypeError, binascii.Error) as exc:
            return False, {
                "code": "SIGNATURE_VERIFICATION_ERROR",
                "message": str(exc),
            }

        return True, {}

    @staticmethod
    def _decode_signature(signature: str, encoding: str) -> bytes:
        if encoding == "hex":
            return bytes.fromhex(signature)
        if encoding == "base64":
            return base64.b64decode(signature, validate=True)
        raise ValueError(f"Unsupported signature encoding: {encoding}")

    @staticmethod
    def _load_public_key(value: PublicKeyValue) -> Ed25519PublicKey:
        if isinstance(value, Ed25519PublicKey):
            return value

        if isinstance(value, bytes):
            return Ed25519PublicKey.from_public_bytes(value)

        if isinstance(value, Mapping):
            raw = value.get("public_key")
            encoding = value.get("encoding", "hex")
            if not isinstance(raw, str):
                raise ValueError("Public key mapping must include string field 'public_key'.")
            if encoding == "hex":
                return Ed25519PublicKey.from_public_bytes(bytes.fromhex(raw))
            if encoding == "base64":
                return Ed25519PublicKey.from_public_bytes(base64.b64decode(raw, validate=True))
            raise ValueError(f"Unsupported public key encoding: {encoding}")

        if isinstance(value, str):
            raw = value
            if raw.startswith("hex:"):
                return Ed25519PublicKey.from_public_bytes(bytes.fromhex(raw[4:]))
            if raw.startswith("base64:"):
                return Ed25519PublicKey.from_public_bytes(base64.b64decode(raw[7:], validate=True))

            try:
                return Ed25519PublicKey.from_public_bytes(bytes.fromhex(raw))
            except ValueError:
                return Ed25519PublicKey.from_public_bytes(base64.b64decode(raw, validate=True))

        raise TypeError(f"Unsupported public key type: {type(value)!r}")

    @staticmethod
    def _run_gate(
        gate: GateCallable,
        unsigned_body: Dict[str, Any],
    ) -> Tuple[bool, Optional[Any]]:
        result = gate(unsigned_body)
        if isinstance(result, Mapping):
            return bool(result.get("passed", False)), result
        return bool(result), None

    def _result(
        self,
        *,
        status: ValidationStatus,
        artifact_hash: Optional[str],
        warnings: List[Dict[str, str]],
        errors: List[Dict[str, str]],
        gate_results: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        validation_summary = {
            "status": status.value,
            "artifact_hash": artifact_hash,
            "warnings": warnings,
            "errors": errors,
            "gate_results": gate_results,
        }
        receipt_hash = hashlib.sha256(self.canonicalize(validation_summary)).hexdigest()
        receipt = {
            "protocol": "DAR-P",
            "receipt_version": "1.0",
            "artifact_hash": artifact_hash,
            "validation_hash": receipt_hash,
            "status": status.value,
        }
        return {
            "status": status.value,
            "warnings": warnings,
            "errors": errors,
            "gate_results": gate_results,
            "receipt": receipt,
        }
