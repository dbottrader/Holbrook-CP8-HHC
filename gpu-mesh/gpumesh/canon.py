"""Canonical JSON hashing, ASIN-HHC canon v1.

Preimage is UTF-8 JSON with sorted keys, separators (`,`, `:`), and
``ensure_ascii=True``. The published ASIN-HHC receipt vectors lock this
function. Ledger timestamps are integer Unix milliseconds so a receipt
round-trips bit for bit.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

GENESIS_PREV = "0" * 64
CANON = "v1"
ALGORITHM = (
    "sha256 over JSON bytes with sort_keys=True, separators=(',',':'), ensure_ascii=True, utf-8"
)
HASHED_FIELDS = ("actor", "kind", "payload", "prev_hash", "seq", "ts")


def canon_dumps(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canon_sha256(obj: Any) -> str:
    return sha256_text(canon_dumps(obj))


def hash_secret(secret: str) -> str:
    return sha256_text(secret)


def output_hash(text: str) -> str:
    return sha256_text(text)
