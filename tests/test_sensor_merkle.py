"""Tests for robotics/sensor_merkle.py — deterministic CSV Merkle proofs."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from robotics.sensor_merkle import (
    DEFAULT_PRECISION,
    SCHEMA,
    SensorMerkleError,
    inclusion_proof,
    leaf_hash,
    load_frames,
    main,
    merkle_root,
    process_csv,
    verify_inclusion_proof,
)

REPO = Path(__file__).resolve().parents[1]
SAMPLE = REPO / "robotics" / "samples" / "humanoid_sensor_log.sample.csv"
SAMPLE_JSON = REPO / "robotics" / "samples" / "humanoid_sensor_log_joints_json.sample.csv"


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]], comments: list[str] | None = None) -> Path:
    with path.open("w", encoding="utf-8", newline="") as handle:
        for line in comments or ["# SYNTHETIC TEST CSV — not real robot data."]:
            handle.write(line + "\n")
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return path


def test_same_csv_same_root() -> None:
    first, _, _ = process_csv(SAMPLE)
    second, _, _ = process_csv(SAMPLE)
    assert first["root"] == second["root"]
    assert first["n_frames"] == 16
    assert first["schema"] == SCHEMA
    assert first["input_digest"] == second["input_digest"]
    assert len(first["root"]) == 64


def test_column_order_does_not_change_root(tmp_path: Path) -> None:
    # Rebuild the sample with shuffled columns; root must stay the same.
    original, _, _ = process_csv(SAMPLE)
    # Read data rows through the loader's own comment-skipping by re-emitting.
    import robotics.sensor_merkle as sm

    fieldnames, rows, _ = sm.open_csv_records(SAMPLE)
    shuffled = list(reversed(fieldnames))
    out = tmp_path / "shuffled.csv"
    with out.open("w", encoding="utf-8", newline="") as handle:
        handle.write("# SYNTHETIC TEST CSV — column order permutation of the sample.\n")
        writer = csv.DictWriter(handle, fieldnames=shuffled)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    shuffled_receipt, _, _ = process_csv(out)
    assert shuffled_receipt["root"] == original["root"]
    assert shuffled_receipt["n_frames"] == original["n_frames"]
    # The raw file bytes changed, so the input digest must change.
    assert shuffled_receipt["input_digest"] != original["input_digest"]


def test_one_value_change_changes_root(tmp_path: Path) -> None:
    original, _, _ = process_csv(SAMPLE)
    import robotics.sensor_merkle as sm

    fieldnames, rows, _ = sm.open_csv_records(SAMPLE)
    rows[0]["joint_l_hip"] = "0.123456789"
    out = tmp_path / "changed.csv"
    with out.open("w", encoding="utf-8", newline="") as handle:
        handle.write("# SYNTHETIC TEST CSV — one joint value changed.\n")
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    changed, _, _ = process_csv(out)
    assert changed["root"] != original["root"]
    assert changed["n_frames"] == original["n_frames"]


def test_inclusion_proof_verify_true_and_false() -> None:
    receipt, frames, leaves = process_csv(SAMPLE, prove=[0, 7, 15])
    root = receipt["root"]
    for proof in receipt["proofs"]:
        idx = proof["index"]
        assert verify_inclusion_proof(frames[idx], proof, root) is True
        # Wrong root.
        assert verify_inclusion_proof(frames[idx], proof, "00" * 32) is False
        # Tampered sibling.
        bad = {
            "index": proof["index"],
            "leaf": proof["leaf"],
            "root": proof["root"],
            "siblings": [
                {**proof["siblings"][0], "hash": "11" * 32},
                *proof["siblings"][1:],
            ]
            if proof["siblings"]
            else proof["siblings"],
        }
        if proof["siblings"]:
            assert verify_inclusion_proof(frames[idx], bad, root) is False
        # Different frame claimed against this leaf.
        other = frames[(idx + 1) % len(frames)]
        if leaf_hash(other) != leaf_hash(frames[idx]):
            assert verify_inclusion_proof(other, proof, root) is False

    # Direct API: out-of-range index.
    with pytest.raises(SensorMerkleError):
        inclusion_proof(leaves, len(leaves))


def test_json_joint_and_column_joint_inputs() -> None:
    column_receipt, column_frames, _ = process_csv(SAMPLE, max_rows=4)
    json_receipt, json_frames, _ = process_csv(SAMPLE_JSON)
    assert json_receipt["n_frames"] == 4
    assert "joints" in json_frames[0]
    assert "joints" in column_frames[0]
    # Same keys and canon values for the shared groups, so roots match.
    assert json_frames[0]["joints"].keys() == column_frames[0]["joints"].keys()
    assert json_receipt["root"] == column_receipt["root"]
    # A JSON-only file must still produce a verifiable proof.
    proof = inclusion_proof(
        [leaf_hash(frame) for frame in json_frames],
        2,
    )
    assert verify_inclusion_proof(json_frames[2], proof, json_receipt["root"]) is True


def test_max_rows_cutoff(tmp_path: Path) -> None:
    full, _, _ = process_csv(SAMPLE)
    cut, cut_frames, _ = process_csv(SAMPLE, max_rows=4)
    assert cut["n_frames"] == 4
    assert len(cut_frames) == 4
    assert cut["root"] != full["root"]
    assert cut["load"]["max_rows"] == 4
    # First 4 rows written alone must match the cutoff root (frame_index 0..3).
    import robotics.sensor_merkle as sm

    fieldnames, rows, _ = sm.open_csv_records(SAMPLE)
    out = tmp_path / "first4.csv"
    with out.open("w", encoding="utf-8", newline="") as handle:
        handle.write("# SYNTHETIC TEST CSV — first four frames of the sample.\n")
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows[:4]:
            writer.writerow(row)
    first4, _, _ = process_csv(out)
    assert first4["root"] == cut["root"]
    assert first4["n_frames"] == 4
    # Input digests differ (different files), roots match.
    assert first4["input_digest"] != cut["input_digest"]


def test_strict_rejects_nan_and_skip_bad_drops_row(tmp_path: Path) -> None:
    path = tmp_path / "nan.csv"
    _write_csv(
        path,
        ["timestamp", "joint_l_hip", "accel_x"],
        [
            {"timestamp": "0.00", "joint_l_hip": "0.1", "accel_x": "0.0"},
            {"timestamp": "0.02", "joint_l_hip": "NaN", "accel_x": "0.0"},
            {"timestamp": "0.04", "joint_l_hip": "0.2", "accel_x": "0.0"},
        ],
    )
    with pytest.raises(SensorMerkleError, match="NaN"):
        load_frames(path, skip_bad=False)
    frames, meta = load_frames(path, skip_bad=True)
    assert len(frames) == 2
    assert meta["rows_skipped_bad"] == 1
    assert frames[0]["frame_index"] == 0
    assert frames[1]["frame_index"] == 1
    assert frames[1]["timestamp"] == "0.040000000"


def test_cli_writes_receipt_and_verify_roundtrip(tmp_path: Path) -> None:
    out = tmp_path / "receipt.json"
    code = main(
        [
            "--csv",
            str(SAMPLE),
            "--prove",
            "0",
            "--out",
            str(out),
        ]
    )
    assert code == 0
    receipt = json.loads(out.read_text(encoding="utf-8"))
    assert receipt["schema"] == SCHEMA
    assert receipt["n_frames"] == 16
    assert receipt["canon"]["float_precision"] == DEFAULT_PRECISION
    assert receipt["canon"]["odd_node"] == "duplicate_last"
    assert receipt["proofs"][0]["index"] == 0
    assert receipt["git_commit"] is not None
    assert len(receipt["input_digest"]) == 64
    verify_code = main(["--verify-receipt", str(out), "--csv", str(SAMPLE)])
    assert verify_code == 0


def test_missing_timestamp_errors(tmp_path: Path) -> None:
    path = tmp_path / "no_ts.csv"
    _write_csv(path, ["joint_l_hip"], [{"joint_l_hip": "0.1"}])
    with pytest.raises(SensorMerkleError, match="timestamp"):
        load_frames(path)


def test_odd_leaf_count_proof(tmp_path: Path) -> None:
    path = tmp_path / "odd.csv"
    rows = [
        {"timestamp": f"{i * 0.02:.2f}", "joint_l_hip": str(0.1 * i), "accel_x": "0.0"}
        for i in range(3)
    ]
    _write_csv(path, ["timestamp", "joint_l_hip", "accel_x"], rows)
    receipt, frames, leaves = process_csv(path, prove=[0, 1, 2])
    assert receipt["n_frames"] == 3
    # Three leaves: last is duplicated at the first level.
    assert merkle_root(leaves).hex() == receipt["root"]
    for proof in receipt["proofs"]:
        assert verify_inclusion_proof(frames[proof["index"]], proof, receipt["root"]) is True
