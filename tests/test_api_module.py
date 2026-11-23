from holbrook_os import api


def test_api_module_imports():
    assert api.app.title == "Holbrook OS"
    assert any(getattr(route, "path", None) == "/health" for route in api.app.routes)
