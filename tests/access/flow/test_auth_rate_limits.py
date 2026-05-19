"""
Regression: verify that post-hoc `limiter.limit(...)` calls in
`root.entrypoints.api.create_app` actually attach to the dispatched view.

Before the fix, the decorator's return value was discarded so Flask kept
dispatching the unwrapped view and no limit ever fired. See the commit that
introduced `_attach_limit(...)` for context.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.flow


def _make_app(monkeypatch, mysql_test_db, *, register_limit: str, recover_limit: str):
    monkeypatch.setenv("ROOT_APP_ENV", "dev")
    monkeypatch.setenv("ACCESS_DEFAULT_LOGIN", "admin")
    monkeypatch.setenv("ACCESS_DEFAULT_PASSWORD", "changeme")
    monkeypatch.setenv("ACCESS_JWT_SECRET", "test-jwt-secret-must-be-at-least-32-bytes")
    monkeypatch.setenv("ROOT_RATE_LIMIT_CUSTOMER_REGISTER", register_limit)
    monkeypatch.setenv("ROOT_RATE_LIMIT_CUSTOMER_RECOVER", recover_limit)
    from root.entrypoints.api import create_app
    return create_app()


def test_register_rate_limit_enforced_even_in_dev(monkeypatch, mysql_test_db):
    """
    Given customer-register limit set to 2/min in dev,
    When 3 register requests fire within the same minute,
    Then the 3rd request returns 429 (the post-hoc limit reassignment fires).
    """
    app = _make_app(
        monkeypatch, mysql_test_db,
        register_limit="2 per minute",
        recover_limit="100 per minute",
    )
    client = app.test_client()

    statuses = [
        client.post(
            "/auth/customer/register",
            json={"email": f"user{i}@example.com", "password": "strong-pw-12"},
        ).status_code
        for i in range(3)
    ]

    assert statuses[0] == 201
    assert statuses[1] == 201
    assert statuses[2] == 429, f"expected rate limit on 3rd attempt, got {statuses}"


def test_recover_rate_limit_enforced_even_in_dev(monkeypatch, mysql_test_db):
    """
    Given customer-recover limit set to 2/min in dev,
    When 3 recover requests fire within the same minute,
    Then the 3rd request returns 429 while the first two return 202.
    """
    app = _make_app(
        monkeypatch, mysql_test_db,
        register_limit="100 per minute",
        recover_limit="2 per minute",
    )
    client = app.test_client()

    # Recovery doesn't require an existing customer — always 202 on success.
    statuses = [
        client.post(
            "/auth/customer/recover",
            json={"email": "ghost@example.com"},
        ).status_code
        for _ in range(3)
    ]

    assert statuses[0] == 202
    assert statuses[1] == 202
    assert statuses[2] == 429, f"expected rate limit on 3rd attempt, got {statuses}"
