from __future__ import annotations

"""
V2 Orchestrator
===============
在 V1 Orchestrator 基础上集成 DecisionAgent：
  - 解析前调用 DecisionAgent 决定解析参数
  - Agent 失败后调用 DecisionAgent 决定降级方案
  - 其余逻辑（路由、重试、断点续跑）保持不变
"""
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
from app.v2.core.decision.decision_agent import DecisionAgent


MAGIC_MAP = {
    b"\x25\x50\x44\x46": "pdf",
    b"\xAC\x1C\x00\x00": "dwg",
    b"\x41\x43\x31\x30": "dxf",
    b"\xFF\xD8\xFF":      "jpg",
    b"\x89\x50\x4E\x47": "png",
}


class OrchestratorV2:
    """
    V2 编排器：静态路由 + DecisionAgent 智能增强

    与 V1 的区别：
      1. 解析前插入 DecisionAgent（pre_parse）
      2. Agent 失败后插入 DecisionAgent（on_failure）决定降级方案
      3. 根据降级方案执行：retry / switch_engine / human_review / skip
    """

    DAG_ROUTES = {
        "pdf":  ["TextExtractAgent", "WireMeshSpecAgent", "WireMeshQuote", "WireMeshReport"],
        "dwg":  ["CadParseAgent",    "WireMeshSpecAgent", "WireMeshQuote", "WireMeshReport"],
        "dxf":  ["CadParseAgent",    "WireMeshSpecAgent", "WireMeshQuote", "WireMeshReport"],
        "jpg":  ["VisionParseAgent", "WireMeshSpecAgent", "WireMeshQuote", "WireMeshReport"],
        "jpeg": ["VisionParseAgent", "WireMeshSpecAgent", "WireMeshQuote", "WireMeshReport"],
        "png":  ["VisionParseAgent", "WireMeshSpecAgent", "WireMeshQuote", "WireMeshReport"],
    }

    STRATEGY_MAP = {
        "pdf":  "TextExtractAgent",
        "dwg":  "CadParseAgent",
        "dxf":  "CadParseAgent",
        "jpg":  "TextExtractAgent",
        "jpeg": "TextExtractAgent",
        "png":  "TextExtractAgent",
    }

    # 可以切换备用引擎的 Agent
    ENGINE_FALLBACK = {
        "TextExtractAgent": "VisionParseAgent",   # MinerU 失败 → 视觉解析
        "CadParseAgent":    "TextExtractAgent",   # CAD 解析失败 → 文本提取
        "VisionParseAgent": "TextExtractAgent",   # 视觉失败 → 文本提取
    }

    # 允许跳过的非关键 Agent
    SKIPPABLE_AGENTS = {"BudgetCheckAgent"}

    def __init__(self, db: AsyncSession):
        self.db = db
        self.hook_manager = HookManager()
        for event in ("before_agent_run", "after_agent_run", "on_agent_error", "on_whole_finish"):
            self.hook_manager.register(event, log_hook(event))
        self._agents: dict[str, BaseAgent] = {}
        self._decision_agent = DecisionAgent(hook_manager=self.hook_manager)
        self._register_agents()

    def _register_agents(self):
        from app.agents.text_extract import TextExtractAgent
        from app.agents.cad_parse import CadParseAgent
        from app.agents.vision_parse import VisionParseAgent
        from app.agents.budget_check import BudgetCheckAgent
        from app.agents.wire_mesh_spec import WireMeshSpecAgent

        for cls in [TextExtractAgent, CadParseAgent, VisionParseAgent, BudgetCheckAgent, WireMeshSpecAgent]:
            agent = cls(hook_manager=self.hook_manager)
            self._agents[agent.name] = agent

    async def run(self, task: Task, start_step: str | None = None):
        trace_id  = task.id
        file_type = task.file_type
        route     = list(self.DAG_ROUTES.get(file_type, []))
        if not route:
            raise ValueError(f"不支持的文件类型: {file_type}，当前支持: {', '.join(self.DAG_ROUTES.keys())}")

        start_idx = 0
        if start_step and start_step in route:
            start_idx = route.index(start_step)

        mem = TaskMemory(trace_id)
        await mem.set("file_id",   task.file_id)
        await mem.set("file_type", file_type)
        await mem.set("file_name", task.file_name)

        # 文件分类（替代 FileClassifyAgent）+ 图片内容分析
        await self._classify_file(task, mem, file_type)

        # 分类结果可以覆盖默认解析 Agent，但计算、审核、报告顺序保持确定。
        parse_strategy = await mem.get("parse_strategy")
        if parse_strategy in self._agents and route:
            route[0] = parse_strategy

        await self._update_task(task.id, status="RUNNING")
        _task_start_ts = time.time()  # 飞轮：记录任务开始时间

        # ── 步骤0：DecisionAgent 预决策（pre_parse）────────────
        if start_idx == 0:
            await self._run_pre_parse_decision(task, mem, file_type)

        # ── 主执行循环 ─────────────────────────────────────────
        retry_counts: dict[str, int] = {}

        for idx, agent_name in enumerate(route):
            if idx < start_idx:
                continue

            agent = self._agents.get(agent_name)
            if not agent:
                # 处理内联方法（原 Agent 已简化为方法）
                if agent_name == "QuantityCalc":
                    logger.info(f"[V2] 执行算量计算（内联）")
                    user_id = task.created_by if hasattr(task, "created_by") else None
                    await self._calculate_quantities(trace_id, user_id)
                    await self._update_step(task.id, agent_name, "SUCCESS", route, duration_ms=0)
                    continue
                elif agent_name == "ReportExport":
                    logger.info(f"[V2] 执行报告导出（内联）")
                    await self._export_report(trace_id)
                    await self._update_step(task.id, agent_name, "SUCCESS", route, duration_ms=0)
                    continue
                elif agent_name == "WireMeshQuote":
                    logger.info("[V2] 执行丝网确定性报价")
                    await self._calculate_wire_mesh_quote(trace_id, task.user_id)
                    await self._update_step(task.id, agent_name, "SUCCESS", route, duration_ms=0)
                    continue
                elif agent_name == "WireMeshReport":
                    logger.info("[V2] 生成丝网报价 PDF/Excel")
                    await self._export_wire_mesh_report(trace_id)
                    await self._update_step(task.id, agent_name, "SUCCESS", route, duration_ms=0)
                    continue
                else:
                    logger.warning(f"Agent {agent_name} 未注册，跳过")
                    continue

            msg = MCPMessage(
                trace_id=trace_id,
                msg_type=MsgType.TASK,
                payload={"step_index": idx},
                sender_agent="orchestrator_v2",
                target_agent=agent_name,
            )

            await self._update_task(task.id, current_step=agent_name,
                                    progress=int(idx / len(route) * 100))
            await self._update_step(task.id, agent_name, "RUNNING", route)

            start_ts = time.time()
            result   = await agent.run(msg)
            duration_ms = int((time.time() - start_ts) * 1000)

            if result.status == AgentStatus.FAILED:
                retry_count = retry_counts.get(agent_name, 0)

                # ── DecisionAgent 决定降级方案 ─────────────────
                fallback = await self._run_failure_decision(
                    task, mem, agent_name, result.error, retry_count
                )

                if fallback == "retry" and retry_count < 2:
                    retry_counts[agent_name] = retry_count + 1
                    logger.info(f"[V2] {agent_name} 重试（第 {retry_count+1} 次）")
                    await asyncio.sleep(1)
                    result = await agent.run(msg)

                elif fallback == "switch_engine":
                    alt_name = self.ENGINE_FALLBACK.get(agent_name)
                    if alt_name and alt_name in self._agents:
                        logger.info(f"[V2] {agent_name} 切换到备用引擎 {alt_name}")
                        alt_msg = MCPMessage(
                            trace_id=trace_id,
                            msg_type=MsgType.TASK,
                            payload={"step_index": idx, "fallback": True},
                            sender_agent="orchestrator_v2",
                            target_agent=alt_name,
                        )
                        result = await self._agents[alt_name].run(alt_msg)
                    else:
                        logger.warning(f"[V2] {agent_name} 无备用引擎，标记失败")

                elif fallback == "skip" and agent_name in self.SKIPPABLE_AGENTS:
                    logger.info(f"[V2] {agent_name} 跳过（非关键步骤）")
                    await self._update_step(task.id, agent_name, "SKIPPED", route, duration_ms)
                    continue

                elif fallback == "human_review":
                    review_data = {
                        "paused_at_step": agent_name,
                        "failure_reason": result.error,
                        "fallback_plan":  fallback,
                        "rooms":          await mem.get("rooms", []),
                        "walls":          await mem.get("walls", []),
                        "quantity_list":  await mem.get("quantity_list", {}),
                        "review_hint":    f"{agent_name} 执行失败，请检查后续跑",
                    }
                    await mem.set("human_review_data", review_data)
                    await self._update_task(task.id, status="PAUSED", current_step=agent_name)
                    await self._record_flywheel_result(
                        task_id=task.id,
                        file_type=file_type,
                        mem=mem,
                        result="paused",
                        failed_agent=agent_name,
                        failure_reason=result.error,
                        fallback_used="human_review",
                        total_duration_ms=int((time.time() - _task_start_ts) * 1000),
                    )
                    logger.info(f"[V2] 任务 {task.id} 暂停等待人工审核")
                    return

            if result.status == AgentStatus.FAILED:
                await self._update_step(task.id, agent_name, "FAILED", route, duration_ms)
                await self._update_task(task.id, status="FAILED", error_msg=result.error)
                await self._record_flywheel_result(
                    task_id=task.id,
                    file_type=file_type,
                    mem=mem,
                    result="failed",
                    failed_agent=agent_name,
                    failure_reason=result.error,
                    fallback_used=retry_counts.get(agent_name, {}) if isinstance(retry_counts.get(agent_name), dict) else "",
                    total_duration_ms=int((time.time() - _task_start_ts) * 1000),
                )
                return

            await self._update_step(task.id, agent_name, "SUCCESS", route, duration_ms)

            # PDF 包含结构图/效果图页，动态插入 VisionParseAgent
            if result.data.get("needs_vision_parse") and agent_name == "TextExtractAgent":
                vision_pages = await mem.get("pdf_vision_pages", {})
                logger.info(f"[V2 Orchestrator] PDF 包含视觉页面: {vision_pages}，插入 VisionParseAgent")
                await self._run_vision_parse_for_pdf(task, mem)

            if result.data.get("need_human_review"):
                review_data = {
                    "paused_at_step": agent_name,
                    "rooms":          await mem.get("rooms", []),
                    "walls":          await mem.get("walls", []),
                    "quantity_list":  await mem.get("quantity_list", {}),
                    "review_hint":    result.data.get("review_hint", "请检查解析结果"),
                }
                await mem.set("human_review_data", review_data)
                await self._update_task(task.id, status="PAUSED", current_step=agent_name)
                return

        await self._update_task(task.id, status="SUCCESS", progress=100, current_step=None)
        await self.hook_manager.trigger("on_whole_finish", task_id=task.id)
        await self._record_flywheel_result(
            task_id=task.id,
            file_type=file_type,
            mem=mem,
            result="success",
            total_duration_ms=int((time.time() - _task_start_ts) * 1000),
        )
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
            strategy = await self._classify_image_content(task, mem, file_type)
        else:
            strategy = self.STRATEGY_MAP.get(file_type, "TextExtractAgent")
            await mem.set("parse_strategy", strategy)

        await mem.set("parse_strategy", strategy)
        logger.info(f"[FileClassify] 类型={file_type}, 策略={strategy}")

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

            # 根据内容类型决定策略（路由已在 DAG_ROUTES 中定义）
            if content_type == "structural_blueprint":
                strategy = "VisionParseAgent"
            elif content_type == "document_scan":
                strategy = "TextExtractAgent"
            elif content_type == "rendering_photo":
                strategy = "VisionParseAgent"
            else:
                # 低置信度混合内容：默认使用 VisionParseAgent
                strategy = "VisionParseAgent"

            await mem.set("parse_strategy", strategy)
            return strategy

        except Exception as e:
            logger.warning(f"[ImageAnalyzer] 分析失败: {e}，默认使用 TextExtractAgent")
            strategy = "TextExtractAgent"
            await mem.set("parse_strategy", strategy)
            return strategy

    async def _calculate_quantities(self, trace_id: str, user_id: str | None = None):
        """算量计算（内联方法，原 QuantityCalcAgent）"""
        from app.agents.quantity_calc import calculate_quantities
        result = await calculate_quantities(trace_id, user_id)
        logger.info(f"[V2 Orchestrator] 算量完成: {trace_id}")

    async def _export_report(self, trace_id: str):
        """报告导出（内联方法，原 ReportExportAgent）"""
        from app.agents.report_export import export_report
        result = await export_report(trace_id)
        logger.info(f"[V2 Orchestrator] 报告已导出: {trace_id}")

    async def _calculate_wire_mesh_quote(self, trace_id: str, owner_id: str):
        from app.core.skill.wire_mesh_pricing import WireMeshSpec
        from app.services.wire_mesh_service import build_quote_from_db

        mem = TaskMemory(trace_id)
        raw = await mem.get("wire_mesh_spec", {})
        required = (
            "product_type", "material", "wire_diameter_mm", "mesh_size_mm",
            "width_m", "length_m", "quantity",
        )
        missing = [key for key in required if raw.get(key) in (None, "")]
        if missing:
            raise ValueError("丝网报价缺少字段: " + ", ".join(missing))
        spec = WireMeshSpec(**{key: raw[key] for key in WireMeshSpec.__dataclass_fields__})
        quote = await build_quote_from_db(self.db, owner_id, spec)
        await mem.set("wire_mesh_quote", quote)

    async def _export_wire_mesh_report(self, trace_id: str):
        from app.services.wire_mesh_report import export_wire_mesh_quote
        await export_wire_mesh_quote(trace_id)

    async def _run_pre_parse_decision(self, task: Task, mem: TaskMemory, file_type: str):
        """解析前调用 DecisionAgent 决定解析参数"""
        try:
            file_size_mb = task.file_id and 1.0 or 0.0

            msg = MCPMessage(
                trace_id=task.id,
                msg_type=MsgType.TASK,
                payload={
                    "trigger":       "pre_parse",
                    "file_size_mb":  file_size_mb,
                    "file_features": {
                        "layer_count":  await mem.get("layer_count", 10),
                        "entity_count": await mem.get("entity_count", 100),
                    },
                },
                sender_agent="orchestrator_v2",
                target_agent="DecisionAgent",
            )
            result = await self._decision_agent.run(msg)
            if result.status == AgentStatus.SUCCESS:
                logger.info(f"[V2] 解析策略: {result.data.get('parse_params')}")
        except Exception as e:
            logger.warning(f"[V2] DecisionAgent pre_parse 失败，使用默认参数: {e}")

    async def _run_failure_decision(
        self, task: Task, mem: TaskMemory,
        failed_agent: str, failure_reason: str, retry_count: int
    ) -> str:
        """Agent 失败后调用 DecisionAgent 决定降级方案"""
        try:
            msg = MCPMessage(
                trace_id=task.id,
                msg_type=MsgType.TASK,
                payload={
                    "trigger":        "on_failure",
                    "failed_agent":   failed_agent,
                    "failure_reason": failure_reason,
                    "retry_count":    retry_count,
                },
                sender_agent="orchestrator_v2",
                target_agent="DecisionAgent",
            )
            result = await self._decision_agent.run(msg)
            if result.status == AgentStatus.SUCCESS:
                plan = result.data.get("fallback_plan", "retry")
                logger.info(
                    f"[V2] 降级决策: {plan} "
                    f"(confidence={result.data.get('confidence', 0):.2f})"
                )
                return plan
        except Exception as e:
            logger.warning(f"[V2] DecisionAgent on_failure 失败: {e}")
        return "retry"

    async def _record_flywheel_result(
        self,
        task_id: str,
        file_type: str,
        mem: TaskMemory,
        result: str,
        failed_agent: str = "",
        failure_reason: str = "",
        fallback_used: str = "",
        total_duration_ms: int = 0,
    ):
        """把任务执行结果写回 DecisionAgent 的 AgentPrivateMemory"""
        try:
            from app.core.memory.redis_memory import AgentPrivateMemory
            decision_mem = AgentPrivateMemory("DecisionAgent")

            parse_params = await mem.get("parse_params", {})
            decision_reasoning = await mem.get("decision_reasoning", "")

            record = {
                "task_id": task_id,
                "file_type": file_type,
                "parse_params": parse_params,
                "decision_reasoning": decision_reasoning,
                "result": result,
                "total_duration_ms": total_duration_ms,
            }

            if result == "failed":
                record["failed_agent"] = failed_agent
                record["failure_reason"] = failure_reason
                record["fallback_used"] = fallback_used

            await decision_mem.append_history(record, max_records=100)
            await self._update_flywheel_stats(decision_mem, file_type, result, parse_params)

            logger.info(f"[飞轮] 结果已写回 DecisionAgent Memory: task={task_id} result={result}")

        except Exception as e:
            logger.warning(f"[飞轮] 结果写回失败（不影响任务）: {e}")

    async def _update_flywheel_stats(
        self,
        decision_mem,
        file_type: str,
        result: str,
        parse_params: dict,
    ):
        """维护聚合统计数据"""
        stats = await decision_mem.get("flywheel_stats", {})
        engine = parse_params.get("engine_mode", "standard")

        if file_type not in stats:
            stats[file_type] = {}
        if engine not in stats[file_type]:
            stats[file_type][engine] = {"success": 0, "failed": 0}

        if result in ("success", "failed"):
            stats[file_type][engine][result] += 1
        await decision_mem.set("flywheel_stats", stats)

    async def _update_task(self, task_id: str, **kwargs):
        result = await self.db.execute(select(Task).where(Task.id == task_id))
        task = result.scalar_one_or_none()
        if task:
            for k, v in kwargs.items():
                setattr(task, k, v)
            await self.db.commit()

    async def _update_step(self, task_id: str, agent_name: str, status: str,
                           route: list, duration_ms: int | None = None):
        result = await self.db.execute(select(Task).where(Task.id == task_id))
        task = result.scalar_one_or_none()
        if not task:
            return
        steps = json.loads(task.steps_json or "[]")
        route_agents = [s for s in route]
        steps_agents = [s["agent"] for s in steps]
        if not steps or len(steps) != len(route) or steps_agents != route_agents:
            # steps_json 与当前路由不一致（如文件类型变更或旧数据），以 route 为准重建
            # 保留已完成步骤的状态
            old_status = {s["agent"]: s for s in steps}
            steps = [
                old_status.get(s, {"agent": s, "status": "PENDING", "duration_ms": None})
                for s in route
            ]
        for s in steps:
            if s["agent"] == agent_name:
                s["status"] = status
                if duration_ms is not None:
                    s["duration_ms"] = duration_ms
        task.steps_json = json.dumps(steps, ensure_ascii=False)
        await self.db.commit()
