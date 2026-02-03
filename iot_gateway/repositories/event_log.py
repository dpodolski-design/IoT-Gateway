"""Event log repository."""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from iot_gateway.models import EventLog


async def create(
    session: AsyncSession,
    event_kind: str,
    result: str,
    device_id: str | None = None,
    rule_id: int | None = None,
    call_id: str | None = None,
    target_number: str | None = None,
    details: dict | None = None,
) -> EventLog:
    log = EventLog(
        event_kind=event_kind,
        device_id=device_id,
        rule_id=rule_id,
        call_id=call_id,
        target_number=target_number,
        result=result,
        details=details,
    )
    session.add(log)
    await session.commit()
    await session.refresh(log)
    return log


async def list_recent(session: AsyncSession, limit: int = 50) -> list[EventLog]:
    result = await session.execute(
        select(EventLog).order_by(EventLog.created_at.desc()).limit(limit)
    )
    return list(result.scalars().all())
