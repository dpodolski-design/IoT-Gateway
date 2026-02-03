"""FastAPI application and routes."""
import logging
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from iot_gateway.config import settings
from iot_gateway.db import get_db
from iot_gateway.repositories import device as device_repo
from iot_gateway.repositories import event_log as event_log_repo
from iot_gateway.repositories import rule as rule_repo
from iot_gateway.schemas import (
    DeviceCreate,
    DeviceResponse,
    DeviceUpdate,
    EventLogResponse,
    RuleCreate,
    RuleResponse,
    RuleUpdate,
    SimulateIncomingCallRequest,
    WebhookRequest,
)
from iot_gateway.services import iot_to_telekom as iot_to_telekom_svc
from iot_gateway.services import telekom_to_iot as telekom_to_iot_svc

from fastapi import FastAPI
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)
app = FastAPI(title="IoT Gateway", description="Prototype TAS IoT integration module")

DB_UNAVAILABLE_MSG = "Database unavailable. Ensure PostgreSQL is running and DATABASE_URL in .env is correct."


async def _db_unavailable_handler(request, exc: Exception):
    return JSONResponse(status_code=503, content={"detail": DB_UNAVAILABLE_MSG})


try:
    import asyncpg.exceptions as _asyncpg_exc
    app.add_exception_handler(_asyncpg_exc.ConnectionDoesNotExistError, _db_unavailable_handler)
    app.add_exception_handler(_asyncpg_exc.InvalidPasswordError, _db_unavailable_handler)
    app.add_exception_handler(_asyncpg_exc.ConnectionFailure, _db_unavailable_handler)
    app.add_exception_handler(_asyncpg_exc.TooManyConnectionsError, _db_unavailable_handler)
except ImportError:
    pass

SessionDep = Annotated[AsyncSession, Depends(get_db)]


@app.get("/")
async def root():
    """Root: redirect to API docs."""
    return RedirectResponse(url="/docs", status_code=302)


def _device_to_response(d):
    return DeviceResponse(
        id=d.id,
        device_id=d.device_id,
        type=d.type,
        msisdn=d.msisdn,
        subscriber_id=d.subscriber_id,
        vendor=d.vendor,
        endpoint=d.endpoint,
        metadata=d.metadata_,
        created_at=d.created_at,
        updated_at=d.updated_at,
    )


@app.get("/devices", response_model=list[DeviceResponse])
async def list_devices(
    session: SessionDep,
    msisdn: str | None = Query(None, description="Filter by MSISDN"),
):
    if msisdn is not None:
        devices = await device_repo.list_by_msisdn(session, msisdn)
    else:
        devices = await device_repo.list_all(session)
    return [_device_to_response(d) for d in devices]


@app.post("/devices", response_model=DeviceResponse)
async def create_device(session: SessionDep, body: DeviceCreate):
    existing = await device_repo.get_by_device_id(session, body.device_id)
    if existing:
        raise HTTPException(status_code=409, detail="Device already exists")
    data = body.model_dump()
    data["metadata_"] = data.pop("metadata", None)
    device = await device_repo.create(session, **data)
    return _device_to_response(device)


@app.get("/devices/{device_id}", response_model=DeviceResponse)
async def get_device(session: SessionDep, device_id: str):
    device = await device_repo.get_by_device_id(session, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return _device_to_response(device)


@app.put("/devices/{device_id}", response_model=DeviceResponse)
async def update_device(session: SessionDep, device_id: str, body: DeviceUpdate):
    device = await device_repo.get_by_device_id(session, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    data = body.model_dump(exclude_unset=True)
    if "metadata" in data:
        data["metadata_"] = data.pop("metadata")
    await device_repo.update(session, device, **data)
    return _device_to_response(device)


@app.delete("/devices/{device_id}", status_code=204)
async def delete_device(session: SessionDep, device_id: str):
    device = await device_repo.get_by_device_id(session, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    await device_repo.delete(session, device)


@app.get("/rules", response_model=list[RuleResponse])
async def list_rules(session: SessionDep):
    rules = await rule_repo.list_all(session)
    return [RuleResponse.model_validate(r) for r in rules]


@app.post("/rules", response_model=RuleResponse)
async def create_rule(session: SessionDep, body: RuleCreate):
    rule = await rule_repo.create(session, **body.model_dump())
    return RuleResponse.model_validate(rule)


@app.get("/rules/{rule_id}", response_model=RuleResponse)
async def get_rule(session: SessionDep, rule_id: int):
    rule = await rule_repo.get_by_id(session, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return RuleResponse.model_validate(rule)


@app.put("/rules/{rule_id}", response_model=RuleResponse)
async def update_rule(session: SessionDep, rule_id: int, body: RuleUpdate):
    rule = await rule_repo.get_by_id(session, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    await rule_repo.update(session, rule, **body.model_dump(exclude_unset=True))
    return RuleResponse.model_validate(rule)


@app.delete("/rules/{rule_id}", status_code=204)
async def delete_rule(session: SessionDep, rule_id: int):
    rule = await rule_repo.get_by_id(session, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    await rule_repo.delete(session, rule)


@app.get("/logs", response_model=list[EventLogResponse])
async def list_logs(session: SessionDep, limit: int = Query(50, ge=1, le=500)):
    logs = await event_log_repo.list_recent(session, limit=limit)
    return [EventLogResponse.model_validate(l) for l in logs]


def _check_webhook_api_key(x_api_key: str | None) -> None:
    if not x_api_key or x_api_key != settings.webhook_api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key")


@app.post("/simulate/incoming-call")
async def simulate_incoming_call(session: SessionDep, body: SimulateIncomingCallRequest):
    """Simulate incoming call to to_msisdn; notify registered speaker device."""
    result = await telekom_to_iot_svc.on_incoming_call(
        session,
        to_msisdn=body.to_msisdn,
        from_cli=body.from_cli,
        call_id=body.call_id,
    )
    if not result.get("notified") and result.get("error") == "no_speaker_for_msisdn":
        raise HTTPException(status_code=404, detail="No speaker device for this MSISDN")
    return result


@app.post("/webhook")
async def webhook(
    session: SessionDep,
    body: WebhookRequest,
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
):
    """Receive IoT events (e.g. smoke); require X-API-Key. Triggers rule action (e.g. call)."""
    _check_webhook_api_key(x_api_key)
    result = await iot_to_telekom_svc.handle_webhook(
        session, event_type=body.event_type, device_id=body.device_id
    )
    return result


@app.post("/test/notify")
async def test_notify(payload: dict):
    """Demo endpoint: receives incoming-call notification (use as device endpoint). Returns 200 and logs body."""
    logger.info("Test notify received: %s", payload)
    return {"status": "ok", "received": payload}
