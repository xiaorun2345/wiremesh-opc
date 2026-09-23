from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.utils.db import get_db
from app.utils.auth import (
    verify_password, create_access_token, create_refresh_token,
    hash_password, get_current_user, blacklist_token,
)
from app.models.user import User
from app.schemas.schemas import LoginRequest, TokenResponse, UserPreferences
from app.core.memory.redis_memory import UserSessionMemory
import uuid

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == body.username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "UNAUTHORIZED", "message": "用户名或密码错误"},
        )
    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: dict, db: AsyncSession = Depends(get_db)):
    from jose import jwt, JWTError
    from config.settings import settings
    try:
        payload = jwt.decode(body.get("refresh_token", ""), settings.SECRET_KEY, algorithms=["HS256"])
        user_id = payload.get("sub")
    except JWTError:
        raise HTTPException(status_code=401, detail={"error": "UNAUTHORIZED", "message": "Refresh Token 无效"})
    return TokenResponse(
        access_token=create_access_token(user_id),
        refresh_token=create_refresh_token(user_id),
    )


@router.post("/register", response_model=TokenResponse)
async def register(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    """开发用注册接口，生产环境可关闭"""
    result = await db.execute(select(User).where(User.username == body.username))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail={"error": "CONFLICT", "message": "用户名已存在"})
    user = User(id=str(uuid.uuid4()), username=body.username, password_hash=hash_password(body.password))
    db.add(user)
    await db.commit()
    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/logout", status_code=204)
async def logout(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """登出：将当前 Token 加入黑名单"""
    token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    if token:
        await blacklist_token(token)


@router.get("/preferences", response_model=UserPreferences)
async def get_preferences(current_user: User = Depends(get_current_user)):
    """获取用户偏好设置"""
    mem = UserSessionMemory(current_user.id)
    prefs = await mem.get_preferences()
    return UserPreferences(**prefs) if prefs else UserPreferences()


@router.put("/preferences", response_model=UserPreferences)
async def update_preferences(
    body: UserPreferences,
    current_user: User = Depends(get_current_user),
):
    """更新用户偏好设置"""
    mem = UserSessionMemory(current_user.id)
    await mem.update_preferences(body.model_dump())
    return body
