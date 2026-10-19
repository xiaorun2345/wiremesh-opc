from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel


# ── 认证 ──────────────────────────────────────────────────────
class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


# ── 任务 ──────────────────────────────────────────────────────
class StepStatus(BaseModel):
    agent: str
    status: str
    duration_ms: int | None = None
    attempts: int = 0
    fallback: str = ""
    message: str = ""

class TaskResponse(BaseModel):
    task_id: str
    status: str
    current_step: str | None = None
    progress: int = 0
    steps: list[StepStatus] = []
    file_name: str
    file_type: str
    file_size: int = 0
    created_at: datetime
    updated_at: datetime
    # PAUSED 时暴露中间数据，供人工审核修改后续跑
    intermediate_data: dict | None = None
    error_msg: str | None = None

class ResumeRequest(BaseModel):
    override_data: dict = {}

class ResumeResponse(BaseModel):
    task_id: str
    status: str
    resumed_from_step: str


# ── 报告 ──────────────────────────────────────────────────────
class ReportMeta(BaseModel):
    task_id: str
    pdf_available: bool
    excel_available: bool
    created_at: datetime


# ── 用户偏好 ──────────────────────────────────────────────────
class UserPreferences(BaseModel):
    default_floor_height: int = 2800
    preferred_material: str = "涂料"
    waterproof_standard: str = "GB50327"
    extra: dict = {}


# ── 通用错误 ──────────────────────────────────────────────────
class ErrorResponse(BaseModel):
    error: str
    message: str
    detail: str | None = None
