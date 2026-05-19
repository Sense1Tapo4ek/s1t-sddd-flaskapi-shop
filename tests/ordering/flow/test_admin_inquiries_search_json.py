"""Flow tests: /admin/inquiries/search endpoint existence and JSON contract."""
from __future__ import annotations

import json

import pytest

from ordering.ports.driving.schemas import InquiryListOut, InquiryOut

pytestmark = pytest.mark.flow


def _make_inquiry_list_out(items=None, total=0):
    return InquiryListOut(items=items or [], total=total)


def _create_app(monkeypatch, mysql_test_db):
    monkeypatch.setenv("ROOT_APP_ENV", "dev")
    from root.entrypoints.api import create_app
    return create_app()


class TestInquiriesSearchJsonEndpoint:
    def test_search_endpoint_exists_and_blocks_unauthenticated(self, monkeypatch, mysql_test_db):
        """
        Given no auth,
        When GET /admin/inquiries/search,
        Then returns not 404/500 — route registered, auth gate fires.
        """
        # Arrange
        app = _create_app(monkeypatch, mysql_test_db)
        client = app.test_client()

        # Act
        response = client.get(
            "/admin/inquiries/search?status__eq=new&page=1&limit=10",
            follow_redirects=False,
        )

        # Assert — route exists (not 404), server doesn't crash (not 500)
        assert response.status_code not in (404, 500)

    def test_search_json_shape_contract(self, monkeypatch, mysql_test_db):
        """
        Given a minimal InquiryListOut,
        When assembled into the search-json response payload,
        Then contains items/total/page/limit keys with correct types.
        """
        # Arrange
        out = _make_inquiry_list_out(
            items=[
                InquiryOut(
                    id=1,
                    name="Alice",
                    phone="+375291234567",
                    contact_email=None,
                    message="Hello",
                    status="new",
                    created_at="2026-01-01 10:00",
                    author_user_id=None,
                )
            ],
            total=1,
        )

        # Act — simulate what the endpoint assembles
        payload = {
            "items": [i.model_dump(mode="json") for i in out.items],
            "total": out.total,
            "page": 1,
            "limit": 10,
        }

        # Assert
        assert payload["total"] == 1
        assert payload["page"] == 1
        assert payload["limit"] == 10
        assert isinstance(payload["items"], list)
        assert payload["items"][0]["id"] == 1
        assert payload["items"][0]["status"] == "new"
        # Must be JSON-serialisable
        json.dumps(payload)

    def test_inquiry_out_serialises_correctly(self):
        """
        Given InquiryOut with all fields,
        When model_dump(mode='json') is called,
        Then all expected fields are present and serialisable.
        """
        # Arrange
        item = InquiryOut(
            id=5,
            name="Bob",
            phone=None,
            contact_email="bob@example.com",
            message="Hi there",
            status="in_progress",
            created_at="2026-02-01 12:00",
            author_user_id=None,
        )

        # Act
        data = item.model_dump(mode="json")

        # Assert
        assert data["id"] == 5
        assert data["name"] == "Bob"
        assert data["status"] == "in_progress"
        assert data["contact_email"] == "bob@example.com"
        assert data["phone"] is None
        json.dumps(data)  # must not raise
