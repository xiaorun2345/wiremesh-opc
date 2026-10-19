from __future__ import annotations

"""Operational automation APIs: prices, follow-ups, order events and inbound channels."""
import json
import io
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.opc import AuditLog, CustomerFollowUp, InboundMessage, Inquiry, KnowledgeDocument, LeadSource, Notification, Order, OrderAttachment, OrderEvent, OverseasLead, PriceRule
from app.models.user import User
from app.utils.auth import get_current_user
from app.utils.db import get_db
from config.settings import settings

router = APIRouter()


class PriceRuleInput(BaseModel):
    category: str
    item_key: str
    unit: str = ""
    unit_price: float = Field(ge=0)
    currency: str = "CNY"
    is_active: int = 1
    extra: dict[str, Any] = {}


class FollowUpInput(BaseModel):
    customer_id: str
    channel: str = "note"
    content: str = Field(min_length=1)
    next_at: datetime | None = None


class OrderEventInput(BaseModel):
    event_type: str
    to_status: str = ""
    data: dict[str, Any] = {}


class InboundInput(BaseModel):
    owner_id: str
    source: str
    external_id: str = ""
    sender: str = ""
    text: str
    attachments: list[dict[str, Any]] = []


class LeadSourceInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    provider: str = Field(pattern="^(ted|sam|contracts_finder|rss)$")
    enabled: bool = True
    config: dict[str, Any] = {}


class LeadStatusInput(BaseModel):
    status: str = Field(pattern="^(NEW|HIGH_PRIORITY|REVIEWING|INTERESTED|IGNORED|ARCHIVED|CONVERTED)$")


class LeadReviewInput(BaseModel):
    decision: str = Field(pattern="^(INTERESTED|IGNORED)$")
    note: str = Field(default="", max_length=2000)


async def audit(db: AsyncSession, owner_id: str, action: str, entity_type: str, entity_id: str, data: dict | None = None):
    db.add(AuditLog(owner_id=owner_id, action=action, entity_type=entity_type, entity_id=entity_id, data_json=json.dumps(data or {}, ensure_ascii=False)))


def lead_out(item: OverseasLead) -> dict:
    return {
        "id": item.id, "source_id": item.source_id, "source": item.source, "external_id": item.external_id,
        "source_url": item.source_url, "title": item.title, "buyer": item.buyer, "country": item.country,
        "language": item.language, "published_at": item.published_at, "deadline_at": item.deadline_at,
        "budget": item.budget, "currency": item.currency, "raw_text": item.raw_text,
        "title_zh": item.title_zh, "summary_zh": item.summary_zh, "translation_status": item.translation_status,
        "review_status": item.review_status, "review_note": item.review_note, "reviewed_at": item.reviewed_at,
        "extracted": json.loads(item.extracted_json or "{}"), "score": item.score,
        "score_reasons": json.loads(item.score_reasons_json or "[]"), "status": item.status,
        "inquiry_id": item.inquiry_id, "created_at": item.created_at,
    }


@router.get("/lead-sources")
async def list_lead_sources(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = await db.execute(select(LeadSource).where(LeadSource.owner_id == user.id).order_by(LeadSource.created_at.desc()))
    return [{"id": x.id, "name": x.name, "provider": x.provider, "enabled": x.enabled, "config": json.loads(x.config_json or "{}"), "last_run_at": x.last_run_at, "last_status": x.last_status, "last_error": x.last_error} for x in rows.scalars().all()]


@router.post("/lead-sources", status_code=201)
async def create_lead_source(body: LeadSourceInput, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    item = LeadSource(owner_id=user.id, name=body.name, provider=body.provider, enabled=body.enabled, config_json=json.dumps(body.config, ensure_ascii=False))
    db.add(item); await db.flush(); await audit(db, user.id, "lead_source.create", "lead_source", item.id, {"provider": body.provider}); await db.commit()
    return {"id": item.id}


@router.post("/lead-sources/install-defaults")
async def install_default_lead_sources(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Install free, official procurement presets once per workspace."""
    from app.services.lead_radar import free_default_sources

    created: list[str] = []
    for preset in free_default_sources():
        exists = await db.execute(select(LeadSource.id).where(
            LeadSource.owner_id == user.id, LeadSource.name == preset["name"],
        ))
        if exists.scalar_one_or_none():
            continue
        item = LeadSource(owner_id=user.id, name=preset["name"], provider=preset["provider"],
                          enabled=preset["enabled"], config_json=json.dumps(preset["config"], ensure_ascii=False))
        db.add(item); await db.flush(); created.append(item.id)
    if created:
        await audit(db, user.id, "lead_source.install_defaults", "lead_source", ",".join(created), {"count": len(created)})
    await db.commit()
    return {"created": len(created), "source_ids": created}


@router.patch("/lead-sources/{source_id}")
async def update_lead_source(source_id: str, body: LeadSourceInput, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    row = await db.execute(select(LeadSource).where(LeadSource.id == source_id, LeadSource.owner_id == user.id)); item = row.scalar_one_or_none()
    if not item: raise HTTPException(404, "数据源不存在")
    item.name = body.name; item.provider = body.provider; item.enabled = body.enabled; item.config_json = json.dumps(body.config, ensure_ascii=False)
    await audit(db, user.id, "lead_source.update", "lead_source", item.id); await db.commit(); return {"id": item.id}


@router.delete("/lead-sources/{source_id}", status_code=204)
async def delete_lead_source(source_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    row = await db.execute(select(LeadSource).where(LeadSource.id == source_id, LeadSource.owner_id == user.id)); item = row.scalar_one_or_none()
    if not item: raise HTTPException(404, "数据源不存在")
    await db.delete(item); await audit(db, user.id, "lead_source.delete", "lead_source", source_id); await db.commit()


@router.post("/lead-sources/{source_id}/run")
async def run_lead_source(source_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    row = await db.execute(select(LeadSource).where(LeadSource.id == source_id, LeadSource.owner_id == user.id)); source = row.scalar_one_or_none()
    if not source: raise HTTPException(404, "数据源不存在")
    from app.services.lead_radar import run_source
    try:
        result = await run_source(db, source)
        await audit(db, user.id, "lead_source.run", "lead_source", source.id, result); await db.commit()
        return result
    except Exception as exc:
        raise HTTPException(502, f"采集失败: {exc}")


@router.get("/leads")
async def list_leads(status: str | None = None, min_score: int = 0, limit: int = 100, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    stmt = select(OverseasLead).where(OverseasLead.owner_id == user.id, OverseasLead.score >= min_score)
    if status: stmt = stmt.where(OverseasLead.status == status)
    rows = await db.execute(stmt.order_by(OverseasLead.score.desc(), OverseasLead.created_at.desc()).limit(min(max(limit, 1), 200)))
    return [lead_out(item) for item in rows.scalars().all()]


@router.patch("/leads/{lead_id}")
async def update_lead_status(lead_id: str, body: LeadStatusInput, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    row = await db.execute(select(OverseasLead).where(OverseasLead.id == lead_id, OverseasLead.owner_id == user.id)); lead = row.scalar_one_or_none()
    if not lead: raise HTTPException(404, "商机不存在")
    lead.status = body.status; await audit(db, user.id, "lead.status", "overseas_lead", lead.id, {"status": body.status}); await db.commit(); return lead_out(lead)


@router.post("/leads/{lead_id}/enrich")
async def enrich_lead(lead_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    row = await db.execute(select(OverseasLead).where(OverseasLead.id == lead_id, OverseasLead.owner_id == user.id)); lead = row.scalar_one_or_none()
    if not lead: raise HTTPException(404, "商机不存在")
    from app.services.lead_enrichment import enrich_to_chinese
    result = await enrich_to_chinese(lead.title, lead.raw_text, lead.buyer, lead.country)
    lead.title_zh = result["title_zh"]; lead.summary_zh = result["summary_zh"]; lead.translation_status = result["translation_status"]
    await audit(db, user.id, "lead.enrich", "overseas_lead", lead.id, {"translation_status": lead.translation_status}); await db.commit()
    return lead_out(lead)


@router.post("/leads/{lead_id}/review")
async def review_lead(lead_id: str, body: LeadReviewInput, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    row = await db.execute(select(OverseasLead).where(OverseasLead.id == lead_id, OverseasLead.owner_id == user.id)); lead = row.scalar_one_or_none()
    if not lead: raise HTTPException(404, "商机不存在")
    lead.status = body.decision; lead.review_status = "APPROVED" if body.decision == "INTERESTED" else "REJECTED"; lead.review_note = body.note; lead.reviewed_at = datetime.utcnow()
    await audit(db, user.id, "lead.review", "overseas_lead", lead.id, {"decision": body.decision, "note": body.note}); await db.commit()
    return lead_out(lead)


@router.post("/leads/{lead_id}/convert-inquiry", status_code=201)
async def convert_lead_to_inquiry(lead_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    row = await db.execute(select(OverseasLead).where(OverseasLead.id == lead_id, OverseasLead.owner_id == user.id)); lead = row.scalar_one_or_none()
    if not lead: raise HTTPException(404, "商机不存在")
    if lead.status != "INTERESTED":
        raise HTTPException(400, "请先完成人工审核，再转入询盘")
    if lead.inquiry_id: return {"inquiry_id": lead.inquiry_id, "existing": True}
    extracted = json.loads(lead.extracted_json or "{}")
    inquiry = Inquiry(owner_id=user.id, source=lead.source, raw_text=lead.raw_text, product_type=extracted.get("spec", {}).get("product_type", ""), specs_json=json.dumps(extracted, ensure_ascii=False), status="NEW", confidence=max(extracted.get("confidence", {}).values(), default=0))
    db.add(inquiry); await db.flush(); lead.inquiry_id = inquiry.id; lead.status = "CONVERTED"
    await audit(db, user.id, "lead.convert", "overseas_lead", lead.id, {"inquiry_id": inquiry.id}); await db.commit()
    return {"inquiry_id": inquiry.id, "existing": False}


@router.get("/notifications")
async def list_notifications(unread_only: bool = False, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    stmt = select(Notification).where(Notification.owner_id == user.id)
    if unread_only: stmt = stmt.where(Notification.read_at.is_(None))
    rows = await db.execute(stmt.order_by(Notification.created_at.desc()).limit(100))
    return [{"id": x.id, "category": x.category, "title": x.title, "body": x.body, "entity_type": x.entity_type, "entity_id": x.entity_id, "priority": x.priority, "read_at": x.read_at, "created_at": x.created_at, "channels": json.loads(x.channel_status_json or "{}")} for x in rows.scalars().all()]


@router.post("/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    row = await db.execute(select(Notification).where(Notification.id == notification_id, Notification.owner_id == user.id)); item = row.scalar_one_or_none()
    if not item: raise HTTPException(404, "通知不存在")
    item.read_at = datetime.utcnow(); await db.commit(); return {"id": item.id, "read_at": item.read_at}


@router.get("/prices")
async def list_prices(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = await db.execute(select(PriceRule).where(PriceRule.owner_id == user.id).order_by(PriceRule.category, PriceRule.item_key, PriceRule.version.desc()))
    return [{"id":x.id,"category":x.category,"item_key":x.item_key,"unit":x.unit,"unit_price":x.unit_price,"currency":x.currency,"version":x.version,"is_active":bool(x.is_active),"extra":json.loads(x.extra_json or "{}")} for x in rows.scalars().all()]


@router.post("/prices", status_code=201)
async def create_price(body: PriceRuleInput, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    previous = await db.execute(select(PriceRule).where(PriceRule.owner_id==user.id, PriceRule.category==body.category, PriceRule.item_key==body.item_key).order_by(PriceRule.version.desc()))
    latest = previous.scalars().first()
    if latest: latest.is_active = 0
    item = PriceRule(owner_id=user.id, category=body.category, item_key=body.item_key, unit=body.unit, unit_price=body.unit_price, currency=body.currency, version=(latest.version+1 if latest else 1), is_active=body.is_active, extra_json=json.dumps(body.extra, ensure_ascii=False))
    db.add(item); await db.flush(); await audit(db,user.id,"price.create","price",item.id,{"category":body.category,"item_key":body.item_key,"unit_price":body.unit_price}); await db.commit()
    return {"id":item.id,"version":item.version}


@router.delete("/prices/{rule_id}", status_code=204)
async def deactivate_price(rule_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    row = await db.execute(select(PriceRule).where(PriceRule.id==rule_id, PriceRule.owner_id==user.id)); item=row.scalar_one_or_none()
    if not item: raise HTTPException(404,"价格规则不存在")
    item.is_active=0; await audit(db,user.id,"price.deactivate","price",item.id); await db.commit()


@router.get("/followups/{customer_id}")
async def list_followups(customer_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows=await db.execute(select(CustomerFollowUp).where(CustomerFollowUp.owner_id==user.id,CustomerFollowUp.customer_id==customer_id).order_by(CustomerFollowUp.created_at.desc()))
    return [{"id":x.id,"channel":x.channel,"content":x.content,"next_at":x.next_at,"status":x.status,"created_at":x.created_at} for x in rows.scalars().all()]


@router.post("/followups", status_code=201)
async def create_followup(body: FollowUpInput, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    item=CustomerFollowUp(owner_id=user.id,**body.model_dump());db.add(item);await db.flush();await audit(db,user.id,"followup.create","customer",body.customer_id,{"followup_id":item.id});await db.commit();return {"id":item.id}


@router.post("/followups/{followup_id}/complete")
async def complete_followup(followup_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    row=await db.execute(select(CustomerFollowUp).where(CustomerFollowUp.id==followup_id,CustomerFollowUp.owner_id==user.id));item=row.scalar_one_or_none()
    if not item: raise HTTPException(404,"跟进记录不存在")
    item.status="DONE";await audit(db,user.id,"followup.complete","followup",item.id);await db.commit();return {"status":"DONE"}


@router.get("/orders/{order_id}/events")
async def list_order_events(order_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows=await db.execute(select(OrderEvent).where(OrderEvent.owner_id==user.id,OrderEvent.order_id==order_id).order_by(OrderEvent.created_at))
    return [{"id":x.id,"event_type":x.event_type,"from_status":x.from_status,"to_status":x.to_status,"data":json.loads(x.data_json or "{}"),"created_at":x.created_at} for x in rows.scalars().all()]


@router.post("/orders/{order_id}/events", status_code=201)
async def create_order_event(order_id: str, body: OrderEventInput, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    row=await db.execute(select(Order).where(Order.id==order_id,Order.owner_id==user.id));order=row.scalar_one_or_none()
    if not order: raise HTTPException(404,"订单不存在")
    previous=order.status
    if body.to_status: order.status=body.to_status
    if body.event_type=="quality_passed": order.quality_status="PASSED"
    if body.event_type=="quality_failed": order.quality_status="FAILED"
    if body.event_type=="logistics_updated": order.logistics_json=json.dumps(body.data,ensure_ascii=False)
    if body.event_type=="payment_updated": order.payment_status=str(body.data.get("payment_status",order.payment_status))
    if body.event_type=="invoice_updated": order.invoice_status=str(body.data.get("invoice_status",order.invoice_status))
    if body.event_type=="contract_signed": order.contract_no=str(body.data.get("contract_no",order.contract_no))
    item=OrderEvent(owner_id=user.id,order_id=order_id,event_type=body.event_type,from_status=previous,to_status=body.to_status,data_json=json.dumps(body.data,ensure_ascii=False));db.add(item);await db.flush();await audit(db,user.id,"order.event","order",order_id,{"event":body.event_type,"to_status":body.to_status});await db.commit();return {"id":item.id,"status":order.status,"quality_status":order.quality_status}


@router.get("/audit")
async def list_audit(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows=await db.execute(select(AuditLog).where(AuditLog.owner_id==user.id).order_by(AuditLog.created_at.desc()).limit(200))
    return [{"id":x.id,"action":x.action,"entity_type":x.entity_type,"entity_id":x.entity_id,"data":json.loads(x.data_json or "{}"),"created_at":x.created_at} for x in rows.scalars().all()]


@router.post("/knowledge/{document_id}/index")
async def index_knowledge(document_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    row=await db.execute(select(KnowledgeDocument).where(KnowledgeDocument.id==document_id,KnowledgeDocument.owner_id==user.id));doc=row.scalar_one_or_none()
    if not doc: raise HTTPException(404,"知识资料不存在")
    from app.services.knowledge_indexer import index_document
    try:
        count=index_document(user.id,doc.id,doc.name,doc.category,doc.content)
        doc.chunk_count=count;doc.status="ACTIVE";await audit(db,user.id,"knowledge.index","knowledge",doc.id,{"chunks":count});await db.commit();return {"status":"ACTIVE","chunk_count":count}
    except Exception as exc:
        doc.status="INDEX_FAILED";await db.commit();raise HTTPException(503,f"知识索引失败: {exc}")


@router.get("/knowledge/search")
async def search_knowledge_api(q: str, limit: int = 5, user: User = Depends(get_current_user)):
    from app.services.knowledge_indexer import search_knowledge
    try: return search_knowledge(user.id,q,min(max(limit,1),20))
    except Exception as exc: raise HTTPException(503,f"知识检索失败: {exc}")


@router.post("/channels/inbound", status_code=202)
async def receive_inbound(body: InboundInput, x_webhook_token: str = Header(default=""), db: AsyncSession = Depends(get_db)):
    if not settings.INBOUND_WEBHOOK_TOKEN or x_webhook_token != settings.INBOUND_WEBHOOK_TOKEN:
        raise HTTPException(401,"Webhook token 无效")
    message=InboundMessage(owner_id=body.owner_id,source=body.source,external_id=body.external_id,sender=body.sender,raw_text=body.text,attachments_json=json.dumps(body.attachments,ensure_ascii=False));db.add(message)
    inquiry=Inquiry(owner_id=body.owner_id,source=body.source,raw_text=body.text,product_type="",specs_json="{}",status="NEW",confidence=0);db.add(inquiry);await db.flush();message.inquiry_id=inquiry.id;message.status="CONVERTED";await audit(db,body.owner_id,"inbound.convert","inquiry",inquiry.id,{"source":body.source,"message_id":message.id});await db.commit()
    return {"message_id":message.id,"inquiry_id":inquiry.id,"status":"CONVERTED"}


@router.get("/orders/{order_id}/attachments")
async def list_order_attachments(order_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows=await db.execute(select(OrderAttachment).where(OrderAttachment.owner_id==user.id,OrderAttachment.order_id==order_id).order_by(OrderAttachment.created_at.desc()))
    return [{"id":x.id,"kind":x.kind,"file_name":x.file_name,"content_type":x.content_type,"created_at":x.created_at} for x in rows.scalars().all()]


@router.post("/orders/{order_id}/attachments", status_code=201)
async def upload_order_attachment(order_id: str, kind: str = Form(...), file: UploadFile = File(...), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    row=await db.execute(select(Order).where(Order.id==order_id,Order.owner_id==user.id));order=row.scalar_one_or_none()
    if not order: raise HTTPException(404,"订单不存在")
    data=await file.read()
    if len(data)>20*1024*1024: raise HTTPException(413,"附件不得超过20MB")
    from app.services.minio_service import MinioService
    attachment=OrderAttachment(owner_id=user.id,order_id=order_id,kind=kind,file_name=file.filename or "attachment",object_path="",content_type=file.content_type or "application/octet-stream")
    db.add(attachment);await db.flush();attachment.object_path=f"orders/{order_id}/{attachment.id}/{attachment.file_name}";MinioService().upload(attachment.object_path,data,attachment.file_name);await audit(db,user.id,"order.attachment","order",order_id,{"attachment_id":attachment.id,"kind":kind});await db.commit();return {"id":attachment.id,"kind":kind,"file_name":attachment.file_name}


@router.get("/orders/{order_id}/attachments/{attachment_id}/download")
async def download_order_attachment(order_id: str, attachment_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    row=await db.execute(select(OrderAttachment).where(OrderAttachment.id==attachment_id,OrderAttachment.order_id==order_id,OrderAttachment.owner_id==user.id));item=row.scalar_one_or_none()
    if not item: raise HTTPException(404,"附件不存在")
    from app.services.minio_service import MinioService
    data=MinioService().download(item.object_path)
    return StreamingResponse(io.BytesIO(data),media_type=item.content_type,headers={"Content-Disposition":f'attachment; filename="{item.file_name}"'})
