"""Flow tests for bulk_action_log decorator (RED phase).

Contract being encoded:
- Decorator emits exactly one logging.INFO record on logger "api.bulk" per request.
- Record carries: event, action, mode, total, ok, failed_count, actor_id.
- Payload contents (ids, filter dict) are NOT present in the log record.
- Decorator passes the response through unchanged.
- On 422 (Pydantic validation failure) it still logs with zero counts.
"""
from __future__ import annotations

import logging

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


# ─── Tests ──────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _reset_bulk_rate_limit_state():
    """Even though these tests don't exercise rate-limit, an earlier test
    in the same process might have populated the bucket. Reset before
    AND after each test to keep isolation tight."""
    reset_bulk_rate_limit_state()
    yield
    reset_bulk_rate_limit_state()


class TestBulkActionLogDecorator:
    def test_logs_event_with_ids_mode_and_counts(self, superadmin_dev_app, caplog):
        """
        Given a superadmin token and POST /admin/products/bulk/activate with ids target,
        When the request completes with 200,
        Then exactly one INFO record on 'api.bulk' is emitted with
             mode='ids', total==3, ok+failed_count==3, and actor_id matches the JWT sub.
        """
        client = superadmin_dev_app.test_client()
        token = _login(client, "superadmin", "superadmin")

        with caplog.at_level(logging.INFO, logger="api.bulk"):
            resp = client.post(
                "/admin/products/bulk/activate",
                json={"target": {"kind": "ids", "ids": [1, 2, 3]}, "active": True},
                headers=_auth(token),
            )

        assert resp.status_code == 200
        bulk_records = [r for r in caplog.records if r.name == "api.bulk"]
        assert len(bulk_records) == 1, f"expected 1 bulk log record, got {len(bulk_records)}"

        rec = bulk_records[0]
        assert rec.event == "bulk action"
        assert rec.action == "products.bulk_activate"
        assert rec.mode == "ids"
        assert rec.total == 3
        assert rec.ok + rec.failed_count == 3
        # actor_id should match the 'sub' from the superadmin JWT
        assert rec.actor_id is not None

    def test_logs_event_with_filter_mode(self, superadmin_dev_app, caplog):
        """
        Given a POST with target.kind='filter',
        When the request completes,
        Then the log record has mode='filter'.
        """
        client = superadmin_dev_app.test_client()
        token = _login(client, "superadmin", "superadmin")

        with caplog.at_level(logging.INFO, logger="api.bulk"):
            resp = client.post(
                "/admin/products/bulk/activate",
                json={"target": {"kind": "filter", "filter": {}}, "active": True},
                headers=_auth(token),
            )

        assert resp.status_code == 200
        bulk_records = [r for r in caplog.records if r.name == "api.bulk"]
        assert len(bulk_records) == 1
        assert bulk_records[0].mode == "filter"

    def test_logs_payload_is_not_in_record(self, superadmin_dev_app, caplog):
        """
        Given a POST with specific ids [1, 2, 3],
        When the decorator logs,
        Then neither the ids list nor any individual id value appears in the record dict.
        """
        client = superadmin_dev_app.test_client()
        token = _login(client, "superadmin", "superadmin")

        with caplog.at_level(logging.INFO, logger="api.bulk"):
            client.post(
                "/admin/products/bulk/activate",
                json={"target": {"kind": "ids", "ids": [1, 2, 3]}, "active": True},
                headers=_auth(token),
            )

        bulk_records = [r for r in caplog.records if r.name == "api.bulk"]
        assert len(bulk_records) == 1
        rec_dict_str = str(bulk_records[0].__dict__)

        # Payload contents must NOT appear in the serialised record dict.
        # The string "ids" appears legitimately only in the mode value ("ids")
        # — the raw list literal and per-id values must not.
        assert "[1, 2, 3]" not in rec_dict_str
        assert "'ids': [" not in rec_dict_str
        # The key 'target' from the request body must not appear
        assert "'target'" not in rec_dict_str
        assert '"target"' not in rec_dict_str

    def test_logs_event_even_on_validation_error(self, superadmin_dev_app, caplog):
        """
        Given a POST with an empty ids list (violates min_length=1),
        When the route returns 422,
        Then the bulk decorator still emits a log record with total=0, ok=0, failed_count=0.
        """
        client = superadmin_dev_app.test_client()
        token = _login(client, "superadmin", "superadmin")

        with caplog.at_level(logging.INFO, logger="api.bulk"):
            resp = client.post(
                "/admin/products/bulk/activate",
                json={"target": {"kind": "ids", "ids": []}, "active": True},
                headers=_auth(token),
            )

        assert resp.status_code == 422
        bulk_records = [r for r in caplog.records if r.name == "api.bulk"]
        assert len(bulk_records) == 1, (
            "decorator must log even when route raises a validation error"
        )
        rec = bulk_records[0]
        assert rec.total == 0
        assert rec.ok == 0
        assert rec.failed_count == 0

    def test_bulk_action_log_is_importable_and_callable(self):
        """
        Given the module is importable (this test runs only if import succeeds),
        When bulk_action_log is called with an action string,
        Then it returns a decorator (callable).
        """
        decorator = bulk_action_log("products.bulk_activate")
        assert callable(decorator)
