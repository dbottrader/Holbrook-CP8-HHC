"""NVIDIA detection via ``nvidia-smi``. Never interpolates a prompt into a shell."""

from __future__ import annotations

import subprocess

CPU_GPU = {"vendor": "cpu", "model": "cpu", "vram_mb": 0, "driver": "", "count": 0}


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
    }


def probe_gpu() -> dict | None:
    try:
        proc = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,driver_version",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None
    if proc.returncode != 0:
        return None
    return parse_nvidia_smi(proc.stdout)
