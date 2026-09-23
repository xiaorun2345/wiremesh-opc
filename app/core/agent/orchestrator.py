from __future__ import annotations

import json
import time
import asyncio
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.agent.base_agent import BaseAgent, AgentStatus
from app.core.mcp.message import MCPMessage, MsgType
from app.core.memory.redis_memory import TaskMemory
from app.core.hooks.hook_manager import HookManager, log_hook
from app.models.task import Task


MAGIC_MAP = {
    b"\x25\x50\x44\x46": "pdf",
    b"\xAC\x1C\x00\x00": "dwg",
    b"\x41\x43\x31\x30": "dxf",
    b"\xFF\xD8\xFF":      "jpg",
    b"\x89\x50\x4E\x47": "png",
}


class AgentOrchestrator:
    """动态 DAG 编排器：根据文件类型运行时决定 Agent 执行路径"""

    # 各文件类型对应的 Agent 执行链（QuantityCalc 和 ReportExport 已内联为方法）
    DAG_ROUTES = {
        "pdf":  ["TextExtractAgent",  "BudgetCheckAgent"],
        "dwg":  ["CadParseAgent",     "BudgetCheckAgent"],
        "dxf":  ["CadParseAgent",     "BudgetCheckAgent"],
        "jpg":  ["TextExtractAgent",  "BudgetCheckAgent"],
        "jpeg": ["TextExtractAgent",  "BudgetCheckAgent"],
        "png":  ["TextExtractAgent",  "BudgetCheckAgent"],
    }

    STRATEGY_MAP = {
        "pdf":  "TextExtractAgent",
        "dwg":  "CadParseAgent",
        "dxf":  "CadParseAgent",
        "jpg":  "TextExtractAgent",
        "jpeg": "TextExtractAgent",
        "png":  "TextExtractAgent",
    }

    def __init__(self, db: AsyncSession):
        self.db = db
        self.hook_manager = HookManager()
        for event in ("before_agent_run", "after_agent_run", "on_agent_error", "on_whole_finish"):
            self.hook_manager.register(event, log_hook(event))
        self._agents: dict[str, BaseAgent] = {}
        self._register_agents()

    def _register_agents(self):
        from app.agents.text_extract import TextExtractAgent
        from app.agents.cad_parse import CadParseAgent
        from app.agents.vision_parse import VisionParseAgent
        from app.agents.budget_check import BudgetCheckAgent

        for agent_cls in [TextExtractAgent, CadParseAgent, VisionParseAgent, BudgetCheckAgent]:
            agent = agent_cls(hook_manager=self.hook_manager)
            self._agents[agent.name] = agent

    async def run(self, task: Task, start_step: str | None = None):
        trace_id = task.id
        file_type = task.file_type
        route = self.DAG_ROUTES.get(file_type, self.DAG_ROUTES["pdf"])

        start_idx = 0
        if start_step and start_step in route:
            start_idx = route.index(start_step)

        mem = TaskMemory(trace_id)
        await mem.set("file_id", task.file_id)
        await mem.set("file_type", file_type)
        await mem.set("file_name", task.file_name)

        # 文件分类（替代 FileClassifyAgent）+ 图片内容分析
        await self._classify_file(task, mem, file_type)

        # 图片分析可能覆盖了路由
        if file_type in ("jpg", "jpeg", "png"):
            image_route = await mem.get("image_route")
            if image_route:
                route = image_route
                start_idx = 0  # 重新计算起始索引

        await self._update_task(task.id, status="RUNNING")

        for idx, agent_name in enumerate(route):
            if idx < start_idx:
                continue

            agent = self._agents.get(agent_name)
            if not agent:
                # 处理内联方法（原 Agent 已简化为方法）
                if agent_name == "QuantityCalc":
                    logger.info(f"[Orchestrator] 执行算量计算（内联）")
                    user_id = task.created_by if hasattr(task, "created_by") else None
                    await self._calculate_quantities(trace_id, user_id)
                    await self._update_step(task.id, agent_name, "SUCCESS", route, duration_ms=0)
                    continue
                elif agent_name == "ReportExport":
                    logger.info(f"[Orchestrator] 执行报告导出（内联）")
                    await self._export_report(trace_id)
                    await self._update_step(task.id, agent_name, "SUCCESS", route, duration_ms=0)
                    continue
                else:
                    logger.warning(f"Agent {agent_name} 未注册，跳过")
                    continue

            msg = MCPMessage(
                trace_id=trace_id,
                msg_type=MsgType.TASK,
                payload={"step_index": idx},
                sender_agent="orchestrator",
                target_agent=agent_name,
            )

            await self._update_task(task.id, current_step=agent_name, progress=int(idx / len(route) * 100))
            await self._update_step(task.id, agent_name, "RUNNING", route)

            start_ts = time.time()
            result = await agent.run(msg)
            duration_ms = int((time.time() - start_ts) * 1000)

            if result.status == AgentStatus.FAILED:
                for retry in range(2):
                    logger.warning(f"[{agent_name}] 第 {retry+1} 次重试")
                    await asyncio.sleep(1)
                    result = await agent.run(msg)
                    if result.status == AgentStatus.SUCCESS:
                        break

            if result.status == AgentStatus.FAILED:
                await self._update_step(task.id, agent_name, "FAILED", route, duration_ms)
                await self._update_task(task.id, status="FAILED", error_msg=result.error)
                return

            await self._update_step(task.id, agent_name, "SUCCESS", route, duration_ms)

            # PDF 包含结构图/效果图页，动态插入 VisionParseAgent
            if result.data.get("needs_vision_parse") and agent_name == "TextExtractAgent":
                vision_pages = await mem.get("pdf_vision_pages", {})
                logger.info(f"[Orchestrator] PDF 包含视觉页面: {vision_pages}，插入 VisionParseAgent")
                await self._run_vision_parse_for_pdf(task, mem)

            if result.data.get("need_human_review"):
                review_data = {
                    "paused_at_step": agent_name,
                    "rooms":        await mem.get("rooms", []),
                    "walls":        await mem.get("walls", []),
                    "doors":        await mem.get("doors", []),
                    "windows":      await mem.get("windows", []),
                    "water_elec":   await mem.get("water_elec", []),
                    "quantity_list": await mem.get("quantity_list", {}),
                    "review_hint":  result.data.get("review_hint", "请检查解析结果后续跑"),
                }
                await mem.set("human_review_data", review_data)
                await self._update_task(task.id, status="PAUSED", current_step=agent_name)
                logger.info(f"[Orchestrator] 任务 {task.id} 暂停等待人工审核，步骤={agent_name}")
                return

        await self._update_task(task.id, status="SUCCESS", progress=100, current_step=None)
        await self.hook_manager.trigger("on_whole_finish", task_id=task.id)
        await mem.clear()

    async def _classify_file(self, task: Task, mem: TaskMemory, file_type: str):
        """文件分类：魔数校验 + 图片内容分析 + 分流策略（替代 FileClassifyAgent）"""
        from app.services.minio_service import MinioService

        try:
            data = MinioService().download(task.file_id)
            header = data[:16]
            detected = next((t for magic, t in MAGIC_MAP.items() if header.startswith(magic)), None)
            if detected and detected != file_type:
                logger.warning(f"文件类型不一致：声明={file_type}, 检测={detected}，以检测为准")
                file_type = detected
                await mem.set("file_type", file_type)
        except Exception as e:
            logger.warning(f"文件魔数校验失败: {e}，使用上传时类型")

        # 图片内容分析：检测是文档扫描件、结构图还是效果图
        if file_type in ("jpg", "jpeg", "png"):
            strategy, route = await self._classify_image_content(task, mem, file_type)
        else:
            strategy = self.STRATEGY_MAP.get(file_type, "TextExtractAgent")
            await mem.set("parse_strategy", strategy)
            route = None

        await mem.set("parse_strategy", strategy)
        logger.info(f"[FileClassify] 类型={file_type}, 策略={strategy}")

    async def _run_vision_parse_for_pdf(self, task: Task, mem: TaskMemory):
        """为 PDF 中的结构图/效果图页运行 VisionParseAgent"""
        vision_agent = self._agents.get("VisionParseAgent")
        if not vision_agent:
            logger.warning("[Orchestrator] VisionParseAgent 未注册，跳过 PDF 视觉解析")
            return

        msg = MCPMessage(
            trace_id=task.id,
            msg_type=MsgType.TASK,
            payload={"step_index": -1, "from_pdf": True},
            sender_agent="orchestrator",
            target_agent="VisionParseAgent",
        )

        try:
            result = await vision_agent.run(msg)
            if result.status == AgentStatus.SUCCESS:
                logger.info(f"[Orchestrator] PDF 视觉解析成功，房间={len(result.data.get('rooms', []))}")
            else:
                logger.warning(f"[Orchestrator] PDF 视觉解析失败: {result.error}")
        except Exception as e:
            logger.warning(f"[Orchestrator] VisionParseAgent 异常: {e}")

    async def _classify_image_content(self, task: Task, mem: TaskMemory, file_type: str):
        """分析图片内容类型，动态决定路由"""
        from app.services.minio_service import MinioService
        from app.utils.image_analyzer import ImageAnalyzer

        try:
            data = MinioService().download(task.file_id)
            analysis = ImageAnalyzer().classify(data)

            content_type = analysis["content_type"]
            confidence = analysis["confidence"]
            await mem.set("image_content_type", content_type)
            await mem.set("image_analysis", analysis)

            logger.info(f"[ImageAnalyzer] 内容={content_type}, 置信度={confidence:.0%}")

            # 根据内容类型决定路由
            if content_type == "structural_blueprint":
                strategy = "VisionParseAgent"
                route = ["VisionParseAgent", "BudgetCheckAgent", "QuantityCalc", "ReportExport"]
            elif content_type == "document_scan":
                strategy = "TextExtractAgent"
                route = ["TextExtractAgent", "BudgetCheckAgent", "QuantityCalc", "ReportExport"]
            elif content_type == "rendering_photo":
                strategy = "VisionParseAgent"
                route = ["VisionParseAgent", "BudgetCheckAgent", "QuantityCalc", "ReportExport"]
            else:
                # 低置信度混合内容：双引擎路径
                strategy = "TextExtractAgent"
                route = ["TextExtractAgent", "VisionParseAgent", "BudgetCheckAgent", "QuantityCalc", "ReportExport"]

            await mem.set("image_route", route)
            return strategy, route

        except Exception as e:
            logger.warning(f"[ImageAnalyzer] 分析失败: {e}，默认使用 TextExtractAgent")
            strategy = "TextExtractAgent"
            await mem.set("parse_strategy", strategy)
            return strategy, None

    async def _calculate_quantities(self, trace_id: str, user_id: str | None = None):
        """算量计算（内联方法，原 QuantityCalcAgent）"""
        from app.agents.quantity_calc import calculate_quantities
        result = await calculate_quantities(trace_id, user_id)
        logger.info(f"[Orchestrator] 算量完成: {trace_id}")

    async def _export_report(self, trace_id: str):
        """报告导出（内联方法，原 ReportExportAgent）"""
        from app.agents.report_export import export_report
        result = await export_report(trace_id)
        logger.info(f"[Orchestrator] 报告已导出: {trace_id}")

    async def _update_task(self, task_id: str, **kwargs):
        result = await self.db.execute(select(Task).where(Task.id == task_id))
        task = result.scalar_one_or_none()
        if task:
            for k, v in kwargs.items():
                setattr(task, k, v)
            await self.db.commit()

    async def _update_step(self, task_id: str, agent_name: str, status: str, route: list, duration_ms: int | None = None):
        result = await self.db.execute(select(Task).where(Task.id == task_id))
        task = result.scalar_one_or_none()
        if not task:
            return
        steps = json.loads(task.steps_json or "[]")
        if not steps or len(steps) != len(route):
            steps = [{"agent": s, "status": "PENDING", "duration_ms": None} for s in route]
        for s in steps:
            if s["agent"] == agent_name:
                s["status"] = status
                if duration_ms is not None:
                    s["duration_ms"] = duration_ms
        task.steps_json = json.dumps(steps, ensure_ascii=False)
        await self.db.commit()
