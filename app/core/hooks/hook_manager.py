from typing import Any, Callable, Awaitable
from loguru import logger


HookHandler = Callable[..., Awaitable[None]]


class HookManager:
    """全生命周期钩子管理器"""

    SUPPORTED_HOOKS = {
        "before_agent_run",
        "after_agent_run",
        "on_agent_error",
        "on_whole_finish",
    }

    def __init__(self):
        self._hooks: dict[str, list[HookHandler]] = {k: [] for k in self.SUPPORTED_HOOKS}

    def register(self, event: str, handler: HookHandler):
        if event not in self.SUPPORTED_HOOKS:
            raise ValueError(f"不支持的Hook事件: {event}，可用: {self.SUPPORTED_HOOKS}")
        self._hooks[event].append(handler)
        logger.debug(f"注册Hook: {event} -> {handler.__name__}")

    async def trigger(self, event: str, **kwargs):
        for handler in self._hooks.get(event, []):
            try:
                await handler(**kwargs)
            except Exception as e:
                logger.warning(f"Hook [{event}] 执行异常: {e}")


def log_hook(event_name: str):
    """通用日志Hook工厂"""
    async def _hook(**kwargs):
        agent = kwargs.get("agent")
        name = agent.name if agent else "unknown"
        logger.debug(f"Hook触发: {event_name} | agent={name}")
    _hook.__name__ = f"log_{event_name}"
    return _hook
