"""CP8 receipt generation for runtime outputs."""

from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
import hashlib
import json


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_json(value):
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


@dataclass
class CP8Receipt:
    envelope_id: str
    runtime: str
    output_hash: str
    model_id: str | None = None
    status: str = "completed"
    metadata: dict = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @classmethod
    def from_output(cls, envelope_id, output, runtime="xybrid", model_id=None, metadata=None):
        return cls(
            envelope_id=envelope_id,
            runtime=runtime,
            output_hash=sha256_json(output),
            model_id=model_id,
            metadata=metadata or {},
        )

    def sealed(self):
        value = asdict(self)
        return {**value, "receipt_hash": sha256_json(value)}
