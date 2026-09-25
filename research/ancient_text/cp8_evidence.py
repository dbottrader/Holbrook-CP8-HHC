"""CP8 evidence fusion for ancient-text restoration benchmarks.

Input is JSONL. Each row must contain:
{
  "id": "sample-1",
  "truth": "Α",
  "candidates": [
    {
      "text": "Α",
      "channels": {
        "model": 0.91,
        "geometry": 0.88,
        "agreement": 0.83,
        "lexical": 0.79,
        "parallel": 0.67,
        "provenance": 1.0
      }
    }
  ]
}

The engine is deliberately model-agnostic. Adapters should transform Ithaca,
Aeneas, Vesuvius, or other outputs into this schema.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


DEFAULT_WEIGHTS = {
    "model": 1.0,
    "geometry": 1.0,
    "agreement": 1.0,
    "lexical": 0.8,
    "parallel": 0.7,
    "provenance": 0.8,
}


@dataclass
class Decision:
    sample_id: str
    prediction: str | None
    confidence: float
    state: str
    alternatives: List[Tuple[str, float]]
    correct: bool | None


def _clip(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def fuse_channels(channels: Dict[str, float], weights: Dict[str, float]) -> float:
    """Weighted geometric mean.

    Geometric fusion is intentionally punitive: one weak independent channel
    can lower confidence instead of being hidden by several strong channels.
    Missing channels are ignored rather than fabricated.
    """
    terms = []
    total_w = 0.0
    for name, value in channels.items():
        if name not in weights:
            continue
        w = float(weights[name])
        if w <= 0:
            continue
        p = max(1e-6, _clip(value))
        terms.append(w * math.log(p))
        total_w += w
    if not terms or total_w == 0:
        return 0.0
    return float(math.exp(sum(terms) / total_w))


def independent_channel_count(channels: Dict[str, float], floor: float = 0.5) -> int:
    return sum(1 for v in channels.values() if _clip(v) >= floor)


def decide_sample(
    row: dict,
    threshold: float,
    min_channels: int,
    weights: Dict[str, float],
) -> Decision:
    scored = []
    for c in row.get("candidates", []):
        score = fuse_channels(c.get("channels", {}), weights)
        nchan = independent_channel_count(c.get("channels", {}))
        scored.append((c.get("text", ""), score, nchan))

    scored.sort(key=lambda x: x[1], reverse=True)
    if not scored:
        return Decision(row.get("id", ""), None, 0.0, "HOLD", [], None)

    best_text, best_score, best_nchan = scored[0]
    state = "PROMOTE" if best_score >= threshold and best_nchan >= min_channels else "HOLD"
    pred = best_text if state == "PROMOTE" else None
    truth = row.get("truth")
    correct = None if truth is None or pred is None else pred == truth
    alternatives = [(text, score) for text, score, _ in scored[1:4]]
    return Decision(row.get("id", ""), pred, best_score, state, alternatives, correct)


def brier(decisions: Iterable[Decision]) -> float | None:
    vals = []
    for d in decisions:
        if d.correct is None or d.state != "PROMOTE":
            continue
        y = 1.0 if d.correct else 0.0
        vals.append((d.confidence - y) ** 2)
    return sum(vals) / len(vals) if vals else None


def expected_calibration_error(decisions: Iterable[Decision], bins: int = 10) -> float | None:
    promoted = [d for d in decisions if d.state == "PROMOTE" and d.correct is not None]
    if not promoted:
        return None
    total = len(promoted)
    ece = 0.0
    for i in range(bins):
        lo, hi = i / bins, (i + 1) / bins
        bucket = [d for d in promoted if lo <= d.confidence <= hi if (i == bins - 1) else lo <= d.confidence < hi]
        if not bucket:
            continue
        acc = sum(1.0 if d.correct else 0.0 for d in bucket) / len(bucket)
        conf = sum(d.confidence for d in bucket) / len(bucket)
        ece += (len(bucket) / total) * abs(acc - conf)
    return ece


def summarize(decisions: List[Decision]) -> dict:
    n = len(decisions)
    promoted = [d for d in decisions if d.state == "PROMOTE"]
    held = n - len(promoted)
    labeled_promoted = [d for d in promoted if d.correct is not None]
    correct = sum(1 for d in labeled_promoted if d.correct)
    wrong = sum(1 for d in labeled_promoted if d.correct is False)

    return {
        "samples": n,
        "promoted": len(promoted),
        "held": held,
        "coverage": len(promoted) / n if n else 0.0,
        "promoted_precision": correct / len(labeled_promoted) if labeled_promoted else None,
        "promoted_errors": wrong,
        "brier": brier(decisions),
        "ece": expected_calibration_error(decisions),
        "decisions": [
            {
                "id": d.sample_id,
                "prediction": d.prediction,
                "confidence": round(d.confidence, 6),
                "state": d.state,
                "alternatives": [[t, round(s, 6)] for t, s in d.alternatives],
                "correct": d.correct,
            }
            for d in decisions
        ],
    }


def load_jsonl(path: Path) -> List[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=Path)
    ap.add_argument("--threshold", type=float, default=0.72)
    ap.add_argument("--min-channels", type=int, default=3)
    ap.add_argument("--output", type=Path)
    args = ap.parse_args()

    rows = load_jsonl(args.input)
    decisions = [
        decide_sample(row, args.threshold, args.min_channels, DEFAULT_WEIGHTS)
        for row in rows
    ]
    report = summarize(decisions)
    text = json.dumps(report, indent=2, ensure_ascii=False)
    if args.output:
        args.output.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)


if __name__ == "__main__":
    main()
