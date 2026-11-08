"""NVIDIA and AMD detection. Never interpolates a prompt into a shell.

``accelerator`` is the hardware backend the hub stores: ``cuda``, ``rocm``, or
``cpu``. The inference runtime (ollama, vLLM, llama.cpp, cpu) is a separate
field. The installer can pass the host probe through ``GPU_MESH_*`` env vars
when ``nvidia-smi`` is not on this process's PATH (a container without the
device mounted). A live probe wins over those env vars.
"""

from __future__ import annotations

import os
import re
import subprocess

CPU_GPU = {
    "vendor": "cpu",
    "model": "cpu",
    "vram_mb": 0,
    "driver": "",
    "count": 0,
    "accelerator": "cpu",
}

_VRAM_BYTES = re.compile(r"VRAM Total Memory \(B\):\s*(\d+)")
_CARD_SERIES = re.compile(r"Card series:\s*(.+)")
_MARKETING = re.compile(r"Marketing Name:\s*(.+)")


def normalize_accelerator(value: str, vendor: str = "", model: str = "", vram_mb: int = 0) -> str:
    text = (value or "").strip().lower()
    if text in {"cuda", "nvidia"}:
        return "cuda"
    if text in {"rocm", "amd", "hip"}:
        return "rocm"
    if text == "cpu":
        return "cpu"
    vendor_name = (vendor or "").strip().lower()
    if vendor_name == "nvidia":
        return "cuda"
    if vendor_name in {"amd", "rocm"}:
        return "rocm"
    if int(vram_mb or 0) > 0 and (model or "").strip().lower() not in {"", "cpu"}:
        return "cuda"
    return "cpu"


def parse_nvidia_smi(text: str) -> dict | None:
    rows: list[tuple[str, int, str]] = []
    for line in text.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) < 2 or not parts[0] or parts[0].lower() in {"name", "nvidia-smi"}:
            continue
        name, memory = parts[0], parts[1]
        driver = parts[2] if len(parts) > 2 else ""
        if name.startswith("[") or "failed" in name.lower():
            continue
        try:
            vram = int(float(memory))
        except ValueError:
            vram = 0
        rows.append((name, vram, driver))
    if not rows:
        return None
    names = [row[0] for row in rows]
    model = names[0] if len(set(names)) == 1 else " + ".join(names)
    return {
        "vendor": "nvidia",
        "model": model,
        "vram_mb": sum(row[1] for row in rows),
        "driver": rows[0][2],
        "count": len(rows),
        "accelerator": "cuda",
    }


def parse_rocm_smi(text: str) -> dict | None:
    """Read ``rocm-smi --showproductname`` and ``--showmeminfo vram`` text."""

    vram_bytes = [int(match) for match in _VRAM_BYTES.findall(text)]
    marketing = [item.strip() for item in _MARKETING.findall(text) if item.strip() and item.strip() != "N/A"]
    series = [item.strip() for item in _CARD_SERIES.findall(text) if item.strip() and item.strip() != "N/A"]
    names = marketing or series
    saw_gpu = "GPU[" in text or bool(vram_bytes)
    if not saw_gpu:
        return None
    model = names[0] if names else "AMD GPU"
    if len(set(names)) > 1:
        model = " + ".join(names)
    count = len(vram_bytes) or (1 if saw_gpu else 0)
    vram_mb = sum(vram_bytes) // (1024 * 1024)
    return {
        "vendor": "amd",
        "model": model,
        "vram_mb": vram_mb,
        "driver": "rocm",
        "count": count,
        "accelerator": "rocm",
    }


def hardware_from_env(environ: dict[str, str] | None = None) -> dict | None:
    env = os.environ if environ is None else environ
    accel_raw = (env.get("GPU_MESH_ACCELERATOR") or "").strip()
    name = (env.get("GPU_MESH_GPU_NAME") or "").strip()
    vram_raw = (env.get("GPU_MESH_VRAM_MB") or "").strip()
    if not accel_raw and not name and not vram_raw:
        return None
    try:
        vram = int(float(vram_raw)) if vram_raw else 0
    except ValueError:
        vram = 0
    try:
        count = int(env.get("GPU_MESH_GPU_COUNT") or "0")
    except ValueError:
        count = 0
    accelerator = normalize_accelerator(accel_raw, model=name, vram_mb=vram)
    if accelerator == "cpu":
        return dict(CPU_GPU)
    vendor = "nvidia" if accelerator == "cuda" else "amd"
    if count <= 0:
        count = 1
    return {
        "vendor": vendor,
        "model": name or vendor,
        "vram_mb": max(0, vram),
        "driver": (env.get("GPU_MESH_GPU_DRIVER") or "")[:64],
        "count": count,
        "accelerator": accelerator,
    }


def _run(argv: list[str]) -> str | None:
    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout


def probe_nvidia() -> dict | None:
    text = _run(
        [
            "nvidia-smi",
            "--query-gpu=name,memory.total,driver_version",
            "--format=csv,noheader,nounits",
        ]
    )
    if text is None:
        return None
    return parse_nvidia_smi(text)


def probe_rocm() -> dict | None:
    product = _run(["rocm-smi", "--showproductname"])
    memory = _run(["rocm-smi", "--showmeminfo", "vram"])
    if product is None and memory is None:
        return None
    return parse_rocm_smi(f"{product or ''}\n{memory or ''}")


def probe_gpu() -> dict | None:
    """Live device first. Installer env is the fallback inside a container."""

    found = probe_nvidia() or probe_rocm()
    if found:
        return found
    return hardware_from_env()
