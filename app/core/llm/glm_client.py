from __future__ import annotations

"""
GLM 文本 LLM 调用封装
使用 OpenAI 兼容格式调用智谱 GLM API
"""
import httpx
import json
import re
from loguru import logger
from config.settings import settings


def call_glm_text(prompt: str, model: str | None = None, max_tokens: int | None = None) -> str:
    """
    同步调用 GLM 文本模型（用于 LangGraph 节点内）
    返回模型响应的文本内容
    内置 3 次重试，遇到 429 速率限制自动退避
    """
    import time
    model = model or settings.LLM_MODEL
    max_tokens = max_tokens or settings.LLM_MAX_TOKENS
    api_key = settings.LLM_API_KEY
    base_url = settings.LLM_BASE_URL

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }

    last_error = None
    for attempt in range(3):
        try:
            with httpx.Client(timeout=60) as client:
                resp = client.post(
                    f"{base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                )
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"]
        except httpx.HTTPStatusError as e:
            last_error = e
            if e.response.status_code == 429 and attempt < 2:
                wait = 2 ** attempt  # 2s, 4s
                logger.warning(f"[GLM] 速率限制，{wait}s 后重试 ({attempt+1}/2)")
                time.sleep(wait)
            else:
                break
        except Exception as e:
            last_error = e
            break

    logger.error(f"[GLM] 文本调用失败: {last_error}")
    raise last_error


def extract_json(text: str) -> dict | list | None:
    """从模型响应中提取 JSON（对象或数组）"""
    # 尝试匹配完整对象
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group())
        except Exception:
            pass
    # 尝试匹配数组
    m = re.search(r"\[.*\]", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group())
        except Exception:
            pass
    return None
