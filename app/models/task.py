from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Text, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.utils.db import Base


class Task(Base):
    __tablename__ = "tasks"

    id:           Mapped[str]      = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id:      Mapped[str]      = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    file_name:    Mapped[str]      = mapped_column(String(256), nullable=False)
    file_type:    Mapped[str]      = mapped_column(String(16), nullable=False)
    file_id:      Mapped[str]      = mapped_column(String(512), nullable=False)
    file_size:    Mapped[int]      = mapped_column(Integer, default=0)  # 文件大小（字节）
    status:       Mapped[str]      = mapped_column(String(16), default="PENDING", index=True)
    current_step: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    progress:     Mapped[int]      = mapped_column(Integer, default=0)
    steps_json:   Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_msg:    Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at:   Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at:   Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
