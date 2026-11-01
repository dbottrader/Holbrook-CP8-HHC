"""``python -m gpumesh_node`` — volunteer GPU process."""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import signal
import socket
from pathlib import Path

from gpumesh_node.agent import NodeAgent
from gpumesh_node.gpu import probe_gpu
from gpumesh_node.runtime import detect_runtime


def _config_from_env(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="GPU Mesh volunteer node")
    parser.add_argument("--coordinator", default=os.environ.get("GPU_MESH_COORDINATOR", ""))
    parser.add_argument("--name", default=os.environ.get("GPU_MESH_NAME", ""))
    parser.add_argument("--backend", default=os.environ.get("GPU_MESH_BACKEND", "auto"))
    parser.add_argument("--allow-cpu", action="store_true", default=os.environ.get("GPU_MESH_ALLOW_CPU", "0") == "1")
    parser.add_argument(
        "--ollama-host",
        default=os.environ.get("GPU_MESH_OLLAMA_HOST", os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")),
    )
    parser.add_argument("--vllm-host", default=os.environ.get("GPU_MESH_VLLM_HOST", "http://127.0.0.1:8000"))
    parser.add_argument("--state", default=os.environ.get("GPU_MESH_STATE", "data/node.json"))
    parser.add_argument("--models", default=os.environ.get("GPU_MESH_MODELS", "mock-tiny"))
    parser.add_argument("--gguf-repo", default=os.environ.get("GPU_MESH_GGUF_REPO", ""))
    parser.add_argument("--gguf-file", default=os.environ.get("GPU_MESH_GGUF_FILE", ""))
    parser.add_argument("--model-id", default=os.environ.get("GPU_MESH_MODEL_ID", ""))
    parser.add_argument("--model-cache", default=os.environ.get("GPU_MESH_MODEL_CACHE", "data/models"))
    parser.add_argument(
        "--llama-threads", type=int, default=int(os.environ.get("GPU_MESH_LLAMA_THREADS", "2"))
    )
    parser.add_argument("--llama-ctx", type=int, default=int(os.environ.get("GPU_MESH_LLAMA_CTX", "2048")))
    parser.add_argument("--gguf-sha256", default=os.environ.get("GPU_MESH_GGUF_SHA256", ""))
    parser.add_argument("--heartbeat", type=float, default=float(os.environ.get("GPU_MESH_HEARTBEAT_SEC", "10")))
    parser.add_argument("--invite", default=os.environ.get("GPU_MESH_INVITE", ""))
    parser.add_argument("--job-timeout", type=float, default=float(os.environ.get("GPU_MESH_JOB_TIMEOUT_SEC", "120")))
    parser.add_argument("--once", action="store_true", help="heartbeat, run at most one job, exit")
    return parser.parse_args(argv)


async def _async_main(args: argparse.Namespace) -> None:
    coordinator = args.coordinator.strip().rstrip("/")
    if not coordinator:
        raise SystemExit("Pass --coordinator or set GPU_MESH_COORDINATOR.")
    name = args.name.strip() or socket.gethostname()
    models = [item.strip() for item in args.models.split(",") if item.strip()]
    gpu = probe_gpu()
    runtime = await detect_runtime(
        args.backend,
        allow_cpu=args.allow_cpu,
        models=models,
        ollama_host=args.ollama_host.rstrip("/"),
        vllm_host=args.vllm_host.rstrip("/"),
        job_timeout=args.job_timeout,
        gpu=gpu,
        llamacpp={
            "repo": args.gguf_repo,
            "filename": args.gguf_file,
            "model_id": args.model_id,
            "cache": args.model_cache,
            "threads": args.llama_threads,
            "n_ctx": args.llama_ctx,
            "sha256": args.gguf_sha256,
        },
    )
    if runtime.name == "cpu":
        logging.getLogger("gpumesh.node").warning(
            "serving the deterministic CPU fallback (%s). This is not a neural model.",
            ", ".join(models),
        )
    elif runtime.name == "llamacpp":
        logging.getLogger("gpumesh.node").info(
            "serving open-weight GGUF %s via llama.cpp. No TOPLOC hidden-state proof is attached.",
            getattr(runtime, "model_id", ""),
        )
    agent = NodeAgent(
        base_url=coordinator,
        runtime=runtime,
        name=name,
        state_path=Path(args.state),
        heartbeat_sec=args.heartbeat,
        invite=args.invite,
    )
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:
            pass
    if args.once:
        await agent.register()
        await agent.heartbeat()
        job = await agent.claim(1)
        if job:
            await agent.execute(job)
        await agent.aclose()
        return
    try:
        await agent.run_forever(stop)
    finally:
        await agent.aclose()


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    args = _config_from_env(argv)
    asyncio.run(_async_main(args))


if __name__ == "__main__":
    main()
