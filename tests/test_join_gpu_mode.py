"""Installer GPU detection: mocked nvidia-smi / rocm-smi, and shellcheck when present."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JOIN = ROOT / "gpu-mesh" / "deploy" / "join"
MODE = JOIN / "gpu-mode.sh"
INSTALL = JOIN / "install.sh"


def _plan(tmp_path: Path, *args: str, bins: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    bindir = tmp_path / "bin"
    bindir.mkdir()
    for name, body in (bins or {}).items():
        path = bindir / name
        path.write_text(body, encoding="utf-8")
        path.chmod(0o755)
    env = os.environ.copy()
    # Mocks come first. /usr/bin and /bin stay so bash itself resolves.
    env["PATH"] = f"{bindir}{os.pathsep}/usr/bin{os.pathsep}/bin"
    return subprocess.run(
        ["bash", str(MODE), *args],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def _fields(stdout: str) -> dict[str, str]:
    found: dict[str, str] = {}
    for line in stdout.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        found[key] = value
    return found


def test_cpu_when_no_gpu_tool_exists(tmp_path: Path):
    done = _plan(tmp_path, bins={"nvidia-smi": "#!/bin/sh\nexit 1\n", "rocm-smi": "#!/bin/sh\nexit 1\n"})
    assert done.returncode == 0, done.stderr
    fields = _fields(done.stdout)
    assert fields["mode"] == "cpu"
    assert fields["accelerator"] == "cpu"
    assert fields["inference_backend"] == "llamacpp"
    assert fields["model"] == "SmolLM2-360M-Instruct"
    assert fields["docker_gpus"] == ""
    assert "CPU mode" in fields["note"]


def test_mocked_nvidia_selects_cuda_ollama_and_sizes_the_model(tmp_path: Path):
    done = _plan(
        tmp_path,
        bins={
            "nvidia-smi": "#!/bin/sh\necho 'NVIDIA GeForce RTX 4090, 24564, 550.90.07'\n",
            "nvidia-ctk": "#!/bin/sh\nexit 0\n",
        },
    )
    assert done.returncode == 0, done.stderr
    fields = _fields(done.stdout)
    assert fields["mode"] == "cuda"
    assert fields["accelerator"] == "cuda"
    assert fields["gpu_name"] == "NVIDIA GeForce RTX 4090"
    assert fields["vram_mb"] == "24564"
    assert fields["inference_backend"] == "ollama"
    assert fields["model"] == "qwen2.5:7b-instruct"
    assert fields["ollama_image"] == "ollama/ollama:0.12.6"
    assert fields["docker_gpus"] == "all"
    assert fields["toolkit"] == "present"
    assert fields["allow_cpu"] == "0"
    assert "GPU mode cuda" in fields["note"]


def test_smaller_vram_selects_3b(tmp_path: Path):
    done = _plan(
        tmp_path,
        bins={
            "nvidia-smi": "#!/bin/sh\necho 'NVIDIA GeForce RTX 3050, 4096, 550.1'\n",
            "nvidia-ctk": "#!/bin/sh\nexit 0\n",
        },
    )
    assert done.returncode == 0, done.stderr
    fields = _fields(done.stdout)
    assert fields["model"] == "qwen2.5:3b-instruct"
    assert fields["vram_mb"] == "4096"


def test_cpu_flag_overrides_a_visible_gpu(tmp_path: Path):
    done = _plan(
        tmp_path,
        "--cpu",
        bins={
            "nvidia-smi": "#!/bin/sh\necho 'NVIDIA GeForce RTX 4090, 24564, 550.90.07'\n",
        },
    )
    assert done.returncode == 0, done.stderr
    fields = _fields(done.stdout)
    assert fields["mode"] == "cpu"
    assert fields["accelerator"] == "cpu"
    assert fields["vram_mb"] == "0"
    assert fields["docker_gpus"] == ""
    assert fields["detected"] == "cuda"
    assert "--cpu" in fields["note"]


def test_gpu_flag_fails_closed_without_a_device(tmp_path: Path):
    done = _plan(tmp_path, "--gpu")
    assert done.returncode == 2
    assert "--gpu" in done.stderr


def test_missing_toolkit_prints_the_install_commands(tmp_path: Path):
    done = subprocess.run(
        ["bash", str(INSTALL), "--dry-run"],
        capture_output=True,
        text=True,
        env={**os.environ, "PATH": f"{tmp_path}{os.pathsep}/usr/bin{os.pathsep}/bin"},
        check=False,
    )
    # No nvidia-smi on this PATH, so the plan is CPU and does not need the toolkit.
    assert done.returncode == 0, done.stderr
    assert "mode=cpu" in done.stdout
    assert "coordinator=https://ecenvlwyenpakrxfuqup.supabase.co/functions/v1/gpu-mesh" in done.stdout

    bindir = tmp_path / "bin"
    bindir.mkdir()
    smi = bindir / "nvidia-smi"
    smi.write_text("#!/bin/sh\necho 'NVIDIA GeForce RTX 4090, 8192, 550.90'\n", encoding="utf-8")
    smi.chmod(0o755)
    forced_env = os.environ.copy()
    forced_env["PATH"] = f"{bindir}{os.pathsep}/usr/bin{os.pathsep}/bin"
    forced_env["GPU_MODE_TOOLKIT_FORCE"] = "missing"
    forced = subprocess.run(
        ["bash", str(INSTALL), "--dry-run"],
        capture_output=True,
        text=True,
        env=forced_env,
        check=False,
    )
    assert forced.returncode == 0, forced.stderr
    assert "toolkit=missing" in forced.stdout
    assert "sudo apt-get install -y nvidia-container-toolkit" in forced.stdout
    assert "nvidia-ctk runtime configure --runtime=docker" in forced.stdout
    assert "model=qwen2.5:7b-instruct" in forced.stdout


def test_rocm_uses_the_rocm_image_and_devices(tmp_path: Path):
    script = r"""#!/bin/sh
if [ "$1" = "--showproductname" ]; then
  echo 'GPU[0] : Card series: Navi 31'
elif [ "$1" = "--showmeminfo" ]; then
  echo 'GPU[0] : VRAM Total Memory (B): 17163091968'
fi
"""
    done = _plan(tmp_path, bins={"nvidia-smi": "#!/bin/sh\nexit 1\n", "rocm-smi": script})
    assert done.returncode == 0, done.stderr
    fields = _fields(done.stdout)
    assert fields["mode"] == "rocm"
    assert fields["accelerator"] == "rocm"
    assert fields["ollama_image"] == "ollama/ollama:rocm"
    assert fields["docker_devices"] == "/dev/kfd /dev/dri"
    assert fields["docker_gpus"] == ""
    assert int(fields["vram_mb"]) > 15000


def test_ollama_ps_gpu_line_is_recognized():
    text = "qwen2.5:7b-instruct  abc  4.7 GB  100% GPU  4096  4 minutes from now\n"
    cpu = "qwen2.5:0.5b-instruct  abc  400 MB  100% CPU  2048  4 minutes from now\n"
    script = (
        "source \"$1\"\n"
        "gpu_mode_ps_uses_gpu \"$2\"\n"
    )
    yes = subprocess.run(["bash", "-c", script, "bash", str(MODE), text], capture_output=True, text=True)
    no = subprocess.run(["bash", "-c", script, "bash", str(MODE), cpu], capture_output=True, text=True)
    assert yes.returncode == 0, yes.stderr
    assert no.returncode != 0


def test_compose_reserves_an_nvidia_gpu_and_a_rocm_device():
    text = (JOIN / "docker-compose.yml").read_text(encoding="utf-8")
    assert "driver: nvidia" in text
    assert "capabilities: [gpu]" in text
    assert "ollama/ollama:rocm" in text
    assert "/dev/kfd" in text
    assert "/dev/dri" in text
    assert "--gpu" in INSTALL.read_text(encoding="utf-8")
    assert "--cpu" in INSTALL.read_text(encoding="utf-8")
    assert "--payout-address" in INSTALL.read_text(encoding="utf-8")


def test_shellcheck_join_scripts():
    shellcheck = shutil.which("shellcheck")
    if shellcheck is None:
        return
    scripts = [
        INSTALL,
        MODE,
        ROOT / "gpu-mesh" / "gpumesh" / "assets" / "install.sh",
        JOIN / "entrypoint.sh",
    ]
    done = subprocess.run([shellcheck, "-x", *(str(path) for path in scripts)], capture_output=True, text=True)
    assert done.returncode == 0, done.stdout + done.stderr
