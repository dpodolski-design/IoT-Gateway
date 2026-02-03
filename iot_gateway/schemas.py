"""Pydantic schemas for API request/response."""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DeviceCreate(BaseModel):
    device_id: str
    type: str = Field(..., pattern="^(speaker|sensor_smoke)$")
    msisdn: str | None = None
    subscriber_id: str | None = None
    vendor: str | None = None
    endpoint: str | None = None
    metadata: dict[str, Any] | None = None


class DeviceUpdate(BaseModel):
    msisdn: str | None = None
    subscriber_id: str | None = None
    vendor: str | None = None
    endpoint: str | None = None
    metadata: dict[str, Any] | None = None


class DeviceResponse(BaseModel):
    id: int
    device_id: str
    type: str
    msisdn: str | None
    subscriber_id: str | None
    vendor: str | None
    endpoint: str | None
    metadata: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RuleCreate(BaseModel):
    event_type: str
    device_id: str
    action_type: str = "call"
    target: str
    active: bool = True


class RuleUpdate(BaseModel):
    action_type: str | None = None
    target: str | None = None
    active: bool | None = None


class RuleResponse(BaseModel):
    id: int
    event_type: str
    device_id: str
    action_type: str
    target: str
    active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class EventLogResponse(BaseModel):
    id: int
    event_kind: str
    device_id: str | None
    rule_id: int | None
    call_id: str | None
    target_number: str | None
    result: str
    details: dict[str, Any] | None
    created_at: datetime

    model_config = {"from_attributes": True}


class SimulateIncomingCallRequest(BaseModel):
    to_msisdn: str
    from_cli: str
    call_id: str | None = None


class WebhookRequest(BaseModel):
    event_type: str
    device_id: str
    timestamp: str | None = None
    payload: dict[str, Any] | None = None
