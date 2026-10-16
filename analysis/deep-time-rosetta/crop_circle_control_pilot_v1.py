#!/usr/bin/env python3
"""Reproduce the Deep-Time Rosetta crop-circle geometry control pilot v1.

This operates on archived metadata/reconstruction features, not raw imagery.
Origin labels are ignored until after the distance matrix is computed.
"""
from __future__ import annotations

import itertools
import json
import math
import pathlib
import statistics

ROOT = pathlib.Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "deep-time-rosetta" / "crop_circle_control_batch.v1.json"


def zscore_columns(rows):
    cols = list(zip(*rows))
    means = [statistics.mean(c) for c in cols]
    sds = [statistics.pstdev(c) for c in cols]
    return [
        [(v - m) / (sd if sd else 1.0) for v, m, sd in zip(row, means, sds)]
        for row in rows
    ]


def distance(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def matrix(rows):
    return [[distance(a, b) for b in rows] for a in rows]


def nearest_neighbors(d):
    out = []
    for i, row in enumerate(d):
        out.append(min((value, j) for j, value in enumerate(row) if i != j)[1])
    return out


def separation(d, labels):
    within, between = [], []
    for i in range(len(labels)):
        for j in range(i + 1, len(labels)):
            (within if labels[i] == labels[j] else between).append(d[i][j])
    return statistics.mean(between) - statistics.mean(within)


def exact_permutation_p(d, labels):
    human_n = sum(x == "HUMAN_MADE_CONFIRMED" for x in labels)
    observed = separation(d, labels)
    effects = []
    for human_idx in itertools.combinations(range(len(labels)), human_n):
        trial = ["ORIGIN_UNRESOLVED"] * len(labels)
        for i in human_idx:
            trial[i] = "HUMAN_MADE_CONFIRMED"
        effects.append(separation(d, trial))
    return sum(x >= observed - 1e-12 for x in effects) / len(effects)


def main():
    data = json.loads(DATA.read_text(encoding="utf-8"))
    rows = [
        x for x in data["controls"] + data["unresolved"]
        if "elements" in x and "span_ft" in x
    ]
    names = [x["name"] for x in rows]
    labels = [x["origin"] for x in rows]

    spec_a = [
        [math.log1p(x["elements"]), math.log1p(x["span_ft"]), x.get("symmetry_order", x.get("symmetry_order_pilot")), x["recursive_multiscale"]]
        for x in rows
    ]
    spec_b = [
        [math.log1p(x["elements"]), math.log1p(x["span_ft"]), x["recursive_multiscale"]]
        for x in rows
    ]

    da = matrix(zscore_columns(spec_a))
    db = matrix(zscore_columns(spec_b))
    nna = nearest_neighbors(da)
    nnb = nearest_neighbors(db)

    result = {
        "names": names,
        "nearest_neighbors_spec_a": {names[i]: names[j] for i, j in enumerate(nna)},
        "nearest_neighbors_spec_b": {names[i]: names[j] for i, j in enumerate(nnb)},
        "same_origin_nn_accuracy_spec_a": sum(labels[i] == labels[j] for i, j in enumerate(nna)) / len(labels),
        "same_origin_nn_accuracy_spec_b": sum(labels[i] == labels[j] for i, j in enumerate(nnb)) / len(labels),
        "permutation_p_spec_a": exact_permutation_p(da, labels),
        "permutation_p_spec_b": exact_permutation_p(db, labels),
        "closest_pair_spec_a": min((da[i][j], names[i], names[j]) for i in range(len(names)) for j in range(i + 1, len(names))),
        "closest_pair_spec_b": min((db[i][j], names[i], names[j]) for i in range(len(names)) for j in range(i + 1, len(names))),
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
