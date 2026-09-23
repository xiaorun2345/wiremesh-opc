from __future__ import annotations

"""CRUD and analytics endpoints for the OPC business workspace."""
import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.opc import Customer, Factory, Inquiry, KnowledgeDocument, Order, Quote
from app.models.user import User
from app.utils.auth import get_current_user
from app.utils.db import get_db


router = APIRouter()


class CustomerInput(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    region: str = ""
    language: str = "zh-CN"
    level: str = "B"
    source: str = "manual"
    contact_name: str = ""
    contact_channel: str = ""
    notes: str = ""


class FactoryInput(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    products: list[str] = []
    surfaces: list[str] = []
    certifications: list[str] = []
    lead_days: int = Field(default=15, ge=1, le=365)
    on_time_rate: float = Field(default=0.0, ge=0, le=1)
    quality_score: int = Field(default=0, ge=0, le=100)
    status: str = "ACTIVE"
    notes: str = ""


class InquiryInput(BaseModel):
    customer_id: str | None = None
    source: str = "manual"
    raw_text: str = ""
    product_type: str = ""
    specs: dict[str, Any] = {}
    status: str = "NEW"
    confidence: float = Field(default=0.0, ge=0, le=1)


class KnowledgeInput(BaseModel):
    name: str = Field(min_length=1, max_length=240)
    category: str = "general"
    source_uri: str = ""
    content: str = ""
    chunk_count: int = Field(default=0, ge=0)
    status: str = "ACTIVE"


class OrderInput(BaseModel):
    quote_id: str
    customer_id: str | None = None
    factory_id: str | None = None
    status: str = "CONFIRMED"
    amount: float = Field(default=0.0, ge=0)
    currency: str = "CNY"
    due_date: datetime | None = None
    quality_status: str = "PENDING"
    payment_status: str = "DEPOSIT_PENDING"
    contract_no: str = ""
    invoice_status: str = "NOT_REQUESTED"
    logistics: dict[str, Any] = {}


async def _owned(db: AsyncSession, model, object_id: str, owner_id: str):
    result = await db.execute(select(model).where(model.id == object_id, model.owner_id == owner_id))
    obj = result.scalar_one_or_none()
    if not obj:
        raise HTTPException(404, "记录不存在")
    return obj


async def _list(db: AsyncSession, model, owner_id: str, limit: int, offset: int, status: str | None = None):
    stmt = select(model).where(model.owner_id == owner_id)
    if status and hasattr(model, "status"):
        stmt = stmt.where(model.status == status)
    result = await db.execute(stmt.order_by(model.created_at.desc()).limit(limit).offset(offset))
    return result.scalars().all()


def customer_out(item: Customer) -> dict:
    return {key: getattr(item, key) for key in (
        "id", "name", "region", "language", "level", "source",
        "contact_name", "contact_channel", "notes", "created_at", "updated_at"
    )}


def factory_out(item: Factory) -> dict:
    return {
        "id": item.id, "name": item.name,
        "products": json.loads(item.products_json or "[]"),
        "surfaces": json.loads(item.surfaces_json or "[]"),
        "certifications": json.loads(item.certifications_json or "[]"),
        "lead_days": item.lead_days, "on_time_rate": item.on_time_rate,
        "quality_score": item.quality_score, "status": item.status,
        "notes": item.notes, "created_at": item.created_at, "updated_at": item.updated_at,
    }


def inquiry_out(item: Inquiry) -> dict:
    return {
        "id": item.id, "customer_id": item.customer_id, "source": item.source,
        "raw_text": item.raw_text, "product_type": item.product_type,
        "specs": json.loads(item.specs_json or "{}"), "status": item.status,
        "confidence": item.confidence, "created_at": item.created_at, "updated_at": item.updated_at,
    }


def knowledge_out(item: KnowledgeDocument) -> dict:
    return {key: getattr(item, key) for key in (
        "id", "name", "category", "source_uri", "content", "chunk_count",
        "status", "created_at", "updated_at"
    )}


def order_out(item: Order) -> dict:
    return {
        "id": item.id, "quote_id": item.quote_id, "customer_id": item.customer_id,
        "factory_id": item.factory_id, "status": item.status, "amount": item.amount,
        "currency": item.currency, "due_date": item.due_date,
        "quality_status": item.quality_status,
        "payment_status": item.payment_status, "contract_no": item.contract_no,
        "invoice_status": item.invoice_status,
        "logistics": json.loads(item.logistics_json or "{}"),
        "created_at": item.created_at, "updated_at": item.updated_at,
    }


@router.get("/customers")
async def list_customers(limit: int = Query(50, le=100), offset: int = 0, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return [customer_out(x) for x in await _list(db, Customer, user.id, limit, offset)]


@router.post("/customers", status_code=201)
async def create_customer(body: CustomerInput, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    item = Customer(owner_id=user.id, **body.model_dump()); db.add(item); await db.commit(); await db.refresh(item); return customer_out(item)


@router.patch("/customers/{object_id}")
async def update_customer(object_id: str, body: CustomerInput, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    item = await _owned(db, Customer, object_id, user.id)
    for key, value in body.model_dump().items(): setattr(item, key, value)
    await db.commit(); await db.refresh(item); return customer_out(item)


@router.delete("/customers/{object_id}", status_code=204)
async def delete_customer(object_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    item = await _owned(db, Customer, object_id, user.id); await db.delete(item); await db.commit(); return Response(status_code=204)


@router.get("/factories")
async def list_factories(limit: int = Query(50, le=100), offset: int = 0, status: str | None = None, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return [factory_out(x) for x in await _list(db, Factory, user.id, limit, offset, status)]


@router.post("/factories", status_code=201)
async def create_factory(body: FactoryInput, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    data = body.model_dump(); products = data.pop("products"); surfaces = data.pop("surfaces"); certifications = data.pop("certifications")
    item = Factory(owner_id=user.id, products_json=json.dumps(products, ensure_ascii=False), surfaces_json=json.dumps(surfaces, ensure_ascii=False), certifications_json=json.dumps(certifications, ensure_ascii=False), **data)
    db.add(item); await db.commit(); await db.refresh(item); return factory_out(item)


@router.patch("/factories/{object_id}")
async def update_factory(object_id: str, body: FactoryInput, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    item = await _owned(db, Factory, object_id, user.id); data = body.model_dump()
    item.products_json = json.dumps(data.pop("products"), ensure_ascii=False); item.surfaces_json = json.dumps(data.pop("surfaces"), ensure_ascii=False); item.certifications_json = json.dumps(data.pop("certifications"), ensure_ascii=False)
    for key, value in data.items(): setattr(item, key, value)
    await db.commit(); await db.refresh(item); return factory_out(item)


@router.delete("/factories/{object_id}", status_code=204)
async def delete_factory(object_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    item = await _owned(db, Factory, object_id, user.id); await db.delete(item); await db.commit(); return Response(status_code=204)


@router.get("/inquiries")
async def list_inquiries(limit: int = Query(50, le=100), offset: int = 0, status: str | None = None, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return [inquiry_out(x) for x in await _list(db, Inquiry, user.id, limit, offset, status)]


@router.post("/inquiries", status_code=201)
async def create_inquiry(body: InquiryInput, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    data = body.model_dump(); specs = data.pop("specs"); item = Inquiry(owner_id=user.id, specs_json=json.dumps(specs, ensure_ascii=False), **data)
    db.add(item); await db.commit(); await db.refresh(item); return inquiry_out(item)


@router.patch("/inquiries/{object_id}")
async def update_inquiry(object_id: str, body: InquiryInput, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    item = await _owned(db, Inquiry, object_id, user.id); data = body.model_dump(); item.specs_json = json.dumps(data.pop("specs"), ensure_ascii=False)
    for key, value in data.items(): setattr(item, key, value)
    await db.commit(); await db.refresh(item); return inquiry_out(item)


@router.delete("/inquiries/{object_id}", status_code=204)
async def delete_inquiry(object_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    item = await _owned(db, Inquiry, object_id, user.id); await db.delete(item); await db.commit(); return Response(status_code=204)


@router.get("/knowledge")
async def list_knowledge(limit: int = Query(50, le=100), offset: int = 0, status: str | None = None, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return [knowledge_out(x) for x in await _list(db, KnowledgeDocument, user.id, limit, offset, status)]


@router.post("/knowledge", status_code=201)
async def create_knowledge(body: KnowledgeInput, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    item = KnowledgeDocument(owner_id=user.id, **body.model_dump()); db.add(item); await db.commit(); await db.refresh(item); return knowledge_out(item)


@router.patch("/knowledge/{object_id}")
async def update_knowledge(object_id: str, body: KnowledgeInput, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    item = await _owned(db, KnowledgeDocument, object_id, user.id)
    for key, value in body.model_dump().items(): setattr(item, key, value)
    await db.commit(); await db.refresh(item); return knowledge_out(item)


@router.delete("/knowledge/{object_id}", status_code=204)
async def delete_knowledge(object_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    item = await _owned(db, KnowledgeDocument, object_id, user.id); await db.delete(item); await db.commit(); return Response(status_code=204)


@router.get("/orders")
async def list_orders(limit: int = Query(50, le=100), offset: int = 0, status: str | None = None, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return [order_out(x) for x in await _list(db, Order, user.id, limit, offset, status)]


@router.post("/orders", status_code=201)
async def create_order(body: OrderInput, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    data = body.model_dump(); logistics = data.pop("logistics"); item = Order(owner_id=user.id, logistics_json=json.dumps(logistics, ensure_ascii=False), **data)
    db.add(item); await db.commit(); await db.refresh(item); return order_out(item)


@router.patch("/orders/{object_id}")
async def update_order(object_id: str, body: OrderInput, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    item = await _owned(db, Order, object_id, user.id); data = body.model_dump(); item.logistics_json = json.dumps(data.pop("logistics"), ensure_ascii=False)
    for key, value in data.items(): setattr(item, key, value)
    await db.commit(); await db.refresh(item); return order_out(item)


@router.delete("/orders/{object_id}", status_code=204)
async def delete_order(object_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    item = await _owned(db, Order, object_id, user.id); await db.delete(item); await db.commit(); return Response(status_code=204)


@router.get("/analytics")
async def analytics(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    async def count(model, status: str | None = None):
        stmt = select(func.count()).select_from(model).where(model.owner_id == user.id)
        if status: stmt = stmt.where(model.status == status)
        return int((await db.execute(stmt)).scalar_one())

    quote_amount = await db.execute(select(Quote.result_json).where(Quote.owner_id == user.id, Quote.status.in_(("APPROVED", "SENT", "WON"))))
    total_amount = sum(json.loads(raw or "{}").get("quote_total", 0) for raw in quote_amount.scalars().all())
    inquiry_count = await count(Inquiry)
    quote_count = await count(Quote)
    won_count = await count(Quote, "WON")
    return {
        "inquiries": inquiry_count, "quotes": quote_count, "won_quotes": won_count,
        "orders": await count(Order), "customers": await count(Customer), "factories": await count(Factory),
        "knowledge_documents": await count(KnowledgeDocument), "approved_quote_amount": round(total_amount, 2),
        "quote_rate": round(quote_count / inquiry_count, 4) if inquiry_count else 0,
        "win_rate": round(won_count / quote_count, 4) if quote_count else 0,
    }
