"""
DecisionAgent V2
================
职责（精准边界）：
  1. 解析策略选择：分析文件特征，决定解析参数（引擎模式、精度设置）
  2. 失败降级决策：Agent 失败后，LLM 推理最优降级方案

不做的事：
  - 不决定走哪条 Agent 链（Orchestrator 按规则来）
  - 不干预 QuantityCalcAgent 的算量计算
  - 不修改 SkillLib 规则
"""
from typing import TypedDict, Literal
from loguru import logger

from app.core.agent.base_agent import BaseAgent, AgentResult, AgentStatus
from app.core.mcp.message import MCPMessage
from app.core.memory.redis_memory import TaskMemory, AgentPrivateMemory
from config.settings import settings


# ── LangGraph 状态定义 ────────────────────────────────────────

class DecisionState(TypedDict):
    # 输入
    task_id: str
    file_type: str
    file_size_mb: float
    trigger: Literal["pre_parse", "on_failure"]  # 触发场景

    # 文件特征（pre_parse 场景）
    file_features: dict   # 图层数、文件大小、质量评分等

    # 失败信息（on_failure 场景）
    failed_agent: str
    failure_reason: str
    retry_count: int

    # 历史决策经验
    history: list

    # 输出
    parse_params: dict    # 解析参数建议
    fallback_plan: str    # 降级方案：retry / switch_engine / human_review / skip
    confidence: float     # 决策置信度 0-1
    reasoning: str        # 决策理由


class DecisionAgent(BaseAgent):
    """
    智能决策 Agent（V2 新增）
    内部使用 LangGraph 实现两种决策场景。
    """
    name = "DecisionAgent"
    description = "智能决策：解析策略选择 + 失败降级推理（LangGraph）"
    timeout_seconds = 60  # 决策不应超过 1 分钟

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._private_mem = AgentPrivateMemory("DecisionAgent")
        # 预编译 LangGraph 实例，避免每次调用都重建
        self._strategy_graph = self._build_strategy_graph()
        self._fallback_graph = self._build_fallback_graph()

    async def execute(self, message: MCPMessage) -> AgentResult:
        mem = TaskMemory(message.trace_id)
        trigger = message.payload.get("trigger", "pre_parse")

        if trigger == "pre_parse":
            result = await self._decide_parse_strategy(message, mem)
        else:
            result = await self._decide_fallback(message, mem)

        return result

    # ── 场景一：解析策略选择 ──────────────────────────────────

    async def _decide_parse_strategy(self, message: MCPMessage, mem: TaskMemory) -> AgentResult:
        """分析文件特征，决定解析参数"""
        import asyncio

        file_type    = await mem.get("file_type", "pdf")
        file_size_mb = message.payload.get("file_size_mb", 0)
        file_features = message.payload.get("file_features", {})

        # 读取历史决策经验
        history = await self._private_mem.get_history(limit=5)

        # 构建初始状态
        state: DecisionState = {
            "task_id":       message.trace_id,
            "file_type":     file_type,
            "file_size_mb":  file_size_mb,
            "trigger":       "pre_parse",
            "file_features": file_features,
            "failed_agent":  "",
            "failure_reason": "",
            "retry_count":   0,
            "history":       history,
            "parse_params":  {},
            "fallback_plan": "",
            "confidence":    0.0,
            "reasoning":     "",
        }

        graph = self._strategy_graph
        final = await asyncio.to_thread(graph.invoke, state)

        # 把决策结果写入 TaskMemory，供后续 Agent 读取
        await mem.set("parse_params", final["parse_params"])
        await mem.set("decision_reasoning", final["reasoning"])

        # 记录决策历史（仅记录决策意图，结果由 OrchestratorV2 写回）
        await self._private_mem.append_history({
            "trigger":      "pre_parse",
            "file_type":    file_type,
            "parse_params": final["parse_params"],
            "confidence":   final["confidence"],
        })

        logger.info(
            f"[DecisionAgent] 解析策略决策完成 "
            f"confidence={final['confidence']:.2f} "
            f"params={final['parse_params']}"
        )
        return AgentResult(
            agent_name=self.name,
            status=AgentStatus.SUCCESS,
            data={
                "parse_params": final["parse_params"],
                "confidence":   final["confidence"],
                "reasoning":    final["reasoning"],
            },
        )

    # ── 场景二：失败降级决策 ──────────────────────────────────

    async def _decide_fallback(self, message: MCPMessage, mem: TaskMemory) -> AgentResult:
        """Agent 失败后，推理最优降级方案"""
        import asyncio

        file_type      = await mem.get("file_type", "pdf")
        failed_agent   = message.payload.get("failed_agent", "")
        failure_reason = message.payload.get("failure_reason", "")
        retry_count    = message.payload.get("retry_count", 0)
        history        = await self._private_mem.get_history(limit=5)

        state: DecisionState = {
            "task_id":        message.trace_id,
            "file_type":      file_type,
            "file_size_mb":   0,
            "trigger":        "on_failure",
            "file_features":  {},
            "failed_agent":   failed_agent,
            "failure_reason": failure_reason,
            "retry_count":    retry_count,
            "history":        history,
            "parse_params":   {},
            "fallback_plan":  "",
            "confidence":     0.0,
            "reasoning":      "",
        }

        graph = self._fallback_graph
        final = await asyncio.to_thread(graph.invoke, state)

        await mem.set("fallback_plan",      final["fallback_plan"])
        await mem.set("fallback_reasoning", final["reasoning"])

        await self._private_mem.append_history({
            "trigger":        "on_failure",
            "failed_agent":   failed_agent,
            "failure_reason": failure_reason,
            "fallback_plan":  final["fallback_plan"],
        })

        logger.info(
            f"[DecisionAgent] 降级决策完成 "
            f"plan={final['fallback_plan']} "
            f"confidence={final['confidence']:.2f}"
        )
        return AgentResult(
            agent_name=self.name,
            status=AgentStatus.SUCCESS,
            data={
                "fallback_plan": final["fallback_plan"],
                "confidence":    final["confidence"],
                "reasoning":     final["reasoning"],
            },
        )

    # ── LangGraph 图构建 ──────────────────────────────────────

    def _build_strategy_graph(self):
        """
        解析策略决策图：
          analyze_features → llm_decide_params → validate → END
        """
        from langgraph.graph import StateGraph, END
        import json, re

        from app.core.llm.glm_client import call_glm_text, extract_json

        def analyze_features(state: DecisionState) -> DecisionState:
            """节点1：规则分析文件特征 + 读取飞轮统计数据"""
            features  = state["file_features"]
            file_type = state["file_type"]
            size_mb   = state["file_size_mb"]

            # 规则评分（不用 LLM，快速稳定）
            quality_score = 1.0
            if size_mb < 0.1:
                quality_score -= 0.3
            if features.get("layer_count", 10) < 3:
                quality_score -= 0.2
            if features.get("entity_count", 100) < 20:
                quality_score -= 0.2

            state["file_features"]["quality_score"] = round(max(0.1, quality_score), 2)
            state["file_features"]["size_mb"]       = size_mb
            state["file_features"]["file_type"]     = file_type

            # ── 飞轮：读取历史成功率统计，直接影响决策 ──────────
            # history 里包含 OrchestratorV2 写回的 result 字段
            flywheel_hint = _compute_flywheel_hint(state["history"], file_type)
            state["file_features"]["flywheel_hint"] = flywheel_hint
            # 如果飞轮数据强烈建议某个引擎，直接提升质量评分偏向
            if flywheel_hint.get("recommended_engine") == "recovery":
                state["file_features"]["quality_score"] = min(
                    state["file_features"]["quality_score"], 0.4
                )  # 强制走 recovery 路径
            return state

        def llm_decide_params(state: DecisionState) -> DecisionState:
            """节点2：LLM 根据特征 + 飞轮统计决定解析参数"""
            features         = state["file_features"]
            history_summary  = _summarize_history(state["history"])
            flywheel_hint    = features.get("flywheel_hint", {})
            flywheel_summary = _summarize_flywheel(flywheel_hint)

            prompt = f"""你是丝网产品图纸解析专家。根据以下文件特征，推荐最优解析参数。

文件特征：
- 类型：{state['file_type']}
- 大小：{state['file_size_mb']:.1f} MB
- 质量评分：{features.get('quality_score', 1.0):.2f}（0-1，越高越好）
- 图层数：{features.get('layer_count', '未知')}
- 实体数：{features.get('entity_count', '未知')}

历史决策参考：
{history_summary}

飞轮统计（历史成功率数据）：
{flywheel_summary}

请以 JSON 格式返回解析参数建议：
{{
  "engine_mode": "standard|recovery|dual",
  "precision": "fast|normal|high",
  "enable_topology": true/false,
  "enable_vision_assist": true/false,
  "floor_height_hint": 2800,
  "reasoning": "决策理由（一句话，需说明是否参考了飞轮数据）",
  "confidence": 0.0-1.0
}}

规则：
- quality_score >= 0.8：standard 模式，normal 精度
- quality_score 0.5-0.8：standard 模式，high 精度
- quality_score < 0.5：recovery 模式，high 精度，开启 vision_assist
- 文件 > 10MB：关闭 enable_topology（太慢）
- 飞轮数据显示某引擎成功率 > 80%：优先推荐该引擎
- 飞轮数据显示某引擎失败率 > 50%：避免使用该引擎
- 只返回 JSON，不要其他文字"""

            try:
                text = call_glm_text(prompt, max_tokens=512)
                params = extract_json(text) or {}
                state["parse_params"] = {
                    "engine_mode":          params.get("engine_mode", "standard"),
                    "precision":            params.get("precision", "normal"),
                    "enable_topology":      params.get("enable_topology", True),
                    "enable_vision_assist": params.get("enable_vision_assist", False),
                    "floor_height_hint":    params.get("floor_height_hint", 2800),
                }
                state["confidence"] = float(params.get("confidence", 0.7))
                state["reasoning"]  = params.get("reasoning", "默认策略")
            except Exception as e:
                logger.warning(f"[DecisionAgent] LLM 决策失败，使用默认参数: {e}")
                state["parse_params"] = _default_params(state["file_type"])
                state["confidence"]   = 0.5
                state["reasoning"]    = "LLM 不可用，使用默认参数"
            return state

        def validate_params(state: DecisionState) -> DecisionState:
            """节点3：校验参数合理性，防止 LLM 给出不合理建议"""
            p = state["parse_params"]
            # 强制约束：QuantityCalcAgent 不受影响
            p.pop("skip_quantity_calc", None)
            p.pop("use_llm_for_calc", None)
            # 确保必要字段存在
            p.setdefault("engine_mode", "standard")
            p.setdefault("precision", "normal")
            p.setdefault("enable_topology", True)
            p.setdefault("floor_height_hint", 2800)
            state["parse_params"] = p
            return state

        graph = StateGraph(DecisionState)
        graph.add_node("analyze_features",  analyze_features)
        graph.add_node("llm_decide_params", llm_decide_params)
        graph.add_node("validate_params",   validate_params)

        graph.set_entry_point("analyze_features")
        graph.add_edge("analyze_features",  "llm_decide_params")
        graph.add_edge("llm_decide_params", "validate_params")
        graph.add_edge("validate_params",   END)

        return graph.compile()

    def _build_fallback_graph(self):
        """
        失败降级决策图：
          assess_failure → llm_decide_fallback → [retry|switch|human|skip] → END
        """
        from langgraph.graph import StateGraph, END
        import json, re

        from app.core.llm.glm_client import call_glm_text, extract_json

        def assess_failure(state: DecisionState) -> DecisionState:
            """节点1：规则快速评估失败类型"""
            reason = state["failure_reason"].lower()
            retries = state["retry_count"]

            # 规则快速判断（不用 LLM）
            if retries >= 2:
                state["fallback_plan"] = "human_review"
                state["confidence"]    = 0.95
                state["reasoning"]     = "已重试 2 次，建议人工介入"
            elif "timeout" in reason or "超时" in reason:
                state["fallback_plan"] = "switch_engine"
                state["confidence"]    = 0.85
                state["reasoning"]     = "超时，切换轻量引擎"
            elif "corrupt" in reason or "损坏" in reason:
                state["fallback_plan"] = "human_review"
                state["confidence"]    = 0.9
                state["reasoning"]     = "文件损坏，需人工处理"
            else:
                state["fallback_plan"] = ""  # 需要 LLM 进一步判断
            return state

        def llm_decide_fallback(state: DecisionState) -> DecisionState:
            """节点2：LLM 推理复杂失败场景的降级方案"""
            if state["fallback_plan"]:  # 规则已决定，跳过 LLM
                return state

            history_summary = _summarize_history(state["history"])
            prompt = f"""丝网产品图纸解析失败，请推荐降级方案。

失败信息：
- 失败 Agent：{state['failed_agent']}
- 失败原因：{state['failure_reason']}
- 已重试次数：{state['retry_count']}
- 文件类型：{state['file_type']}

历史参考：{history_summary}

可选方案：
- retry：直接重试（适合偶发网络错误）
- switch_engine：切换备用引擎（如 MinerU → pdfplumber）
- human_review：暂停等待人工介入
- skip：跳过此步骤，用空数据继续（适合非关键步骤）

以 JSON 返回：
{{"plan": "retry|switch_engine|human_review|skip", "reasoning": "理由", "confidence": 0.0-1.0}}

只返回 JSON。"""

            try:
                text = call_glm_text(prompt, max_tokens=256)
                result = extract_json(text) or {}
                state["fallback_plan"] = result.get("plan", "retry")
                state["confidence"]    = float(result.get("confidence", 0.6))
                state["reasoning"]     = result.get("reasoning", "LLM 推荐")
            except Exception as e:
                logger.warning(f"[DecisionAgent] 降级 LLM 失败: {e}")
                state["fallback_plan"] = "retry"
                state["confidence"]    = 0.5
                state["reasoning"]     = "LLM 不可用，默认重试"
            return state

        def should_use_llm(state: DecisionState) -> str:
            """条件边：规则已决定则跳过 LLM"""
            return "skip_llm" if state["fallback_plan"] else "use_llm"

        graph = StateGraph(DecisionState)
        graph.add_node("assess_failure",      assess_failure)
        graph.add_node("llm_decide_fallback", llm_decide_fallback)

        graph.set_entry_point("assess_failure")
        graph.add_conditional_edges(
            "assess_failure",
            should_use_llm,
            {"use_llm": "llm_decide_fallback", "skip_llm": END},
        )
        graph.add_edge("llm_decide_fallback", END)

        return graph.compile()


# ── 工具函数 ──────────────────────────────────────────────────

def _default_params(file_type: str) -> dict:
    return {
        "engine_mode":          "standard",
        "precision":            "normal",
        "enable_topology":      file_type in ("dwg", "dxf"),
        "enable_vision_assist": False,
        "floor_height_hint":    2800,
    }


def _summarize_history(history: list) -> str:
    if not history:
        return "无历史记录"
    lines = []
    for h in history[-5:]:
        if h.get("trigger") == "pre_parse":
            result = h.get("result", "unknown")
            engine = h.get("parse_params", {}).get("engine_mode", "?")
            duration = h.get("total_duration_ms", 0)
            lines.append(
                f"- {h.get('file_type')} → {engine} → {result}"
                + (f"（{duration//1000}s）" if duration else "")
            )
        elif h.get("trigger") == "on_failure":
            lines.append(
                f"- {h.get('failed_agent')} 失败 → {h.get('fallback_plan', '?')}"
            )
        elif h.get("result"):
            # OrchestratorV2 写回的结果记录
            engine = h.get("parse_params", {}).get("engine_mode", "?")
            result = h.get("result", "?")
            lines.append(f"- {h.get('file_type')} {engine} → {result}")
    return "\n".join(lines) if lines else "无历史记录"


def _compute_flywheel_hint(history: list, file_type: str) -> dict:
    """
    从历史记录中计算飞轮统计提示。
    返回：{recommended_engine, success_rates, sample_count}
    """
    # 统计各引擎的成功/失败次数
    engine_stats: dict[str, dict] = {}
    for h in history:
        if h.get("file_type") != file_type:
            continue
        if "result" not in h:
            continue
        engine = h.get("parse_params", {}).get("engine_mode", "standard")
        if engine not in engine_stats:
            engine_stats[engine] = {"success": 0, "failed": 0}
        engine_stats[engine][h["result"]] = engine_stats[engine].get(h["result"], 0) + 1

    if not engine_stats:
        return {"recommended_engine": None, "success_rates": {}, "sample_count": 0}

    # 计算成功率
    success_rates = {}
    for engine, counts in engine_stats.items():
        total = counts.get("success", 0) + counts.get("failed", 0)
        if total > 0:
            success_rates[engine] = round(counts.get("success", 0) / total, 2)

    # 推荐成功率最高的引擎（样本数 >= 3 才有参考价值）
    recommended = None
    total_samples = sum(
        v.get("success", 0) + v.get("failed", 0)
        for v in engine_stats.values()
    )
    if total_samples >= 3:
        recommended = max(success_rates, key=success_rates.get)

    return {
        "recommended_engine": recommended,
        "success_rates":      success_rates,
        "sample_count":       total_samples,
    }


def _summarize_flywheel(flywheel_hint: dict) -> str:
    """把飞轮统计格式化为 Prompt 可读的文字"""
    if not flywheel_hint or not flywheel_hint.get("success_rates"):
        return "暂无飞轮统计数据（首次处理此类文件）"

    lines = [f"样本数：{flywheel_hint.get('sample_count', 0)} 次"]
    for engine, rate in flywheel_hint.get("success_rates", {}).items():
        lines.append(f"- {engine} 引擎成功率：{rate*100:.0f}%")

    recommended = flywheel_hint.get("recommended_engine")
    if recommended:
        lines.append(f"→ 飞轮推荐：{recommended} 引擎（历史成功率最高）")

    return "\n".join(lines)
