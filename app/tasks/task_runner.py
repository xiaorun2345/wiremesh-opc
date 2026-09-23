from __future__ import annotations

"""
Celery 任务定义
替代 FastAPI BackgroundTasks，提供可靠的异步任务执行
"""
import asyncio
from loguru import logger
from app.core.celery_app import celery_app


@celery_app.task(
    bind=True,
    name="openspec.run_task",
    max_retries=0,          # 不自动重试（由 Orchestrator 内部处理重试）
    acks_late=True,
)
def run_task_celery(self, task_id: str, start_step: str | None = None):
    """
    Celery 任务：执行算量任务。
    在独立 worker 进程中运行，不阻塞 FastAPI 主进程。
    """
    logger.info(f"[Celery] 开始执行任务 {task_id}, start_step={start_step}")
    try:
        # 使用独立事件循环，避免与 Celery 内部循环冲突
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(_run_task_async(task_id, start_step))
        finally:
            loop.close()
        logger.info(f"[Celery] 任务 {task_id} 完成")
    except Exception as e:
        logger.error(f"[Celery] 任务 {task_id} 失败: {e}")
        raise


async def _run_task_async(task_id: str, start_step: str | None):
    """异步执行任务（在 Celery worker 的事件循环中运行）"""
    from app.utils.db import AsyncSessionLocal
    from app.v2.core.task_service_v2 import TaskServiceV2

    async with AsyncSessionLocal() as db:
        svc = TaskServiceV2(db)
        await svc.run_task(task_id, start_step=start_step)
