"""Job lifecycle: register, schedule, complete, spot-check, and credit.

Credits are a simulated ledger. They are not money, not a token, and they
cannot be transferred. A completed inference appends one hash-chained receipt.
A sample of those jobs is run again on a different node. Canaries (known
answers) run against whoever is online, including a network of one.
"""

from __future__ import annotations

import json
import logging
import random
import secrets
import time
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from gpumesh.canon import output_hash
from gpumesh.db import (
    ApiKey,
    Ban,
    Chunk,
    Job,
    LedgerEntry,
    Meta,
    Node,
    NodeCredential,
    Settlement,
    Usage,
)
from gpumesh.errors import MeshError
from gpumesh.ledger import append, entry_public, tip_status, verify_session
from gpumesh.settings import Settings
from gpumesh.textutil import canon_answer, judge_outputs

log = logging.getLogger("gpumesh.work")

TERMINAL = {"completed", "failed", "cancelled", "expired", "verified", "disputed", "rejected"}
CLIENT_READY = TERMINAL | {"verifying"}
DELIVERABLE = {"completed", "verifying", "verified", "disputed", "rejected"}
ACTIVE = ("leased", "running")
REPLAY = {"completed", "verifying", "verified", "disputed", "rejected", "failed", "cancelled", "expired"}
VERIFIER_PAY = 2
CANARY_PAY = 1
CANARY_PENALTY = 5
UPTIME_KUDOS = 1
QUARANTINE_STRIKES = 3
REPUTATION_FLOOR = 40
FAILURES_BEFORE_STRIKE = 5

CANARIES: tuple[tuple[str, str], ...] = (
    ("Reply with exactly the token: MESH_OK", "MESH_OK"),
    ("Reply with exactly: mesh-beacon-4c91", "mesh-beacon-4c91"),
    ("Repeat only this string: PING_MESH_9", "PING_MESH_9"),
)


def _as_int(value: object, default: int = 0) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(6)}"


def new_secret(prefix: str) -> str:
    return prefix + secrets.token_urlsafe(32)


def _loads(raw: str, fallback: Any) -> Any:
    try:
        return json.loads(raw) if raw else fallback
    except json.JSONDecodeError:
        return fallback


def model_ids_of(node: Node) -> list[str]:
    models = _loads(node.models_json, [])
    found: list[str] = []
    for item in models:
        if isinstance(item, dict) and item.get("id"):
            found.append(str(item["id"]))
        elif isinstance(item, str):
            found.append(item)
    return found


def _gpu_fields(gpu: dict | None) -> dict[str, Any]:
    gpu = gpu or {}
    return {
        "gpu_json": json.dumps(gpu, sort_keys=True),
        "gpu_name": str(gpu.get("model") or "cpu")[:160],
        "vram_mb": int(gpu.get("vram_mb") or 0),
        "gpu_count": int(gpu.get("count") or 0),
        "driver": str(gpu.get("driver") or "")[:64],
    }


def _normalize_backend(backend: str) -> str:
    if backend in {"cpu-fallback", "cpu"}:
        return "cpu"
    if backend in {"ollama", "vllm", "llamacpp"}:
        return backend
    raise MeshError(400, "backend must be ollama, vllm, llamacpp, or cpu", code="bad_backend")


def credit_weight(node: Node) -> int:
    if node.backend == "cpu" or node.vram_mb <= 0:
        return 1
    if node.vram_mb >= 20000:
        return 8
    if node.vram_mb >= 12000:
        return 4
    return 2


def inference_credits(node: Node, completion_tokens: int) -> int:
    tokens = max(1, completion_tokens)
    return tokens * credit_weight(node)


def _meta_get(session: Session, key: str, default: str = "") -> str:
    row = session.get(Meta, key)
    return row.value if row else default


def _meta_set(session: Session, key: str, value: str) -> None:
    row = session.get(Meta, key)
    if row is None:
        session.add(Meta(key=key, value=value))
    else:
        row.value = value


def ip_banned(session: Session, ip: str) -> bool:
    if not ip:
        return False
    row = session.scalar(select(Ban).where(Ban.kind == "ip", Ban.value == ip))
    return row is not None


def register_node(session: Session, settings: Settings, spec: dict, ip: str) -> tuple[Node, str, str]:
    if ip_banned(session, ip):
        raise MeshError(403, "this address is banned", "permission_error", "banned")
    name = str(spec.get("name") or "").strip()
    if not name or len(name) > 63:
        raise MeshError(400, "name is required (63 characters max)", code="bad_name")
    backend = _normalize_backend(str(spec.get("backend") or "cpu"))
    models = spec.get("models") or []
    if not isinstance(models, list) or not models:
        raise MeshError(400, "advertise at least one model", code="no_models")
    if len(models) > 64:
        raise MeshError(400, "too many models", code="too_many_models")
    clean_models = []
    for item in models:
        if isinstance(item, str):
            item = {"id": item, "resident": False}
        if not isinstance(item, dict) or not str(item.get("id") or "").strip():
            raise MeshError(400, "each model needs an id", code="bad_model")
        mid = str(item["id"]).strip()
        if len(mid) > 128 or any(c in mid for c in "\n\r\t"):
            raise MeshError(400, f"model id {mid!r} is not usable", code="bad_model")
        digest = str(item.get("digest") or "").strip()
        if not digest:
            digest = "cpu-fallback" if backend == "cpu" else "unpinned"
        clean_models.append(
            {
                "id": mid,
                "resident": bool(item.get("resident")),
                "source": str(item.get("source") or backend)[:32],
                "digest": digest[:128],
            }
        )
    requested = int(spec.get("max_inflight") or 1)
    cap = max(1, settings.max_node_inflight)
    token = new_secret("gmt_")
    from gpumesh.canon import hash_secret

    now = time.time()
    node = Node(
        id=new_id("node"),
        name=name,
        token_hash=hash_secret(token),
        backend=backend,
        models_json=json.dumps(clean_models),
        status="online",
        reputation=100,
        max_inflight=min(max(1, requested), cap),
        last_heartbeat=now,
        created_at=now,
        last_ip=ip[:64],
        version=str(spec.get("version") or "")[:32],
        **_gpu_fields(spec.get("gpu") if isinstance(spec.get("gpu"), dict) else None),
    )
    session.add(node)
    session.flush()
    _issue_credential(session, node, token, generation=1)
    entry = append(
        session,
        actor=node.id,
        kind="node_register",
        payload={
            "schema": "gpumesh.node_register.v1",
            "node_id": node.id,
            "name": node.name,
            "backend": node.backend,
            "gpu": node.gpu_name,
            "vram_mb": node.vram_mb,
            "models": [m["id"] for m in clean_models],
            "model_digests": [m["digest"] for m in clean_models],
            "credits": 0,
            "amount": 0,
        },
    )
    log.info("node registered %s name=%s backend=%s gpu=%s", node.id, node.name, node.backend, node.gpu_name)
    return node, token, entry.hash


def _issue_credential(session: Session, node: Node, token: str, generation: int | None = None) -> NodeCredential:
    from gpumesh.canon import hash_secret

    if generation is None:
        generation = 1 + int(
            session.scalar(select(func.max(NodeCredential.generation)).where(NodeCredential.node_id == node.id))
            or 0
        )
    row = NodeCredential(
        node_id=node.id,
        token_hash=hash_secret(token),
        generation=generation,
        revoked=0,
        created_at=time.time(),
    )
    session.add(row)
    node.token_hash = row.token_hash
    session.flush()
    return row


def node_by_token(session: Session, token: str) -> Node | None:
    from gpumesh.canon import hash_secret

    if not token:
        return None
    digest = hash_secret(token)
    cred = session.scalar(
        select(NodeCredential).where(NodeCredential.token_hash == digest, NodeCredential.revoked == 0)
    )
    if cred is not None:
        return session.get(Node, cred.node_id)
    node = session.scalar(select(Node).where(Node.token_hash == digest))
    if node is None:
        return None
    any_cred = session.scalar(
        select(func.count()).select_from(NodeCredential).where(NodeCredential.node_id == node.id)
    )
    if any_cred:
        return None
    return node


def rotate_credential(session: Session, node: Node) -> str:
    rows = list(session.scalars(select(NodeCredential).where(NodeCredential.node_id == node.id)))
    live = [row for row in rows if row.revoked == 0]
    if rows and not live:
        raise MeshError(401, "node credentials are revoked", "authentication_error", "revoked")
    now = time.time()
    for row in live:
        row.revoked = 1
        row.revoked_at = now
    token = new_secret("gmt_")
    _issue_credential(session, node, token)
    return token


def revoke_node_credentials(session: Session, node_id: str) -> int:
    node = session.get(Node, node_id)
    if node is None:
        raise MeshError(404, "unknown node", code="unknown_node")
    now = time.time()
    rows = list(
        session.scalars(
            select(NodeCredential).where(NodeCredential.node_id == node.id, NodeCredential.revoked == 0)
        )
    )
    for row in rows:
        row.revoked = 1
        row.revoked_at = now
    node.token_hash = f"revoked-{node.id}"
    return len(rows)


def heartbeat(session: Session, node: Node, spec: dict, ip: str) -> Node:
    if node.status == "banned":
        raise MeshError(403, "node banned", "permission_error", "banned")
    if ip_banned(session, ip):
        raise MeshError(403, "this address is banned", "permission_error", "banned")
    node.last_heartbeat = time.time()
    node.last_ip = (ip or node.last_ip)[:64]
    # Identity, GPU class, backend, and model ids are pinned at registration.
    # A heartbeat may only flip residency on a model that was already declared.
    if isinstance(spec.get("models"), list):
        known = _loads(node.models_json, [])
        by_id = {item.get("id"): item for item in known if isinstance(item, dict) and item.get("id")}
        changed = False
        for item in spec["models"][:64]:
            if not isinstance(item, dict) or "resident" not in item:
                continue
            current = by_id.get(str(item.get("id") or ""))
            if current is None:
                continue
            current["resident"] = bool(item.get("resident"))
            changed = True
        if changed:
            node.models_json = json.dumps(list(by_id.values()))
    if node.status == "offline":
        node.status = "online"
    _maybe_uptime(session, node)
    return node


def _capable_online(session: Session, model: str, exclude: set[str] | None = None) -> list[Node]:
    exclude = exclude or set()
    nodes = session.scalars(select(Node).where(Node.status == "online")).all()
    found = []
    for node in nodes:
        if node.id in exclude:
            continue
        if model in model_ids_of(node):
            found.append(node)
    return found


def _model_known(session: Session, model: str) -> bool:
    nodes = session.scalars(select(Node)).all()
    return any(model in model_ids_of(node) for node in nodes)


def _client_inflight(session: Session, client_key: str) -> int:
    return int(
        session.scalar(
            select(func.count())
            .select_from(Job)
            .where(Job.client_key == client_key, Job.status.in_(("queued", "leased", "running")))
        )
        or 0
    )


def _queue_depth(session: Session) -> int:
    return int(session.scalar(select(func.count()).select_from(Job).where(Job.status == "queued")) or 0)


def _global_inflight(session: Session) -> int:
    return int(
        session.scalar(select(func.count()).select_from(Job).where(Job.status.in_(ACTIVE))) or 0
    )


def enqueue_inference(
    session: Session,
    settings: Settings,
    *,
    model: str,
    messages: list[dict],
    temperature: float,
    max_tokens: int,
    seed: int | None,
    stop: list[str] | None,
    client_key: str,
    priority: int = 0,
    kudos_cost: int = 0,
) -> Job:
    # Unknown models are 404 even when this client already has work in flight.
    if not _model_known(session, model):
        raise MeshError(404, f"model {model} is not served by any node", code="model_not_found")
    cap = settings.max_inflight_per_client
    if client_key.startswith("ip:"):
        cap = min(cap, settings.anon_inflight)
    if _client_inflight(session, client_key) >= cap:
        raise MeshError(
            429,
            "too many jobs in flight for this client",
            "rate_limit_error",
            "inflight",
            headers={"retry-after": "5"},
        )
    online = _capable_online(session, model)
    if not online:
        raise MeshError(
            503,
            f"no online node is serving {model}",
            "server_error",
            "no_capacity",
            headers={"retry-after": "10"},
        )
    if _queue_depth(session) >= settings.max_queue_depth:
        raise MeshError(
            503,
            "the queue is full",
            "server_error",
            "queue_full",
            headers={"retry-after": "5"},
        )
    if _global_inflight(session) >= settings.max_global_inflight:
        raise MeshError(
            503,
            "too many jobs are running",
            "server_error",
            "overloaded",
            headers={"retry-after": "5"},
        )
    now = time.time()
    job = Job(
        id=new_id("job"),
        kind="inference",
        status="queued",
        model=model,
        messages_json=json.dumps(messages),
        temperature=temperature,
        max_tokens=max_tokens,
        seed=seed,
        stop_json=json.dumps(stop),
        max_attempts=settings.max_attempts,
        client_key=client_key,
        created_at=now,
        priority=max(0, int(priority)),
        kudos_cost=max(0, int(kudos_cost)),
    )
    session.add(job)
    session.flush()
    return job


def enqueue_canary(session: Session, settings: Settings, model: str | None = None) -> Job | None:
    nodes = list(session.scalars(select(Node).where(Node.status == "online")))
    if not nodes:
        return None
    outstanding = int(
        session.scalar(
            select(func.count())
            .select_from(Job)
            .where(Job.kind == "canary", Job.status.notin_(tuple(TERMINAL)))
        )
        or 0
    )
    if outstanding >= 4:
        return None
    if model is None:
        random.shuffle(nodes)
        picked = None
        for node in nodes:
            ids = model_ids_of(node)
            if ids:
                picked = random.choice(ids)
                break
        if picked is None:
            return None
        model = picked
    prompt, expected = random.choice(CANARIES)
    now = time.time()
    job = Job(
        id=new_id("job"),
        kind="canary",
        status="queued",
        model=model,
        messages_json=json.dumps([{"role": "user", "content": prompt}]),
        temperature=0,
        max_tokens=16,
        seed=0,
        stop_json="null",
        expected_text=expected,
        max_attempts=settings.max_attempts,
        client_key="canary",
        created_at=now,
    )
    session.add(job)
    session.flush()
    log.info("canary queued %s model=%s", job.id, model)
    return job


def maybe_inject_canary(session: Session, settings: Settings) -> None:
    if settings.canary_interval_sec <= 0:
        return
    last = float(_meta_get(session, "last_canary_at", "0") or 0)
    now = time.time()
    if now - last < settings.canary_interval_sec:
        return
    job = enqueue_canary(session, settings)
    if job is not None:
        _meta_set(session, "last_canary_at", str(now))


def _maybe_enqueue_verification(session: Session, settings: Settings, parent: Job) -> Job | None:
    if parent.kind != "inference":
        return None
    if settings.verify_sample_rate <= 0:
        return None
    if random.random() > settings.verify_sample_rate:
        return None
    outstanding = int(
        session.scalar(
            select(func.count())
            .select_from(Job)
            .where(Job.kind == "verification", Job.status.notin_(tuple(TERMINAL)))
        )
        or 0
    )
    if outstanding >= settings.max_outstanding_verifications:
        return None
    seed = parent.seed if parent.temperature <= 0 and parent.seed is not None else 0
    now = time.time()
    job = Job(
        id=new_id("job"),
        kind="verification",
        status="queued",
        model=parent.model,
        messages_json=parent.messages_json,
        temperature=0,
        max_tokens=parent.max_tokens,
        seed=seed,
        stop_json=parent.stop_json,
        origin_node_id=parent.assigned_node_id,
        parent_job_id=parent.id,
        excluded_nodes_json=json.dumps([parent.assigned_node_id] if parent.assigned_node_id else []),
        max_attempts=settings.max_attempts,
        client_key="verify",
        created_at=now,
    )
    session.add(job)
    session.flush()
    log.info("verification queued %s parent=%s exclude=%s", job.id, parent.id, parent.assigned_node_id)
    return job


def claim_job(session: Session, settings: Settings, node: Node) -> Job | None:
    # autoflush is off, so a sweep that just requeued a job must hit the database
    # before the queued-status filter runs.
    session.flush()
    if node.status != "online":
        return None
    if node.inflight >= node.max_inflight:
        return None
    ids = model_ids_of(node)
    if not ids:
        return None
    candidates = session.scalars(
        select(Job)
        .where(Job.status == "queued", Job.model.in_(ids))
        .order_by(Job.priority.desc(), Job.created_at.asc())
        .limit(40)
    ).all()
    now = time.time()
    for job in candidates:
        excluded = set(_loads(job.excluded_nodes_json, []))
        if node.id in excluded:
            continue
        if job.kind == "verification" and job.origin_node_id == node.id:
            continue
        if job.kind == "verification" and _skip_repeat_verifier(session, job, node):
            continue
        new_attempt = job.attempt + 1
        new_gen = int(job.lease_generation or 0) + 1
        deadline = now + settings.job_timeout_sec
        result = session.execute(
            update(Job)
            .where(Job.id == job.id, Job.status == "queued")
            .values(
                status="leased",
                assigned_node_id=node.id,
                assigned_at=now,
                deadline_at=deadline,
                lease_expires_at=deadline,
                lease_generation=new_gen,
                attempt=new_attempt,
                cancel_requested=0,
                model_digest=_digest_for(node, job.model),
            )
        )
        if result.rowcount != 1:
            continue
        job.status = "leased"
        job.assigned_node_id = node.id
        job.assigned_at = now
        job.deadline_at = deadline
        job.lease_expires_at = deadline
        job.lease_generation = new_gen
        job.attempt = new_attempt
        job.cancel_requested = 0
        job.model_digest = _digest_for(node, job.model)
        node.inflight += 1
        node.last_assigned = now
        session.flush()
        return job
    return None


def _digest_for(node: Node, model: str) -> str:
    for item in _loads(node.models_json, []):
        if isinstance(item, dict) and item.get("id") == model:
            return str(item.get("digest") or "")[:128]
    return ""


def _skip_repeat_verifier(session: Session, job: Job, node: Node) -> bool:
    """Prefer a checker that did not verify this origin last time, when another node exists."""
    if not job.origin_node_id:
        return False
    previous = session.scalar(
        select(Job)
        .where(
            Job.kind == "verification",
            Job.origin_node_id == job.origin_node_id,
            Job.assigned_node_id != "",
            Job.id != job.id,
        )
        .order_by(Job.completed_at.desc())
        .limit(1)
    )
    if previous is None or previous.assigned_node_id != node.id:
        return False
    others = [
        candidate
        for candidate in _capable_online(session, job.model, {job.origin_node_id, node.id})
        if candidate.status == "online"
    ]
    return bool(others)


def job_for_node(job: Job) -> dict[str, Any]:
    """What a node is allowed to see. Kind and expected answers stay on the coordinator."""
    return {
        "job_id": job.id,
        "model": job.model,
        "messages": _loads(job.messages_json, []),
        "temperature": job.temperature,
        "max_tokens": job.max_tokens,
        "seed": job.seed,
        "stop": _loads(job.stop_json, None),
        "deadline_at": job.deadline_at,
        "fencing_token": job.lease_generation,
        "lease_generation": job.lease_generation,
        "lease_expires_at": job.lease_expires_at,
        "model_digest": job.model_digest,
    }


def _owned(session: Session, node: Node, job_id: str) -> Job:
    job = session.get(Job, job_id)
    if job is None:
        raise MeshError(404, "unknown job", code="unknown_job")
    if job.assigned_node_id != node.id:
        raise MeshError(403, "job is not assigned to this node", "permission_error", "not_your_job")
    return job


def mark_running(session: Session, node: Node, job_id: str) -> None:
    job = _owned(session, node, job_id)
    if job.status == "leased":
        job.status = "running"
        job.started_at = time.time()


def add_chunk(session: Session, node: Node, job_id: str, seq: int, text: str) -> None:
    job = _owned(session, node, job_id)
    if job.status in TERMINAL:
        return
    if job.status == "leased":
        job.status = "running"
        job.started_at = job.started_at or time.time()
    if len(text) > 8000:
        text = text[:8000]
    existing = session.scalar(select(Chunk).where(Chunk.job_id == job_id, Chunk.seq == seq))
    if existing is not None:
        return
    session.add(Chunk(job_id=job_id, seq=seq, text=text))


def _release_inflight(node: Node) -> None:
    node.inflight = max(0, node.inflight - 1)


def _exclude(job: Job, node_id: str) -> None:
    excluded = _loads(job.excluded_nodes_json, [])
    if node_id and node_id not in excluded:
        excluded.append(node_id)
    job.excluded_nodes_json = json.dumps(excluded)


def _requeue_or_fail(job: Job, node_id: str, error: str) -> str:
    _exclude(job, node_id)
    job.assigned_node_id = ""
    job.assigned_at = 0
    job.deadline_at = 0
    job.lease_expires_at = 0
    job.error = error[:500]
    if job.attempt >= job.max_attempts:
        job.status = "failed"
        job.completed_at = time.time()
        return "failed"
    job.status = "queued"
    return "queued"


def _note_failure(session: Session, node: Node, job: Job, error: str) -> None:
    node.consecutive_failures += 1
    node.jobs_failed += 1
    if node.consecutive_failures >= FAILURES_BEFORE_STRIKE:
        node.consecutive_failures = 0
        _penalize(session, node, 1, f"repeated failures: {error[:120]}", job.id)


def _penalize(session: Session, node: Node, amount: int, reason: str, job_id: str) -> None:
    amount = max(1, int(amount))
    node.credits -= amount
    node.strikes += 1
    node.reputation = max(0, node.reputation - 15)
    entry = append(
        session,
        actor=node.id,
        kind="credit_penalty",
        payload={
            "schema": "gpumesh.credit_penalty.v1",
            "node_id": node.id,
            "job_id": job_id,
            "credits": -amount,
            "reason": reason,
            "strikes": node.strikes,
            "amount": -amount,
            "worker_id": node.id,
            "settlement_id": f"{job_id}:penalty",
        },
    )
    if node.status != "quarantined" and (
        node.strikes >= QUARANTINE_STRIKES or node.reputation < REPUTATION_FLOOR
    ):
        node.status = "quarantined"
        node.inflight = 0
        append(
            session,
            actor=node.id,
            kind="node_quarantine",
            payload={
                "schema": "gpumesh.node_quarantine.v1",
                "node_id": node.id,
                "job_id": job_id,
                "credits": 0,
                "reason": reason,
                "strikes": node.strikes,
                "reputation": node.reputation,
            },
        )
        log.warning("quarantined %s strikes=%s reputation=%s", node.id, node.strikes, node.reputation)
    return entry


def _pay(session: Session, node: Node, amount: int, kind: str, payload: dict) -> LedgerEntry:
    amount = int(amount)
    if amount > 0:
        _hold_kudos(session, node, amount)
    elif amount < 0:
        node.credits += amount
    body = dict(payload)
    body["credits"] = amount
    body["amount"] = amount
    body["node_id"] = node.id
    body["worker_id"] = node.id
    return append(session, actor=node.id, kind=kind, payload=body)


def _hold_kudos(session: Session, node: Node, amount: int) -> None:
    del session
    if node.trusted:
        node.credits += amount
    else:
        node.escrow_credits += amount


def _maybe_release(session: Session, settings: Settings, node: Node) -> None:
    if node.trusted:
        return
    if time.time() - node.created_at < settings.trust_min_age_sec:
        return
    if node.verified_jobs < settings.trust_min_verified:
        return
    node.trusted = 1
    released = int(node.escrow_credits or 0)
    node.credits += released
    node.escrow_credits = 0
    if released:
        append(
            session,
            actor=node.id,
            kind="kudos_release",
            payload={
                "schema": "gpumesh.kudos_release.v1",
                "node_id": node.id,
                "worker_id": node.id,
                "amount": released,
                "credits": released,
                "settlement_id": f"{node.id}:kudos_release:{node.verified_jobs}",
                "reason": "trusted",
            },
        )


def _maybe_uptime(session: Session, node: Node) -> None:
    now = time.time()
    previous = node.last_uptime_at or node.created_at or now
    if now - previous < 600:
        return
    node.last_uptime_at = now
    _hold_kudos(session, node, UPTIME_KUDOS)
    append(
        session,
        actor=node.id,
        kind="uptime_kudos",
        payload={
            "schema": "gpumesh.uptime_kudos.v1",
            "node_id": node.id,
            "worker_id": node.id,
            "amount": UPTIME_KUDOS,
            "credits": UPTIME_KUDOS,
            "escrow": 0 if node.trusted else 1,
            "settlement_id": f"{node.id}:uptime:{int(now)}",
        },
    )


def _suspect(settings: Settings, node: Node, points: int) -> None:
    node.suspicion = int(node.suspicion or 0) + max(1, points)
    if node.status == "online" and node.suspicion >= settings.suspicion_pause:
        node.status = "paused"
        node.inflight = 0


def _refund_kudos(session: Session, job: Job) -> None:
    if job.kudos_cost <= 0 or job.kudos_refunded:
        return
    if not str(job.client_key).startswith("key:"):
        job.kudos_refunded = 1
        return
    key_id = job.client_key.removeprefix("key:")
    row = session.get(ApiKey, key_id)
    if row is not None:
        row.kudos += job.kudos_cost
    job.kudos_refunded = 1


def _meter(session: Session, job: Job) -> None:
    if not job.client_key or job.client_key in {"canary", "verify"}:
        return
    day = time.strftime("%Y-%m-%d", time.gmtime(job.completed_at or time.time()))
    row = session.scalar(
        select(Usage).where(Usage.client_key == job.client_key, Usage.model == job.model, Usage.day == day)
    )
    if row is None:
        row = Usage(client_key=job.client_key, model=job.model, day=day, requests=0, prompt_tokens=0, completion_tokens=0)
        session.add(row)
    row.requests += 1
    row.prompt_tokens += int(job.prompt_tokens or 0)
    row.completion_tokens += int(job.completion_tokens or 0)


def _hash_for_seq(session: Session, seq: int) -> str:
    row = session.get(LedgerEntry, seq)
    return row.hash if row is not None else ""


def settle_once(
    session: Session,
    *,
    key: str,
    job: Job,
    node: Node,
    kind: str,
    amount: int,
    payload: dict,
    settings: Settings | None = None,
) -> tuple[str, int]:
    """Insert one settlement. A unique key makes a replay or a race a no-op."""
    body = dict(payload)
    body["settlement_id"] = key
    body["worker_id"] = node.id
    body["node_id"] = node.id
    for _attempt in range(6):
        existing = session.scalar(select(Settlement).where(Settlement.idempotency_key == key))
        if existing is not None:
            return _hash_for_seq(session, existing.ledger_seq), int(existing.credits)
        try:
            with session.begin_nested():
                if amount == 0:
                    body["credits"] = 0
                    body["amount"] = 0
                    entry = append(session, actor=node.id, kind=kind, payload=body)
                else:
                    entry = _pay(session, node, amount, kind, body)
                session.add(
                    Settlement(
                        idempotency_key=key,
                        job_id=job.id,
                        node_id=node.id,
                        kind=kind,
                        credits=int(amount),
                        ledger_seq=entry.seq,
                        lease_generation=int(job.lease_generation or 0),
                    )
                )
                session.flush()
        except IntegrityError:
            session.expire(node)
            existing = session.scalar(select(Settlement).where(Settlement.idempotency_key == key))
            if existing is not None:
                return _hash_for_seq(session, existing.ledger_seq), int(existing.credits)
            continue
        if amount > 0 and settings is not None and kind in {"inference_receipt", "canary_pass", "verification_pass"}:
            node.verified_jobs += 1
            _maybe_release(session, settings, node)
        return entry.hash, int(amount)
    raise MeshError(409, "settlement could not be recorded", code="settle_race")


def submit_fail(session: Session, settings: Settings, node: Node, job_id: str, error: str) -> dict:
    job = _owned(session, node, job_id)
    if job.status in REPLAY:
        return {"ok": True, "status": job.status}
    _release_inflight(node)
    status = _requeue_or_fail(job, node.id, error or "node reported failure")
    _note_failure(session, node, job, error or "node reported failure")
    _suspect(settings, node, 1)
    if status == "failed":
        _refund_kudos(session, job)
    return {"ok": True, "status": status, "job_id": job.id}


def _presented_fence(spec: dict) -> int | None:
    if "fencing_token" not in spec or spec.get("fencing_token") is None or spec.get("fencing_token") == "":
        return None
    try:
        return int(spec["fencing_token"])
    except (TypeError, ValueError):
        return -1


def _store_toploc(job: Job, spec: dict) -> None:
    proofs = spec.get("toploc_proofs")
    if isinstance(proofs, list) and proofs and all(isinstance(item, str) for item in proofs):
        job.toploc_proofs = json.dumps(proofs[:32])
        source = str(spec.get("toploc_source") or "")
        job.toploc_source = source if source in {"prompt-trace", "hidden-state"} else "prompt-trace"


def submit_result(session: Session, settings: Settings, node: Node, job_id: str, spec: dict) -> dict:
    job = session.get(Job, job_id)
    if job is None:
        raise MeshError(404, "unknown job", code="unknown_job")
    if job.status in REPLAY and job.assigned_node_id == node.id:
        return _result_body(job)
    if job.assigned_node_id != node.id:
        raise MeshError(403, "job is not assigned to this node", "permission_error", "not_your_job")
    if _presented_fence(spec) != int(job.lease_generation or 0):
        raise MeshError(409, "stale lease", code="stale_lease")
    if job.lease_expires_at and time.time() > job.lease_expires_at:
        raise MeshError(409, "lease expired", code="lease_expired")
    if job.status in REPLAY:
        raise MeshError(409, f"job is {job.status}", code="job_closed")
    if job.status not in ACTIVE:
        raise MeshError(409, f"job is {job.status}", code="job_not_active")

    text = str(spec.get("output_text") if spec.get("output_text") is not None else "")
    if len(text) > settings.max_output_chars:
        text = text[: settings.max_output_chars]
        finish = "length"
    else:
        finish = spec.get("finish_reason") if spec.get("finish_reason") in {"stop", "length", "error"} else "stop"
    prompt_tokens = min(_as_int(spec.get("prompt_tokens")), settings.max_prompt_chars)
    completion_tokens = min(
        _as_int(spec.get("completion_tokens")),
        max(job.max_tokens, 1),
        settings.max_completion_tokens,
    )
    if completion_tokens <= 0:
        completion_tokens = max(1, len(text.split())) if text.strip() else 0
    duration_ms = min(max(_as_int(spec.get("duration_ms")), 0), 3_600_000)

    if not text.strip():
        _release_inflight(node)
        status = _requeue_or_fail(job, node.id, "empty output")
        _note_failure(session, node, job, "empty output")
        _suspect(settings, node, 1)
        return {"ok": False, "status": status, "job_id": job.id, "error": "empty output"}

    job.output_text = text
    job.output_hash = output_hash(text)
    job.prompt_tokens = prompt_tokens
    job.completion_tokens = completion_tokens
    job.duration_ms = duration_ms
    job.finish_reason = finish
    job.completed_at = time.time()
    job.error = ""
    _store_toploc(job, spec)
    _release_inflight(node)
    node.consecutive_failures = 0
    node.jobs_completed += 1
    # Absurdly fast replies are a GPU-backend signal. The CPU stub and the
    # llama.cpp worker both answer canaries immediately, so they are not flagged.
    if node.backend in {"ollama", "vllm"} and duration_ms < 20 and completion_tokens >= 1:
        _suspect(settings, node, 2)
    _meter(session, job)

    receipt_hash = ""
    credits = 0
    verdict = ""

    if job.cancel_requested:
        job.status = "cancelled"
        job.verdict = "cancelled"
        job.credits_awarded = 0
        _refund_kudos(session, job)
        receipt_hash, _credits = settle_once(
            session,
            key=f"{job.id}:cancelled",
            job=job,
            node=node,
            kind="execution_submitted",
            amount=0,
            payload=_execution_payload(node, job, 0, "cancelled"),
            settings=settings,
        )
        job.receipt_hash = receipt_hash
        return _result_body(job)

    job.status = "completed"
    if job.kind == "canary":
        verdict, credits, receipt_hash = _settle_canary(session, settings, node, job)
        job.status = "verified" if verdict == "canary_pass" else "rejected"
    elif job.kind == "verification":
        verdict, credits, receipt_hash = _settle_verification(session, settings, node, job, spec)
        job.status = "verified" if verdict == "agree" else "disputed"
    else:
        receipt_hash, _zero = settle_once(
            session,
            key=f"{job.id}:execution",
            job=job,
            node=node,
            kind="execution_submitted",
            amount=0,
            payload=_execution_payload(node, job, 0, "pending"),
            settings=settings,
        )
        credits = 0
        job.credits_awarded = 0
        verdict = "pending"
        if _maybe_enqueue_verification(session, settings, job) is not None:
            job.status = "verifying"
        else:
            job.status = "completed"

    job.receipt_hash = receipt_hash
    job.verdict = verdict
    if job.kind != "inference":
        job.credits_awarded = credits
    log.info(
        "job %s kind=%s node=%s model=%s tokens=%s duration_ms=%s verdict=%s",
        job.id,
        job.kind,
        node.id,
        job.model,
        completion_tokens,
        duration_ms,
        verdict,
    )
    return _result_body(job)


def _execution_payload(node: Node, job: Job, amount: int, decision: str) -> dict[str, Any]:
    return {
        "schema": "gpumesh.execution.v1",
        "job_id": job.id,
        "lease_generation": int(job.lease_generation or 0),
        "node_id": node.id,
        "worker_id": node.id,
        "model": job.model,
        "model_digest": job.model_digest or "",
        "runtime": node.backend,
        "backend": node.backend,
        "temperature": job.temperature,
        "max_tokens": job.max_tokens,
        "seed": 0 if job.seed is None else int(job.seed),
        "prompt_tokens": job.prompt_tokens,
        "completion_tokens": job.completion_tokens,
        "duration_ms": job.duration_ms,
        "output_hash": job.output_hash,
        "verifier_decision": decision,
        "verifier_ids": "",
        "amount": amount,
        "credits": amount,
    }


def _settle_canary(session: Session, settings: Settings, node: Node, job: Job) -> tuple[str, int, str]:
    ok = canon_answer(job.output_text) == canon_answer(job.expected_text)
    if ok:
        node.reputation = min(100, node.reputation + 1)
        receipt, credits = settle_once(
            session,
            key=f"{job.id}:canary_award",
            job=job,
            node=node,
            kind="canary_pass",
            amount=CANARY_PAY,
            payload={
                "schema": "gpumesh.canary_pass.v1",
                "job_id": job.id,
                "model": job.model,
                "output_hash": job.output_hash,
                "duration_ms": job.duration_ms,
                "prompt_tokens": job.prompt_tokens,
                "completion_tokens": job.completion_tokens,
                "verifier_decision": "canary_pass",
            },
            settings=settings,
        )
        return "canary_pass", credits, receipt
    _penalize(session, node, CANARY_PENALTY, "canary mismatch", job.id)
    _suspect(settings, node, 2)
    receipt, _credits = settle_once(
        session,
        key=f"{job.id}:canary_fail",
        job=job,
        node=node,
        kind="canary_fail",
        amount=0,
        payload={
            "schema": "gpumesh.canary_fail.v1",
            "job_id": job.id,
            "model": job.model,
            "output_hash": job.output_hash,
            "expected_hash": output_hash(job.expected_text),
            "verifier_decision": "canary_fail",
        },
        settings=settings,
    )
    return "canary_fail", 0, receipt


def _toploc_verdict(parent: Job, spec: dict) -> dict[str, str | bool]:
    from gpumesh_node.toploc_proof import library_ready, verify_hidden_proofs, verify_prompt_proofs

    if not library_ready():
        # Text spot-checks still run. A missing proof fails only when the
        # proof extra is installed, which is what a public coordinator should do
        # before it treats TOPLOC as required.
        return {"ok": True, "status": "unavailable"}
    proofs = _loads(parent.toploc_proofs, [])
    if not isinstance(proofs, list) or not proofs:
        return {"ok": False, "status": "missing"}
    if parent.toploc_source == "hidden-state":
        rows = spec.get("toploc_activations")
        report = verify_hidden_proofs(rows if isinstance(rows, list) else [], [str(item) for item in proofs])
    else:
        report = verify_prompt_proofs(
            _loads(parent.messages_json, []),
            parent.model,
            [str(item) for item in proofs],
        )
    return {"ok": bool(report.get("ok")), "status": "pass" if report.get("ok") else "fail"}


def _settle_verification(session: Session, settings: Settings, node: Node, job: Job, spec: dict | None = None) -> tuple[str, int, str]:
    parent = session.get(Job, job.parent_job_id) if job.parent_job_id else None
    if parent is None or not parent.output_text:
        entry = append(
            session,
            actor=node.id,
            kind="verification_skip",
            payload={
                "schema": "gpumesh.verification_skip.v1",
                "node_id": node.id,
                "job_id": job.id,
                "parent_job_id": job.parent_job_id,
                "credits": 0,
                "reason": "parent missing",
            },
        )
        return "skip", 0, entry.hash

    verdict = judge_outputs(parent.output_text, job.output_text, parent.temperature, settings.verify_similarity)
    base = {
        "schema": "gpumesh.verification.v1",
        "job_id": job.id,
        "parent_job_id": parent.id,
        "model": job.model,
        "output_hash": job.output_hash,
        "parent_output_hash": parent.output_hash,
        "duration_ms": job.duration_ms,
        "prompt_tokens": job.prompt_tokens,
        "completion_tokens": job.completion_tokens,
        "origin_node_id": parent.assigned_node_id,
    }
    if verdict == "child_empty":
        _penalize(session, node, CANARY_PENALTY, "verification returned empty", job.id)
        _suspect(settings, node, 1)
        return "child_empty", 0, job.receipt_hash

    toploc = _toploc_verdict(parent, spec or {})
    # Activations for a hidden-state proof travel on the checker result, stored beside the proof field.
    base["verifier_ids"] = node.id
    base["verifier_decision"] = verdict
    base["toploc"] = toploc["status"]
    receipt, pay = settle_once(
        session,
        key=f"{job.id}:verifier_award",
        job=job,
        node=node,
        kind=_verification_kind(verdict),
        amount=VERIFIER_PAY,
        payload=base,
        settings=settings,
    )
    parent.verdict = verdict if toploc["ok"] else "toploc_fail"
    if verdict == "agree" and toploc["ok"] and not parent.cancel_requested:
        origin = session.get(Node, parent.assigned_node_id) if parent.assigned_node_id else None
        if origin is not None and origin.id != node.id:
            award = inference_credits(origin, parent.completion_tokens)
            award_hash, awarded = settle_once(
                session,
                key=f"{parent.id}:worker_award",
                job=parent,
                node=origin,
                kind="inference_receipt",
                amount=award,
                payload={
                    **_execution_payload(origin, parent, award, "agree"),
                    "verifier_ids": node.id,
                    "verifier_decision": "agree",
                    "toploc": toploc["status"],
                },
                settings=settings,
            )
            parent.credits_awarded = awarded
            parent.receipt_hash = award_hash
            parent.status = "verified"
            parent.verdict = "agree"
    else:
        parent.status = "disputed"
        if not toploc["ok"]:
            origin = session.get(Node, parent.assigned_node_id) if parent.assigned_node_id else None
            if origin is not None:
                _suspect(settings, origin, 3)
        if verdict in {"disagree_deterministic", "parent_empty"}:
            origin = session.get(Node, parent.assigned_node_id) if parent.assigned_node_id else None
            if origin is not None and origin.id != node.id:
                _penalize(
                    session,
                    origin,
                    max(1, parent.credits_awarded or 1),
                    "spot-check disagreed on a temperature-0 job" if verdict != "parent_empty" else "empty parent output",
                    parent.id,
                )
                parent.status = "disputed"
    return verdict if toploc["ok"] else "toploc_fail", pay, receipt


def _verification_kind(verdict: str) -> str:
    return {
        "agree": "verification_pass",
        "disagree_deterministic": "verification_fail",
        "disagree_sampling": "verification_disagree",
        "parent_empty": "verification_fail",
    }.get(verdict, "verification_disagree")


def _result_body(job: Job) -> dict[str, Any]:
    return {
        "ok": job.status in DELIVERABLE or job.status == "verified",
        "job_id": job.id,
        "status": job.status,
        "receipt": job.receipt_hash,
        "credits": job.credits_awarded,
        "verdict": job.verdict,
        "output_hash": job.output_hash,
    }


def job_phase(status: str) -> str:
    return {
        "queued": "submitted",
        "leased": "executing",
        "running": "executing",
        "completed": "executed",
        "verifying": "verifying",
        "verified": "credited",
        "disputed": "disputed",
        "rejected": "rejected",
    }.get(status, status)


def cancel_if_queued(session: Session, job_id: str) -> None:
    abandon_job(session, job_id)


def abandon_job(session: Session, job_id: str) -> str:
    job = session.get(Job, job_id)
    if job is None:
        return "missing"
    prior = job.status
    if prior == "queued":
        job.status = "cancelled"
        job.error = "client gone"
        job.completed_at = time.time()
        _refund_kudos(session, job)
        return "queued"
    if prior == "leased":
        node = session.get(Node, job.assigned_node_id) if job.assigned_node_id else None
        if node is not None:
            _release_inflight(node)
        job.status = "cancelled"
        job.error = "client gone"
        job.completed_at = time.time()
        job.lease_expires_at = time.time()
        _refund_kudos(session, job)
        return "leased"
    if prior == "running":
        job.cancel_requested = 1
        return "running"
    return prior


def job_snapshot(job: Job) -> dict[str, Any]:
    return {
        "id": job.id,
        "kind": job.kind,
        "status": job.status,
        "model": job.model,
        "output_text": job.output_text,
        "output_hash": job.output_hash,
        "prompt_tokens": job.prompt_tokens,
        "completion_tokens": job.completion_tokens,
        "duration_ms": job.duration_ms,
        "finish_reason": job.finish_reason or "stop",
        "error": job.error,
        "verdict": job.verdict,
        "phase": job_phase(job.status),
        "receipt_hash": job.receipt_hash,
        "assigned_node_id": job.assigned_node_id,
        "credits_awarded": job.credits_awarded,
        "created_at": job.created_at,
        "completed_at": job.completed_at,
        "temperature": job.temperature,
    }


def chunks_after(session: Session, job_id: str, seq: int) -> list[Chunk]:
    return list(
        session.scalars(
            select(Chunk).where(Chunk.job_id == job_id, Chunk.seq > seq).order_by(Chunk.seq.asc())
        )
    )


def sweep(session: Session, settings: Settings) -> None:
    now = time.time()
    stale = session.scalars(
        select(Node).where(Node.status == "online", Node.last_heartbeat < now - settings.heartbeat_timeout_sec)
    ).all()
    for node in stale:
        node.status = "offline"
        node.inflight = 0
        jobs = session.scalars(
            select(Job).where(Job.assigned_node_id == node.id, Job.status.in_(ACTIVE))
        ).all()
        for job in jobs:
            if _requeue_or_fail(job, node.id, "heartbeat timeout") == "failed":
                _refund_kudos(session, job)
        if jobs:
            log.info("node %s offline, requeued %s jobs", node.id, len(jobs))

    overdue = session.scalars(
        select(Job).where(Job.status.in_(ACTIVE), Job.deadline_at > 0, Job.deadline_at < now)
    ).all()
    for job in overdue:
        node = session.get(Node, job.assigned_node_id) if job.assigned_node_id else None
        if node is not None:
            _release_inflight(node)
            _note_failure(session, node, job, "deadline exceeded")
        else:
            if _requeue_or_fail(job, job.assigned_node_id, "deadline exceeded") == "failed":
                _refund_kudos(session, job)
            continue
        if _requeue_or_fail(job, node.id, "deadline exceeded") == "failed":
            _refund_kudos(session, job)

    queued = session.scalars(select(Job).where(Job.status == "queued")).all()
    online = list(session.scalars(select(Node).where(Node.status == "online")))
    for job in queued:
        age = now - job.created_at
        if job.kind == "verification" and age > settings.verify_queue_ttl_sec:
            job.status = "expired"
            job.error = "no second node in time"
            job.completed_at = now
            _refund_kudos(session, job)
            parent = session.get(Job, job.parent_job_id) if job.parent_job_id else None
            if parent is not None and parent.status == "verifying":
                parent.status = "completed"
                parent.verdict = "unverified"
            continue
        if job.attempt <= 0 or age < 15:
            continue
        capable = {n.id for n in online if job.model in model_ids_of(n)}
        excluded = set(_loads(job.excluded_nodes_json, []))
        if capable and capable.issubset(excluded):
            if job.attempt >= job.max_attempts:
                job.status = "failed"
                job.error = "no capable node left"
                job.completed_at = now
                _refund_kudos(session, job)
            else:
                job.excluded_nodes_json = "[]"

    if settings.prompt_retention_sec > 0:
        cutoff = now - settings.prompt_retention_sec
        old = session.scalars(
            select(Job).where(Job.status.in_(tuple(TERMINAL)), Job.completed_at > 0, Job.completed_at < cutoff)
        ).all()
        for job in old:
            if job.messages_json not in ("[]", ""):
                job.messages_json = "[]"

    maybe_inject_canary(session, settings)


def create_api_key(session: Session, name: str, rpm: int) -> tuple[ApiKey, str]:
    from gpumesh.canon import hash_secret

    secret = new_secret("sk-mesh-")
    row = ApiKey(
        id=new_id("key"),
        name=name[:64] or "key",
        key_hash=hash_secret(secret),
        rpm=max(1, rpm),
        created_at=time.time(),
        revoked=0,
        kudos=25,
    )
    session.add(row)
    session.flush()
    return row, secret


def revoke_api_key(session: Session, key_id: str) -> None:
    row = session.get(ApiKey, key_id)
    if row is None:
        raise MeshError(404, "unknown key", code="unknown_key")
    row.revoked = 1


def ban_ip(session: Session, ip: str, reason: str) -> None:
    if session.scalar(select(Ban).where(Ban.kind == "ip", Ban.value == ip)):
        return
    session.add(Ban(kind="ip", value=ip[:80], reason=reason[:200], created_at=time.time()))


def unban_ip(session: Session, ip: str) -> None:
    row = session.scalar(select(Ban).where(Ban.kind == "ip", Ban.value == ip))
    if row is not None:
        session.delete(row)


def set_node_status(session: Session, node_id: str, status: str) -> Node:
    node = session.get(Node, node_id)
    if node is None:
        raise MeshError(404, "unknown node", code="unknown_node")
    if status == "online":
        node.status = "online"
        node.strikes = 0
        node.reputation = max(node.reputation, 70)
        append(
            session,
            actor=node.id,
            kind="node_reinstated",
            payload={
                "schema": "gpumesh.node_reinstated.v1",
                "node_id": node.id,
                "credits": 0,
                "reputation": node.reputation,
            },
        )
    elif status == "banned":
        node.status = "banned"
        append(
            session,
            actor=node.id,
            kind="node_banned",
            payload={"schema": "gpumesh.node_banned.v1", "node_id": node.id, "credits": 0},
        )
    else:
        raise MeshError(400, "status must be online or banned", code="bad_status")
    return node


def list_public_models(session: Session) -> list[dict[str, Any]]:
    nodes = list(session.scalars(select(Node).where(Node.status == "online")))
    merged: dict[str, dict[str, Any]] = {}
    for node in nodes:
        for item in _loads(node.models_json, []):
            if not isinstance(item, dict):
                continue
            mid = item.get("id")
            if not mid:
                continue
            slot = merged.setdefault(
                mid,
                {
                    "id": mid,
                    "object": "model",
                    "created": int(node.created_at or time.time()),
                    "owned_by": "gpumesh",
                    "gpumesh": {
                        "online_nodes": 0,
                        "resident_nodes": 0,
                        "backends": [],
                        "notice": "",
                    },
                },
            )
            slot["gpumesh"]["online_nodes"] += 1
            if item.get("resident"):
                slot["gpumesh"]["resident_nodes"] += 1
            if node.backend not in slot["gpumesh"]["backends"]:
                slot["gpumesh"]["backends"].append(node.backend)
            if node.backend == "cpu":
                slot["gpumesh"]["notice"] = "deterministic CPU fallback, not a neural model"
    return sorted(merged.values(), key=lambda row: row["id"])


def stats(session: Session, settings: Settings) -> dict[str, Any]:
    now = time.time()
    nodes = list(session.scalars(select(Node).order_by(Node.credits.desc(), Node.jobs_completed.desc())))
    online = [n for n in nodes if n.status == "online"]
    recent_cut = now - 60
    completed_recent = int(
        session.scalar(
            select(func.count())
            .select_from(Job)
            .where(Job.status == "completed", Job.completed_at >= recent_cut)
        )
        or 0
    )
    jobs_completed = int(
        session.scalar(select(func.count()).select_from(Job).where(Job.status == "completed")) or 0
    )
    jobs_failed = int(session.scalar(select(func.count()).select_from(Job).where(Job.status == "failed")) or 0)
    queue_depth = int(session.scalar(select(func.count()).select_from(Job).where(Job.status == "queued")) or 0)
    inflight = int(
        session.scalar(
            select(func.count()).select_from(Job).where(Job.status.in_(ACTIVE))
        )
        or 0
    )
    names = {n.id: n.name for n in nodes}
    recent_jobs = session.scalars(select(Job).order_by(Job.created_at.desc()).limit(12)).all()
    recent_receipts = session.scalars(select(LedgerEntry).order_by(LedgerEntry.seq.desc()).limit(12)).all()
    chain = tip_status(session)
    return {
        "network": "gpu-mesh",
        "version": "0.1.0",
        "notice": "Integer kudos on the simulated ledger. Escrowed until a worker is trusted. Nothing is minted or sold.",
        "ledger_backend": "simulated",
        "online_nodes": len(online),
        "total_nodes": len(nodes),
        "quarantined_nodes": sum(1 for n in nodes if n.status == "quarantined"),
        "vram_mb_online": sum(n.vram_mb for n in online),
        "gpu_count_online": sum(n.gpu_count for n in online),
        "jobs_per_sec": round(completed_recent / 60, 4),
        "jobs_completed_last_minute": completed_recent,
        "jobs_completed": jobs_completed,
        "jobs_failed": jobs_failed,
        "queue_depth": queue_depth,
        "inflight": inflight,
        "ledger": chain,
        "public_base_url": settings.public_base_url,
        "models": list_public_models(session),
        "top_contributors": [_node_public(n) for n in nodes[:8]],
        "nodes": [_node_public(n, now) for n in nodes],
        "recent_jobs": [
            {
                "id": job.id,
                "kind": job.kind,
                "status": job.status,
                "model": job.model,
                "node_id": job.assigned_node_id,
                "node_name": names.get(job.assigned_node_id, ""),
                "duration_ms": job.duration_ms,
                "verdict": job.verdict,
                "phase": job_phase(job.status),
                "credits": job.credits_awarded,
                "created_at": job.created_at,
            }
            for job in recent_jobs
        ],
        "recent_receipts": [_receipt_brief(entry) for entry in recent_receipts],
        "metering": _metering(session),
    }


def _metering(session: Session) -> dict[str, Any]:
    rows = list(session.scalars(select(Usage)))
    by_model: dict[str, dict[str, int]] = {}
    prompt = completion = requests = 0
    for row in rows:
        prompt += row.prompt_tokens
        completion += row.completion_tokens
        requests += row.requests
        slot = by_model.setdefault(row.model, {"model": row.model, "requests": 0, "prompt_tokens": 0, "completion_tokens": 0})
        slot["requests"] += row.requests
        slot["prompt_tokens"] += row.prompt_tokens
        slot["completion_tokens"] += row.completion_tokens
    return {
        "requests": requests,
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "models": sorted(by_model.values(), key=lambda item: item["model"]),
    }


def failed_jobs(session: Session, limit: int = 50) -> list[dict[str, Any]]:
    rows = session.scalars(
        select(Job).where(Job.status.in_(("failed", "disputed", "rejected"))).order_by(Job.completed_at.desc()).limit(limit)
    ).all()
    return [
        {
            "id": job.id,
            "kind": job.kind,
            "status": job.status,
            "phase": job_phase(job.status),
            "model": job.model,
            "node_id": job.assigned_node_id,
            "error": job.error,
            "verdict": job.verdict,
        }
        for job in rows
    ]


def _node_public(node: Node, now: float | None = None) -> dict[str, Any]:
    now = now if now is not None else time.time()
    return {
        "node_id": node.id,
        "name": node.name,
        "status": node.status,
        "backend": node.backend,
        "gpu": node.gpu_name,
        "vram_mb": node.vram_mb,
        "gpu_count": node.gpu_count,
        "driver": node.driver,
        "models": model_ids_of(node),
        "reputation": node.reputation,
        "strikes": node.strikes,
        "credits": node.credits,
        "escrow_credits": node.escrow_credits,
        "suspicion": node.suspicion,
        "trusted": bool(node.trusted),
        "jobs_completed": node.jobs_completed,
        "jobs_failed": node.jobs_failed,
        "inflight": node.inflight,
        "last_seen_sec": max(0, int(now - node.last_heartbeat)) if node.last_heartbeat else None,
        "version": node.version,
    }


def _receipt_brief(entry: LedgerEntry) -> dict[str, Any]:
    payload = _loads(entry.payload, {})
    return {
        "seq": entry.seq,
        "ts": entry.ts,
        "actor": entry.actor,
        "kind": entry.kind,
        "hash": entry.hash,
        "prev_hash": entry.prev_hash,
        "credits": payload.get("credits") if isinstance(payload, dict) else None,
        "job_id": payload.get("job_id") if isinstance(payload, dict) else None,
        "model": payload.get("model") if isinstance(payload, dict) else None,
        "output_hash": payload.get("output_hash") if isinstance(payload, dict) else None,
    }


def receipt_page(session: Session, limit: int, before_seq: int | None) -> dict[str, Any]:
    stmt = select(LedgerEntry).order_by(LedgerEntry.seq.desc()).limit(min(max(limit, 1), 200))
    if before_seq:
        stmt = (
            select(LedgerEntry)
            .where(LedgerEntry.seq < before_seq)
            .order_by(LedgerEntry.seq.desc())
            .limit(min(max(limit, 1), 200))
        )
    rows = list(session.scalars(stmt))
    detailed = []
    for entry in rows:
        item = entry_public(entry)
        item["payload_obj"] = _loads(entry.payload, {})
        detailed.append(item)
    return {"receipts": detailed, "canon": "v1"}


def ledger_export(session: Session) -> dict[str, Any]:
    from gpumesh.canon import ALGORITHM, CANON

    rows = list(session.scalars(select(LedgerEntry).order_by(LedgerEntry.seq.asc())))
    return {
        "network": "GPU-MESH",
        "canon": CANON,
        "algorithm": ALGORITHM,
        "hashed_fields": ["actor", "kind", "payload", "prev_hash", "seq", "ts"],
        "note": "Simulated integer credits. Signed claims. Nothing is minted.",
        "entries": [entry_public(row) for row in rows],
    }


def full_verify(session: Session) -> dict[str, Any]:
    return verify_session(session)
