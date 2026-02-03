"""IoT -> Telekom: on webhook event (e.g. smoke), find rule and originate call."""
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from iot_gateway.integrations.freeswitch import originate as freeswitch_originate
from iot_gateway.repositories import device as device_repo
from iot_gateway.repositories import event_log as event_log_repo
from iot_gateway.repositories import rule as rule_repo

logger = logging.getLogger(__name__)


async def handle_webhook(
    session: AsyncSession,
    event_type: str,
    device_id: str,
) -> dict:
    """
    Find device and rule for event_type+device_id, run action (call), log result.
    Returns dict with success (bool), rule_id (int|None), target (str|None), call_result (dict).
    """
    device = await device_repo.get_by_device_id(session, device_id)
    if not device:
        await event_log_repo.create(
            session,
            event_kind="smoke_trigger_call",
            result="failure",
            device_id=device_id,
            details={"reason": "device_not_found"},
        )
        return {"success": False, "rule_id": None, "target": None, "call_result": None}

    rule = await rule_repo.get_by_event_and_device(session, event_type, device_id)
    if not rule or rule.action_type != "call":
        await event_log_repo.create(
            session,
            event_kind="smoke_trigger_call",
            result="failure",
            device_id=device_id,
            details={"reason": "no_rule_or_not_call", "event_type": event_type},
        )
        return {"success": False, "rule_id": None, "target": None, "call_result": None}

    target = rule.target
    call_result = await freeswitch_originate(target, caller_id="IoT-Gateway")
    call_id = call_result.get("call_id") if call_result else None
    success = call_result.get("success", False) if call_result else False

    await event_log_repo.create(
        session,
        event_kind="smoke_trigger_call",
        result="success" if success else "failure",
        device_id=device_id,
        rule_id=rule.id,
        call_id=call_id,
        target_number=target,
        details=call_result,
    )
    return {"success": success, "rule_id": rule.id, "target": target, "call_result": call_result}
