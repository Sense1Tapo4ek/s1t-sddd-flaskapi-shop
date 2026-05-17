"""Flow tests for bulk_rate_limited decorator (RED phase).

Contract being encoded:
- When BULK_RATE_LIMIT_ENABLED=False (default), no rate limiting occurs.
- When BULK_RATE_LIMIT_ENABLED=True and max_per_min threshold is exceeded, 429 is returned.
- Buckets are keyed by (actor_id, action): separate actions have separate buckets.
- reset_bulk_rate_limit_state() clears all in-memory bucket state.
"""
from __future__ import annotations

import pytest

from shared.adapters.driving.bulk import (  # noqa: F401  — expected ImportError (RED)
    bulk_action_log,
    bulk_rate_limited,
    reset_bulk_rate_limit_state,
)

pytestmark = pytest.mark.flow

# ─── Helpers ────────────────────────────────────────────────────────────────


def _login(client, login: str, password: str) -> str:
    resp = client.post("/auth/login", json={"login": login, "password": password})
    assert resp.status_code == 200, f"login failed: {resp.get_json()}"
    return resp.get_json()["token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _make_app(monkeypatch, tmp_path):
    monkeypatch.setenv("INFRA_DATABASE_URL", f"sqlite:///{tmp_path / 'shop.db'}")
    monkeypatch.setenv("ROOT_APP_ENV", "dev")
    monkeypatch.setenv("ACCESS_DEFAULT_LOGIN", "superadmin")
    monkeypatch.setenv("ACCESS_DEFAULT_PASSWORD", "superadmin")
    monkeypatch.setenv("ACCESS_PROMOTE_TO_SUPERADMIN", "true")
    from root.entrypoints.api import create_app
    return create_app()


# ─── Fixtures ───────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _reset_rate_limit_state():
    """Clear in-memory bucket state before and after each test."""
    reset_bulk_rate_limit_state()
    yield
    reset_bulk_rate_limit_state()


# ─── Tests ──────────────────────────────────────────────────────────────────


class TestBulkRateLimited:
    def test_no_rate_limit_when_disabled(self, monkeypatch, tmp_path):
        """
        Given BULK_RATE_LIMIT_ENABLED=False,
        When 15 consecutive POSTs are issued to /admin/products/bulk/activate,
        Then all 15 responses are 200 (not 429).
        """
        app = _make_app(monkeypatch, tmp_path)
        app.config["BULK_RATE_LIMIT_ENABLED"] = False
        client = app.test_client()
        token = _login(client, "superadmin", "superadmin")

        for i in range(15):
            resp = client.post(
                "/admin/products/bulk/activate",
                json={"target": {"kind": "ids", "ids": [1]}, "active": True},
                headers=_auth(token),
            )
            assert resp.status_code == 200, (
                f"request {i + 1}/15 returned {resp.status_code} with rate limiting disabled"
            )

    def test_rate_limited_after_threshold(self, monkeypatch, tmp_path):
        """
        Given BULK_RATE_LIMIT_ENABLED=True and max_per_min=10,
        When 10 POSTs succeed,
        Then the 11th POST returns 429 with a machine-readable code in the body.
        """
        app = _make_app(monkeypatch, tmp_path)
        app.config["BULK_RATE_LIMIT_ENABLED"] = True
        client = app.test_client()
        token = _login(client, "superadmin", "superadmin")

        for i in range(10):
            resp = client.post(
                "/admin/products/bulk/activate",
                json={"target": {"kind": "ids", "ids": [1]}, "active": True},
                headers=_auth(token),
            )
            assert resp.status_code == 200, f"request {i + 1}/10 was unexpectedly blocked"

        resp_11 = client.post(
            "/admin/products/bulk/activate",
            json={"target": {"kind": "ids", "ids": [1]}, "active": True},
            headers=_auth(token),
        )
        assert resp_11.status_code == 429, (
            f"11th request should be rate-limited (429), got {resp_11.status_code}"
        )
        # Response body should contain a machine-readable rate-limit indicator
        body = resp_11.get_data(as_text=True)
        assert "RATE_LIMITED" in body or "429" in body or "rate" in body.lower(), (
            f"expected rate-limit indicator in body, got: {body!r}"
        )

    def test_separate_actions_have_separate_buckets(self, monkeypatch, tmp_path):
        """
        Given BULK_RATE_LIMIT_ENABLED=True,
        When 10 POSTs hit /bulk/activate and 10 POSTs hit /bulk/delete independently,
        Then each action's 11th call returns 429 but the other action's bucket is unaffected.
        """
        app = _make_app(monkeypatch, tmp_path)
        app.config["BULK_RATE_LIMIT_ENABLED"] = True
        client = app.test_client()
        token = _login(client, "superadmin", "superadmin")

        # Fill activate bucket to limit
        for i in range(10):
            resp = client.post(
                "/admin/products/bulk/activate",
                json={"target": {"kind": "ids", "ids": [1]}, "active": True},
                headers=_auth(token),
            )
            assert resp.status_code == 200, f"activate request {i + 1}/10 blocked early"

        # Fill delete bucket to limit independently
        for i in range(10):
            resp = client.post(
                "/admin/products/bulk/delete",
                json={"target": {"kind": "ids", "ids": [9999]}},
                headers=_auth(token),
            )
            assert resp.status_code == 200, f"delete request {i + 1}/10 blocked early"

        # 11th activate → 429
        resp_act = client.post(
            "/admin/products/bulk/activate",
            json={"target": {"kind": "ids", "ids": [1]}, "active": True},
            headers=_auth(token),
        )
        assert resp_act.status_code == 429, (
            f"11th activate should be 429, got {resp_act.status_code}"
        )

        # 11th delete → 429
        resp_del = client.post(
            "/admin/products/bulk/delete",
            json={"target": {"kind": "ids", "ids": [9999]}},
            headers=_auth(token),
        )
        assert resp_del.status_code == 429, (
            f"11th delete should be 429, got {resp_del.status_code}"
        )

    def test_reset_helper_clears_buckets(self, monkeypatch, tmp_path):
        """
        Given BULK_RATE_LIMIT_ENABLED=True and the activate bucket is at limit,
        When reset_bulk_rate_limit_state() is called,
        Then the next POST returns 200 (bucket is cleared).
        """
        app = _make_app(monkeypatch, tmp_path)
        app.config["BULK_RATE_LIMIT_ENABLED"] = True
        client = app.test_client()
        token = _login(client, "superadmin", "superadmin")

        # Fill bucket to limit
        for i in range(10):
            resp = client.post(
                "/admin/products/bulk/activate",
                json={"target": {"kind": "ids", "ids": [1]}, "active": True},
                headers=_auth(token),
            )
            assert resp.status_code == 200, f"fill request {i + 1}/10 blocked early"

        # Verify bucket is full
        resp_blocked = client.post(
            "/admin/products/bulk/activate",
            json={"target": {"kind": "ids", "ids": [1]}, "active": True},
            headers=_auth(token),
        )
        assert resp_blocked.status_code == 429, "bucket should be exhausted before reset"

        # Reset state
        reset_bulk_rate_limit_state()

        # First request after reset should succeed
        resp_after = client.post(
            "/admin/products/bulk/activate",
            json={"target": {"kind": "ids", "ids": [1]}, "active": True},
            headers=_auth(token),
        )
        assert resp_after.status_code == 200, (
            f"first request after reset should be 200, got {resp_after.status_code}"
        )
