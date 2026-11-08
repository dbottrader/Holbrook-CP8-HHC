"""Text comparison used by canaries and spot-checks.

Verified mesh jobs are deterministic. Agreement is exact text, then a
whitespace and Unicode normalization for CPU versus GPU float drift.
The rule that matched is returned with the verdict.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata

_EXACT = (
    re.compile(r"reply with exactly(?: the token)?[:\s]+(\S+)", re.IGNORECASE),
    re.compile(r"repeat only this string[:\s]+(\S+)", re.IGNORECASE),
)

# Sent on every volunteer request. Ollama's defaults (top_p 0.9, repeat_penalty
# 1.1) and a Modelfile num_ctx must not differ between hosts.
DET_TEMPERATURE = 0
DET_TOP_K = 1
DET_TOP_P = 1.0
DET_REPEAT_PENALTY = 1.0
DET_NUM_CTX = 2048


def normalize_text(text: str) -> str:
    return " ".join(text.lower().split())


def canon_answer(text: str) -> str:
    """Case- and whitespace-insensitive answer, with one layer of trailing punctuation removed."""
    return normalize_text(text).strip(".,!;:\"'`")


def mesh_seed(job_id: str) -> int:
    """Stable signed-32-bit seed for one job. The verifier copies this value."""

    digest = hashlib.sha256(f"gpumesh.seed.v1:{job_id}".encode()).digest()
    return int.from_bytes(digest[:4], "big") & 0x7FFFFFFF


def normalize_match(text: str) -> str:
    """NFKC plus one ASCII space between tokens. Case is left as written."""

    folded = unicodedata.normalize("NFKC", text)
    chars: list[str] = []
    for char in folded:
        if unicodedata.category(char) == "Zs" or char in "\t\r\n\f\v":
            chars.append(" ")
        else:
            chars.append(char)
    return re.sub(r" +", " ", "".join(chars)).strip()


def compare_outputs(parent_text: str, child_text: str) -> tuple[str, str]:
    """Return ``(verdict, match_rule)``.

    ``match_rule`` is ``exact``, ``normalized``, or empty when the texts disagree.
    """

    if not parent_text.strip():
        return "parent_empty", ""
    if not child_text.strip():
        return "child_empty", ""
    if parent_text == child_text:
        return "agree", "exact"
    if normalize_match(parent_text) == normalize_match(child_text):
        return "agree", "normalized"
    return "disagree_deterministic", ""


def exact_reply(messages: list[dict]) -> str | None:
    """If the prompt demands a single exact token, return that token. Otherwise None."""
    for message in messages:
        content = message.get("content")
        if not isinstance(content, str):
            continue
        for pattern in _EXACT:
            match = pattern.search(content)
            if match:
                return match.group(1).strip(".,!;:\"'`")
    return None


def flatten_content(content: object) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
                continue
            if not isinstance(part, dict):
                continue
            kind = part.get("type")
            if kind == "text":
                parts.append(str(part.get("text") or ""))
            elif kind in {"image_url", "input_image", "image"}:
                raise ValueError("image inputs are not supported")
        return "\n".join(parts)
    return str(content)


def judge_outputs(parent_text: str, child_text: str, parent_temperature: float, threshold: float) -> str:
    """Verdict only. Temperature and the old word-overlap threshold are not used.

    Verified jobs run at temperature 0. A mismatch is ``disagree_deterministic``.
    """

    del parent_temperature, threshold
    verdict, _rule = compare_outputs(parent_text, child_text)
    return verdict
