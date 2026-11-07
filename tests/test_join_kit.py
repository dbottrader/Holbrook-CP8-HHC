"""The volunteer join kit is one image, Compose, and a one-line installer."""

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JOIN = ROOT / "gpu-mesh" / "deploy" / "join"


def test_installer_and_entrypoint_parse():
    for name in ("install.sh", "entrypoint.sh"):
        subprocess.run(["bash", "-n", str(JOIN / name)], check=True)


def test_installer_defaults_to_the_public_coordinator():
    url = "https://ecenvlwyenpakrxfuqup.supabase.co/functions/v1/gpu-mesh"
    text = (JOIN / "install.sh").read_text(encoding="utf-8")
    assert url in text
    assert "open" in text
    done = subprocess.run(["bash", str(JOIN / "install.sh"), "--dry-run"], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    assert f"coordinator={url}" in done.stdout
    for name in ("docker-compose.yml", "Dockerfile", "entrypoint.sh"):
        assert url in (JOIN / name).read_text(encoding="utf-8")


def test_compose_pins_one_image_and_ollama():
    text = (JOIN / "docker-compose.yml").read_text(encoding="utf-8")
    dockerfile = (JOIN / "Dockerfile").read_text(encoding="utf-8")
    assert "ghcr.io/dbottrader/holbrook-cp8-hhc/gpumesh-join" in text
    assert "ollama/ollama:0.12.6" in text
    assert "GPU_MESH_COORDINATOR" in text
    assert "llama_cpp_python-0.3.36-py3-none-manylinux2014_x86_64.manylinux_2_17_x86_64.whl" in dockerfile
    assert "--only-binary=:all:" in dockerfile
    assert "llama-cpp-python>=" not in dockerfile
    assert "gpumesh_node" in dockerfile
    readme = (JOIN / "README.md").read_text(encoding="utf-8").lower()
    windows = (JOIN / "WINDOWS.md").read_text(encoding="utf-8").lower()
    assert "simulated utility credit" in readme
    assert "windows" in windows
    for banned in ("token sale", "airdrop", "investor"):
        assert banned not in readme
        assert banned not in windows
