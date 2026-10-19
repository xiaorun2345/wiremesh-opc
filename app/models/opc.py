from __future__ import annotations

"""Persistent business entities for the wire-mesh OPC workspace."""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.utils.db import Base


def new_id() -> str:
    return str(uuid.uuid4())


class Customer(Base):
    __tablename__ = "opc_customers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    region: Mapped[str] = mapped_column(String(120), default="")
    language: Mapped[str] = mapped_column(String(16), default="zh-CN")
    level: Mapped[str] = mapped_column(String(8), default="B")
    source: Mapped[str] = mapped_column(String(64), default="manual")
    contact_name: Mapped[str] = mapped_column(String(80), default="")
    contact_channel: Mapped[str] = mapped_column(String(160), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Factory(Base):
    __tablename__ = "opc_factories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    products_json: Mapped[str] = mapped_column(Text, default="[]")
    surfaces_json: Mapped[str] = mapped_column(Text, default="[]")
    certifications_json: Mapped[str] = mapped_column(Text, default="[]")
    lead_days: Mapped[int] = mapped_column(Integer, default=15)
    on_time_rate: Mapped[float] = mapped_column(Float, default=0.0)
    quality_score: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Inquiry(Base):
    __tablename__ = "opc_inquiries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    customer_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("opc_customers.id"), nullable=True)
    source: Mapped[str] = mapped_column(String(64), default="manual")
    raw_text: Mapped[str] = mapped_column(Text, default="")
    product_type: Mapped[str] = mapped_column(String(64), default="")
    specs_json: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[str] = mapped_column(String(32), default="NEW", index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Quote(Base):
    __tablename__ = "opc_quotes"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    inquiry_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("opc_inquiries.id"), nullable=True)
    spec_json: Mapped[str] = mapped_column(Text, nullable=False)
    result_json: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="DRAFT", index=True)
    approval_note: Mapped[str] = mapped_column(Text, default="")
    approved_by: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    pdf_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    excel_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Order(Base):
    __tablename__ = "opc_orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    quote_id: Mapped[str] = mapped_column(String(40), ForeignKey("opc_quotes.id"), nullable=False)
    customer_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("opc_customers.id"), nullable=True)
    factory_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("opc_factories.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="CONFIRMED", index=True)
    amount: Mapped[float] = mapped_column(Float, default=0.0)
    currency: Mapped[str] = mapped_column(String(8), default="CNY")
    due_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    quality_status: Mapped[str] = mapped_column(String(32), default="PENDING")
    payment_status: Mapped[str] = mapped_column(String(32), default="DEPOSIT_PENDING")
    contract_no: Mapped[str] = mapped_column(String(80), default="")
    invoice_status: Mapped[str] = mapped_column(String(32), default="NOT_REQUESTED")
    logistics_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class KnowledgeDocument(Base):
    __tablename__ = "opc_knowledge_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(240), nullable=False)
    category: Mapped[str] = mapped_column(String(64), default="general", index=True)
    source_uri: Mapped[str] = mapped_column(String(512), default="")
    content: Mapped[str] = mapped_column(Text, default="")
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PriceRule(Base):
    __tablename__ = "opc_price_rules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    category: Mapped[str] = mapped_column(String(64), index=True)
    item_key: Mapped[str] = mapped_column(String(80), index=True)
    unit: Mapped[str] = mapped_column(String(24), default="")
    unit_price: Mapped[float] = mapped_column(Float, default=0.0)
    currency: Mapped[str] = mapped_column(String(8), default="CNY")
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_active: Mapped[int] = mapped_column(Integer, default=1)
    extra_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CustomerFollowUp(Base):
    __tablename__ = "opc_customer_followups"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    customer_id: Mapped[str] = mapped_column(String(36), ForeignKey("opc_customers.id"), index=True)
    channel: Mapped[str] = mapped_column(String(32), default="note")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    next_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(24), default="OPEN")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class OrderEvent(Base):
    __tablename__ = "opc_order_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    order_id: Mapped[str] = mapped_column(String(36), ForeignKey("opc_orders.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(40), index=True)
    from_status: Mapped[str] = mapped_column(String(32), default="")
    to_status: Mapped[str] = mapped_column(String(32), default="")
    data_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class InboundMessage(Base):
    __tablename__ = "opc_inbound_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    source: Mapped[str] = mapped_column(String(32), index=True)
    external_id: Mapped[str] = mapped_column(String(160), default="", index=True)
    sender: Mapped[str] = mapped_column(String(160), default="")
    raw_text: Mapped[str] = mapped_column(Text, default="")
    attachments_json: Mapped[str] = mapped_column(Text, default="[]")
    status: Mapped[str] = mapped_column(String(24), default="RECEIVED", index=True)
    inquiry_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("opc_inquiries.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AuditLog(Base):
    __tablename__ = "opc_audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    action: Mapped[str] = mapped_column(String(80), index=True)
    entity_type: Mapped[str] = mapped_column(String(40), index=True)
    entity_id: Mapped[str] = mapped_column(String(64), default="")
    data_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class OrderAttachment(Base):
    __tablename__ = "opc_order_attachments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    order_id: Mapped[str] = mapped_column(String(36), ForeignKey("opc_orders.id"), index=True)
    kind: Mapped[str] = mapped_column(String(32), index=True)
    file_name: Mapped[str] = mapped_column(String(256))
    object_path: Mapped[str] = mapped_column(String(512))
    content_type: Mapped[str] = mapped_column(String(120), default="application/octet-stream")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class LeadSource(Base):
    """A configured public procurement source for one workspace."""
    __tablename__ = "opc_lead_sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    provider: Mapped[str] = mapped_column(String(32), index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    config_json: Mapped[str] = mapped_column(Text, default="{}")
    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_status: Mapped[str] = mapped_column(String(32), default="NEVER")
    last_error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class OverseasLead(Base):
    """Normalized public opportunity before it becomes a sales inquiry."""
    __tablename__ = "opc_overseas_leads"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    source_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("opc_lead_sources.id"), nullable=True)
    source: Mapped[str] = mapped_column(String(32), index=True)
    external_id: Mapped[str] = mapped_column(String(200), index=True)
    dedupe_key: Mapped[str] = mapped_column(String(280), unique=True, index=True)
    source_url: Mapped[str] = mapped_column(String(1024), default="")
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    buyer: Mapped[str] = mapped_column(String(240), default="")
    country: Mapped[str] = mapped_column(String(80), default="")
    language: Mapped[str] = mapped_column(String(16), default="en")
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    deadline_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    budget: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(8), default="")
    raw_text: Mapped[str] = mapped_column(Text, default="")
    raw_json: Mapped[str] = mapped_column(Text, default="{}")
    extracted_json: Mapped[str] = mapped_column(Text, default="{}")
    title_zh: Mapped[str] = mapped_column(String(500), default="")
    summary_zh: Mapped[str] = mapped_column(Text, default="")
    translation_status: Mapped[str] = mapped_column(String(32), default="PENDING")
    review_status: Mapped[str] = mapped_column(String(32), default="NEEDS_REVIEW", index=True)
    review_note: Mapped[str] = mapped_column(Text, default="")
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    score: Mapped[int] = mapped_column(Integer, default=0, index=True)
    score_reasons_json: Mapped[str] = mapped_column(Text, default="[]")
    status: Mapped[str] = mapped_column(String(32), default="NEW", index=True)
    inquiry_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("opc_inquiries.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Notification(Base):
    __tablename__ = "opc_notifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    category: Mapped[str] = mapped_column(String(32), index=True)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    body: Mapped[str] = mapped_column(Text, default="")
    entity_type: Mapped[str] = mapped_column(String(32), default="")
    entity_id: Mapped[str] = mapped_column(String(64), default="")
    priority: Mapped[str] = mapped_column(String(16), default="NORMAL")
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    channel_status_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
