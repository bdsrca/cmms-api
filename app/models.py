"""Pydantic request and response models used by controlled AI routes."""

from typing import Any

from pydantic import BaseModel, Field


class TextRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=4000)
    environment_code: str | None = None
    source: str | None = None


class SummaryResponse(BaseModel):
    summary: str


class AssistantResponse(BaseModel):
    mode: str
    response: str
    model: str
    safety: dict[str, Any]


class ExtractFieldsRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=4000)
    environment_code: str | None = None
    valid_buildings: list[str] | None = None
    valid_priorities: list[str] | None = None
    source: str | None = None


class EmailIntakeRequest(BaseModel):
    from_email: str = Field(..., min_length=1, max_length=320)
    to_email: str = Field(..., min_length=1, max_length=320)
    subject: str = Field(..., min_length=1, max_length=240)
    body: str = Field(..., min_length=1, max_length=4000)
    environment_code: str | None = None


class ExtractFieldsResponse(BaseModel):
    request_type: str
    building: str | None
    room: str | None
    priority: str
    summary: str
    missing_fields: list[str]
    needs_human_review: bool
    confidence: float


class IntakeFields(BaseModel):
    building: str | None
    room: str | None
    priority: str
    summary: str


class IntakeValidation(BaseModel):
    can_create_work_order: bool
    needs_human_review: bool
    missing_fields: list[str]
    errors: list[str]
    warnings: list[str]


class IntakeDrafts(BaseModel):
    draft_wo_description: str
    internal_note: str
    client_reply: str


class IntakeResponse(BaseModel):
    run_id: str | None = None
    endpoint: str | None = None
    environment_code: str | None = None
    trace: dict[str, Any] | None = None
    contract: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    ai_validation: dict[str, Any] | None = None
    review: dict[str, Any] | None = None
    submission: dict[str, Any] | None = None
    request: dict[str, Any] | None = None
    metadata_review: dict[str, Any] | None = None
    raw: dict[str, Any] | None = None
    request_type: str | None = None
    classification_confidence: float | None = None
    fields: IntakeFields | None = None
    validation: IntakeValidation | None = None
    drafts: IntakeDrafts | None = None
    model: str
