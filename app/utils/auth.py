from datetime import datetime, timedelta
from jose import jwt, JWTError
import bcrypt
import hashlib
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from config.settings import settings
from app.utils.db import get_db
from app.models.user import User

bearer_scheme = HTTPBearer()
ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    pwd_bytes = password.encode("utf-8")[:72]
    return bcrypt.hashpw(pwd_bytes, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    pwd_bytes = plain.encode("utf-8")[:72]
    return bcrypt.checkpw(pwd_bytes, hashed.encode("utf-8"))


def create_token(user_id: str, expires_minutes: int) -> str:
    expire = datetime.utcnow() + timedelta(minutes=expires_minutes)
    return jwt.encode(
        {"sub": user_id, "exp": expire},
        settings.SECRET_KEY,
        algorithm=ALGORITHM,
    )


def create_access_token(user_id: str) -> str:
    return create_token(user_id, settings.ACCESS_TOKEN_EXPIRE_MINUTES)


def create_refresh_token(user_id: str) -> str:
    return create_token(user_id, 60 * 24 * 7)  # 7天


def _token_blacklist_key(token: str) -> str:
    """Token 黑名单 Redis key（用 SHA256 避免存明文）"""
    return f"token_blacklist:{hashlib.sha256(token.encode()).hexdigest()}"


async def blacklist_token(token: str):
    """将 Token 加入黑名单，TTL 与 Token 过期时间一致"""
    try:
        from app.core.memory.redis_memory import get_redis
        r = get_redis()
        # 解析剩余有效期
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM],
                             options={"verify_exp": False})
        exp = payload.get("exp", 0)
        ttl = max(0, int(exp - datetime.utcnow().timestamp()))
        if ttl > 0:
            await r.set(_token_blacklist_key(token), "1", ex=ttl)
    except Exception:
        pass  # 黑名单写入失败不影响登出流程


async def is_token_blacklisted(token: str) -> bool:
    """检查 Token 是否在黑名单中"""
    try:
        from app.core.memory.redis_memory import get_redis
        r = get_redis()
        return await r.exists(_token_blacklist_key(token)) > 0
    except Exception:
        return False  # Redis 不可用时放行，不影响正常使用


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if not user_id:
            raise ValueError
    except (JWTError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "UNAUTHORIZED", "message": "Token 无效或已过期"},
        )

    # 检查黑名单（已登出的 Token）
    if await is_token_blacklisted(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "UNAUTHORIZED", "message": "Token 已失效，请重新登录"},
        )

    result = await db.execute(select(User).where(User.id == user_id, User.is_active == True))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "UNAUTHORIZED", "message": "用户不存在或已禁用"},
        )
    return user
