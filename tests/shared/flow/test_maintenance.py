from __future__ import annotations

import pytest
from flask import Flask

import shared.adapters.driving.maintenance as maintenance


def _make_app(handler_status: int = 200) -> Flask:
    """Minimal Flask app with maintenance gate registered."""
    app = Flask(__name__)
    maintenance.init_maintenance(app)

    @app.route("/foo")
    def foo():
        return "ok", handler_status

    @app.route("/auth/login")
    def auth_login():
        return "ok", handler_status

    @app.route("/admin/backups/snapshot")
    def backup_snapshot():
        return "ok", handler_status

    @app.route("/static/x.css")
    def static_css():
        return "ok", handler_status

    @app.route("/media/file.jpg")
    def media_file():
        return "ok", handler_status

    return app


@pytest.mark.flow
def test_no_flag_handler_runs(tmp_path, monkeypatch):
    """No maintenance flag — all requests pass through."""
    flag = tmp_path / ".maintenance"
    monkeypatch.setattr(maintenance, "MAINTENANCE_FLAG", flag)

    app = _make_app()
    with app.test_client() as client:
        resp = client.get("/foo")
        assert resp.status_code == 200


@pytest.mark.flow
def test_flag_present_non_whitelisted_returns_503(tmp_path, monkeypatch):
    """Flag present + non-whitelisted path → 503 JSON error."""
    flag = tmp_path / ".maintenance"
    flag.touch()
    monkeypatch.setattr(maintenance, "MAINTENANCE_FLAG", flag)

    app = _make_app()
    with app.test_client() as client:
        resp = client.get("/foo")
        assert resp.status_code == 503
        assert resp.get_json() == {"error": "maintenance"}


@pytest.mark.flow
def test_flag_present_auth_path_passes(tmp_path, monkeypatch):
    """Flag present + /auth/... → handler runs (whitelisted prefix)."""
    flag = tmp_path / ".maintenance"
    flag.touch()
    monkeypatch.setattr(maintenance, "MAINTENANCE_FLAG", flag)

    app = _make_app()
    with app.test_client() as client:
        resp = client.get("/auth/login")
        assert resp.status_code == 200


@pytest.mark.flow
def test_flag_present_admin_backups_passes(tmp_path, monkeypatch):
    """Flag present + /admin/backups/snapshot → handler runs."""
    flag = tmp_path / ".maintenance"
    flag.touch()
    monkeypatch.setattr(maintenance, "MAINTENANCE_FLAG", flag)

    app = _make_app()
    with app.test_client() as client:
        resp = client.get("/admin/backups/snapshot")
        assert resp.status_code == 200


@pytest.mark.flow
def test_flag_present_static_path_passes(tmp_path, monkeypatch):
    """Flag present + /static/... → handler runs."""
    flag = tmp_path / ".maintenance"
    flag.touch()
    monkeypatch.setattr(maintenance, "MAINTENANCE_FLAG", flag)

    app = _make_app()
    with app.test_client() as client:
        resp = client.get("/static/x.css")
        assert resp.status_code == 200


@pytest.mark.flow
def test_enter_maintenance_creates_file(tmp_path, monkeypatch):
    """enter_maintenance() creates the flag file (and parent dirs)."""
    flag = tmp_path / "nested" / ".maintenance"
    monkeypatch.setattr(maintenance, "MAINTENANCE_FLAG", flag)

    assert not flag.exists()
    maintenance.enter_maintenance()
    assert flag.exists()


@pytest.mark.flow
def test_exit_maintenance_removes_file(tmp_path, monkeypatch):
    """exit_maintenance() removes the flag; idempotent if already absent."""
    flag = tmp_path / ".maintenance"
    flag.touch()
    monkeypatch.setattr(maintenance, "MAINTENANCE_FLAG", flag)

    maintenance.exit_maintenance()
    assert not flag.exists()

    # Second call must not raise
    maintenance.exit_maintenance()
