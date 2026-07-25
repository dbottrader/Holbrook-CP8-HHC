"""ASIN-HHC-CP8 HOS reference runtime.

Turns an Anchor/Shape/Intention/Number packet into a canonical, hash-sealed
receipt. Frequency values are namespace labels; they do not increase
cryptographic strength.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Iterable

ROOMS = ("Vault", "Resonance", "Workshop", "Bridge", "Expansion", "Archive")
ALLOWED_NUMBERS = (111, 428, 528, 963)


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_hex(value: Any) -> str:
    payload = value if isinstance(value, str) else canonical_json(value)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ASINPacket:
    anchor: str
    shape: str
    intention: str
    number: int = 428
    rooms: tuple[str, ...] = ("Vault", "Resonance", "Workshop", "Bridge")
    evidence_tier: str = "E0"

    def validate(self) -> None:
        for field_name in ("anchor", "shape", "intention"):
            if not getattr(self, field_name).strip():
                raise ValueError(f"{field_name} must not be empty")
        if self.number not in ALLOWED_NUMBERS:
            raise ValueError(f"number must be one of {ALLOWED_NUMBERS}")
        if not self.rooms:
            raise ValueError("at least one room is required")
        unknown = [room for room in self.rooms if room not in ROOMS]
        if unknown:
            raise ValueError(f"unknown room(s): {unknown}")


@dataclass(frozen=True)
class HOSReceipt:
    receipt_id: str
    created_at: str
    packet: dict[str, Any]
    packet_sha256: str
    actions: tuple[str, ...]
    checks: dict[str, Any]
    authority: str = "USER_REVIEW_REQUIRED"
    runtime_claim: str = "REFERENCE_IMPLEMENTATION"


def process_packet(packet: ASINPacket, actions: Iterable[str] = ()) -> HOSReceipt:
    packet.validate()
    packet_dict = asdict(packet)
    packet_hash = sha256_hex(packet_dict)
    action_tuple = tuple(a.strip() for a in actions if a and a.strip())
    return HOSReceipt(
        receipt_id=f"hos-{packet_hash[:16]}",
        created_at=datetime.now(timezone.utc).isoformat(),
        packet=packet_dict,
        packet_sha256=packet_hash,
        actions=action_tuple,
        checks={
            "canonical_serialization": "PASS",
            "sha256": "PASS",
            "rooms_valid": True,
            "number_namespace": packet.number,
            "evidence_tier": packet.evidence_tier,
            "promotion_allowed": False,
            "review_required": True,
        },
    )


def verify_receipt(receipt: HOSReceipt) -> bool:
    return sha256_hex(receipt.packet) == receipt.packet_sha256
