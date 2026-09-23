from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.utils.db import Base


class Report(Base):
    __tablename__ = "reports"

    id:         Mapped[str]      = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id:    Mapped[str]      = mapped_column(String(36), ForeignKey("tasks.id"), unique=True, nullable=False)
    pdf_path:   Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    excel_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
