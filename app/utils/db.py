from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from loguru import logger
from config.settings import settings

# 异步引擎（pymysql → aiomysql）
_async_url = settings.DATABASE_URL.replace(
    "mysql+pymysql://", "mysql+aiomysql://"
)
engine = create_async_engine(_async_url, echo=settings.DEBUG, pool_pre_ping=True)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def init_db():
    """启动时建表（开发用，生产用 alembic）"""
    if not settings.AUTO_CREATE_TABLES:
        logger.info("跳过自动建表；生产环境使用 Alembic 管理数据库结构")
        return
    from app.models import user, task, report, opc  # noqa: F401 触发模型注册
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("数据库初始化完成")


async def get_db():
    """FastAPI 依赖注入：获取数据库会话"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
