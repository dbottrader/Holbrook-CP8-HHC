from gpumesh_node.gpu import parse_nvidia_smi


def test_parse_two_gpus():
    text = "NVIDIA GeForce RTX 4090, 24564, 550.90.07\nNVIDIA GeForce RTX 4090, 24564, 550.90.07\n"
    info = parse_nvidia_smi(text)
    assert info is not None
    assert info["count"] == 2
    assert info["vram_mb"] == 49128
    assert "4090" in info["model"]
    assert info["driver"] == "550.90.07"


def test_parse_empty_and_na():
    assert parse_nvidia_smi("") is None
    info = parse_nvidia_smi("NVIDIA A100, [N/A], 535.1\n")
    assert info is not None
    assert info["vram_mb"] == 0
    assert info["count"] == 1
