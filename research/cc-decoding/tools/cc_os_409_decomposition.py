#!/usr/bin/env python3
"""CC-OS 409 decomposition experiment.

This is deliberately a geometry-independent first pass. It tests whether the reported
aggregate count can support a balanced six-arm hierarchical address space before any
semantic interpretation is allowed.

Input:
  total circles (default 409)
  arm count (default 6)
  reported major/spine circles per arm (default 13)

Outputs a machine-readable candidate decomposition and falsification conditions.

The experiment does NOT establish that the physical formation has this structure.
It establishes only what exact arithmetic consequences follow if the measured inputs
are correct. Geometry must later decide whether the partition exists spatially.
"""

from __future__ import annotations
import argparse
import json
from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class Decomposition:
    total: int
    arms: int
    center_nodes: int
    nodes_per_arm: int
    spine_per_arm: int
    satellite_per_arm: int
    reconstructed_total: int
    balanced: bool


def decompose(total: int, arms: int, spine_per_arm: int, center_nodes: int = 1) -> Decomposition:
    remainder = total - center_nodes
    balanced = remainder >= 0 and remainder % arms == 0
    nodes_per_arm = remainder // arms if balanced else -1
    satellite_per_arm = nodes_per_arm - spine_per_arm if balanced else -1
    reconstructed = center_nodes + arms * (spine_per_arm + satellite_per_arm) if balanced else -1
    return Decomposition(
        total=total,
        arms=arms,
        center_nodes=center_nodes,
        nodes_per_arm=nodes_per_arm,
        spine_per_arm=spine_per_arm,
        satellite_per_arm=satellite_per_arm,
        reconstructed_total=reconstructed,
        balanced=balanced and satellite_per_arm >= 0,
    )


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--total", type=int, default=409)
    p.add_argument("--arms", type=int, default=6)
    p.add_argument("--spine-per-arm", type=int, default=13)
    p.add_argument("--center", type=int, default=1)
    args = p.parse_args()

    d = decompose(args.total, args.arms, args.spine_per_arm, args.center)

    receipt = {
        "schema": "CP8-CC-OS-EXPERIMENT-v1",
        "experiment_id": "409-OS-DECOMPOSITION-001",
        "status": "EXECUTED_EXPLORATORY_HOLD",
        "observed_inputs": {
            "reported_total_circles": args.total,
            "reported_arm_count": args.arms,
            "reported_spine_circles_per_arm": args.spine_per_arm,
            "center_nodes_assumed": args.center,
        },
        "derived_structure": asdict(d),
        "discovery": {
            "exact_balance": d.balanced,
            "equation": (
                f"{args.total} = {args.center} + {args.arms}*"
                f"({args.spine_per_arm} + {d.satellite_per_arm})"
                if d.balanced else None
            ),
            "residual_satellites_total": (
                args.total - args.center - args.arms * args.spine_per_arm
                if d.balanced else None
            ),
            "residual_satellites_factorization": (
                f"{args.arms}*{d.satellite_per_arm}" if d.balanced else None
            ),
        },
        "interpretation": {
            "candidate_os_address_space":
                "1 center node + 6 balanced arm modules; each module = 13 spine + 55 residual nodes"
                if d.balanced else None,
            "semantic_claim": False,
            "geometry_claim": False,
            "next_test":
                "Blindly segment the highest-resolution aerial source, assign every detected circle "
                "to one of six arm sectors, and test whether the 13/55 split is spatially real."
                if d.balanced else "Acquire corrected measurements.",
        },
        "falsifiers": [
            "Total count is not 409 after complete source reconstruction.",
            "Arm count is not six under blind geometry extraction.",
            "Per-arm node counts are materially unbalanced after perspective/terrain correction.",
            "A 13-circle spine cannot be independently recovered in each arm.",
            "The remaining nodes do not partition into approximately 55 per arm.",
        ],
        "promotion": "HOLD",
    }
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
