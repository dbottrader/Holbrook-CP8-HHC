"""Operational harmonic algebra for measurable HOS state correction.

The project frequency values are namespace labels. This module makes no claim
that they provide physical, medical, or cryptographic effects.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from typing import Iterable, Sequence

NAMESPACE_LABELS = {111: "chronal", 428: "core", 528: "fusion", 963: "integration"}


def delta_state(ideal: Sequence[float], actual: Sequence[float]) -> tuple[float, ...]:
    if len(ideal) != len(actual):
        raise ValueError("ideal and actual vectors must have equal length")
    return tuple(float(i) - float(a) for i, a in zip(ideal, actual))


def l2_norm(vector: Iterable[float]) -> float:
    return sqrt(sum(float(v) ** 2 for v in vector))


def harmonic_state(ideal: Sequence[float], actual: Sequence[float]) -> float:
    """Return E_HOS = 1 / (1 + ||ideal - actual||_2), in (0, 1]."""
    return 1.0 / (1.0 + l2_norm(delta_state(ideal, actual)))


def bounded_correction(
    ideal: Sequence[float],
    actual: Sequence[float],
    *,
    alpha: float = 1.0,
    bound: float = 1.0,
) -> tuple[float, ...]:
    if not 0.0 < alpha <= 1.0:
        raise ValueError("alpha must be in (0, 1]")
    if bound <= 0.0:
        raise ValueError("bound must be positive")
    delta = delta_state(ideal, actual)
    return tuple(
        float(a) + alpha * max(-bound, min(bound, d))
        for a, d in zip(actual, delta)
    )


@dataclass(frozen=True)
class HarmonicStateResult:
    namespace: int
    namespace_name: str
    ideal: tuple[float, ...]
    actual: tuple[float, ...]
    delta: tuple[float, ...]
    efficiency: float


def evaluate_state(
    ideal: Sequence[float], actual: Sequence[float], namespace: int = 428
) -> HarmonicStateResult:
    if namespace not in NAMESPACE_LABELS:
        raise ValueError(f"namespace must be one of {tuple(NAMESPACE_LABELS)}")
    ideal_t = tuple(map(float, ideal))
    actual_t = tuple(map(float, actual))
    delta = delta_state(ideal_t, actual_t)
    return HarmonicStateResult(
        namespace=namespace,
        namespace_name=NAMESPACE_LABELS[namespace],
        ideal=ideal_t,
        actual=actual_t,
        delta=delta,
        efficiency=1.0 / (1.0 + l2_norm(delta)),
    )
