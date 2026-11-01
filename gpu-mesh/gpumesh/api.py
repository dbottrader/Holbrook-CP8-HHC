"""HTTP surface: OpenAI-compatible public API, node protocol, admin, and dashboard."""

from __future__ import annotations

import asyncio
import hashlib
import io
import json
import logging
import tarfile
import time
from pathlib import Path

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import (
    FileResponse,
    JSONResponse,
    PlainTextResponse,
    Response,
    StreamingResponse,
)

import gpumesh_node
from gpumesh.canon import hash_secret
from gpumesh.db import ApiKey, read_session, write_session
from gpumesh.errors import MeshError
from gpumesh.ratelimit import RateLimiter
from gpumesh.textutil import flatten_content
from gpumesh.work import (
    CLIENT_READY,
    DELIVERABLE,
    abandon_job,
    add_chunk,
    ban_ip,
    chunks_after,
    claim_job,
    create_api_key,
    enqueue_canary,
    enqueue_inference,
    failed_jobs,
    full_verify,
    heartbeat,
    ip_banned,
    job_for_node,
    job_snapshot,
    ledger_export,
    list_public_models,
    node_by_token,
    receipt_page,
    register_node,
    revoke_api_key,
    revoke_node_credentials,
    rotate_credential,
    set_node_status,
    stats,
    submit_fail,
    submit_result,
    unban_ip,
)

log = logging.getLogger("gpumesh.api")
STATIC = Path(__file__).resolve().parent / "static"
ASSETS = Path(__file__).resolve().parent / "assets"

public = APIRouter()
nodes = APIRouter()
admin = APIRouter()
pages = APIRouter()


def _bearer(request: Request) -> str:
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    return ""


def _client_ip(request: Request) -> str:
    settings = request.app.state.settings
    if settings.trust_proxy:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",")[0].strip() or "unknown"
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _require_admin(request: Request) -> None:
    token = _bearer(request)
    expected = request.app.state.settings.admin_token
    if not expected or not token or not _constant_eq(token, expected):
        raise MeshError(401, "admin token required", "authentication_error", "admin_required")


def _constant_eq(left: str, right: str) -> bool:
    import hmac

    return hmac.compare_digest(left.encode(), right.encode())


async def _json_object(request: Request) -> dict:
    try:
        data = await request.json()
    except Exception as exc:
        raise MeshError(400, "request body must be JSON", code="invalid_json") from exc
    if not isinstance(data, dict):
        raise MeshError(400, "JSON body must be an object", code="invalid_json")
    return data


def _auth_node(request: Request, session):  # noqa: ANN001
    token = _bearer(request)
    if not token:
        raise MeshError(401, "node token required", "authentication_error", "node_required")
    node = node_by_token(session, token)
    if node is None:
        raise MeshError(401, "unknown node token", "authentication_error", "unknown_node")
    if node.status == "banned":
        raise MeshError(403, "node banned", "permission_error", "banned")
    return node


def _identity(request: Request, session) -> tuple[str, int, int]:  # noqa: ANN001
    settings = request.app.state.settings
    ip = _client_ip(request)
    if ip_banned(session, ip):
        raise MeshError(403, "this address is banned", "permission_error", "banned")
    token = _bearer(request)
    if token.startswith("gmt_"):
        raise MeshError(401, "node tokens are not API keys", "authentication_error", "wrong_token")
    if token.startswith("sk-mesh-"):
        row = session.query(ApiKey).filter(ApiKey.key_hash == hash_secret(token), ApiKey.revoked == 0).one_or_none()
        if row is None:
            raise MeshError(401, "unknown API key", "authentication_error", "unknown_key")
        return f"key:{row.id}", row.rpm, int(row.kudos or 0)
    if token:
        raise MeshError(401, "unknown API key", "authentication_error", "unknown_key")
    return f"ip:{ip}", settings.anon_rpm, 0


def _hit(request: Request, bucket: str, limit: int, window: float, code: str) -> int:
    limiter: RateLimiter = request.app.state.limiter
    ok, remaining = limiter.allow(bucket, limit, window)
    if not ok:
        raise MeshError(
            429,
            "rate limit exceeded",
            "rate_limit_error",
            code,
            headers={"retry-after": str(int(window)), "x-ratelimit-limit": str(limit), "x-ratelimit-remaining": "0"},
        )
    return remaining


def _parse_chat(data: dict, settings) -> dict:  # noqa: ANN001
    model = str(data.get("model") or "").strip()
    if not model or len(model) > 128:
        raise MeshError(400, "model is required", code="model_required")
    raw_messages = data.get("messages")
    if not isinstance(raw_messages, list) or not raw_messages:
        raise MeshError(400, "messages must be a non-empty list", code="messages_required")
    if len(raw_messages) > settings.max_messages:
        raise MeshError(400, f"at most {settings.max_messages} messages", code="too_many_messages")
    n = data.get("n", 1)
    if n != 1:
        raise MeshError(400, "only n=1 is supported", code="unsupported_n")
    messages = []
    total = 0
    for item in raw_messages:
        if not isinstance(item, dict):
            raise MeshError(400, "each message must be an object", code="bad_message")
        role = str(item.get("role") or "")
        if role not in {"system", "user", "assistant", "tool"}:
            raise MeshError(400, f"unsupported role {role}", code="bad_role")
        try:
            content = flatten_content(item.get("content"))
        except ValueError as exc:
            raise MeshError(400, str(exc), code="unsupported_content") from exc
        total += len(content)
        messages.append({"role": role, "content": content})
    if total == 0:
        raise MeshError(400, "messages are empty", code="empty_prompt")
    if total > settings.max_prompt_chars:
        raise MeshError(400, f"prompt exceeds {settings.max_prompt_chars} characters", code="prompt_too_long")
    temperature = data.get("temperature", 0.7)
    try:
        temperature = float(temperature)
    except (TypeError, ValueError) as exc:
        raise MeshError(400, "temperature must be a number", code="bad_temperature") from exc
    temperature = max(0.0, min(2.0, temperature))
    raw_max = data.get("max_tokens", data.get("max_completion_tokens", 256))
    try:
        max_tokens = int(raw_max if raw_max is not None else 256)
    except (TypeError, ValueError) as exc:
        raise MeshError(400, "max_tokens must be an integer", code="bad_max_tokens") from exc
    if max_tokens < 1 or max_tokens > 100000:
        raise MeshError(400, "max_tokens is out of range", code="bad_max_tokens")
    max_tokens = min(max_tokens, settings.max_completion_tokens)
    seed = data.get("seed", None)
    if seed is not None:
        try:
            seed = int(seed)
        except (TypeError, ValueError) as exc:
            raise MeshError(400, "seed must be an integer", code="bad_seed") from exc
        if seed < -1_000_000_000 or seed > 1_000_000_000:
            raise MeshError(400, "seed is out of range", code="bad_seed")
    stop = data.get("stop")
    if stop is None:
        stop_list = None
    elif isinstance(stop, str):
        stop_list = [stop[:64]]
    elif isinstance(stop, list) and all(isinstance(item, str) for item in stop) and len(stop) <= 4:
        stop_list = [item[:64] for item in stop]
    else:
        raise MeshError(400, "stop must be a string or a list of up to 4 strings", code="bad_stop")
    stream = bool(data.get("stream", False))
    return {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "seed": seed,
        "stop": stop_list,
        "stream": stream,
    }


def _completion(snap: dict) -> dict:
    created = int(snap["created_at"] or time.time())
    text = snap["output_text"] or ""
    return {
        "id": f"chatcmpl-{snap['id'].removeprefix('job_')}",
        "object": "chat.completion",
        "created": created,
        "model": snap["model"],
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": text},
                "finish_reason": snap["finish_reason"] or "stop",
            }
        ],
        "usage": {
            "prompt_tokens": snap["prompt_tokens"],
            "completion_tokens": snap["completion_tokens"],
            "total_tokens": snap["prompt_tokens"] + snap["completion_tokens"],
        },
        "system_fingerprint": f"fp_{(snap['receipt_hash'] or 'none')[:16]}",
        "gpumesh": {
            "job_id": snap["id"],
            "node_id": snap["assigned_node_id"],
            "receipt": snap["receipt_hash"],
            "output_hash": snap["output_hash"],
            "verdict": snap["verdict"],
            "duration_ms": snap["duration_ms"],
            "credits": snap["credits_awarded"],
        },
    }


def _chunk_line(snap: dict, delta: dict, finish: str | None) -> str:
    payload = {
        "id": f"chatcmpl-{snap['id'].removeprefix('job_')}",
        "object": "chat.completion.chunk",
        "created": int(snap["created_at"] or time.time()),
        "model": snap["model"],
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
    }
    return f"data: {json.dumps(payload, separators=(',', ':'))}\n\n"


def _pieces(text: str, size: int = 24) -> list[str]:
    return [text[i : i + size] for i in range(0, len(text), size)] or [""]


async def _wait_terminal(app: FastAPI, job_id: str, timeout: float) -> dict | None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with read_session(app) as session:
            from gpumesh.db import Job

            job = session.get(Job, job_id)
            if job is not None and job.status in CLIENT_READY:
                return job_snapshot(job)
        await asyncio.sleep(0.05)
    return None


async def _fail_if_abandoned(app: FastAPI, job_id: str) -> str:
    with write_session(app) as session:
        from gpumesh.db import Job

        job = session.get(Job, job_id)
        if job is None:
            return "missing"
        return abandon_job(session, job_id)


@public.get("/health")
def health(request: Request) -> dict:
    try:
        with read_session(request.app) as session:
            from gpumesh.db import Node

            online = session.query(Node).filter(Node.status == "online").count()
    except Exception:
        log.exception("health check failed")
        raise MeshError(503, "database unavailable", "server_error", "db") from None
    return {"ok": True, "version": "0.1.0", "nodes_online": online}


@public.get("/v1/models")
def models(request: Request) -> dict:
    with read_session(request.app) as session:
        data = list_public_models(session)
    return {"object": "list", "data": data}


@public.post("/v1/chat/completions")
async def chat(request: Request):
    data = await _json_object(request)
    settings = request.app.state.settings
    parsed = _parse_chat(data, settings)
    ip = _client_ip(request)
    _hit(request, f"ipcap:{ip}", max(settings.anon_rpm * 5, 60), 60, "ip")
    with write_session(request.app) as session:
        client_key, rpm, kudos = _identity(request, session)
    remaining = _hit(request, f"rpm:{client_key}", rpm, 60, "rpm")
    from gpumesh.canon import canon_sha256

    digest = canon_sha256({"model": parsed["model"], "messages": parsed["messages"]})[:24]
    _hit(request, f"dup:{client_key}:{digest}", settings.dup_per_min, 60, "duplicate")
    _hit(request, f"flood:{client_key}", settings.flood_per_min, 60, "flood")
    cost = 0
    if parsed["max_tokens"] > settings.kudos_free_max_tokens:
        cost = max(1, (parsed["max_tokens"] - settings.kudos_free_max_tokens) // 64)
        if kudos < cost:
            raise MeshError(
                402,
                "this request is above the free size and needs kudos on an API key",
                "insufficient_quota",
                "kudos_required",
            )
    with write_session(request.app) as session:
        if cost and client_key.startswith("key:"):
            from gpumesh.db import ApiKey as KeyRow

            row = session.get(KeyRow, client_key.removeprefix("key:"))
            if row is None or int(row.kudos or 0) < cost:
                raise MeshError(402, "not enough kudos", "insufficient_quota", "kudos_required")
            row.kudos -= cost
            kudos = int(row.kudos)
        job = enqueue_inference(
            session,
            settings,
            model=parsed["model"],
            messages=parsed["messages"],
            temperature=parsed["temperature"],
            max_tokens=parsed["max_tokens"],
            seed=parsed["seed"],
            stop=parsed["stop"],
            client_key=client_key,
            priority=kudos,
            kudos_cost=cost,
        )
        job_id = job.id
        created_at = job.created_at
        model = job.model
    wait_header = request.headers.get("x-gpumesh-wait-seconds")
    if wait_header is not None:
        try:
            timeout = float(wait_header)
        except ValueError as exc:
            raise MeshError(400, "X-GPUMesh-Wait-Seconds must be a number", code="bad_wait") from exc
    else:
        timeout = settings.request_timeout_sec
    timeout = max(0.0, min(timeout, settings.request_timeout_sec))
    if parsed["stream"]:
        timeout = min(timeout, settings.stream_timeout_sec)
    headers = {"x-ratelimit-limit": str(rpm), "x-ratelimit-remaining": str(remaining)}
    if timeout == 0:
        body = {
            "id": job_id,
            "object": "gpumesh.job",
            "status": "queued",
            "model": model,
            "created": int(created_at),
            "poll": f"/v1/jobs/{job_id}",
        }
        return JSONResponse(status_code=202, content=body, headers=headers)
    if parsed["stream"]:
        generator = _stream(request.app, job_id, timeout)
        return StreamingResponse(generator, media_type="text/event-stream", headers={**headers, "cache-control": "no-cache", "x-accel-buffering": "no"})
    try:
        snap = await _wait_terminal(request.app, job_id, timeout)
    except asyncio.CancelledError:
        await _fail_if_abandoned(request.app, job_id)
        raise
    if snap is None:
        status = await _fail_if_abandoned(request.app, job_id)
        if status == "queued":
            raise MeshError(503, "no node accepted the job in time", "server_error", "no_capacity", headers={"retry-after": "5"})
        raise MeshError(504, f"job {job_id} did not finish before the timeout", "server_error", "timeout")
    if snap["status"] not in DELIVERABLE:
        raise MeshError(502, snap["error"] or f"job {snap['status']}", "server_error", snap["status"])
    return JSONResponse(_completion(snap), headers=headers)


@public.get("/v1/jobs/{job_id}")
async def job_status(request: Request, job_id: str):
    with read_session(request.app) as session:
        from gpumesh.db import Job

        job = session.get(Job, job_id)
        if job is None:
            raise MeshError(404, "unknown job", code="unknown_job")
        snap = job_snapshot(job)
    if snap["status"] in DELIVERABLE:
        return _completion(snap)
    return {
        "id": job_id,
        "object": "gpumesh.job",
        "status": snap["status"],
        "model": snap["model"],
        "error": snap["error"],
        "verdict": snap["verdict"],
    }


async def _stream(app: FastAPI, job_id: str, timeout: float):
    deadline = time.monotonic() + timeout
    sent = -1
    started = False
    try:
        while True:
            with read_session(app) as session:
                from gpumesh.db import Job

                job = session.get(Job, job_id)
                if job is None:
                    yield 'data: {"error":{"message":"unknown job","type":"server_error","code":"unknown_job"}}\n\n'
                    yield "data: [DONE]\n\n"
                    return
                snap = job_snapshot(job)
                fresh = chunks_after(session, job_id, sent)
                chunk_payloads = [(row.seq, row.text) for row in fresh]
            if not started:
                yield _chunk_line(snap, {"role": "assistant"}, None)
                started = True
            for seq, text in chunk_payloads:
                if text:
                    yield _chunk_line(snap, {"content": text}, None)
                sent = seq
            if snap["status"] in CLIENT_READY:
                if sent < 0 and snap["status"] in DELIVERABLE and snap["output_text"]:
                    for piece in _pieces(snap["output_text"]):
                        if piece:
                            yield _chunk_line(snap, {"content": piece}, None)
                if snap["status"] in DELIVERABLE:
                    yield _chunk_line(snap, {}, snap["finish_reason"] or "stop")
                else:
                    message = snap["error"] or snap["status"]
                    yield f"data: {json.dumps({'error': {'message': message, 'type': 'server_error', 'code': snap['status']}})}\n\n"
                yield "data: [DONE]\n\n"
                return
            if time.monotonic() > deadline:
                status = await _fail_if_abandoned(app, job_id)
                code = "no_capacity" if status == "queued" else "timeout"
                yield f"data: {json.dumps({'error': {'message': 'timed out waiting for a node', 'type': 'server_error', 'code': code}})}\n\n"
                yield "data: [DONE]\n\n"
                return
            await asyncio.sleep(0.05)
    except asyncio.CancelledError:
        await _fail_if_abandoned(app, job_id)
        raise


@public.get("/api/stats")
def api_stats(request: Request) -> dict:
    with read_session(request.app) as session:
        return stats(session, request.app.state.settings)


@public.get("/api/receipts")
def api_receipts(request: Request, limit: int = 50, before_seq: int | None = None) -> dict:
    with read_session(request.app) as session:
        return receipt_page(session, limit, before_seq)


@public.get("/api/ledger")
def api_ledger(request: Request) -> dict:
    with read_session(request.app) as session:
        return ledger_export(session)


@public.get("/api/ledger/verify")
def api_ledger_verify(request: Request) -> dict:
    with read_session(request.app) as session:
        return full_verify(session)


@nodes.post("/api/nodes/register")
async def api_register(request: Request):
    spec = await _json_object(request)
    ip = _client_ip(request)
    settings = request.app.state.settings
    _hit(request, f"register:{ip}", settings.register_per_hour, 3600, "register")
    if settings.invite_only:
        presented = request.headers.get("x-gpumesh-invite", "") or str(spec.get("invite") or "")
        if not settings.invite_token or not _constant_eq(presented, settings.invite_token):
            raise MeshError(403, "an invite is required to join this cohort", "permission_error", "invite_required")
    with write_session(request.app) as session:
        from gpumesh.db import Node

        if session.query(Node).count() >= settings.max_nodes:
            raise MeshError(503, "the node cohort is full", "server_error", "cohort_full")
        node, token, receipt = register_node(session, settings, spec, ip)
        return {
            "node_id": node.id,
            "token": token,
            "receipt": receipt,
            "status": node.status,
        }


@nodes.post("/api/nodes/credentials/rotate")
def api_rotate(request: Request):
    with write_session(request.app) as session:
        node = _auth_node(request, session)
        token = rotate_credential(session, node)
        return {"node_id": node.id, "token": token}


@nodes.post("/api/nodes/heartbeat")
async def api_heartbeat(request: Request):
    spec = await _json_object(request)
    ip = _client_ip(request)
    with write_session(request.app) as session:
        node = _auth_node(request, session)
        heartbeat(session, node, spec, ip)
        return {"ok": True, "node_id": node.id, "status": node.status}


@nodes.post("/api/nodes/jobs/claim")
async def api_claim(request: Request):
    try:
        wait = float(request.query_params.get("wait", "20"))
    except ValueError as exc:
        raise MeshError(400, "wait must be a number", code="bad_wait") from exc
    wait = max(0.0, min(wait, 25))
    deadline = time.monotonic() + wait
    while True:
        with write_session(request.app) as session:
            node = _auth_node(request, session)
            job = claim_job(session, request.app.state.settings, node)
            payload = job_for_node(job) if job is not None else None
        if payload is not None or time.monotonic() >= deadline:
            return {"job": payload}
        await asyncio.sleep(0.2)


@nodes.post("/api/nodes/jobs/{job_id}/chunks")
async def api_chunks(request: Request, job_id: str):
    spec = await _json_object(request)
    try:
        seq = int(spec.get("seq"))
    except (TypeError, ValueError) as exc:
        raise MeshError(400, "seq is required", code="bad_seq") from exc
    text = str(spec.get("text") or "")
    with write_session(request.app) as session:
        node = _auth_node(request, session)
        add_chunk(session, node, job_id, seq, text)
    return {"ok": True}


@nodes.post("/api/nodes/jobs/{job_id}/result")
async def api_result(request: Request, job_id: str):
    spec = await _json_object(request)
    with write_session(request.app) as session:
        node = _auth_node(request, session)
        return submit_result(session, request.app.state.settings, node, job_id, spec)


@nodes.post("/api/nodes/jobs/{job_id}/fail")
async def api_fail(request: Request, job_id: str):
    spec = await _json_object(request)
    with write_session(request.app) as session:
        node = _auth_node(request, session)
        return submit_fail(session, request.app.state.settings, node, job_id, str(spec.get("error") or "failed"))


@admin.post("/api/admin/keys")
async def admin_keys(request: Request):
    _require_admin(request)
    spec = await _json_object(request)
    name = str(spec.get("name") or "key")
    try:
        rpm = int(spec.get("rpm") or request.app.state.settings.default_key_rpm)
    except (TypeError, ValueError) as exc:
        raise MeshError(400, "rpm must be an integer", code="bad_rpm") from exc
    with write_session(request.app) as session:
        row, secret = create_api_key(session, name, rpm)
        return {"id": row.id, "name": row.name, "rpm": row.rpm, "key": secret}


@admin.post("/api/admin/keys/{key_id}/revoke")
def admin_revoke(request: Request, key_id: str):
    _require_admin(request)
    with write_session(request.app) as session:
        revoke_api_key(session, key_id)
    return {"ok": True}


@admin.post("/api/admin/bans")
async def admin_ban(request: Request):
    _require_admin(request)
    spec = await _json_object(request)
    ip = str(spec.get("ip") or "").strip()
    if not ip:
        raise MeshError(400, "ip is required", code="ip_required")
    with write_session(request.app) as session:
        ban_ip(session, ip, str(spec.get("reason") or ""))
    return {"ok": True}


@admin.post("/api/admin/bans/lift")
async def admin_unban(request: Request):
    _require_admin(request)
    spec = await _json_object(request)
    ip = str(spec.get("ip") or "").strip()
    with write_session(request.app) as session:
        unban_ip(session, ip)
    return {"ok": True}


@admin.post("/api/admin/nodes/{node_id}/reinstate")
def admin_reinstate(request: Request, node_id: str):
    _require_admin(request)
    with write_session(request.app) as session:
        node = set_node_status(session, node_id, "online")
        return {"ok": True, "node_id": node.id, "status": node.status, "reputation": node.reputation}


@admin.post("/api/admin/nodes/{node_id}/revoke-credentials")
def admin_revoke_credentials(request: Request, node_id: str):
    _require_admin(request)
    with write_session(request.app) as session:
        count = revoke_node_credentials(session, node_id)
    return {"ok": True, "revoked": count}


@admin.get("/api/admin/jobs/failed")
def admin_failed(request: Request):
    _require_admin(request)
    with read_session(request.app) as session:
        return {"jobs": failed_jobs(session)}


@admin.post("/api/admin/ledger/anchor")
def admin_anchor(request: Request):
    _require_admin(request)
    from gpumesh.ledger_backend import get_backend

    backend = get_backend(request.app.state.settings.ledger_backend)
    with write_session(request.app) as session:
        return backend.anchor(session)


@public.get("/api/ledger/anchor")
def api_anchor(request: Request):
    from gpumesh.merkle import latest_anchor

    with read_session(request.app) as session:
        return {"anchor": latest_anchor(session), "backend": request.app.state.settings.ledger_backend}


@admin.post("/api/admin/nodes/{node_id}/ban")
def admin_ban_node(request: Request, node_id: str):
    _require_admin(request)
    with write_session(request.app) as session:
        node = set_node_status(session, node_id, "banned")
        return {"ok": True, "node_id": node.id, "status": node.status}


@admin.post("/api/admin/canary")
async def admin_canary(request: Request):
    _require_admin(request)
    model = None
    raw = await request.body()
    if raw:
        try:
            spec = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise MeshError(400, "request body must be JSON", code="invalid_json") from exc
        if not isinstance(spec, dict):
            raise MeshError(400, "JSON body must be an object", code="invalid_json")
        model = spec.get("model")
    with write_session(request.app) as session:
        job = enqueue_canary(session, request.app.state.settings, str(model) if model else None)
        if job is None:
            raise MeshError(503, "no online node to canary", "server_error", "no_capacity")
        return {"job_id": job.id, "model": job.model}


def _asset(name: str) -> str:
    path = ASSETS / name
    if not path.is_file():
        raise MeshError(404, f"missing asset {name}", code="missing_asset")
    return path.read_text(encoding="utf-8")


def external_base(request: Request) -> str:
    configured = request.app.state.settings.public_base_url.strip()
    if configured:
        return configured.rstrip("/")
    return str(request.base_url).rstrip("/")


@public.get("/install.sh")
def install_script(request: Request) -> Response:
    text = _asset("install.sh").replace("__DEFAULT_COORDINATOR__", external_base(request))
    return PlainTextResponse(text, media_type="text/x-shellscript")


@public.get("/gpumesh-node.service")
def unit_file() -> Response:
    return PlainTextResponse(_asset("gpumesh-node.service"), media_type="text/plain")


def _node_tarball() -> bytes:
    root = Path(gpumesh_node.__file__).resolve().parent
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as archive:
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            if "__pycache__" in path.parts or path.suffix == ".pyc":
                continue
            archive.add(path, arcname=str(Path("gpumesh_node") / path.relative_to(root)))
        req = b"httpx>=0.27\n"
        info = tarfile.TarInfo("requirements.txt")
        info.size = len(req)
        info.mtime = int(time.time())
        archive.addfile(info, io.BytesIO(req))
    return buf.getvalue()


@public.get("/dl/gpumesh-node.tar.gz")
def download_node(request: Request) -> Response:
    if request.app.state.tarball is None:
        request.app.state.tarball = _node_tarball()
    return Response(content=request.app.state.tarball, media_type="application/gzip")


@public.get("/dl/gpumesh-node.tar.gz.sha256")
def download_node_sha(request: Request) -> PlainTextResponse:
    if request.app.state.tarball is None:
        request.app.state.tarball = _node_tarball()
    digest = hashlib.sha256(request.app.state.tarball).hexdigest()
    return PlainTextResponse(f"{digest}  gpumesh-node.tar.gz\n")


@pages.get("/")
@pages.get("/contribute")
@pages.get("/nodes")
@pages.get("/receipts")
def dashboard_page() -> FileResponse:
    return FileResponse(STATIC / "index.html")
