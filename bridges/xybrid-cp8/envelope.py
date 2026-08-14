"""Holbrook CP8 runtime envelope.

Original integration code for transporting CP8 provenance metadata to a local model
runtime such as Xybrid. SHA-256 is the integrity primitive.
"""

from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
import hashlib
import json
import uuid

HOS_GROUND_TRUTH = "63b5160ef51f0464295e86888c3e6605d8f6cc970635183887083818e8749320"
PROTOCOL = "ASH-0.2"


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_json(value):
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


@dataclass
class CP8Envelope:
    payload: dict
    capability: str
    scopes: list[str]
    model_id: str | None = None
    metadata: dict = field(default_factory=dict)
    provenance: dict = field(default_factory=dict)
    envelope_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    protocol: str = PROTOCOL
    hos_ground_truth: str = HOS_GROUND_TRUTH
    seal: str | None = None

    def unsigned(self):
        value = asdict(self)
        value.pop("seal", None)
        return value

    def sign(self):
        self.seal = sha256_json(self.unsigned())
        return self

    def verify_integrity(self):
        return self.seal == sha256_json(self.unsigned()) if self.seal else False

    def capability_allowed(self):
        return self.capability in self.scopes or "*" in self.scopes

    def valid(self):
        return self.verify_integrity() and self.capability_allowed()

    def runtime_packet(self):
        if not self.valid():
            raise ValueError("CP8 envelope failed integrity or scope validation")
        return {
            "model_id": self.model_id,
            "input": self.payload,
            "metadata": {
                **self.metadata,
                "cp8": {
                    "envelope_id": self.envelope_id,
                    "protocol": self.protocol,
                    "hos_ground_truth": self.hos_ground_truth,
                    "capability": self.capability,
                    "provenance": self.provenance,
                    "seal": self.seal,
                },
            },
        }


def text_envelope(text, model_id=None, capability="model.run", scopes=None, metadata=None):
    return CP8Envelope(
        payload={"type": "text", "text": text},
        capability=capability,
        scopes=scopes or [capability],
        model_id=model_id,
        metadata=metadata or {},
    ).sign()
