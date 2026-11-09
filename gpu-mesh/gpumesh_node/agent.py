"""Pull-based miner loop. Jobs come from the coordinator; the node opens no inbound port."""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import logging
import os
import re
import subprocess
import time
from pathlib import Path

import httpx

from gpumesh_node import __version__
from gpumesh_node.gpu import CPU_GPU, probe_gpu
from gpumesh_node.runtime import InferenceResult, Runtime, generation_controls

log = logging.getLogger("gpumesh.node")
_PAYOUT = re.compile(r"^0x[0-9a-fA-F]{40}$")
# One claim HTTP call stays open this long. The hub checks the queue every
# few hundred milliseconds inside that call. Shorter HTTP waits would multiply
# Supabase edge invocations past the free-tier budget. The hub caps wait at 20s.
CLAIM_WAIT_SEC = 15.0
_REVISION: str | None = None


def agent_revision() -> str:
    """Git commit of this checkout, or the package version when git is absent."""

    global _REVISION
    if _REVISION is not None:
        return _REVISION
    for key in ("GPUMESH_COMMIT", "GIT_COMMIT", "SOURCE_COMMIT"):
        value = os.environ.get(key, "").strip()
        if value:
            _REVISION = value[:64]
            return _REVISION
    start = Path(__file__).resolve()
    for parent in start.parents:
        if not (parent / ".git").exists():
            continue
        try:
            out = subprocess.check_output(
                ["git", "rev-parse", "HEAD"],
                cwd=parent,
                stderr=subprocess.DEVNULL,
                timeout=2,
            )
        except (OSError, subprocess.SubprocessError):
            break
        text = out.decode().strip()
        if text:
            _REVISION = text[:64]
            return _REVISION
        break
    _REVISION = __version__
    return _REVISION


def normalize_payout_address(value: str) -> str:
    """Return a payout address, or empty when the worker has not set one."""

    text = str(value or "").strip()
    if not text:
        return ""
    if not _PAYOUT.match(text) or text.lower() == "0x" + ("0" * 40):
        raise ValueError("payout address must be a non-zero 0x EVM address")
    return text


class NodeAgent:
    def __init__(
        self,
        *,
        base_url: str,
        runtime: Runtime,
        name: str,
        http: httpx.AsyncClient | None = None,
        state_path: Path | None = None,
        heartbeat_sec: float = 10,
        claim_wait_sec: float = CLAIM_WAIT_SEC,
        invite: str = "",
        payout_address: str = "",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.runtime = runtime
        self.name = name
        self.http = http
        self._owns = http is None
        self.state_path = state_path
        self.heartbeat_sec = heartbeat_sec
        self.claim_wait_sec = claim_wait_sec
        self.invite = invite
        self.payout_address = normalize_payout_address(payout_address)
        self.token: str | None = None
        self.node_id: str | None = None
        self._gpu = probe_gpu() or dict(CPU_GPU)
        self._last_heartbeat = 0.0

    async def _client(self) -> httpx.AsyncClient:
        if self.http is None:
            self.http = httpx.AsyncClient(base_url=self.base_url, timeout=httpx.Timeout(30, read=140))
            self._owns = True
        return self.http

    def _headers(self) -> dict[str, str]:
        if not self.token:
            return {}
        return {"authorization": f"Bearer {self.token}"}

    def _load_state(self) -> bool:
        if self.state_path is None or not self.state_path.exists():
            return False
        data = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.token = data.get("token")
        self.node_id = data.get("node_id")
        return bool(self.token)

    def _save_state(self) -> None:
        if self.state_path is None:
            return
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({"node_id": self.node_id, "token": self.token})
        tmp = self.state_path.with_suffix(".tmp")
        tmp.write_text(payload, encoding="utf-8")
        try:
            os.chmod(tmp, 0o600)
        except OSError:
            pass
        tmp.replace(self.state_path)

    async def _body(self) -> dict:
        models = await self.runtime.list_models()
        self._gpu = probe_gpu() or self._gpu
        body = {
            "name": self.name,
            "backend": self.runtime.name,
            "gpu": self._gpu,
            "models": models,
            "version": __version__,
            "agent_commit": agent_revision(),
            "runtime_name": self.runtime.name,
            "runtime_version": str(getattr(self.runtime, "version", "") or ""),
            "max_inflight": 1,
        }
        if self.payout_address:
            body["payout_address"] = self.payout_address
        batch = os.environ.get("GPU_MESH_BATCH_ID", "").strip()
        if batch:
            body["batch_id"] = batch
        return body

    async def register(self, force: bool = False) -> None:
        if self.token and not force:
            return
        if not force and self._load_state():
            log.info("reusing node identity %s", self.node_id)
            return
        client = await self._client()
        headers = {"x-gpumesh-invite": self.invite} if self.invite else None
        response = await client.post("/api/nodes/register", json=await self._body(), headers=headers)
        if response.status_code >= 400:
            raise RuntimeError(f"register failed ({response.status_code}): {response.text}")
        data = response.json()
        self.token = data["token"]
        self.node_id = data["node_id"]
        self._save_state()
        log.info("registered %s as %s", self.node_id, self.name)

    async def heartbeat(self) -> dict:
        client = await self._client()
        response = await client.post("/api/nodes/heartbeat", json=await self._body(), headers=self._headers())
        if response.status_code == 401:
            log.warning("coordinator forgot this token; registering again")
            await self.register(force=True)
            response = await client.post("/api/nodes/heartbeat", json=await self._body(), headers=self._headers())
        if response.status_code == 403:
            log.error("this node is banned or the address is blocked; not minting a new identity")
            return {"ok": False, "status": "banned"}
        response.raise_for_status()
        return response.json()

    async def claim(self, wait: float = 20) -> dict | None:
        client = await self._client()
        response = await client.post(f"/api/nodes/jobs/claim?wait={wait}", headers=self._headers())
        if response.status_code == 401:
            await self.register(force=True)
            return None
        response.raise_for_status()
        if response.status_code == 204 or not response.content:
            return None
        return response.json().get("job")

    async def execute(self, job: dict) -> InferenceResult | None:
        seq = 0

        async def on_delta(text: str) -> None:
            nonlocal seq
            client = await self._client()
            response = await client.post(
                f"/api/nodes/jobs/{job['job_id']}/chunks",
                json={"seq": seq, "text": text},
                headers=self._headers(),
            )
            response.raise_for_status()
            seq += 1

        try:
            result = await self.runtime.complete(job, on_delta)
        except Exception as exc:
            log.exception("inference failed for %s", job.get("job_id"))
            client = await self._client()
            await client.post(
                f"/api/nodes/jobs/{job['job_id']}/fail",
                json={"error": str(exc)[:400]},
                headers=self._headers(),
            )
            return None
        proofs = None
        source = ""
        # Prompt-trace proofs bind the job to the prompt. Real Ollama, vLLM, and
        # llama.cpp workers do not set this. A test double can, so a machine
        # with TOPLOC installed still credits an exact match.
        if self.runtime.name == "cpu" or getattr(self.runtime, "prompt_proofs", False):
            try:
                from gpumesh_node.toploc_proof import build_prompt_proofs

                proofs = build_prompt_proofs(job.get("messages") or [], str(job.get("model") or ""))
                source = "prompt-trace" if proofs else ""
            except Exception:
                log.exception("TOPLOC proof was not built")
                proofs = None
        client = await self._client()
        if job.get("commit_required"):
            commitment = hashlib.sha256(result.text.encode("utf-8")).hexdigest()
            committed = await client.post(
                f"/api/nodes/jobs/{job['job_id']}/commit",
                json={"commitment": commitment, "fencing_token": job.get("fencing_token")},
                headers=self._headers(),
            )
            committed.raise_for_status()
        custom = getattr(self.runtime, "effective_generation", None)
        generation = custom(job) if custom is not None else generation_controls(job)
        body = {
            "output_text": result.text,
            "prompt_tokens": result.prompt_tokens,
            "completion_tokens": result.completion_tokens,
            "duration_ms": result.duration_ms,
            "finish_reason": result.finish_reason,
            "fencing_token": job.get("fencing_token"),
            "agent_commit": agent_revision(),
            "runtime_name": self.runtime.name,
            "runtime_version": str(getattr(self.runtime, "version", "") or ""),
            "generation": generation,
        }
        weights = os.environ.get("GPU_MESH_GGUF_SHA256", "").strip()
        if weights:
            body["weights_digest"] = weights
        if proofs:
            body["toploc_proofs"] = proofs
            body["toploc_source"] = source
        response = await client.post(
            f"/api/nodes/jobs/{job['job_id']}/result",
            json=body,
            headers=self._headers(),
        )
        response.raise_for_status()
        log.info("finished %s in %sms", job.get("job_id"), result.duration_ms)
        return result

    async def run_forever(self, stop: asyncio.Event) -> None:
        await self.register()
        if self.runtime.name == "llamacpp":
            note = "Open-weight GGUF via llama.cpp. No TOPLOC hidden-state proof is attached."
        else:
            note = "Local model server. No TOPLOC hidden-state proof is attached."
        log.info(
            "node %s online via %s (%s). %s",
            self.node_id,
            self.runtime.name,
            self._gpu.get("model"),
            note,
        )
        await self._safe_heartbeat()
        while not stop.is_set():
            try:
                # Claim first. A heartbeat must not sit in front of the next job.
                job = await self.claim(self.claim_wait_sec)
                if not job:
                    if self._heartbeat_due():
                        await self._safe_heartbeat()
                    continue
                beater = asyncio.create_task(self._beat_during(stop))
                try:
                    await self.execute(job)
                finally:
                    beater.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await beater
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("node loop error")
                if stop.is_set():
                    break
                try:
                    await asyncio.wait_for(stop.wait(), timeout=0.5)
                except TimeoutError:
                    pass

    def _heartbeat_due(self) -> bool:
        if self._last_heartbeat <= 0:
            return True
        return time.monotonic() - self._last_heartbeat >= self.heartbeat_sec

    async def _safe_heartbeat(self) -> None:
        try:
            await self.heartbeat()
        except Exception:
            log.exception("heartbeat failed")
            return
        self._last_heartbeat = time.monotonic()

    async def _beat_during(self, stop: asyncio.Event) -> None:
        while not stop.is_set():
            elapsed = time.monotonic() - self._last_heartbeat if self._last_heartbeat else 0.0
            delay = max(0.0, self.heartbeat_sec - elapsed)
            if delay:
                try:
                    await asyncio.wait_for(stop.wait(), timeout=delay)
                except TimeoutError:
                    pass
                else:
                    return
            if stop.is_set():
                return
            await self._safe_heartbeat()

    async def aclose(self) -> None:
        if self._owns and self.http is not None:
            await self.http.aclose()
