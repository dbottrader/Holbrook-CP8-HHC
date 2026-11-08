from gpumesh.db import build_database, session_scope
from gpumesh.work import register_node
from gpumesh_node.gpu import (
    hardware_from_env,
    normalize_accelerator,
    parse_nvidia_smi,
    parse_rocm_smi,
    probe_gpu,
)
from tests.conftest import make_settings


def test_parse_two_gpus():
    text = "NVIDIA GeForce RTX 4090, 24564, 550.90.07\nNVIDIA GeForce RTX 4090, 24564, 550.90.07\n"
    info = parse_nvidia_smi(text)
    assert info is not None
    assert info["count"] == 2
    assert info["vram_mb"] == 49128
    assert "4090" in info["model"]
    assert info["driver"] == "550.90.07"
    assert info["accelerator"] == "cuda"
    assert info["vendor"] == "nvidia"


def test_parse_empty_and_na():
    assert parse_nvidia_smi("") is None
    info = parse_nvidia_smi("NVIDIA A100, [N/A], 535.1\n")
    assert info is not None
    assert info["vram_mb"] == 0
    assert info["count"] == 1
    assert info["accelerator"] == "cuda"


ROCM = """
GPU[0]          : Card series:          Navi 31
GPU[0]          : VRAM Total Memory (B): 17163091968
"""


def test_parse_rocm_vram_and_name():
    info = parse_rocm_smi(ROCM)
    assert info is not None
    assert info["accelerator"] == "rocm"
    assert info["vendor"] == "amd"
    assert info["model"] == "Navi 31"
    assert info["vram_mb"] == 17163091968 // (1024 * 1024)
    assert info["count"] == 1


def test_parse_rocm_without_a_card_is_none():
    assert parse_rocm_smi("no devices\n") is None


def test_normalize_accelerator_prefers_the_explicit_field():
    assert normalize_accelerator("rocm", vendor="nvidia", model="RTX", vram_mb=8000) == "rocm"
    assert normalize_accelerator("", vendor="nvidia") == "cuda"
    assert normalize_accelerator("", vendor="amd", model="Navi", vram_mb=8000) == "rocm"
    assert normalize_accelerator("", model="cpu", vram_mb=0) == "cpu"


def test_env_reports_cuda_and_live_probe_wins(monkeypatch):
    reported = hardware_from_env(
        {
            "GPU_MESH_ACCELERATOR": "cuda",
            "GPU_MESH_GPU_NAME": "NVIDIA GeForce RTX 4090",
            "GPU_MESH_VRAM_MB": "24564",
            "GPU_MESH_GPU_COUNT": "1",
            "GPU_MESH_GPU_DRIVER": "550.90",
        }
    )
    assert reported is not None
    assert reported["accelerator"] == "cuda"
    assert reported["vram_mb"] == 24564
    assert hardware_from_env({}) is None
    assert hardware_from_env({"GPU_MESH_ACCELERATOR": "cpu"})["model"] == "cpu"

    monkeypatch.setattr("gpumesh_node.gpu.probe_nvidia", lambda: {"accelerator": "cuda", "model": "live"})
    monkeypatch.setattr("gpumesh_node.gpu.probe_rocm", lambda: None)
    monkeypatch.setenv("GPU_MESH_ACCELERATOR", "rocm")
    assert probe_gpu()["model"] == "live"


def test_register_stores_cuda_hardware(tmp_path):
    settings = make_settings(tmp_path)
    _engine, session_factory = build_database(settings)
    spec = {
        "name": "rig",
        "backend": "ollama",
        "gpu": {
            "vendor": "nvidia",
            "model": "NVIDIA GeForce RTX 4090",
            "vram_mb": 24564,
            "driver": "550.90",
            "count": 1,
            "accelerator": "cuda",
        },
        "models": [{"id": "qwen2.5:7b-instruct", "resident": True, "source": "ollama"}],
    }
    with session_scope(session_factory) as session:
        node, _token, _receipt = register_node(session, settings, spec, "10.0.0.8")
        assert node.backend == "ollama"
        assert node.gpu_name == "NVIDIA GeForce RTX 4090"
        assert node.vram_mb == 24564
        assert node.accelerator == "cuda"
