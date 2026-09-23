from dataclasses import dataclass, field
from enum import Enum
from typing import Any
import uuid
import time


class MsgType(str, Enum):
    TASK = "task"          # 任务下发
    RESULT = "result"      # 结果回传
    BROADCAST = "broadcast"  # 广播
    CALLBACK = "callback"  # 链式回调


@dataclass
class MCPMessage:
    """私有MCP通信消息体"""
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    msg_type: MsgType = MsgType.TASK
    payload: dict = field(default_factory=dict)
    sender_agent: str = "orchestrator"
    target_agent: str = "*"
    priority: int = 5          # 1-10，数字越小优先级越高
    created_at: float = field(default_factory=time.time)
    metadata: dict = field(default_factory=dict)

    def reply(self, payload: dict, sender: str) -> "MCPMessage":
        """生成回复消息"""
        return MCPMessage(
            trace_id=self.trace_id,
            msg_type=MsgType.CALLBACK,
            payload=payload,
            sender_agent=sender,
            target_agent=self.sender_agent,
            priority=self.priority,
        )
