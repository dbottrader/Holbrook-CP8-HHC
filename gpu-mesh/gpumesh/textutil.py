"""Text normalization used by canaries and spot-checks."""

from __future__ import annotations

import difflib
import re

_EXACT = (
    re.compile(r"reply with exactly(?: the token)?[:\s]+(\S+)", re.IGNORECASE),
    re.compile(r"repeat only this string[:\s]+(\S+)", re.IGNORECASE),
)


def normalize_text(text: str) -> str:
    return " ".join(text.lower().split())


def canon_answer(text: str) -> str:
    """Case- and whitespace-insensitive answer, with one layer of trailing punctuation removed."""
    return normalize_text(text).strip(".,!;:\"'`")


def similarity(a: str, b: str) -> float:
    left, right = normalize_text(a), normalize_text(b)
    if left == right:
        return 1.0
    if not left or not right:
        return 0.0
    return difflib.SequenceMatcher(None, left, right).ratio()


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
    if not parent_text.strip():
        return "parent_empty"
    if not child_text.strip():
        return "child_empty"
    if similarity(parent_text, child_text) >= threshold:
        return "agree"
    if parent_temperature <= 0.0:
        return "disagree_deterministic"
    return "disagree_sampling"
