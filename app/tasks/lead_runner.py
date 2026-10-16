"""Celery jobs for scheduled public procurement lead collection."""
from __future__ import annotations

import asyncio

from loguru import logger
from sqlalchemy import select

from app.core.celery_app import celery_app


@celery_app.task(name="wiremesh_opc.poll_leads", acks_late=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def poll_leads_celery() -> dict:
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_poll_all())
    finally:
        loop.close()


async def _poll_all() -> dict:
    from app.models.opc import LeadSource
    from app.services.lead_radar import run_source
    from app.utils.db import AsyncSessionLocal

    result = {"sources": 0, "created": 0, "duplicates": 0, "high_priority": 0, "failed": 0}
    async with AsyncSessionLocal() as db:
        rows = await db.execute(select(LeadSource).where(LeadSource.enabled.is_(True)))
        for source in rows.scalars().all():
            result["sources"] += 1
            try:
                outcome = await run_source(db, source)
                for key in ("created", "duplicates", "high_priority"):
                    result[key] += outcome.get(key, 0)
            except Exception as exc:
                result["failed"] += 1
                logger.warning("海外商机数据源 {} 采集失败：{}", source.name, exc)
    return result
