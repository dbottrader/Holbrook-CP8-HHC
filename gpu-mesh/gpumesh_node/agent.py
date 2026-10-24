"""Pull-based miner loop. Jobs come from the coordinator; the node opens no inbound port."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
from pathlib import Path

import httpx

from gpumesh_node import __version__
from gpumesh_node.gpu import CPU_GPU, probe_gpu
from gpumesh_node.runtime import InferenceResult, Runtime

log = logging.getLogger("gpumesh.node")


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
        invite: str = "",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.runtime = runtime
        self.name = name
        self.http = http
        self._owns = http is None
        self.state_path = state_path
        self.heartbeat_sec = heartbeat_sec
        self.invite = invite
        self.token: str | None = None
        self.node_id: str | None = None
        self._gpu = probe_gpu() or dict(CPU_GPU)

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
        return {
            "name": self.name,
            "backend": self.runtime.name,
            "gpu": self._gpu,
            "models": models,
            "version": __version__,
            "max_inflight": 1,
        }

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
        if self.runtime.name == "cpu":
            try:
                from gpumesh_node.toploc_proof import build_prompt_proofs

                proofs = build_prompt_proofs(job.get("messages") or [], str(job.get("model") or ""))
                source = "prompt-trace" if proofs else ""
            except Exception:
                log.exception("TOPLOC proof was not built")
                proofs = None
        client = await self._client()
        body = {
            "output_text": result.text,
            "prompt_tokens": result.prompt_tokens,
            "completion_tokens": result.completion_tokens,
            "duration_ms": result.duration_ms,
            "finish_reason": result.finish_reason,
            "fencing_token": job.get("fencing_token"),
        }
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
        if self.runtime.name == "cpu":
            note = "CPU fallback is not a neural model."
        elif self.runtime.name == "llamacpp":
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
        while not stop.is_set():
            try:
                await self.heartbeat()
                job = await self.claim(min(20.0, max(self.heartbeat_sec, 1)))
                if not job:
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
                try:
                    await asyncio.wait_for(stop.wait(), timeout=3)
                except TimeoutError:
                    pass

    async def _beat_during(self, stop: asyncio.Event) -> None:
        while not stop.is_set():
            await asyncio.sleep(self.heartbeat_sec)
            try:
                await self.heartbeat()
            except Exception:
                log.exception("heartbeat during job failed")

    async def aclose(self) -> None:
        if self._owns and self.http is not None:
            await self.http.aclose()
