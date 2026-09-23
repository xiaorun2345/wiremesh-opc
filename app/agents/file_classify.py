from app.core.agent.base_agent import BaseAgent, AgentResult, AgentStatus
from app.core.mcp.message import MCPMessage
from app.core.memory.redis_memory import TaskMemory
from app.services.minio_service import MinioService
from loguru import logger


MAGIC_MAP = {
    b"\x25\x50\x44\x46": "pdf",
    b"\xAC\x1C\x00\x00": "dwg",
    b"\x41\x43\x31\x30": "dxf",
    b"\xFF\xD8\xFF":      "jpg",
    b"\x89\x50\x4E\x47": "png",
}


class FileClassifyAgent(BaseAgent):
    name = "FileClassifyAgent"
    description = "文件格式识别与分流策略生成"

    async def execute(self, message: MCPMessage) -> AgentResult:
        mem = TaskMemory(message.trace_id)
        file_id   = await mem.get("file_id")
        file_type = await mem.get("file_type")  # 已由上传接口检测，此处二次确认

        # 从 MinIO 读取文件头做二次魔数校验
        try:
            data = MinioService().download(file_id)
            header = data[:16]
            detected = next((t for magic, t in MAGIC_MAP.items() if header.startswith(magic)), None)
            if detected and detected != file_type:
                logger.warning(f"文件类型不一致：声明={file_type}, 检测={detected}，以检测为准")
                file_type = detected
                await mem.set("file_type", file_type)
        except Exception as e:
            logger.warning(f"FileClassify 魔数二次校验失败: {e}，使用上传时类型")

        # 生成分流策略
        strategy = {
            "pdf":  "TextExtractAgent",
            "dwg":  "CadParseAgent",
            "dxf":  "CadParseAgent",
            "jpg":  "VisionParseAgent",
            "jpeg": "VisionParseAgent",
            "png":  "VisionParseAgent",
        }.get(file_type, "TextExtractAgent")

        await mem.set("parse_strategy", strategy)

        logger.info(f"[FileClassify] 类型={file_type}, 策略={strategy}")
        return AgentResult(
            agent_name=self.name,
            status=AgentStatus.SUCCESS,
            data={"file_type": file_type, "strategy": strategy},
        )
