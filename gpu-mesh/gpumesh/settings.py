"""Coordinator settings. Every field is overridden by ``GPU_MESH_<NAME>``."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GPU_MESH_", extra="ignore")

    database_url: str = "sqlite:///./data/gpumesh.db"
    data_dir: str = ""
    admin_token: str = ""
    host: str = "0.0.0.0"
    port: int = 8741
    log_level: str = "INFO"
    public_base_url: str = ""
    trust_proxy: bool = False

    heartbeat_timeout_sec: float = 30
    job_timeout_sec: float = 120
    request_timeout_sec: float = 90
    verify_queue_ttl_sec: float = 180
    max_attempts: int = 3
    verify_sample_rate: float = 0.1
    verify_similarity: float = 0.82
    canary_interval_sec: float = 45
    max_outstanding_verifications: int = 8
    prompt_retention_sec: float = 86400

    anon_rpm: int = 30
    default_key_rpm: int = 120
    register_per_hour: int = 10
    dup_per_min: int = 12
    flood_per_min: int = 40
    max_inflight_per_client: int = 2
    max_node_inflight: int = 1

    max_prompt_chars: int = 16000
    max_messages: int = 40
    max_completion_tokens: int = 1024
    max_output_chars: int = 64000

    max_queue_depth: int = 100
    max_global_inflight: int = 32
    anon_inflight: int = 1
    stream_timeout_sec: float = 60
    invite_only: bool = False
    invite_token: str = ""
    max_nodes: int = 64
    ledger_backend: str = "simulated"
    trust_min_age_sec: float = 7 * 24 * 3600
    trust_min_verified: int = 3
    kudos_free_max_tokens: int = 256
    suspicion_pause: int = 5
    starter_kudos: int = 25
    uptime_interval_sec: float = 600

    def resolved_data_dir(self) -> Path:
        if self.data_dir:
            return Path(self.data_dir)
        url = self.database_url
        if url.startswith("sqlite:///"):
            raw = url[len("sqlite:///") :]
            if raw and not raw.startswith("file:") and raw != ":memory:":
                return Path(raw).parent
        return Path("data")
