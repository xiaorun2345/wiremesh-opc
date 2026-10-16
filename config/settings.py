from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from dotenv import dotenv_values
from pathlib import Path
import os

# Read .env file directly and override system env vars
_env_path = Path(__file__).parent.parent / ".env"
if _env_path.exists():
    _env_values = dotenv_values(_env_path)
    for key, value in _env_values.items():
        if value is not None:
            os.environ[key] = value


class Settings(BaseSettings):
    APP_NAME: str = "WireMesh OPC"
    APP_ENV: str = "development"
    DEBUG: bool = True
    SECRET_KEY: str = "change-me"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    DATABASE_URL: str = "mysql+pymysql://root:password@localhost:3306/wiremesh_opc"
    REDIS_URL: str = "redis://localhost:6379/0"

    # 文本 LLM
    LLM_PROVIDER: str = "deepseek"
    LLM_MODEL: str = "deepseek-chat"
    LLM_MAX_TOKENS: int = 4096
    LLM_BASE_URL: str = "https://api.deepseek.com"
    LLM_API_KEY: str = ""

    # 多模态大模型（VisionParseAgent 使用）
    # 模式：claude | openai_compatible | zhipu | custom
    MULTIMODAL_PROVIDER: str = "zhipu"
    MULTIMODAL_MODEL: str = "glm-4.6v"
    MULTIMODAL_MAX_TOKENS: int = 4096
    MULTIMODAL_BASE_URL: str = "https://open.bigmodel.cn/api/paas/v4"
    MULTIMODAL_API_KEY: str = ""

    # MinIO
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "wiremesh-opc"
    MINIO_SECURE: bool = False

    # MinerU
    MINERU_API_URL: str = "https://mineru.net/api/kie"
    MINERU_PIPELINE_ID: str = ""
    MINERU_API_KEY: str = ""

    # 企业微信（留空时只生成待审批记录，不向外发送）
    WECOM_WEBHOOK_URL: str = ""
    PUBLIC_BASE_URL: str = "http://localhost:8000"
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"
    INBOUND_WEBHOOK_TOKEN: str = ""
    USE_CELERY: bool = False
    AUTO_CREATE_TABLES: bool = True
    SAM_GOV_API_KEY: str = ""
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_STARTTLS: bool = True
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""
    NOTIFY_EMAILS: str = ""

    # ChromaDB
    CHROMA_HOST: str = "localhost"
    CHROMA_PORT: int = 8002
    EMBEDDING_MODEL: str = "BAAI/bge-small-zh-v1.5"

    # 文件上传
    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE_MB: int = 100

    # 报告配置
    REPORT_TITLE: str = "丝网产品报价与审核报告"
    REPORT_COMPANY: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
