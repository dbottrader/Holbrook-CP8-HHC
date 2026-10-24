import json
from pathlib import Path

import pytest
import requests

from cp8_agent import (
    BoundedExecutor,
    CP8Worker,
    GENESIS,
    Moltbook,
    ReceiptLedger,
    Settings,
    canonical,
    result_nonce,
    sha256,
)

POST_ID = "5b4a9d23-dcc9-4127-8957-bf03b2beb5e9"
OTHER_ID = "451280f7-f8a5-4b58-80db-801184e4a398"
TASK = "798db35c-ba7b-455e-97a9-f70a95a846b4"
SERVER_HASH = "ab" * 32
OTHER_HASH = "cd" * 32


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


def sample_receipt(task_id: str = TASK) -> dict:
    body = {"previous_receipt_hash": GENESIS, "promotion": "HOLD", "task_id": task_id}
    return {
        "body": body,
        "receipt_hash": sha256(canonical(body)),
        "signature": None,
        "signature_state": "UNSIGNED",
        "result": {"task_id": task_id},
    }


class Response:
    def __init__(self, status: int, payload: dict) -> None:
        self.status_code = status
        self.ok = 200 <= status < 300
        self.text = json.dumps(payload)
        self._payload = payload

    def json(self) -> dict:
        return self._payload


class QueueSession:
    def __init__(self, post_payload: dict | None = None, complete_statuses: list[int] | None = None, fail_posts: int = 0) -> None:
        self.posts: list[dict] = []
        self.completes: list[dict] = []
        self.post_payload = post_payload
        self.complete_statuses = list(complete_statuses or [200])
        self.fail_posts = fail_posts
        self.headers: dict[str, str] = {}

    def request(self, method: str, url: str, timeout: int | None = None, **kwargs):
        if url.endswith("/heartbeat"):
            return Response(200, {"ok": True})
        if url.endswith("/claim"):
            task_id = url.split("/work/items/")[1].split("/claim")[0]
            return Response(200, {"ok": True, "item": {
                "work_id": task_id, "title": "t", "description": "d", "metadata": {}, "room_slug": "cp8-ops",
            }})
        if url.endswith("/posts"):
            body = kwargs.get("json") or {}
            self.posts.append(body)
            if self.fail_posts:
                self.fail_posts -= 1
                raise requests.ConnectionError("down")
            payload = self.post_payload or {
                "ok": True,
                "post": {"post_id": POST_ID, "content_hash": SERVER_HASH, "promotion": "HOLD"},
            }
            return Response(200, payload)
        if url.endswith("/complete"):
            body = kwargs.get("json") or {}
            self.completes.append(body)
            status = self.complete_statuses.pop(0) if self.complete_statuses else 200
            if status != 200:
                return Response(status, {"ok": False, "error": "complete_failed", "message": "unavailable"})
            return Response(200, {"ok": True, "item": {
                "status": "completed",
                "result_post_id": body.get("result_post_id"),
                "result_hash": body.get("result_hash"),
            }})
        raise AssertionError(url)


def api_with(tmp_path: Path, payload: dict, status: int = 200) -> Moltbook:
    api = Moltbook(settings(tmp_path))

    class Session:
        headers: dict[str, str] = {}

        def request(self, method: str, url: str, timeout: int | None = None, **kwargs):
            return Response(status, payload)

    api.http = Session()
    return api


def start_worker(tmp_path: Path, session: QueueSession) -> tuple[CP8Worker, dict[str, int]]:
    worker = CP8Worker(settings(tmp_path))
    worker.api.http = session
    calls = {"n": 0}

    def propose(task: dict) -> tuple[dict, dict]:
        calls["n"] += 1
        return {"tool": "none", "args": {}}, {"provider": "ollama", "model": "test-model"}

    worker.model.propose = propose
    return worker, calls


@pytest.mark.parametrize(
    ("post", "match"),
    [
        (None, "result post missing"),
        ({}, "valid ID"),
        ({"post_id": "not-a-uuid", "content_hash": SERVER_HASH, "promotion": "HOLD"}, "valid ID"),
        ({"post_id": "", "content_hash": SERVER_HASH, "promotion": "HOLD"}, "valid ID"),
        ({"post_id": POST_ID, "promotion": "HOLD"}, "content hash"),
        ({"post_id": POST_ID, "content_hash": "abc", "promotion": "HOLD"}, "content hash"),
        ({"post_id": POST_ID, "content_hash": SERVER_HASH.upper(), "promotion": "HOLD"}, "content hash"),
        ({"post_id": POST_ID, "content_hash": SERVER_HASH, "promotion": "PROMOTED"}, "not HOLD"),
    ],
)
def test_publish_requires_server_post_id_and_hash(tmp_path: Path, post: dict | None, match: str) -> None:
    payload = {"ok": True, "post": post} if post is not None else {"ok": True}
    api = api_with(tmp_path, payload)
    with pytest.raises(RuntimeError, match=match):
        api.publish({"room_slug": "cp8-ops"}, sample_receipt())


def test_publish_returns_server_id_and_hash_unchanged(tmp_path: Path) -> None:
    api = api_with(tmp_path, {"ok": True, "post": {
        "post_id": POST_ID.upper(), "content_hash": SERVER_HASH,
    }})
    assert api.publish({"room_slug": "cp8-ops"}, sample_receipt()) == (POST_ID, SERVER_HASH)


def test_publish_rejects_false_ok(tmp_path: Path) -> None:
    api = api_with(tmp_path, {"ok": False, "error": "write_failed", "message": "no"})
    with pytest.raises(RuntimeError, match="rejected"):
        api.publish({"room_slug": "cp8-ops"}, sample_receipt())


def test_complete_refuses_invented_binding(tmp_path: Path) -> None:
    api = Moltbook(settings(tmp_path))

    def boom(*args, **kwargs):
        raise AssertionError("complete must not call the server without a server binding")

    api.http.request = boom
    with pytest.raises(RuntimeError, match="valid ID"):
        api.complete(TASK, "not-a-uuid", SERVER_HASH)
    with pytest.raises(RuntimeError, match="content hash"):
        api.complete(TASK, POST_ID, "deadbeef")


def test_complete_rejects_a_different_server_binding(tmp_path: Path) -> None:
    api = api_with(tmp_path, {"ok": True, "item": {"result_post_id": OTHER_ID, "result_hash": SERVER_HASH}})
    with pytest.raises(RuntimeError, match="different post id"):
        api.complete(TASK, POST_ID, SERVER_HASH)
    api = api_with(tmp_path, {"ok": True, "item": {"result_post_id": POST_ID, "result_hash": OTHER_HASH}})
    with pytest.raises(RuntimeError, match="different content hash"):
        api.complete(TASK, POST_ID, SERVER_HASH)


def test_complete_accepts_matching_or_empty_item(tmp_path: Path) -> None:
    api = api_with(tmp_path, {"ok": True, "item": None})
    api.complete(TASK, POST_ID, SERVER_HASH)
    api = api_with(tmp_path, {"ok": True, "item": {"result_post_id": POST_ID, "result_hash": SERVER_HASH}})
    api.complete(TASK, POST_ID, SERVER_HASH)


def test_completion_failure_reuses_the_server_post(tmp_path: Path) -> None:
    session = QueueSession(complete_statuses=[400, 200])
    calls = {"n": 0}

    def propose(task: dict) -> tuple[dict, dict]:
        calls["n"] += 1
        return {"tool": "none", "args": {}}, {"provider": "ollama", "model": "test-model"}

    worker, _calls = start_worker(tmp_path, session)
    worker.model.propose = propose
    worker.process({"work_id": TASK})
    restarted, _calls = start_worker(tmp_path, session)
    restarted.model.propose = propose
    restarted.process({"work_id": TASK})
    assert calls["n"] == 1
    assert len(session.posts) == 1
    assert session.posts[0]["nonce"] == result_nonce(TASK, json.loads(session.posts[0]["content"])["receipt"]["receipt_hash"])
    assert session.completes == [
        {"result_post_id": POST_ID, "result_hash": SERVER_HASH},
        {"result_post_id": POST_ID, "result_hash": SERVER_HASH},
    ]
    assert session.completes[0]["result_hash"] != sha256(session.posts[0]["content"].encode())


def test_saved_post_survives_ledger_append_failure(tmp_path: Path) -> None:
    session = QueueSession()
    worker, _calls = start_worker(tmp_path, session)

    def fail_append(receipt: dict, binding: dict) -> None:
        raise OSError("disk full")

    worker.ledger.append = fail_append
    worker.process({"work_id": TASK})
    staged = worker.ledger.read_stage(TASK)
    assert staged is not None
    assert staged["post_id"] == POST_ID
    assert staged["post_content_hash"] == SERVER_HASH
    assert session.completes == []
    restarted, _calls = start_worker(tmp_path, session)
    restarted.model.propose = lambda task: (_ for _ in ()).throw(AssertionError("model"))
    restarted.process({"work_id": TASK})
    assert len(session.posts) == 1
    assert session.completes == [{"result_post_id": POST_ID, "result_hash": SERVER_HASH}]
    ReceiptLedger(restarted.s.ledger, None)


def test_unpublished_result_replays_the_same_nonce(tmp_path: Path) -> None:
    session = QueueSession(fail_posts=1)
    calls = {"n": 0}

    def propose(task: dict) -> tuple[dict, dict]:
        calls["n"] += 1
        return {"tool": "none", "args": {}}, {"provider": "ollama", "model": "test-model"}

    worker, _ignored = start_worker(tmp_path, session)
    worker.model.propose = propose
    worker.process({"work_id": TASK})
    assert session.completes == []
    staged = worker.ledger.read_stage(TASK)
    assert staged is not None and "post_id" not in staged
    restarted, _ignored = start_worker(tmp_path, session)
    restarted.model.propose = propose
    restarted.process({"work_id": TASK})
    assert calls["n"] == 1
    assert len(session.posts) == 2
    assert session.posts[0]["nonce"] == session.posts[1]["nonce"]
    assert session.posts[0]["content"] == session.posts[1]["content"]
    assert session.completes == [{"result_post_id": POST_ID, "result_hash": SERVER_HASH}]


def test_invalid_journaled_binding_does_not_publish(tmp_path: Path) -> None:
    session = QueueSession()
    worker, _calls = start_worker(tmp_path, session)
    task = {"work_id": TASK, "metadata": {}}
    receipt = worker.ledger.make(
        task, {"provider": "ollama", "model": "test-model"}, {"tool": "none", "args": {}},
        {"tool": "none", "state": "NO_ACTION", "exit_code": 0, "stdout": "", "stderr": ""},
    )
    worker.ledger.append(receipt, {"task_id": TASK, "post_id": "not-a-server-id", "post_content_hash": SERVER_HASH})
    restarted, _calls = start_worker(tmp_path, session)
    with pytest.raises(RuntimeError, match="journaled result binding is invalid"):
        restarted.ledger.find_bound(TASK)
    restarted.model.propose = lambda task: (_ for _ in ()).throw(AssertionError("model"))
    restarted.process({"work_id": TASK})
    assert session.posts == []
    assert session.completes == []


def test_existing_journal_completes_without_a_new_post(tmp_path: Path) -> None:
    session = QueueSession()
    worker, _calls = start_worker(tmp_path, session)
    task = {"work_id": TASK, "metadata": {}}
    receipt = worker.ledger.make(
        task, {"provider": "ollama", "model": "test-model"}, {"tool": "none", "args": {}},
        {"tool": "none", "state": "NO_ACTION", "exit_code": 0, "stdout": "", "stderr": ""},
    )
    worker.ledger.append(receipt, {"post_id": POST_ID, "post_content_hash": SERVER_HASH})
    restarted, _calls = start_worker(tmp_path, session)
    restarted.model.propose = lambda task: (_ for _ in ()).throw(AssertionError("model"))
    restarted.process({"work_id": TASK})
    assert session.posts == []
    assert session.completes == [{"result_post_id": POST_ID, "result_hash": SERVER_HASH}]


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
