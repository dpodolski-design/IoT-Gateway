"""Device repository."""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from iot_gateway.models import Device


async def get_by_device_id(session: AsyncSession, device_id: str) -> Device | None:
    result = await session.execute(select(Device).where(Device.device_id == device_id))
    return result.scalar_one_or_none()


async def get_speaker_by_msisdn(session: AsyncSession, msisdn: str) -> Device | None:
    result = await session.execute(
        select(Device).where(Device.msisdn == msisdn, Device.type == "speaker")
    )
    return result.scalar_one_or_none()


async def list_by_msisdn(session: AsyncSession, msisdn: str) -> list[Device]:
    result = await session.execute(select(Device).where(Device.msisdn == msisdn))
    return list(result.scalars().all())


async def list_all(session: AsyncSession) -> list[Device]:
    result = await session.execute(select(Device).order_by(Device.id))
    return list(result.scalars().all())


async def create(session: AsyncSession, **kwargs) -> Device:
    device = Device(**kwargs)
    session.add(device)
    await session.commit()
    await session.refresh(device)
    return device


async def update(session: AsyncSession, device: Device, **kwargs) -> Device:
    for k, v in kwargs.items():
        if v is not None and hasattr(device, k):
            setattr(device, k, v)
    await session.commit()
    await session.refresh(device)
    return device


async def delete(session: AsyncSession, device: Device) -> None:
    await session.delete(device)
    await session.commit()
