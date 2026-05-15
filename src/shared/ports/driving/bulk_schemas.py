"""Shared schemas for bulk operations across contexts.

Two target modes — explicit ids or current filter — encoded as a
discriminated union by ``kind``. Caller is responsible for defining
the filter schema; here it stays untyped (``dict``) because every
context has its own filter shape.

See ``docs/superpowers/specs/2026-05-15-bulk-actions-design.md`` §5.1.
"""
from __future__ import annotations

from typing import Annotated, Any, Literal, Union
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# Aggregate ids may be either int (autoincrement, the current project's
# default) or UUID (future contexts that adopt UUID PKs). Pydantic tries
# int first and falls back to UUID, so the discriminator stays unambiguous.
AggregateId = Union[int, UUID]


class BulkTargetIds(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: Literal["ids"] = "ids"
    ids: list[AggregateId] = Field(..., min_length=1, max_length=1000)


class BulkTargetFilter(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: Literal["filter"] = "filter"
    filter: dict[str, Any] = Field(default_factory=dict)


BulkTarget = Annotated[
    Union[BulkTargetIds, BulkTargetFilter],
    Field(discriminator="kind"),
]


class BulkFailureSchema(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: AggregateId
    reason: str


class BulkResultSchema(BaseModel):
    model_config = ConfigDict(frozen=True)

    total: int = Field(..., ge=0)
    ok: int = Field(..., ge=0)
    failed: list[BulkFailureSchema] = Field(default_factory=list)
