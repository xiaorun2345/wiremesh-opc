from __future__ import annotations

import uuid
import json
import io
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.core.memory.redis_memory import TaskMemory
from app.core.skill.wire_mesh_pricing import WireMeshSpec
from app.integrations.wecom import notify_quote_review
from app.models.user import User
from app.models.opc import Order, OrderEvent, Quote
from app.services.wire_mesh_service import build_quote_from_db
from app.utils.auth import get_current_user
from app.utils.db import get_db
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


router = APIRouter()


class WireMeshSpecRequest(BaseModel):
    product_type: Literal["welded_mesh", "fence_mesh", "hexagonal_mesh", "screen_mesh", "expanded_mesh"]
    material: Literal["low_carbon_steel", "galvanized_steel", "stainless_304", "stainless_316"]
    wire_diameter_mm: float = Field(gt=0, le=30)
    mesh_size_mm: float = Field(gt=0, le=1000)
    width_m: float = Field(gt=0, le=20)
    length_m: float = Field(gt=0, le=1000)
    quantity: int = Field(gt=0, le=1_000_000)
    surface_treatment: Literal["none", "electro_galvanized", "hot_dip_galvanized", "pvc_coated", "powder_coated"] = "none"
    packaging: Literal["bulk", "pallet", "export"] = "export"
    margin_rate: float = Field(default=0.15, ge=0.05, le=0.50)
    freight: float = Field(default=0.0, ge=0)
    currency: str = Field(default="CNY", min_length=3, max_length=3)


class ApprovalDecisionRequest(BaseModel):
    decision: Literal["approve", "reject"]
    note: str = Field(default="", max_length=500)


class ConvertOrderRequest(BaseModel):
    customer_id: str | None = None
    factory_id: str | None = None
    due_date: datetime | None = None


def _to_spec(body: WireMeshSpecRequest) -> WireMeshSpec:
    return WireMeshSpec(**body.model_dump())


@router.post("/preview")
async def preview_quote(
    body: WireMeshSpecRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    quote_id = f"QT-{uuid.uuid4().hex[:12].upper()}"
    quote = await build_quote_from_db(db, current_user.id, _to_spec(body))
    quote.update({
        "quote_id": quote_id,
        "status": "DRAFT",
        "created_by": current_user.id,
    })
    mem = TaskMemory(quote_id, ttl=86400)
    await mem.set("quote", quote)
    db.add(Quote(
        id=quote_id, owner_id=current_user.id,
        spec_json=json.dumps(quote["spec"], ensure_ascii=False),
        result_json=json.dumps(quote, ensure_ascii=False), status="DRAFT",
    ))
    await db.commit()
    return quote


@router.get("")
async def list_quotes(
    status: str | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Quote).where(Quote.owner_id == current_user.id)
    if status:
        stmt = stmt.where(Quote.status == status)
    rows = await db.execute(stmt.order_by(Quote.created_at.desc()).limit(100))
    return [json.loads(row.result_json) | {
        "status": row.status,
        "approval_note": row.approval_note,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    } for row in rows.scalars().all()]


@router.get("/{quote_id}")
async def get_quote(
    quote_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Quote).where(Quote.id == quote_id, Quote.owner_id == current_user.id))
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(404, "报价不存在")
    quote = json.loads(row.result_json)
    quote["status"] = row.status
    quote["approval_note"] = row.approval_note
    return quote


@router.post("/{quote_id}/submit")
async def submit_for_approval(
    quote_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Quote).where(Quote.id == quote_id, Quote.owner_id == current_user.id))
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(404, "报价不存在")
    if row.status not in ("DRAFT", "REJECTED"):
        raise HTTPException(409, f"当前状态 {row.status} 不可提交审批")

    quote = json.loads(row.result_json)
    quote["status"] = "PENDING_APPROVAL"
    notified = await notify_quote_review(quote_id, quote)
    quote["wecom_notified"] = notified
    row.status = "PENDING_APPROVAL"
    row.result_json = json.dumps(quote, ensure_ascii=False)
    await db.commit()
    mem = TaskMemory(quote_id, ttl=86400)
    await mem.set("quote", quote)
    return quote


@router.post("/{quote_id}/decision")
async def decide_quote(
    quote_id: str,
    body: ApprovalDecisionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Quote).where(Quote.id == quote_id, Quote.owner_id == current_user.id))
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(404, "报价不存在")
    if row.status != "PENDING_APPROVAL":
        raise HTTPException(409, f"当前状态 {row.status} 不可审批")

    quote = json.loads(row.result_json)
    quote["status"] = "APPROVED" if body.decision == "approve" else "REJECTED"
    quote["approval_note"] = body.note
    quote["approved_by"] = current_user.id
    row.status = quote["status"]
    row.approval_note = body.note
    row.approved_by = current_user.id
    row.result_json = json.dumps(quote, ensure_ascii=False)
    await db.commit()
    mem = TaskMemory(quote_id, ttl=86400)
    await mem.set("quote", quote)
    return quote


@router.get("/{quote_id}/download")
async def download_quote(
    quote_id: str,
    format: Literal["pdf", "excel"] = Query("pdf"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result=await db.execute(select(Quote).where(Quote.id==quote_id,Quote.owner_id==current_user.id));row=result.scalar_one_or_none()
    if not row: raise HTTPException(404,"报价不存在")
    quote=json.loads(row.result_json)
    from app.services.wire_mesh_report import build_quote_excel, build_quote_pdf
    if format=="pdf":
        data=build_quote_pdf(quote,quote_id);media="application/pdf";name=f"{quote_id}.pdf"
    else:
        data=build_quote_excel(quote,quote_id);media="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";name=f"{quote_id}.xlsx"
    return StreamingResponse(io.BytesIO(data),media_type=media,headers={"Content-Disposition":f'attachment; filename="{name}"'})


@router.post("/{quote_id}/convert-order", status_code=201)
async def convert_quote_to_order(
    quote_id: str,
    body: ConvertOrderRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result=await db.execute(select(Quote).where(Quote.id==quote_id,Quote.owner_id==current_user.id));quote_row=result.scalar_one_or_none()
    if not quote_row: raise HTTPException(404,"报价不存在")
    if quote_row.status not in ("APPROVED","SENT","WON"): raise HTTPException(409,"报价批准后才能转订单")
    existing=await db.execute(select(Order).where(Order.quote_id==quote_id,Order.owner_id==current_user.id));order=existing.scalar_one_or_none()
    if order: return {"id":order.id,"status":order.status,"existing":True}
    quote=json.loads(quote_row.result_json)
    order=Order(owner_id=current_user.id,quote_id=quote_id,customer_id=body.customer_id,factory_id=body.factory_id,status="待排产",amount=quote["quote_total"],currency=quote["currency"],due_date=body.due_date,quality_status="PENDING",payment_status="DEPOSIT_PENDING",logistics_json="{}")
    db.add(order);await db.flush();db.add(OrderEvent(owner_id=current_user.id,order_id=order.id,event_type="created_from_quote",from_status="",to_status="待排产",data_json=json.dumps({"quote_id":quote_id},ensure_ascii=False)));quote_row.status="WON";await db.commit()
    return {"id":order.id,"status":order.status,"existing":False}
