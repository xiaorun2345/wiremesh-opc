from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
import asyncio
from loguru import logger

from app.core.mcp.message import MCPMessage
from app.core.hooks.hook_manager import HookManager

# 各 Agent 默认超时（秒），子类可覆盖
DEFAULT_TIMEOUT = 300  # 5 分钟


class AgentStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class AgentResult:
    agent_name: str
    status: AgentStatus
    data: dict = field(default_factory=dict)
    error: str = ""


class BaseAgent(ABC):
    """所有Agent的基类"""

    name: str = "base_agent"
    description: str = ""
    timeout_seconds: int = DEFAULT_TIMEOUT  # 子类可覆盖

    def __init__(self, hook_manager: HookManager | None = None):
        self.hook_manager = hook_manager or HookManager()
        self.status = AgentStatus.IDLE

    async def run(self, message: MCPMessage) -> AgentResult:
        self.status = AgentStatus.RUNNING
        logger.info(f"[{self.name}] 开始执行, trace_id={message.trace_id}, timeout={self.timeout_seconds}s")

        await self.hook_manager.trigger("before_agent_run", agent=self, message=message)

        try:
            result = await asyncio.wait_for(
                self.execute(message),
                timeout=self.timeout_seconds,
            )
            self.status = AgentStatus.SUCCESS
            logger.info(f"[{self.name}] 执行成功")
            await self.hook_manager.trigger("after_agent_run", agent=self, result=result)
            return result

        except asyncio.TimeoutError:
            self.status = AgentStatus.FAILED
            msg = f"执行超时（{self.timeout_seconds}s）"
            logger.error(f"[{self.name}] {msg}")
            await self.hook_manager.trigger("on_agent_error", agent=self, error=TimeoutError(msg))
            return AgentResult(agent_name=self.name, status=AgentStatus.FAILED, error=msg)

        except Exception as e:
            self.status = AgentStatus.FAILED
            logger.error(f"[{self.name}] 执行失败: {e}")
            await self.hook_manager.trigger("on_agent_error", agent=self, error=e)
            return AgentResult(agent_name=self.name, status=AgentStatus.FAILED, error=str(e))

    @abstractmethod
    async def execute(self, message: MCPMessage) -> AgentResult:
        """子类实现具体业务逻辑"""
        ...

    def can_handle(self, message: MCPMessage) -> bool:
        return message.target_agent == self.name or message.target_agent == "*"
