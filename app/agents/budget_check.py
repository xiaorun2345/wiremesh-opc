from typing import TypedDict
from loguru import logger

from app.core.agent.base_agent import BaseAgent, AgentResult, AgentStatus
from app.core.mcp.message import MCPMessage
from app.core.memory.redis_memory import TaskMemory
from config.settings import settings


class BudgetCheckState(TypedDict):
    quantity_list: dict
    rag_results: list
    compliance_issues: list
    round: int
    done: bool
    use_builtin_standards: bool


class BudgetCheckAgent(BaseAgent):
    """
    预算合规审核 Agent。
    内部使用 LangGraph 实现多轮 RAG 召回 + 推理。
    LLM 调用通过 asyncio.to_thread 放入线程池，避免阻塞事件循环。
    """
    name = "BudgetCheckAgent"
    description = "预算合规审核（RAG + LangGraph 多轮推理）"

    async def execute(self, message: MCPMessage) -> AgentResult:
        mem = TaskMemory(message.trace_id)
        quantity_list = await mem.get("quantity_list", {})

        import asyncio
        # LangGraph 图的构建和执行放入线程池（图内有同步 LLM 调用）
        graph = self._build_graph()
        final_state = await asyncio.to_thread(
            graph.invoke,
            {
                "quantity_list": quantity_list,
                "rag_results": [],
                "compliance_issues": [],
                "round": 0,
                "done": False,
                "use_builtin_standards": False,
            }
        )

        compliance_report = {
            "issues":   final_state["compliance_issues"],
            "rag_refs": final_state["rag_results"],
            "passed":   len(final_state["compliance_issues"]) == 0,
        }

        await mem.set("compliance_report", compliance_report)
        issue_count = len(compliance_report["issues"])
        logger.info(f"[BudgetCheck] 审核完成，发现 {issue_count} 条问题")
        return AgentResult(
            agent_name=self.name,
            status=AgentStatus.SUCCESS,
            data=compliance_report,
        )

    def _build_graph(self):
        from langgraph.graph import StateGraph, END

        from app.core.llm.glm_client import call_glm_text, extract_json
        from app.core.skill.compliance_standards import (
            get_all_standards,
            get_standard_by_id,
            format_standard_ref,
        )

        def _extract_keywords(quantity_list: dict) -> str:
            """从工程量清单提取关键词，用于 RAG 查询"""
            text = str(quantity_list)
            # 装修领域关键词
            domain_kw = {'防水', '防火', '电气', '排水', '墙面', '地面', '卫生间', '厨房',
                         '水电', '泥瓦', '木工', '油漆', '吊顶', '隔墙', '门窗', '瓷砖',
                         '地板', '涂料', '灯具', '洁具', '水管', '电线', '防水层', '找平',
                         '抹灰', '腻子', '吊顶', '地暖', '空调', '新风', '栏杆', '扶手'}
            found = [w for w in domain_kw if w in text]
            # 如果没找到领域关键词，提取高频名词
            if not found:
                import re
                nouns = re.findall(r'[\u4e00-\u9fa5]{2,4}', text)
                from collections import Counter
                common = Counter(nouns).most_common(5)
                found = [w for w, _ in common]
            return ' '.join(found) if found else '装修 工程量'

        def rag_retrieve(state: BudgetCheckState) -> BudgetCheckState:
            """节点1：RAG 召回国标条文（关键词提取 + 多路召回），失败时用内置条文兜底"""
            try:
                import chromadb
                chroma = chromadb.HttpClient(host=settings.CHROMA_HOST, port=settings.CHROMA_PORT)
                collection = chroma.get_or_create_collection("standards")

                # 优化1：从清单提取领域关键词
                keywords = _extract_keywords(state["quantity_list"])

                # 优化2：多路召回 - 向量检索 Top-8
                results = collection.query(
                    query_texts=[keywords],
                    n_results=8,
                    include=["documents", "metadatas", "distances"]
                )
                docs = results.get("documents", [[]])[0]
                metas = results.get("metadatas", [[]])[0]
                distances = results.get("distances", [[]])[0]

                # 去重：同一条文只保留一次
                seen = set()
                unique_docs = []
                for doc, m, dist in zip(docs, metas, distances):
                    key = f"{m.get('standard_name', '')}_{m.get('section', '')}"
                    if key not in seen:
                        seen.add(key)
                        unique_docs.append((doc, m, dist))

                # 拼成结构化条文块：【标准名】第X.X条 内容（section 已含"第X.X条"）
                state["rag_results"] = [
                    f"【{m.get('standard_name', '')}】{m.get('section', '')} {doc}"
                    for doc, m, _ in unique_docs
                ]
                state["use_builtin_standards"] = False
            except Exception as e:
                logger.warning(f"RAG 召回失败，使用内置国标条文兜底: {e}")
                # 使用内置条文兜底，每条附带 ID
                standards = get_all_standards()
                state["rag_results"] = [
                    f"【{s['id']}】{s['content']}" for s in standards
                ]
                state["use_builtin_standards"] = True
            return state

        def llm_check(state: BudgetCheckState) -> BudgetCheckState:
            """节点2：LLM 合规判断，每条问题绑定对应国标条文"""
            raw_results = state["rag_results"]
            rag_refs = raw_results[:3] if raw_results else []
            rag_context = "\n".join(rag_refs) if rag_refs else "无相关条文，请根据通用装修规范判断"
            prompt = (
                f"你是装修工程量合规审核专家。根据以下国标条文，审核工程量清单是否合规。\n\n"
                f"国标条文参考（方括号内为标准编号和条文号）：\n{rag_context}\n\n"
                f"工程量清单：\n{state['quantity_list']}\n\n"
                f"请以 JSON 数组格式返回不合规项，每项包含：\n"
                f"  - issue: 问题描述\n"
                f"  - ref: 对应条文引用（如 'GB50327-2001 第6.3.4条'，无对应填空字符串）\n"
                f"  - suggestion: 整改建议\n"
                f"如无问题返回空数组 []。只返回 JSON 数组，不要其他文字。\n"
                f"示例：[{{\"issue\":\"防水面积不足\",\"ref\":\"GB50327-2001 第6.3.4条\",\"suggestion\":\"卫生间墙面上翻至少300mm\"}}]"
            )
            try:
                text = call_glm_text(prompt, max_tokens=1024)
                raw_issues = extract_json(text) or []

                enriched = []
                for item in raw_issues:
                    if isinstance(item, str):
                        enriched.append({"issue": item, "ref": "", "suggestion": ""})
                    elif isinstance(item, dict):
                        enriched.append({
                            "issue":      item.get("issue", ""),
                            "ref":        item.get("ref", ""),
                            "suggestion": item.get("suggestion", ""),
                        })
                state["compliance_issues"] = enriched
            except Exception as e:
                logger.warning(f"LLM 合规判断失败: {e}")
                state["compliance_issues"] = []
            state["round"] += 1
            return state

        def expand_rag(state: BudgetCheckState) -> BudgetCheckState:
            """节点3：用不合规项扩大 RAG 召回范围（仅 RAG 模式）"""
            if state.get("use_builtin_standards", False):
                return state
            try:
                import chromadb
                chroma = chromadb.HttpClient(host=settings.CHROMA_HOST, port=settings.CHROMA_PORT)
                collection = chroma.get_or_create_collection("standards")

                # 从已发现的问题提取关键词
                issues_text = ' '.join(str(i) for i in state["compliance_issues"])[:300]
                keywords = _extract_keywords({"_expand": issues_text})

                results = collection.query(
                    query_texts=[keywords],
                    n_results=8,
                    include=["documents", "metadatas", "distances"]
                )
                docs = results.get("documents", [[]])[0]
                metas = results.get("metadatas", [[]])[0]
                distances = results.get("distances", [[]])[0]

                seen = set()
                unique_docs = []
                for doc, m, dist in zip(docs, metas, distances):
                    key = f"{m.get('standard_name', '')}_{m.get('section', '')}"
                    if key not in seen:
                        seen.add(key)
                        unique_docs.append((doc, m, dist))

                state["rag_results"] = [
                    f"【{m.get('standard_name', '')}】{m.get('section', '')} {doc}"
                    for doc, m, _ in unique_docs
                ]
            except Exception as e:
                logger.warning(f"扩大 RAG 召回失败: {e}")
            return state

        def should_expand(state: BudgetCheckState) -> str:
            if state["round"] >= 2:
                return "end"
            if state["compliance_issues"] and state["round"] < 2:
                return "expand"
            return "end"

        graph = StateGraph(BudgetCheckState)
        graph.add_node("rag_retrieve", rag_retrieve)
        graph.add_node("llm_check",    llm_check)
        graph.add_node("expand_rag",   expand_rag)

        graph.set_entry_point("rag_retrieve")
        graph.add_edge("rag_retrieve", "llm_check")
        graph.add_conditional_edges("llm_check", should_expand, {"expand": "expand_rag", "end": END})
        graph.add_edge("expand_rag", "llm_check")

        return graph.compile()
