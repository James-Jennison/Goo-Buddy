"""The developer-only synthetic card harness must never become an app route."""

from backend.app.main import app


def test_production_asgi_app_has_no_synthetic_preview_route():
    paths = [getattr(route, "path", "") for route in app.routes]
    assert not any("synthetic" in path.lower() for path in paths)
