"""Encrypted, user-selected OpenAI-compatible model providers."""
from __future__ import annotations

import base64
import hashlib

import httpx
from cryptography.fernet import Fernet
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.opc import ModelProviderConfig
from config.settings import settings


def _vault() -> Fernet:
    key = base64.urlsafe_b64encode(hashlib.sha256(settings.SECRET_KEY.encode()).digest())
    return Fernet(key)


def encrypt_api_key(value: str) -> str:
    return _vault().encrypt(value.encode()).decode()


def decrypt_api_key(value: str) -> str:
    return _vault().decrypt(value.encode()).decode()


def mask_api_key(value: str) -> str:
    return "已配置（已加密）" if value else "未配置"


async def get_active_model(db: AsyncSession, owner_id: str, purpose: str = "text") -> dict | None:
    row = await db.execute(select(ModelProviderConfig).where(
        ModelProviderConfig.owner_id == owner_id,
        ModelProviderConfig.purpose == purpose,
        ModelProviderConfig.enabled.is_(True),
    ).order_by(ModelProviderConfig.updated_at.desc()))
    item = row.scalars().first()
    if not item or not item.api_key_encrypted:
        return None
    try:
        return {"provider": item.provider, "model": item.model, "base_url": item.base_url.rstrip("/"), "api_key": decrypt_api_key(item.api_key_encrypted)}
    except Exception:
        return None


async def call_model_text(config: dict, prompt: str) -> str:
    headers = {"Authorization": f"Bearer {config['api_key']}", "Content-Type": "application/json"}
    payload = {"model": config["model"], "messages": [{"role": "user", "content": prompt}], "temperature": 0.2}
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(f"{config['base_url']}/chat/completions", headers=headers, json=payload)
        response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]
