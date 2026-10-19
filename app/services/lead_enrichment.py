"""Chinese enrichment for public procurement leads.

An LLM is optional. Without a configured key, this module retains the original
notice and builds a clearly-labelled glossary summary so review can continue.
"""
from __future__ import annotations

import asyncio
from typing import Any

from app.core.llm.glm_client import call_glm_text, extract_json
from config.settings import settings


GLOSSARY = {
    "wire mesh": "丝网", "welded mesh": "焊接网", "welded wire": "焊接钢丝网",
    "security fencing": "安全围栏", "anti-climb": "防攀爬", "fencing": "围栏",
    "metal netting": "金属网", "wire cloth": "金属丝布", "mining screen": "矿用筛网",
    "gabion": "石笼网", "stainless steel": "不锈钢", "galvanized": "镀锌",
    "supply of": "供应", "installation": "安装", "procurement": "采购",
}


def glossary_chinese(text: str) -> str:
    translated = text
    for source, target in sorted(GLOSSARY.items(), key=lambda item: len(item[0]), reverse=True):
        translated = translated.replace(source, target).replace(source.title(), target)
    return translated


async def enrich_to_chinese(title: str, text: str, buyer: str, country: str) -> dict[str, str]:
    """Translate and summarize, preferring a configured OpenAI-compatible model."""
    if settings.LLM_API_KEY:
        prompt = (
            "将以下海外丝网采购公告整理为中文。只返回 JSON："
            '{"title_zh":"","summary_zh":""}。summary_zh 包含产品、关键规格、采购方、国家和待确认项，'
            "不得编造原文没有的信息。\n"
            f"标题：{title}\n采购方：{buyer}\n国家：{country}\n原文：{text[:6000]}"
        )
        try:
            parsed = extract_json(await asyncio.to_thread(call_glm_text, prompt))
            if isinstance(parsed, dict) and parsed.get("title_zh"):
                return {"title_zh": str(parsed["title_zh"])[:500], "summary_zh": str(parsed.get("summary_zh", "")), "translation_status": "LLM"}
        except Exception:
            pass

    title_zh = glossary_chinese(title)
    summary = f"采购方：{buyer or '待确认'}；国家/地区：{country or '待确认'}。原文标题：{title}。"
    if text:
        summary += f" 原文摘要：{glossary_chinese(text[:500])}"
    return {"title_zh": title_zh, "summary_zh": summary, "translation_status": "GLOSSARY"}
