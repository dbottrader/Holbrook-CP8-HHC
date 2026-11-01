"""SQLAlchemy models and sessions. SQLite by default, Postgres when the URL says so."""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import Float, Integer, String, Text, UniqueConstraint, create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from gpumesh.settings import Settings


class Base(DeclarativeBase):
    pass


class Node(Base):
    __tablename__ = "nodes"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(64), default="")
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    backend: Mapped[str] = mapped_column(String(32), default="cpu")
    gpu_json: Mapped[str] = mapped_column(Text, default="{}")
    gpu_name: Mapped[str] = mapped_column(String(160), default="cpu")
    vram_mb: Mapped[int] = mapped_column(Integer, default=0)
    gpu_count: Mapped[int] = mapped_column(Integer, default=0)
    driver: Mapped[str] = mapped_column(String(64), default="")
    models_json: Mapped[str] = mapped_column(Text, default="[]")
    status: Mapped[str] = mapped_column(String(24), default="online", index=True)
    reputation: Mapped[int] = mapped_column(Integer, default=100)
    strikes: Mapped[int] = mapped_column(Integer, default=0)
    credits: Mapped[int] = mapped_column(Integer, default=0)
    escrow_credits: Mapped[int] = mapped_column(Integer, default=0)
    suspicion: Mapped[int] = mapped_column(Integer, default=0)
    trusted: Mapped[int] = mapped_column(Integer, default=0)
    verified_jobs: Mapped[int] = mapped_column(Integer, default=0)
    last_uptime_at: Mapped[float] = mapped_column(Float, default=0)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
    jobs_completed: Mapped[int] = mapped_column(Integer, default=0)
    jobs_failed: Mapped[int] = mapped_column(Integer, default=0)
    inflight: Mapped[int] = mapped_column(Integer, default=0)
    max_inflight: Mapped[int] = mapped_column(Integer, default=1)
    last_heartbeat: Mapped[float] = mapped_column(Float, default=0)
    last_assigned: Mapped[float] = mapped_column(Float, default=0)
    last_ip: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[float] = mapped_column(Float, default=0)
    version: Mapped[str] = mapped_column(String(32), default="")


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    kind: Mapped[str] = mapped_column(String(24), default="inference", index=True)
    status: Mapped[str] = mapped_column(String(24), default="queued", index=True)
    model: Mapped[str] = mapped_column(String(128), index=True)
    messages_json: Mapped[str] = mapped_column(Text, default="[]")
    temperature: Mapped[float] = mapped_column(Float, default=0)
    max_tokens: Mapped[int] = mapped_column(Integer, default=256)
    seed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stop_json: Mapped[str] = mapped_column(Text, default="null")
    assigned_node_id: Mapped[str] = mapped_column(String(40), default="")
    origin_node_id: Mapped[str] = mapped_column(String(40), default="")
    parent_job_id: Mapped[str] = mapped_column(String(40), default="")
    excluded_nodes_json: Mapped[str] = mapped_column(Text, default="[]")
    attempt: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    expected_text: Mapped[str] = mapped_column(Text, default="")
    output_text: Mapped[str] = mapped_column(Text, default="")
    output_hash: Mapped[str] = mapped_column(String(64), default="")
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    finish_reason: Mapped[str] = mapped_column(String(24), default="")
    credits_awarded: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(Text, default="")
    verdict: Mapped[str] = mapped_column(String(32), default="")
    client_key: Mapped[str] = mapped_column(String(80), default="", index=True)
    receipt_hash: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[float] = mapped_column(Float, default=0, index=True)
    assigned_at: Mapped[float] = mapped_column(Float, default=0)
    started_at: Mapped[float] = mapped_column(Float, default=0)
    completed_at: Mapped[float] = mapped_column(Float, default=0)
    deadline_at: Mapped[float] = mapped_column(Float, default=0)
    lease_generation: Mapped[int] = mapped_column(Integer, default=0)
    lease_expires_at: Mapped[float] = mapped_column(Float, default=0)
    model_digest: Mapped[str] = mapped_column(String(128), default="")
    cancel_requested: Mapped[int] = mapped_column(Integer, default=0)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    kudos_cost: Mapped[int] = mapped_column(Integer, default=0)
    kudos_refunded: Mapped[int] = mapped_column(Integer, default=0)
    toploc_proofs: Mapped[str] = mapped_column(Text, default="")
    toploc_source: Mapped[str] = mapped_column(String(32), default="")


class Chunk(Base):
    __tablename__ = "chunks"
    __table_args__ = (UniqueConstraint("job_id", "seq", name="uq_chunk_job_seq"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(String(40), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text, default="")


class LedgerEntry(Base):
    __tablename__ = "ledger"

    seq: Mapped[int] = mapped_column(Integer, primary_key=True)
    ts: Mapped[int] = mapped_column(Integer)
    actor: Mapped[str] = mapped_column(String(40), index=True)
    kind: Mapped[str] = mapped_column(String(40), index=True)
    payload: Mapped[str] = mapped_column(Text)
    prev_hash: Mapped[str] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64), unique=True)
    canon: Mapped[str] = mapped_column(String(16), default="v1")
    body_json: Mapped[str] = mapped_column(Text)
    signature: Mapped[str] = mapped_column(Text, default="")
    signer: Mapped[str] = mapped_column(String(128), default="")
    typed_json: Mapped[str] = mapped_column(Text, default="")
    amount: Mapped[int] = mapped_column(Integer, default=0)


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(64), default="")
    key_hash: Mapped[str] = mapped_column(String(64), unique=True)
    rpm: Mapped[int] = mapped_column(Integer, default=120)
    created_at: Mapped[float] = mapped_column(Float, default=0)
    revoked: Mapped[int] = mapped_column(Integer, default=0)
    kudos: Mapped[int] = mapped_column(Integer, default=25)


class Ban(Base):
    __tablename__ = "bans"
    __table_args__ = (UniqueConstraint("kind", "value", name="uq_ban_kind_value"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(16))
    value: Mapped[str] = mapped_column(String(80))
    reason: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[float] = mapped_column(Float, default=0)


class Settlement(Base):
    """One row per credit movement. The unique key is the exactly-once backstop."""

    __tablename__ = "settlements"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_settlement_idempotency"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    idempotency_key: Mapped[str] = mapped_column(String(160))
    job_id: Mapped[str] = mapped_column(String(40), index=True, default="")
    node_id: Mapped[str] = mapped_column(String(40), index=True, default="")
    kind: Mapped[str] = mapped_column(String(40), default="")
    credits: Mapped[int] = mapped_column(Integer, default=0)
    ledger_seq: Mapped[int] = mapped_column(Integer, default=0)
    lease_generation: Mapped[int] = mapped_column(Integer, default=0)


class NodeCredential(Base):
    __tablename__ = "node_credentials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    node_id: Mapped[str] = mapped_column(String(40), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    generation: Mapped[int] = mapped_column(Integer, default=1)
    revoked: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[float] = mapped_column(Float, default=0)
    revoked_at: Mapped[float] = mapped_column(Float, default=0)


class Anchor(Base):
    """A local Merkle commitment of the receipt chain. published stays 0."""

    __tablename__ = "anchors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[float] = mapped_column(Float, default=0)
    from_seq: Mapped[int] = mapped_column(Integer, default=0)
    to_seq: Mapped[int] = mapped_column(Integer, default=0)
    count: Mapped[int] = mapped_column(Integer, default=0)
    root: Mapped[str] = mapped_column(String(64), default="")
    tip_hash: Mapped[str] = mapped_column(String(64), default="")
    backend: Mapped[str] = mapped_column(String(24), default="simulated")
    published: Mapped[int] = mapped_column(Integer, default=0)


class Usage(Base):
    """Per-key, per-model, per-day token meter. GPUStack-style usage, not a bill."""

    __tablename__ = "usage"
    __table_args__ = (UniqueConstraint("client_key", "model", "day", name="uq_usage_bucket"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    client_key: Mapped[str] = mapped_column(String(80), index=True, default="")
    model: Mapped[str] = mapped_column(String(128), default="")
    day: Mapped[str] = mapped_column(String(10), default="")
    requests: Mapped[int] = mapped_column(Integer, default=0)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)


class Meta(Base):
    __tablename__ = "meta"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")


def ensure_sqlite_parent(url: str) -> None:
    if not url.startswith("sqlite:///"):
        return
    raw = url[len("sqlite:///") :]
    if not raw or raw == ":memory:" or raw.startswith("file:"):
        return
    parent = Path(raw).parent
    if str(parent) not in ("", "."):
        parent.mkdir(parents=True, exist_ok=True)


def make_engine(url: str) -> Engine:
    ensure_sqlite_parent(url)
    if url.startswith("sqlite"):
        engine = create_engine(url, future=True, connect_args={"check_same_thread": False, "timeout": 30})

        @event.listens_for(engine, "connect")
        def _sqlite_pragmas(conn, _record) -> None:  # type: ignore[no-untyped-def]
            cursor = conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=30000")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        return engine
    return create_engine(url, future=True, pool_pre_ping=True)


def make_session_factory(engine: Engine) -> sessionmaker:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


@contextmanager
def session_scope(factory: sessionmaker, lock: threading.Lock | None = None) -> Iterator:
    if lock is not None:
        lock.acquire()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
        if lock is not None:
            lock.release()


def write_session(app) -> Iterator:  # noqa: ANN001
    return session_scope(app.state.Session, app.state.ledger_lock)


def read_session(app) -> Iterator:  # noqa: ANN001
    return session_scope(app.state.Session, None)


_COLUMN_ADDS: dict[str, dict[str, str]] = {
    "nodes": {
        "escrow_credits": "INTEGER DEFAULT 0",
        "suspicion": "INTEGER DEFAULT 0",
        "trusted": "INTEGER DEFAULT 0",
        "verified_jobs": "INTEGER DEFAULT 0",
        "last_uptime_at": "FLOAT DEFAULT 0",
    },
    "jobs": {
        "lease_generation": "INTEGER DEFAULT 0",
        "lease_expires_at": "FLOAT DEFAULT 0",
        "model_digest": "VARCHAR(128) DEFAULT ''",
        "cancel_requested": "INTEGER DEFAULT 0",
        "priority": "INTEGER DEFAULT 0",
        "kudos_cost": "INTEGER DEFAULT 0",
        "kudos_refunded": "INTEGER DEFAULT 0",
        "toploc_proofs": "TEXT DEFAULT ''",
        "toploc_source": "VARCHAR(32) DEFAULT ''",
    },
    "ledger": {
        "signature": "TEXT DEFAULT ''",
        "signer": "VARCHAR(128) DEFAULT ''",
        "typed_json": "TEXT DEFAULT ''",
        "amount": "INTEGER DEFAULT 0",
    },
    "api_keys": {"kudos": "INTEGER DEFAULT 25"},
}


def _migrate_columns(engine: Engine) -> None:
    from sqlalchemy import inspect

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    with engine.begin() as conn:
        for table, columns in _COLUMN_ADDS.items():
            if table not in existing_tables:
                continue
            have = {col["name"] for col in inspector.get_columns(table)}
            for name, ddl in columns.items():
                if name not in have:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))


def init_db(engine: Engine) -> None:
    from gpumesh.ledger import append_genesis

    Base.metadata.create_all(engine)
    _migrate_columns(engine)
    factory = make_session_factory(engine)
    with session_scope(factory) as session:
        existing = session.query(LedgerEntry).count()
        if existing == 0:
            append_genesis(session)


def postgres_ledger_lock(session) -> None:  # noqa: ANN001
    bind = session.get_bind()
    if bind is not None and bind.dialect.name == "postgresql":
        session.execute(text("SELECT pg_advisory_xact_lock(8741001)"))


def build_database(settings: Settings) -> tuple[Engine, sessionmaker]:
    from gpumesh.signing import configure_signer

    configure_signer(settings.resolved_data_dir() / "ledger_signing.key")
    engine = make_engine(settings.database_url)
    init_db(engine)
    return engine, make_session_factory(engine)
