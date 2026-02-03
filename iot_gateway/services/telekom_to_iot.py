"""Telekom -> IoT: on incoming call, notify speaker device."""
import logging
from uuid import uuid4

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from iot_gateway.repositories import device as device_repo
from iot_gateway.repositories import event_log as event_log_repo

logger = logging.getLogger(__name__)


async def on_incoming_call(
    session: AsyncSession,
    to_msisdn: str,
    from_cli: str,
    call_id: str | None = None,
) -> dict:
    """
    Find speaker for to_msisdn, POST notification to device endpoint, log result.
    Returns dict with notified (bool), device_id (str|None), error (str|None).
    """
    call_id = call_id or str(uuid4())
    device = await device_repo.get_speaker_by_msisdn(session, to_msisdn)
    if not device:
        await event_log_repo.create(
            session,
            event_kind="incoming_call_notify",
            result="failure",
            device_id=None,
            details={"reason": "no_speaker_for_msisdn", "to_msisdn": to_msisdn},
        )
        return {"notified": False, "device_id": None, "error": "no_speaker_for_msisdn"}

    if not device.endpoint:
        await event_log_repo.create(
            session,
            event_kind="incoming_call_notify",
            result="failure",
            device_id=device.device_id,
            details={"reason": "no_endpoint"},
        )
        return {"notified": False, "device_id": device.device_id, "error": "no_endpoint"}

    payload = {"event": "incoming_call", "from_cli": from_cli, "call_id": call_id}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(device.endpoint, json=payload)
            success = 200 <= r.status_code < 300
            await event_log_repo.create(
                session,
                event_kind="incoming_call_notify",
                result="success" if success else "failure",
                device_id=device.device_id,
                call_id=call_id,
                details={"status_code": r.status_code, "response": r.text[:500] if r.text else None},
            )
            if not success:
                return {"notified": False, "device_id": device.device_id, "error": r.text}
            return {"notified": True, "device_id": device.device_id, "error": None}
    except Exception as e:
        logger.exception("Notify speaker failed")
        await event_log_repo.create(
            session,
            event_kind="incoming_call_notify",
            result="failure",
            device_id=device.device_id,
            call_id=call_id,
            details={"error": str(e)},
        )
        return {"notified": False, "device_id": device.device_id, "error": str(e)}
