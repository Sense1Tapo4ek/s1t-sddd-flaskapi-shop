from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from shared.ports.driving.bulk_schemas import (
    BulkFailureSchema,
    BulkResultSchema,
    BulkTarget,
    BulkTargetFilter,
    BulkTargetIds,
)

pytestmark = pytest.mark.unit

_target_adapter: TypeAdapter[BulkTarget] = TypeAdapter(BulkTarget)


class TestBulkTargetDiscriminator:
    def test_parses_ids_variant(self):
        """
        Given JSON with kind='ids',
        When parsed through the discriminated union,
        Then it becomes a BulkTargetIds.
        """
        ids = [str(uuid4()), str(uuid4())]
        parsed = _target_adapter.validate_python({"kind": "ids", "ids": ids})
        assert isinstance(parsed, BulkTargetIds)
        assert len(parsed.ids) == 2

    def test_parses_filter_variant(self):
        """
        Given JSON with kind='filter',
        When parsed through the discriminated union,
        Then it becomes a BulkTargetFilter.
        """
        parsed = _target_adapter.validate_python({
            "kind": "filter", "filter": {"active": True},
        })
        assert isinstance(parsed, BulkTargetFilter)
        assert parsed.filter == {"active": True}

    def test_rejects_unknown_kind(self):
        with pytest.raises(ValidationError):
            _target_adapter.validate_python({"kind": "csv", "rows": []})


class TestBulkTargetIdsLimits:
    def test_rejects_empty_ids(self):
        with pytest.raises(ValidationError):
            BulkTargetIds(ids=[])

    def test_rejects_more_than_1000_ids(self):
        with pytest.raises(ValidationError):
            BulkTargetIds(ids=[uuid4() for _ in range(1001)])

    def test_accepts_exactly_1000(self):
        target = BulkTargetIds(ids=[uuid4() for _ in range(1000)])
        assert len(target.ids) == 1000


class TestBulkResultSchema:
    def test_default_failed_empty_list(self):
        result = BulkResultSchema(total=5, ok=5)
        assert result.failed == []

    def test_rejects_negative_counters(self):
        with pytest.raises(ValidationError):
            BulkResultSchema(total=-1, ok=0)
        with pytest.raises(ValidationError):
            BulkResultSchema(total=0, ok=-1)

    def test_carries_failures(self):
        failed = [BulkFailureSchema(id=uuid4(), reason="in_use")]
        result = BulkResultSchema(total=3, ok=2, failed=failed)
        assert result.failed[0].reason == "in_use"
