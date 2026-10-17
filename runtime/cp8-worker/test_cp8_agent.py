import json
import tempfile
from pathlib import Path

import pytest

from cp8_agent import BoundedExecutor, GENESIS, ReceiptLedger, Settings, canonical, sha256


def settings(root: Path, enable_pytest: bool = False) -> Settings:
    return Settings(
        api_url="https://example.invalid", token="test-token", provider="ollama",
        model="test-model", workspace=root, ledger=root / "receipts.jsonl",
        poll_seconds=10, lease_minutes=15, request_timeout=5, model_timeout=5,
        enable_pytest=enable_pytest, signing_key_file=None,
    )


def test_unknown_tool_never_executes(tmp_path: Path) -> None:
    result = BoundedExecutor(settings(tmp_path)).run(
        {"tool": "shell", "args": {"command": "touch SHOULD_NOT_EXIST"}}
    )
    assert result["exit_code"] == -1
    assert not (tmp_path / "SHOULD_NOT_EXIST").exists()


def test_pytest_is_disabled_by_default(tmp_path: Path) -> None:
    (tmp_path / "tests").mkdir()
    result = BoundedExecutor(settings(tmp_path)).run({"tool": "run_pytest", "args": {}})
    assert result["exit_code"] == 126
    assert "disabled_by_policy" in result["stderr"]


def test_hash_file_is_workspace_scoped(tmp_path: Path) -> None:
    (tmp_path / "note.txt").write_text("CP8", encoding="utf-8")
    result = BoundedExecutor(settings(tmp_path)).run(
        {"tool": "sha256_file", "args": {"path": "note.txt"}}
    )
    assert result["exit_code"] == 0
    assert sha256(b"CP8") in result["stdout"]


def test_hash_file_rejects_path_traversal(tmp_path: Path) -> None:
    result = BoundedExecutor(settings(tmp_path)).run(
        {"tool": "sha256_file", "args": {"path": "../outside.txt"}}
    )
    assert result["exit_code"] == -1
    assert result["stderr"] == "path_outside_workspace"


def test_hash_file_rejects_symlink(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside-secret.txt"
    outside.write_text("not in workspace", encoding="utf-8")
    (tmp_path / "linked.txt").symlink_to(outside)
    result = BoundedExecutor(settings(tmp_path)).run(
        {"tool": "sha256_file", "args": {"path": "linked.txt"}}
    )
    assert result["exit_code"] == -1
    assert result["stderr"] == "symlink_not_allowed"


def test_receipt_chain_head_and_tamper_detection(tmp_path: Path) -> None:
    path = tmp_path / "receipts.jsonl"
    body = {"previous_receipt_hash": GENESIS, "promotion": "HOLD"}
    record = {"body": body, "receipt_hash": sha256(canonical(body))}
    path.write_text(json.dumps(record) + "\n", encoding="utf-8")
    ledger = ReceiptLedger(path, None)
    assert ledger.previous == record["receipt_hash"]
    altered = {"body": {**body, "promotion": "PROMOTED"}, "receipt_hash": record["receipt_hash"]}
    path.write_text(json.dumps(altered) + "\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="hash mismatch"):
        ReceiptLedger(path, None)
