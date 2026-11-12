#!/usr/bin/env python3
"""CP8 sensor Merkle proofs for humanoid robot sensor logs.

Load a CSV of timestamped frames (joint positions, IMU, torque, and other
numeric channels), canonicalize each frame, and commit the batch to a
SHA-256 Merkle tree. Inclusion proofs can be generated and checked for any
frame index. Replay is independent: the same file and canon parameters must
produce the same root.

Usage:
    python robotics/sensor_merkle.py --csv path/to/log.csv
    python robotics/sensor_merkle.py --csv path/to/log.csv --max-rows 100
    python robotics/sensor_merkle.py --csv path/to/log.csv --prove 0 --out receipt.json
    python robotics/sensor_merkle.py --csv path/to/log.csv --skip-bad
    python robotics/sensor_merkle.py --verify-receipt receipt.json

CSV shape
    A timestamp column is required (timestamp, time, ts, t, time_s, time_ms,
    time_us, frame_time, t_sec, or sec). Joint positions may be separate
    columns (joint_*, q_*) or a JSON object/array column (joints,
    joint_positions, joint_pos, q, q_json, positions). IMU may be imu_*,
    accel_*/acc_*, gyro_*/gyr_*, quat_*, orientation_*, angvel_*/angular_*,
    or a JSON column named imu / imu_json. Torque may be torque_*, tau_*,
    effort_*, or a JSON column named torque / torques / tau / effort.
    Remaining columns go under "other". Lines that start with '#' are
    comments and are ignored, so a sample file can be labelled synthetic.

Canon
    Keys are sorted. Floats become fixed-precision decimal strings (default
    9 places, half-even). Integers stay JSON integers. Compact JSON is
    json.dumps(..., sort_keys=True, separators=(',', ':'), ensure_ascii=True)
    encoded as UTF-8. NaN and Infinity are rejected (the row errors in
    --strict, or is dropped with --skip-bad).

Merkle
    Leaf  = SHA-256(0x00 || canonical_frame_utf8)
    Node  = SHA-256(0x01 || left || right)
    Odd-node rule (Bitcoin / gpu-mesh style): if a level has an odd number
    of nodes, the last node is duplicated before pairwise hashing.

    This is deliberately stronger than the two existing helpers in this
    repo. gpu-mesh/gpumesh/merkle.py hashes raw digest concatenation with
    no domain-separation prefixes. scripts/build-merkle.py hashes the UTF-8
    concatenation of hex strings. Prefixes here follow RFC 6962 so a leaf
    cannot be confused with an internal node. The receipt records the
    prefixes and the odd-node rule so a verifier does not have to guess.

Receipt schema
    cp8.sensor_merkle.v1 — input_digest (SHA-256 of the raw CSV bytes),
    canon parameters, root, n_frames, tool version, and git commit. The
    Merkle root does not include the git commit or tool version; those are
    provenance for the producer, not inputs to the hash.

Physical-State Bridge
    The robotics docs describe the protocol as: hash each frame, commit
    the batch to a Merkle tree, and store the root so a third party can
    replay the original log. There is no module in this repo named
    "Physical-State Bridge". This tool is the concrete implementation of
    that receipt/replay path for sensor logs. See robotics/README.md for
    how the root can be referenced from a manifest, and what is not yet
    wired to CP8Oracle / Settlement / HOS.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import subprocess
import sys
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping, Sequence, TextIO

SCHEMA = "cp8.sensor_merkle.v1"
TOOL_NAME = "sensor_merkle.py"
TOOL_VERSION = "1.0.0"
DEFAULT_PRECISION = 9
LEAF_PREFIX = b"\x00"
NODE_PREFIX = b"\x01"
ODD_NODE_RULE = "duplicate_last"

TIMESTAMP_NAMES = frozenset(
    {
        "timestamp",
        "time",
        "ts",
        "t",
        "time_s",
        "time_ms",
        "time_us",
        "frame_time",
        "t_sec",
        "sec",
    }
)
JOINT_JSON_NAMES = frozenset(
    {"joints", "joint_positions", "joint_pos", "q", "q_json", "positions"}
)
IMU_JSON_NAMES = frozenset({"imu", "imu_json"})
TORQUE_JSON_NAMES = frozenset({"torque", "torques", "tau", "effort"})

JOINT_PREFIXES = ("joint_", "q_")
IMU_PREFIXES = (
    "imu_",
    "accel_",
    "acc_",
    "gyro_",
    "gyr_",
    "quat_",
    "orientation_",
    "angvel_",
    "angular_",
)
TORQUE_PREFIXES = ("torque_", "tau_", "effort_")

# acc_ would also match accel_ if we checked it first; longest prefix is
# only used for documentation. Classification uses startswith on any prefix.


class SensorMerkleError(ValueError):
    """User-facing input or verification error."""


def _sha(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_integer_literal(text: str) -> bool:
    return re.fullmatch(r"[+-]?\d+", text) is not None


def format_number(value: Any, precision: int) -> int | str:
    """Canonical number: JSON int, or a fixed-precision decimal string.

    NaN and Infinity are rejected. Decimal text from the CSV is parsed as
    decimal, not binary float, so '0.1' does not become a binary
    approximation before rounding.
    """
    if isinstance(value, bool):
        # bool is a subclass of int; keep it out of the integer path.
        raise SensorMerkleError("boolean is not a sensor numeric value")
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            raise SensorMerkleError("NaN and Infinity are not allowed")
        text = format(value, ".16g")
        try:
            decimal_value = Decimal(text)
        except InvalidOperation as exc:
            raise SensorMerkleError(f"invalid number: {value!r}") from exc
    elif isinstance(value, str):
        text = value.strip()
        if text.lower() in {"nan", "+nan", "-nan", "inf", "+inf", "-inf", "infinity", "+infinity", "-infinity"}:
            raise SensorMerkleError(f"NaN and Infinity are not allowed: {value!r}")
        if _is_integer_literal(text):
            return int(text)
        try:
            decimal_value = Decimal(text)
        except InvalidOperation as exc:
            raise SensorMerkleError(f"invalid number: {value!r}") from exc
        if not decimal_value.is_finite():
            raise SensorMerkleError(f"NaN and Infinity are not allowed: {value!r}")
    elif isinstance(value, Decimal):
        if not value.is_finite():
            raise SensorMerkleError("NaN and Infinity are not allowed")
        decimal_value = value
    else:
        raise SensorMerkleError(f"unsupported numeric type: {type(value).__name__}")

    quantizer = Decimal("1").scaleb(-precision)
    rounded = decimal_value.quantize(quantizer, rounding=ROUND_HALF_EVEN)
    # Fixed-point string, no exponent, so language JSON number parsers are
    # not required to reproduce the leaf.
    return format(rounded, "f")


_NON_FINITE_TOKENS = frozenset(
    {
        "nan",
        "+nan",
        "-nan",
        "inf",
        "+inf",
        "-inf",
        "infinity",
        "+infinity",
        "-infinity",
    }
)


def _is_numeric_token(text: str) -> bool:
    """True if text should be parsed as a number (including NaN / Infinity)."""
    stripped = text.strip()
    if stripped == "":
        return False
    if stripped.lower() in _NON_FINITE_TOKENS:
        return True
    if _is_integer_literal(stripped):
        return True
    try:
        Decimal(stripped)
    except InvalidOperation:
        return False
    return True


def canonicalize_value(value: Any, precision: int) -> Any:
    """Recursively canonicalize a JSON-like value for hashing."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float, Decimal)):
        return format_number(value, precision)
    if isinstance(value, str):
        stripped = value.strip()
        # Numeric strings (including NaN / Infinity) go through format_number.
        # NaN is rejected there; only non-numeric text stays a string.
        if stripped == "":
            return ""
        if _is_numeric_token(stripped):
            return format_number(stripped, precision)
        return stripped
    if isinstance(value, Mapping):
        return {str(key): canonicalize_value(val, precision) for key, val in value.items()}
    if isinstance(value, (list, tuple)):
        return [canonicalize_value(item, precision) for item in value]
    raise SensorMerkleError(f"unsupported value type: {type(value).__name__}")


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _looks_like_json(text: str) -> bool:
    stripped = text.lstrip()
    return stripped.startswith("{") or stripped.startswith("[")


def parse_cell(text: str, precision: int, *, json_expected: bool = False) -> Any:
    stripped = text.strip()
    if stripped == "":
        return None
    if json_expected or _looks_like_json(stripped):
        try:
            loaded = json.loads(stripped)
        except json.JSONDecodeError as exc:
            if json_expected:
                raise SensorMerkleError(f"invalid JSON: {exc.msg}") from exc
            return canonicalize_value(stripped, precision)
        return canonicalize_value(loaded, precision)
    return canonicalize_value(stripped, precision)


def classify_column(name: str) -> tuple[str, str]:
    """Return (group, key) for a CSV header.

    group is one of: timestamp, joints, imu, torque, other, skip.
    """
    lowered = name.strip().lower()
    if lowered == "":
        return "skip", name
    if lowered in TIMESTAMP_NAMES:
        return "timestamp", lowered
    if lowered in JOINT_JSON_NAMES:
        return "joints_json", name.strip()
    if lowered in IMU_JSON_NAMES:
        return "imu_json", name.strip()
    if lowered in TORQUE_JSON_NAMES:
        return "torque_json", name.strip()
    if any(lowered.startswith(prefix) for prefix in JOINT_PREFIXES):
        return "joints", name.strip()
    if any(lowered.startswith(prefix) for prefix in IMU_PREFIXES):
        return "imu", name.strip()
    if any(lowered.startswith(prefix) for prefix in TORQUE_PREFIXES):
        return "torque", name.strip()
    return "other", name.strip()


def _merge_group(target: dict[str, Any], incoming: Any, *, label: str) -> None:
    """Fold a JSON column or a single field into a group dict."""
    if incoming is None:
        return
    if isinstance(incoming, Mapping):
        for key, val in incoming.items():
            if key in target:
                raise SensorMerkleError(f"duplicate {label} key {key!r}")
            target[str(key)] = val
        return
    if isinstance(incoming, list):
        for index, val in enumerate(incoming):
            key = str(index)
            if key in target:
                raise SensorMerkleError(f"duplicate {label} key {key!r}")
            target[key] = val
        return
    raise SensorMerkleError(f"{label} JSON must be an object or array, not {type(incoming).__name__}")


def _comment_or_blank(line: str) -> bool:
    stripped = line.lstrip()
    return stripped == "" or stripped.startswith("#")


def open_csv_records(path: Path) -> tuple[list[str], list[dict[str, str]], int]:
    """Read a UTF-8 CSV, skipping '#' comment lines and blank lines.

    Returns (fieldnames, rows, skipped_comment_or_blank_count).
    """
    raw_lines: list[str] = []
    skipped = 0
    with path.open("r", encoding="utf-8", newline="") as handle:
        for line in handle:
            if _comment_or_blank(line):
                skipped += 1
                continue
            raw_lines.append(line)
    if not raw_lines:
        raise SensorMerkleError(f"no CSV header in {path}")
    reader = csv.DictReader(raw_lines)
    if reader.fieldnames is None:
        raise SensorMerkleError(f"no CSV header in {path}")
    fieldnames: list[str] = []
    seen: set[str] = set()
    for name in reader.fieldnames:
        if name is None or name.strip() == "":
            raise SensorMerkleError("CSV has an empty column name")
        if name in seen:
            raise SensorMerkleError(f"duplicate CSV column {name!r}")
        seen.add(name)
        fieldnames.append(name)
    rows: list[dict[str, str]] = []
    for row in reader:
        # csv.DictReader puts leftover columns under None; treat as error.
        if None in row:
            raise SensorMerkleError(
                f"row has more fields than the header: extra={row[None]!r}"
            )
        rows.append({key: ("" if value is None else value) for key, value in row.items()})
    return fieldnames, rows, skipped


def classify_header(fieldnames: Sequence[str]) -> dict[str, tuple[str, str]]:
    mapping: dict[str, tuple[str, str]] = {}
    timestamp_columns = 0
    for name in fieldnames:
        group, key = classify_column(name)
        if group == "timestamp":
            timestamp_columns += 1
        mapping[name] = (group, key)
    if timestamp_columns == 0:
        raise SensorMerkleError(
            "CSV must include a timestamp column "
            f"(one of: {', '.join(sorted(TIMESTAMP_NAMES))})"
        )
    if timestamp_columns > 1:
        raise SensorMerkleError("CSV has more than one timestamp column")
    return mapping


def row_to_frame(
    row: Mapping[str, str],
    header_map: Mapping[str, tuple[str, str]],
    frame_index: int,
    precision: int,
) -> dict[str, Any]:
    timestamp: Any = None
    joints: dict[str, Any] = {}
    imu: dict[str, Any] = {}
    torque: dict[str, Any] = {}
    other: dict[str, Any] = {}

    for column, raw in row.items():
        group, key = header_map[column]
        json_expected = group.endswith("_json")
        try:
            parsed = parse_cell(raw, precision, json_expected=json_expected)
        except SensorMerkleError as exc:
            raise SensorMerkleError(f"column {column!r}: {exc}") from exc

        if group == "timestamp":
            if parsed is None:
                raise SensorMerkleError("timestamp is empty")
            timestamp = parsed
        elif group == "joints":
            if parsed is not None:
                if key in joints:
                    raise SensorMerkleError(f"duplicate joints key {key!r}")
                joints[key] = parsed
        elif group == "imu":
            if parsed is not None:
                if key in imu:
                    raise SensorMerkleError(f"duplicate imu key {key!r}")
                imu[key] = parsed
        elif group == "torque":
            if parsed is not None:
                if key in torque:
                    raise SensorMerkleError(f"duplicate torque key {key!r}")
                torque[key] = parsed
        elif group == "joints_json":
            _merge_group(joints, parsed, label="joints")
        elif group == "imu_json":
            _merge_group(imu, parsed, label="imu")
        elif group == "torque_json":
            _merge_group(torque, parsed, label="torque")
        elif group == "other":
            if parsed is not None:
                if key in other:
                    raise SensorMerkleError(f"duplicate other key {key!r}")
                other[key] = parsed
        elif group == "skip":
            continue
        else:
            raise SensorMerkleError(f"unknown column group {group!r}")

    if timestamp is None:
        raise SensorMerkleError("timestamp is empty")

    frame: dict[str, Any] = {
        "frame_index": frame_index,
        "timestamp": timestamp,
    }
    if joints:
        frame["joints"] = joints
    if imu:
        frame["imu"] = imu
    if torque:
        frame["torque"] = torque
    if other:
        frame["other"] = other
    return frame


def load_frames(
    path: Path,
    *,
    precision: int = DEFAULT_PRECISION,
    max_rows: int | None = None,
    skip_bad: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Load and canonicalize frames from a CSV file.

    Returns (frames, load_meta). load_meta records rows_read, rows_skipped,
    and skipped_comments for the receipt.
    """
    if max_rows is not None and max_rows < 0:
        raise SensorMerkleError("--max-rows must be >= 0")
    fieldnames, rows, skipped_comments = open_csv_records(path)
    header_map = classify_header(fieldnames)

    frames: list[dict[str, Any]] = []
    rows_skipped = 0
    rows_read = 0
    for raw_index, row in enumerate(rows):
        if max_rows is not None and len(frames) >= max_rows:
            break
        rows_read += 1
        try:
            frame = row_to_frame(row, header_map, len(frames), precision)
        except SensorMerkleError as exc:
            if skip_bad:
                rows_skipped += 1
                continue
            raise SensorMerkleError(f"row {raw_index + 2}: {exc}") from exc
        frames.append(frame)

    if not frames:
        raise SensorMerkleError("no usable frames after loading the CSV")

    meta = {
        "columns": list(fieldnames),
        "rows_read": rows_read,
        "rows_skipped_bad": rows_skipped,
        "comment_or_blank_lines": skipped_comments,
        "skip_bad": skip_bad,
        "max_rows": max_rows,
        "precision": precision,
    }
    return frames, meta


def leaf_hash(frame: Mapping[str, Any]) -> bytes:
    payload = canonical_json(frame).encode("utf-8")
    return _sha(LEAF_PREFIX + payload)


def build_tree(leaves: Sequence[bytes]) -> list[list[bytes]]:
    """Return tree levels, leaves at [0], root as the single node of [-1]."""
    if not leaves:
        raise SensorMerkleError("cannot build a Merkle tree with no leaves")
    levels: list[list[bytes]] = [list(leaves)]
    while len(levels[-1]) > 1:
        current = levels[-1]
        work = current + [current[-1]] if len(current) % 2 == 1 else current
        nxt = [
            _sha(NODE_PREFIX + work[i] + work[i + 1])
            for i in range(0, len(work), 2)
        ]
        levels.append(nxt)
    return levels


def merkle_root(leaves: Sequence[bytes]) -> bytes:
    return build_tree(leaves)[-1][0]


def inclusion_proof(leaves: Sequence[bytes], index: int) -> dict[str, Any]:
    if index < 0 or index >= len(leaves):
        raise SensorMerkleError(f"proof index {index} out of range (n={len(leaves)})")
    levels = build_tree(leaves)
    siblings: list[dict[str, str]] = []
    idx = index
    for level in levels[:-1]:
        work = level + [level[-1]] if len(level) % 2 == 1 else level
        if idx % 2 == 0:
            siblings.append({"side": "right", "hash": work[idx + 1].hex()})
        else:
            siblings.append({"side": "left", "hash": work[idx - 1].hex()})
        idx //= 2
    leaf = leaves[index]
    root = levels[-1][0]
    return {
        "index": index,
        "leaf": leaf.hex(),
        "root": root.hex(),
        "siblings": siblings,
    }


def verify_inclusion_proof(
    frame: Mapping[str, Any] | None,
    proof: Mapping[str, Any],
    root_hex: str,
    *,
    leaf_hex: str | None = None,
) -> bool:
    """Return True iff the proof reconstructs root_hex.

    If frame is provided, its leaf hash must also match proof['leaf']
    (and leaf_hex, when given). A mismatched leaf, a bad sibling, or a
    wrong root all return False rather than raising.
    """
    try:
        if frame is not None:
            computed = leaf_hash(frame).hex()
            if computed != str(proof["leaf"]):
                return False
            if leaf_hex is not None and computed != leaf_hex:
                return False
        elif leaf_hex is not None and leaf_hex != str(proof["leaf"]):
            return False
        current = bytes.fromhex(str(proof["leaf"]))
        for step in proof["siblings"]:
            sibling = bytes.fromhex(str(step["hash"]))
            side = step["side"]
            if side == "right":
                current = _sha(NODE_PREFIX + current + sibling)
            elif side == "left":
                current = _sha(NODE_PREFIX + sibling + current)
            else:
                return False
        return current.hex() == root_hex == str(proof["root"])
    except (KeyError, TypeError, ValueError):
        return False


def git_commit(repo_hint: Path | None = None) -> str | None:
    """Best-effort HEAD SHA. None if git is unavailable or this is not a repo."""
    start = repo_hint if repo_hint is not None else Path(__file__).resolve().parent
    candidates = [start, start.parent, Path.cwd()]
    for candidate in candidates:
        try:
            result = subprocess.run(
                ["git", "-C", str(candidate), "rev-parse", "HEAD"],
                check=False,
                capture_output=True,
                text=True,
            )
        except OSError:
            return None
        if result.returncode == 0:
            sha = result.stdout.strip()
            if re.fullmatch(r"[0-9a-f]{40}", sha):
                return sha
    return None


def canon_params(precision: int) -> dict[str, Any]:
    return {
        "float_precision": precision,
        "float_rounding": "ROUND_HALF_EVEN",
        "json": {
            "sort_keys": True,
            "separators": [",", ":"],
            "ensure_ascii": True,
        },
        "hash": "sha256",
        "leaf_prefix": "0x00",
        "node_prefix": "0x01",
        "odd_node": ODD_NODE_RULE,
        "encoding": "utf-8",
    }


def build_receipt(
    *,
    csv_path: Path,
    frames: Sequence[Mapping[str, Any]],
    leaves: Sequence[bytes],
    root: bytes,
    precision: int,
    load_meta: Mapping[str, Any],
    proofs: list[dict[str, Any]] | None = None,
    repo_hint: Path | None = None,
) -> dict[str, Any]:
    receipt: dict[str, Any] = {
        "schema": SCHEMA,
        "input_digest": sha256_file(csv_path),
        "source_path": str(csv_path),
        "canon": canon_params(precision),
        "root": root.hex(),
        "n_frames": len(frames),
        "tool": TOOL_NAME,
        "tool_version": TOOL_VERSION,
        "git_commit": git_commit(repo_hint),
        "load": dict(load_meta),
    }
    if proofs:
        receipt["proofs"] = proofs
    return receipt


def process_csv(
    csv_path: Path,
    *,
    precision: int = DEFAULT_PRECISION,
    max_rows: int | None = None,
    skip_bad: bool = False,
    prove: list[int] | None = None,
    repo_hint: Path | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[bytes]]:
    frames, load_meta = load_frames(
        csv_path, precision=precision, max_rows=max_rows, skip_bad=skip_bad
    )
    leaves = [leaf_hash(frame) for frame in frames]
    root = merkle_root(leaves)
    proofs = [inclusion_proof(leaves, index) for index in (prove or [])]
    receipt = build_receipt(
        csv_path=csv_path,
        frames=frames,
        leaves=leaves,
        root=root,
        precision=precision,
        load_meta=load_meta,
        proofs=proofs or None,
        repo_hint=repo_hint,
    )
    return receipt, frames, leaves


def verify_receipt_against_csv(receipt: Mapping[str, Any], csv_path: Path) -> dict[str, Any]:
    """Recompute the tree from csv_path and compare it to the receipt."""
    if receipt.get("schema") != SCHEMA:
        raise SensorMerkleError(
            f"unsupported receipt schema {receipt.get('schema')!r}; expected {SCHEMA}"
        )
    canon = receipt.get("canon") or {}
    precision = int(canon.get("float_precision", DEFAULT_PRECISION))
    load = receipt.get("load") or {}
    max_rows = load.get("max_rows")
    skip_bad = bool(load.get("skip_bad", False))
    recomputed, _frames, _leaves = process_csv(
        csv_path,
        precision=precision,
        max_rows=max_rows,
        skip_bad=skip_bad,
    )
    mismatches: list[str] = []
    if recomputed["root"] != receipt.get("root"):
        mismatches.append("root")
    if recomputed["n_frames"] != receipt.get("n_frames"):
        mismatches.append("n_frames")
    if recomputed["input_digest"] != receipt.get("input_digest"):
        mismatches.append("input_digest")
    return {
        "ok": not mismatches,
        "mismatches": mismatches,
        "expected_root": receipt.get("root"),
        "recomputed_root": recomputed["root"],
        "expected_n_frames": receipt.get("n_frames"),
        "recomputed_n_frames": recomputed["n_frames"],
        "expected_input_digest": receipt.get("input_digest"),
        "recomputed_input_digest": recomputed["input_digest"],
    }


def _print_summary(receipt: Mapping[str, Any], out: TextIO = sys.stdout) -> None:
    print(f"schema:        {receipt['schema']}", file=out)
    print(f"root:          {receipt['root']}", file=out)
    print(f"n_frames:      {receipt['n_frames']}", file=out)
    print(f"precision:     {receipt['canon']['float_precision']}", file=out)
    print(f"odd_node:      {receipt['canon']['odd_node']}", file=out)
    print(f"leaf_prefix:   {receipt['canon']['leaf_prefix']}", file=out)
    print(f"node_prefix:   {receipt['canon']['node_prefix']}", file=out)
    print(f"input_digest:  {receipt['input_digest']}", file=out)
    print(f"tool:          {receipt['tool']} {receipt['tool_version']}", file=out)
    print(f"git_commit:    {receipt['git_commit'] or 'unknown'}", file=out)
    load = receipt.get("load") or {}
    if load.get("max_rows") is not None:
        print(f"max_rows:      {load['max_rows']}", file=out)
    if load.get("rows_skipped_bad"):
        print(f"skipped_bad:   {load['rows_skipped_bad']}", file=out)
    for proof in receipt.get("proofs") or []:
        print(f"proof[{proof['index']}]:   leaf={proof['leaf']}", file=out)
        print(f"               siblings={len(proof['siblings'])}", file=out)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build a cp8.sensor_merkle.v1 receipt from a robot sensor CSV.",
    )
    parser.add_argument("--csv", dest="csv_path", help="Path to the sensor log CSV.")
    parser.add_argument(
        "--max-rows",
        type=int,
        default=None,
        help="Use only the first N usable frames.",
    )
    parser.add_argument(
        "--prove",
        type=int,
        action="append",
        default=None,
        metavar="I",
        help="Include an inclusion proof for frame index I (repeatable).",
    )
    parser.add_argument(
        "--out",
        dest="out_path",
        default=None,
        help="Write the receipt JSON to this path.",
    )
    parser.add_argument(
        "--precision",
        type=int,
        default=DEFAULT_PRECISION,
        help=f"Decimal places for non-integer numbers (default {DEFAULT_PRECISION}).",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--strict",
        action="store_true",
        default=True,
        help="Error on a bad row (default).",
    )
    mode.add_argument(
        "--skip-bad",
        action="store_true",
        help="Skip rows that fail to parse instead of exiting.",
    )
    parser.add_argument(
        "--verify-receipt",
        dest="verify_receipt",
        default=None,
        help="Recompute the tree for --csv (or the path in the receipt) and compare.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        if args.verify_receipt:
            receipt_path = Path(args.verify_receipt)
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            csv_path = Path(args.csv_path) if args.csv_path else Path(receipt["source_path"])
            result = verify_receipt_against_csv(receipt, csv_path)
            print(canonical_json(result))
            return 0 if result["ok"] else 1

        if not args.csv_path:
            parser.error("--csv is required unless --verify-receipt is used with a source_path")

        if args.precision < 0:
            raise SensorMerkleError("--precision must be >= 0")

        csv_path = Path(args.csv_path)
        if not csv_path.is_file():
            raise SensorMerkleError(f"CSV not found: {csv_path}")

        receipt, _frames, _leaves = process_csv(
            csv_path,
            precision=args.precision,
            max_rows=args.max_rows,
            skip_bad=bool(args.skip_bad),
            prove=args.prove,
        )
        _print_summary(receipt)
        if args.out_path:
            out_path = Path(args.out_path)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(
                json.dumps(receipt, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            print(f"receipt:       {out_path}")
        return 0
    except SensorMerkleError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
