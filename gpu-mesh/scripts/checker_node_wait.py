"""Watch a checker node and stop it after one verification receipt.

The node log is the source of the node id. The public receipt list is the
source of whether that node finished a verification. The node token is never
read or printed.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import signal
import time
import urllib.error
import urllib.request
from pathlib import Path

VERIFICATION_KINDS = frozenset({"verification_pass", "verification_fail"})
_NODE_ID = re.compile(r"registered (node_[0-9a-fA-F]+) as ")
_FINISHED = re.compile(r"finished (job_[0-9a-fA-F]+) in ")


def node_id_from_log(text: str) -> str:
    found = _NODE_ID.findall(text)
    return found[-1] if found else ""


def finished_job_ids(text: str) -> list[str]:
    return _FINISHED.findall(text)


def verification_for(node_id: str, receipts: list) -> dict[str, str] | None:
    """Return the newest verification receipt this node wrote, if any."""

    if not node_id:
        return None
    for row in receipts:
        if not isinstance(row, dict) or row.get("actor") != node_id:
            continue
        kind = row.get("kind")
        if kind not in VERIFICATION_KINDS:
            continue
        payload = row.get("payload") or {}
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except json.JSONDecodeError:
                payload = {}
        if not isinstance(payload, dict):
            payload = {}
        return {
            "kind": str(kind),
            "job_id": str(payload.get("job_id") or ""),
            "parent_job_id": str(payload.get("parent_job_id") or ""),
        }
    return None


def process_alive(pid: int) -> bool:
    stat = Path(f"/proc/{pid}/stat")
    try:
        text = stat.read_text(encoding="utf-8")
    except OSError:
        return False
    parts = text.rsplit(")", 1)
    if len(parts) != 2:
        return False
    fields = parts[1].split()
    if not fields:
        return False
    return fields[0] != "Z"


def fetch_receipts(coordinator: str, timeout: float = 30) -> list:
    url = coordinator.rstrip("/") + "/api/receipts?limit=50"
    request = urllib.request.Request(url, headers={"accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = json.load(response)
    rows = body.get("receipts") if isinstance(body, dict) else None
    return rows if isinstance(rows, list) else []


def emit(line: str) -> None:
    print(line, flush=True)
    summary = os.environ.get("GITHUB_STEP_SUMMARY", "").strip()
    if not summary:
        return
    with open(summary, "a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def stop_process(pid: int) -> None:
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        return
    deadline = time.time() + 15
    while time.time() < deadline:
        if not process_alive(pid):
            return
        time.sleep(0.5)
    try:
        os.kill(pid, signal.SIGKILL)
    except OSError:
        return


def watch(log_path: Path, coordinator: str, minutes: float, pid: int, poll_sec: float) -> int:
    deadline = time.time() + max(0.0, minutes) * 60
    seen_node = ""
    announced: set[str] = set()
    while True:
        text = ""
        if log_path.exists():
            text = log_path.read_text(encoding="utf-8", errors="replace")
        node_id = node_id_from_log(text)
        if node_id and node_id != seen_node:
            seen_node = node_id
            emit(f"GPUMESH_NODE_ID={node_id}")
        for job_id in finished_job_ids(text):
            if job_id in announced:
                continue
            announced.add(job_id)
            emit(f"GPUMESH_FINISHED_JOB={job_id}")
        found = None
        if seen_node:
            try:
                found = verification_for(seen_node, fetch_receipts(coordinator))
            except (OSError, urllib.error.URLError, json.JSONDecodeError, TimeoutError) as exc:
                emit(f"receipt poll failed: {exc}")
                found = None
        if found is not None:
            emit("GPUMESH_VERIFICATION_CLAIMED=yes")
            emit(f"GPUMESH_VERIFICATION_KIND={found['kind']}")
            if found["job_id"]:
                emit(f"GPUMESH_VERIFICATION_JOB={found['job_id']}")
            if found["parent_job_id"]:
                emit(f"GPUMESH_PARENT_JOB={found['parent_job_id']}")
            stop_process(pid)
            return 0
        if not process_alive(pid):
            emit("GPUMESH_VERIFICATION_CLAIMED=no")
            emit("checker node exited before a verification receipt")
            return 1
        if time.time() >= deadline:
            emit("GPUMESH_VERIFICATION_CLAIMED=no")
            emit(f"checker stopped after {minutes:g} minutes without a verification receipt")
            stop_process(pid)
            return 1
        time.sleep(poll_sec)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Stop the checker after one verification")
    parser.add_argument("--log", required=True, type=Path)
    parser.add_argument("--coordinator", required=True)
    parser.add_argument("--minutes", type=float, required=True)
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--poll-sec", type=float, default=10)
    args = parser.parse_args(argv)
    return watch(args.log, args.coordinator, args.minutes, args.pid, args.poll_sec)


if __name__ == "__main__":
    raise SystemExit(main())
