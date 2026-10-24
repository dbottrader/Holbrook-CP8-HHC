"""TOPLOC proofs. The polynomial math is Prime Intellect's library (MIT).

CPU-fallback jobs have no transformer activations. For those, both the node
and the coordinator build the same deterministic bfloat16 trace from the
canonical prompt and model id, then call ``toploc.build_proofs_base64`` /
``toploc.verify_proofs_base64``. That binds the job to the prompt. It does
not claim a neural net ran.

A hidden-state proof is the real check: the node commits last-layer
activations and the coordinator verifies that proof against the activations
a second node recomputed. Thresholds follow the paper: any exponent mismatch,
or a mantissa error above 1, rejects the proof.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

DECODE_BATCHING_SIZE = 3
TOPK = 4
_PREFILL = 4 * 16
_DECODE_STEPS = 6


def library_ready() -> bool:
    try:
        import toploc  # noqa: F401
        import torch  # noqa: F401

        return True
    except Exception:
        return False


def prompt_activations(messages: list, model: str) -> list:
    """Deterministic trace shared by the node and the coordinator.

    The sample is a seeded normal draw, not raw hash bits. TOPLOC's polynomial
    rejects many raw bfloat16 bit patterns (NaNs and ties). A normal sample
    still changes when the prompt or model id changes, and both sides rebuild
    it, so a proof only verifies for the prompt it was built from.
    """
    import torch

    # Same canonical JSON as gpumesh.canon.canon_dumps. Kept here so the node
    # image, which does not install the coordinator package, still matches.
    material = json.dumps(
        {"messages": messages, "model": model},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    digest = hashlib.sha256(material).digest()
    seed = int.from_bytes(digest[:8], "little") % (2**31 - 1)
    generator = torch.Generator()
    generator.manual_seed(seed)
    prefill = torch.randn(_PREFILL // 16, 16, generator=generator).to(torch.bfloat16).contiguous()
    steps = [
        torch.randn(16, generator=generator).to(torch.bfloat16).contiguous()
        for _ in range(_DECODE_STEPS)
    ]
    return [prefill, *steps]


def hidden_activations(rows: list) -> list:
    """Rows are lists of floats from a checker that reran the model."""
    import torch

    if not isinstance(rows, list) or not rows or len(rows) > 64:
        raise ValueError("activations must be 1 to 64 tensors")
    tensors = []
    for row in rows:
        if not isinstance(row, list) or not row or len(row) > 4096:
            raise ValueError("each activation row must be 1 to 4096 floats")
        tensors.append(torch.tensor([float(item) for item in row], dtype=torch.bfloat16))
    return tensors


def build_proofs(activations: list) -> list[str]:
    from toploc import build_proofs_base64

    return build_proofs_base64(
        activations,
        decode_batching_size=DECODE_BATCHING_SIZE,
        topk=TOPK,
        skip_prefill=False,
    )


def build_prompt_proofs(messages: list, model: str) -> list[str] | None:
    if not library_ready():
        return None
    return build_proofs(prompt_activations(messages, model))


def _accepted(result: Any) -> bool:
    mismatches = getattr(result, "exp_mismatches", None)
    if mismatches is None:
        mismatches = TOPK - int(getattr(result, "exp_intersections", 0))
    mean = float(getattr(result, "mant_err_mean", 2**32))
    median = float(getattr(result, "mant_err_median", 2**32))
    return int(mismatches) == 0 and mean <= 1 and median <= 1


def verify_activations(activations: list, proofs: list[str]) -> dict[str, Any]:
    from toploc import verify_proofs_base64

    if not proofs:
        return {"ok": False, "reason": "missing proof", "batches": 0}
    results = verify_proofs_base64(
        activations,
        proofs,
        decode_batching_size=DECODE_BATCHING_SIZE,
        topk=TOPK,
        skip_prefill=False,
    )
    ok = bool(results) and all(_accepted(item) for item in results)
    return {
        "ok": ok,
        "batches": len(results),
        "exp_mismatches": [int(getattr(item, "exp_mismatches", -1)) for item in results],
        "mant_err_mean": [float(getattr(item, "mant_err_mean", -1)) for item in results],
    }


def verify_prompt_proofs(messages: list, model: str, proofs: list[str]) -> dict[str, Any]:
    if not library_ready():
        return {"ok": False, "reason": "toploc is not installed", "batches": 0}
    try:
        report = verify_activations(prompt_activations(messages, model), proofs)
    except Exception as exc:
        return {"ok": False, "reason": str(exc)[:200], "batches": 0}
    report["source"] = "prompt-trace"
    return report


def verify_hidden_proofs(rows: list, proofs: list[str]) -> dict[str, Any]:
    if not library_ready():
        return {"ok": False, "reason": "toploc is not installed", "batches": 0}
    try:
        report = verify_activations(hidden_activations(rows), proofs)
    except Exception as exc:
        return {"ok": False, "reason": str(exc)[:200], "batches": 0}
    report["source"] = "hidden-state"
    return report
