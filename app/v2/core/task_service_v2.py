from __future__ import annotations

"""
V2 TaskService
==============
与 V1 相同，只是把 AgentOrchestrator 换成 OrchestratorV2。
"""
import json
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from loguru import logger

from app.models.task import Task
from app.v2.core.orchestrator_v2 import OrchestratorV2
from app.services.minio_service import MinioService
from app.core.memory.redis_memory import TaskMemory

TASK_TIMEOUT = 1800

# 文件类型 → 解析 Agent 映射
PARSE_AGENT_MAP = {
    "pdf":  "TextExtractAgent",
    "dwg":  "CadParseAgent",
    "dxf":  "CadParseAgent",
    "jpg":  "VisionParseAgent",
    "jpeg": "VisionParseAgent",
    "png":  "VisionParseAgent",
}

def _get_steps(file_type: str) -> list:
    """根据文件类型生成正确的步骤列表"""
    parse_agent = PARSE_AGENT_MAP.get(file_type, "TextExtractAgent")
    return [
        parse_agent,
        "WireMeshSpecAgent", "WireMeshQuote", "WireMeshReport",
    ]


class TaskServiceV2:
    def __init__(self, db: AsyncSession):
        self.db   = db
        self.minio = MinioService()

    async def create_task(self, task_id: str, user_id: str,
                          file_name: str, file_type: str, content: bytes) -> Task:
        file_id = f"uploads/{task_id}/{file_name}"
        self.minio.upload(file_id, content, file_name)

        steps = [{"agent": s, "status": "PENDING", "duration_ms": None} for s in _get_steps(file_type)]
        task = Task(
            id=task_id, user_id=user_id,
            file_name=file_name, file_type=file_type,
            file_id=file_id, file_size=len(content),
            status="PENDING",
            steps_json=json.dumps(steps, ensure_ascii=False),
        )
        self.db.add(task)
        await self.db.commit()
        await self.db.refresh(task)
        return task

    async def create_task_streaming(self, task_id: str, user_id: str,
                                    file_name: str, file_type: str,
                                    file_obj, file_size: int) -> Task:
        """流式创建任务：文件通过流式上传到 MinIO，避免全量加载到内存"""
        file_id = f"uploads/{task_id}/{file_name}"
        self.minio.upload_stream(file_id, file_obj, file_size, file_name)

        steps = [{"agent": s, "status": "PENDING", "duration_ms": None} for s in _get_steps(file_type)]
        task = Task(
            id=task_id, user_id=user_id,
            file_name=file_name, file_type=file_type,
            file_id=file_id, file_size=file_size,
            status="PENDING",
            steps_json=json.dumps(steps, ensure_ascii=False),
        )
        self.db.add(task)
        await self.db.commit()
        await self.db.refresh(task)
        return task

    async def run_task(self, task_id: str, start_step: str | None = None):
        """后台执行任务（使用 OrchestratorV2 + DecisionAgent）"""
        result = await self.db.execute(select(Task).where(Task.id == task_id))
        task = result.scalar_one_or_none()
        if not task:
            return

        mem_before = self._get_memory_mb()
        logger.info(f"[V2] 任务 {task_id} 开始，内存={mem_before:.1f}MB")

        orchestrator = OrchestratorV2(self.db)
        try:
            await asyncio.wait_for(
                orchestrator.run(task, start_step=start_step),
                timeout=TASK_TIMEOUT,
            )
        except asyncio.TimeoutError:
            logger.error(f"[V2] 任务 {task_id} 超时")
            task.status    = "FAILED"
            task.error_msg = f"任务执行超时（{TASK_TIMEOUT // 60} 分钟）"
            await self.db.commit()
        except Exception as e:
            logger.error(f"[V2] 任务 {task_id} 异常: {e}")
            task.status    = "FAILED"
            task.error_msg = str(e)
            await self.db.commit()
        finally:
            mem_after = self._get_memory_mb()
            logger.info(f"[V2] 任务 {task_id} 结束，内存增量={mem_after - mem_before:+.1f}MB")

    def _get_memory_mb(self) -> float:
        try:
            import psutil
            return psutil.Process().memory_info().rss / 1024 / 1024
        except ImportError:
            return 0.0

    async def resume_task(self, task_id: str, override_data: dict) -> str:
        result = await self.db.execute(select(Task).where(Task.id == task_id))
        task = result.scalar_one_or_none()

        steps = json.loads(task.steps_json or "[]")
        default_step = _get_steps(task.file_type)[0]
        failed_step = next(
            (s["agent"] for s in steps if s["status"] in ("FAILED", "RUNNING", "PAUSED")),
            default_step,
        )

        if override_data:
            mem = TaskMemory(task_id)
            await mem.set("override_data", override_data)
            for key in ("rooms", "walls", "doors", "windows", "water_elec", "quantity_list"):
                if key in override_data:
                    await mem.set(key, override_data[key])

        task.status = "RUNNING"
        await self.db.commit()
        return failed_step

    async def cancel_task(self, task_id: str):
        result = await self.db.execute(select(Task).where(Task.id == task_id))
        task = result.scalar_one_or_none()
        if task:
            task.status = "CANCELLED"
            await self.db.commit()
