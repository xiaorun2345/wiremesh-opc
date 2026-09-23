from __future__ import annotations

import json
import time
from typing import Any
from loguru import logger

import redis.asyncio as aioredis
from config.settings import settings

_redis: aioredis.Redis | None = None
_redis_available = True


async def init_redis():
    global _redis, _redis_available
    try:
        _redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        await _redis.ping()
        logger.info("Redis 连接成功")
    except Exception as e:
        logger.warning(f"Redis 连接失败，使用内存 mock 降级: {e}")
        _redis_available = False
        # 创建一个假的 Redis 对象，避免 get_redis() 报错
        _redis = FakeRedis()


class FakeRedis:
    """内存 mock Redis，用于无 Redis 环境下的开发测试"""
    def __init__(self):
        self._data = {}
        self._lists = {}  # Redis list 数据结构

    async def ping(self):
        return True

    async def get(self, key):
        return self._data.get(key)

    async def set(self, key, value, ex=None):
        self._data[key] = value

    async def delete(self, *keys):
        for k in keys:
            self._data.pop(k, None)

    async def exists(self, key):
        return 1 if key in self._data else 0

    async def keys(self, pattern):
        import fnmatch
        return [k for k in self._data if fnmatch.fnmatch(k, pattern)]

    async def flushdb(self):
        self._data.clear()
        self._lists.clear()

    # List operations
    async def lpush(self, key, *values):
        if key not in self._lists:
            self._lists[key] = []
        for v in reversed(values):
            self._lists[key].insert(0, v)
        return len(self._lists[key])

    async def rpush(self, key, *values):
        if key not in self._lists:
            self._lists[key] = []
        for v in values:
            self._lists[key].append(v)
        return len(self._lists[key])

    async def lrange(self, key, start, end):
        lst = self._lists.get(key, [])
        if end == -1:
            end = len(lst)
        else:
            end += 1
        return lst[start:end]

    async def ltrim(self, key, start, end):
        lst = self._lists.get(key, [])
        if end == -1:
            end = len(lst)
        else:
            end += 1
        self._lists[key] = lst[start:end]

    async def llen(self, key):
        return len(self._lists.get(key, []))

    async def expire(self, key, seconds):
        pass  # FakeRedis 不处理 TTL


def get_redis() -> aioredis.Redis:
    if _redis is None:
        raise RuntimeError("Redis 未初始化，请先调用 init_redis()")
    return _redis


class TaskMemory:
    """任务级共享记忆 — 同一 trace_id 下所有 Agent 共享"""

    def __init__(self, trace_id: str, ttl: int = 3600):
        self.trace_id = trace_id
        self.ttl = ttl
        self._prefix = f"task_mem:{trace_id}"

    async def set(self, key: str, value: Any):
        r = get_redis()
        full_key = f"{self._prefix}:{key}"
        # bytes 类型转为 base64 字符串以便 JSON 序列化
        if isinstance(value, bytes):
            import base64
            value = {"__type__": "bytes", "__data__": base64.b64encode(value).decode()}
        await r.set(full_key, json.dumps(value, ensure_ascii=False), ex=self.ttl)

    async def get(self, key: str, default=None) -> Any:
        r = get_redis()
        raw = await r.get(f"{self._prefix}:{key}")
        if raw is None:
            return default
        value = json.loads(raw)
        # 还原 bytes 类型
        if isinstance(value, dict) and value.get("__type__") == "bytes":
            import base64
            return base64.b64decode(value["__data__"])
        return value

    async def delete(self, key: str):
        r = get_redis()
        await r.delete(f"{self._prefix}:{key}")

    async def clear(self):
        """任务结束后清理所有记忆"""
        r = get_redis()
        keys = await r.keys(f"{self._prefix}:*")
        if keys:
            await r.delete(*keys)
        logger.debug(f"TaskMemory 已清理: trace_id={self.trace_id}")


class AgentPrivateMemory:
    """单体Agent私有记忆 — 跨任务持久化"""

    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self._prefix = f"agent_mem:{agent_name}"

    async def set(self, key: str, value: Any, ttl: int = 86400 * 7):
        r = get_redis()
        await r.set(f"{self._prefix}:{key}", json.dumps(value, ensure_ascii=False), ex=ttl)

    async def get(self, key: str, default=None) -> Any:
        r = get_redis()
        raw = await r.get(f"{self._prefix}:{key}")
        if raw is None:
            return default
        return json.loads(raw)

    async def append_history(self, record: dict, max_records: int = 50):
        """追加执行历史，保留最近N条"""
        r = get_redis()
        key = f"{self._prefix}:history"
        await r.lpush(key, json.dumps(record, ensure_ascii=False))
        await r.ltrim(key, 0, max_records - 1)
        await r.expire(key, 86400 * 30)

    async def get_history(self, limit: int = 10) -> list:
        r = get_redis()
        raw_list = await r.lrange(f"{self._prefix}:history", 0, limit - 1)
        return [json.loads(x) for x in raw_list]


class UserSessionMemory:
    """用户级长记忆 — 跨会话持久化"""

    def __init__(self, user_id: str):
        self.user_id = user_id
        self._prefix = f"user_mem:{user_id}"

    async def set(self, key: str, value: Any, ttl: int = 86400 * 90):
        r = get_redis()
        await r.set(f"{self._prefix}:{key}", json.dumps(value, ensure_ascii=False), ex=ttl)

    async def get(self, key: str, default=None) -> Any:
        r = get_redis()
        raw = await r.get(f"{self._prefix}:{key}")
        if raw is None:
            return default
        return json.loads(raw)

    async def get_preferences(self) -> dict:
        return await self.get("preferences", {})

    async def update_preferences(self, updates: dict):
        prefs = await self.get_preferences()
        prefs.update(updates)
        await self.set("preferences", prefs)
