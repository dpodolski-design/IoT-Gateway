"""Rule repository."""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from iot_gateway.models import Rule


async def get_by_id(session: AsyncSession, id: int) -> Rule | None:
    result = await session.execute(select(Rule).where(Rule.id == id))
    return result.scalar_one_or_none()


async def get_by_event_and_device(session: AsyncSession, event_type: str, device_id: str) -> Rule | None:
    result = await session.execute(
        select(Rule).where(
            Rule.event_type == event_type,
            Rule.device_id == device_id,
            Rule.active == True,
        )
    )
    return result.scalar_one_or_none()


async def list_all(session: AsyncSession) -> list[Rule]:
    result = await session.execute(select(Rule).order_by(Rule.id))
    return list(result.scalars().all())


async def create(session: AsyncSession, **kwargs) -> Rule:
    rule = Rule(**kwargs)
    session.add(rule)
    await session.commit()
    await session.refresh(rule)
    return rule


async def update(session: AsyncSession, rule: Rule, **kwargs) -> Rule:
    for k, v in kwargs.items():
        if v is not None and hasattr(rule, k):
            setattr(rule, k, v)
    await session.commit()
    await session.refresh(rule)
    return rule


async def delete(session: AsyncSession, rule: Rule) -> None:
    await session.delete(rule)
    await session.commit()
