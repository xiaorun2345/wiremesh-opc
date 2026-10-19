"""Public procurement lead collectors and normalization pipeline.

Collectors only query official APIs or explicit public RSS/JSON feeds configured
by the workspace owner. They deliberately do not automate login-only B2B sites.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.wire_mesh_spec import extract_wire_mesh_spec
from app.models.opc import LeadSource, Notification, OverseasLead


DEFAULT_KEYWORDS = [
    "wire mesh", "welded mesh", "welded wire", "metal netting", "wire cloth",
    "wire-mesh fencing", "security fencing", "anti-climb fence", "chain link",
    "gabion", "mining screen", "quarry screen", "stainless steel mesh",
    "expanded metal", "perforated metal", "fencing wire", "safety fencing",
    "焊接网", "护栏网", "筛网", "六角网", "石笼网", "钢板网",
]

DEFAULT_CPV_CODES = ["44313100", "44313000", "44313200", "44312000", "34928200", "34928310"]


def free_default_sources() -> list[dict[str, Any]]:
    """Return no-subscription source presets for a new workspace."""
    return [
        {"name": "TED 欧盟采购（丝网）", "provider": "ted", "enabled": True, "config": {
            "cpv_codes": DEFAULT_CPV_CODES,
            "keywords": ["wire mesh", "security fencing", "mining screen"],
            "countries": [], "limit": 50,
        }},
        {"name": "英国 Contracts Finder（丝网）", "provider": "contracts_finder", "enabled": True, "config": {
            "url": "https://www.contractsfinder.service.gov.uk/Published/Notices/OCDS/Search",
            "keywords": ["wire mesh", "welded mesh", "security fencing", "metal netting", "wire cloth"],
            "limit": 100,
        }},
        {"name": "SAM.gov 美国政府采购（待填免费 Key）", "provider": "sam", "enabled": False, "config": {
            "api_key_env": "SAM_GOV_API_KEY", "keyword": "wire mesh",
            "lookback_days": 2, "limit": 100, "countries": ["US"],
        }},
    ]


@dataclass
class LeadCandidate:
    source: str
    external_id: str
    title: str
    source_url: str = ""
    buyer: str = ""
    country: str = ""
    language: str = "en"
    published_at: datetime | None = None
    deadline_at: datetime | None = None
    budget: float | None = None
    currency: str = ""
    text: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


def _value(item: dict, *names: str, default: Any = "") -> Any:
    for name in names:
        value = item.get(name)
        if value not in (None, ""):
            return value
    return default


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    text = str(value).strip()
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        pass
    try:
        return parsedate_to_datetime(text).replace(tzinfo=None)
    except (TypeError, ValueError):
        return None


def _join_text(item: dict) -> str:
    values: list[str] = []
    for key, value in item.items():
        if isinstance(value, str):
            values.append(value)
        elif isinstance(value, list):
            values.extend(str(part) for part in value if isinstance(part, (str, int, float)))
    return "\n".join(values)


def _keywords(config: dict) -> list[str]:
    return list(dict.fromkeys(DEFAULT_KEYWORDS + list(config.get("keywords", []))))


def score_candidate(candidate: LeadCandidate, config: dict) -> tuple[int, list[str], dict]:
    text = f"{candidate.title}\n{candidate.text}".lower().replace("-", " ")
    keywords = _keywords(config)
    matched = [keyword for keyword in keywords if keyword.lower() in text]
    score = min(30, len(matched) * 6)
    reasons = [f"匹配关键词：{', '.join(matched[:5])}"] if matched else []
    spec, confidence = extract_wire_mesh_spec(candidate.text)
    populated = sum(spec.get(key) not in (None, "") for key in (
        "product_type", "material", "wire_diameter_mm", "mesh_size_mm", "width_m", "length_m", "quantity",
    ))
    if populated:
        score += min(20, populated * 3)
        reasons.append(f"规格完整度：{populated}/7")
    if spec.get("product_type"):
        score += 8
        reasons.append("产品分类已识别")
    if spec.get("material"):
        score += 5
        reasons.append("材料已识别")
    if candidate.budget:
        score += 10
        reasons.append("公告含预算")
    if candidate.deadline_at:
        remaining = (candidate.deadline_at - datetime.utcnow()).days
        if remaining >= 7:
            score += 10
            reasons.append(f"距截止日 {remaining} 天")
        elif remaining < 0:
            score -= 100
            reasons.append("已过截止日期")
    if candidate.source in {"ted", "sam", "contracts_finder", "ungm"}:
        score += 10
        reasons.append("官方采购来源")
    target_countries = {str(x).lower() for x in config.get("countries", [])}
    if target_countries and candidate.country.lower() in target_countries:
        score += 10
        reasons.append("目标国家匹配")
    if candidate.buyer:
        score += 5
    return max(0, min(100, score)), reasons, {"spec": spec, "confidence": confidence, "matched_keywords": matched}


async def collect_ted(config: dict) -> list[LeadCandidate]:
    """Collect published EU notices via the official TED Search API."""
    cpv = config.get("cpv_codes", DEFAULT_CPV_CODES)
    expert_query = config.get("expert_query") or " OR ".join(f"classification-cpv = {code}" for code in cpv)
    payload = {
        "query": expert_query,
        "fields": ["publication-number", "notice-title", "buyer-name", "country", "publication-date", "deadline", "notice-url"],
        "limit": min(int(config.get("limit", 50)), 250),
        "page": 1,
        "scope": "ACTIVE",
        "checkQuerySyntax": False,
        "paginationMode": "PAGE_NUMBER",
    }
    url = config.get("url", "https://api.ted.europa.eu/v3/notices/search")
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
    rows = data.get("notices") or data.get("results") or data.get("items") or []
    candidates = []
    for row in rows:
        external_id = str(_value(row, "publication-number", "publicationNumber", "noticeId", "id"))
        title = str(_value(row, "notice-title", "title", "noticeTitle"))
        if not external_id or not title:
            continue
        candidates.append(LeadCandidate(
            source="ted", external_id=external_id, title=title,
            source_url=str(_value(row, "notice-url", "noticeUrl", "url")),
            buyer=str(_value(row, "buyer-name", "buyerName")),
            country=str(_value(row, "country", "countryCode")),
            published_at=_parse_datetime(_value(row, "publication-date", "publicationDate")),
            deadline_at=_parse_datetime(_value(row, "deadline", "deadlineDate")),
            text=_join_text(row), raw=row,
        ))
    return candidates


async def collect_sam(config: dict) -> list[LeadCandidate]:
    """Collect US public opportunities. Requires a SAM.gov API key."""
    api_key = os.getenv(config.get("api_key_env", "SAM_GOV_API_KEY"), "")
    if not api_key:
        raise ValueError("SAM.gov API Key 未配置")
    today = datetime.utcnow().date()
    start = today - timedelta(days=int(config.get("lookback_days", 2)))
    params = {
        "api_key": api_key,
        "postedFrom": config.get("posted_from", start.strftime("%m/%d/%Y")),
        "postedTo": config.get("posted_to", today.strftime("%m/%d/%Y")),
        "limit": min(int(config.get("limit", 100)), 1000),
    }
    if config.get("keyword"):
        params["title"] = config["keyword"]
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(config.get("url", "https://api.sam.gov/opportunities/v2/search"), params=params)
        response.raise_for_status()
        data = response.json()
    rows = data.get("opportunitiesData", [])
    candidates = []
    for row in rows:
        external_id = str(_value(row, "noticeId", "solicitationNumber", "id"))
        title = str(_value(row, "title"))
        if not external_id or not title:
            continue
        place = row.get("placeOfPerformance") or {}
        candidates.append(LeadCandidate(
            source="sam", external_id=external_id, title=title,
            source_url=str(_value(row, "uiLink", "link", "url")),
            buyer=str(_value(row, "fullParentPathName", "department", "office")),
            country=str(_value(place, "country", default="US")),
            published_at=_parse_datetime(_value(row, "postedDate")),
            deadline_at=_parse_datetime(_value(row, "responseDeadLine", "responseDeadline")),
            text=_join_text(row), raw=row,
        ))
    return candidates


async def collect_contracts_finder(config: dict) -> list[LeadCandidate]:
    """Collect UK OCDS search results from a configured official endpoint."""
    url = config.get("url")
    if not url:
        raise ValueError("Contracts Finder 需要在数据源配置中提供 OCDS Search URL")
    params = {"publishedFrom": config.get("published_from", (datetime.utcnow() - timedelta(days=2)).isoformat()), "publishedTo": config.get("published_to", datetime.utcnow().isoformat()), "limit": min(int(config.get("limit", 100)), 250)}
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        data = response.json()
    rows = data.get("releases") or data.get("notices") or data.get("items") or []
    candidates = []
    for row in rows:
        tender = row.get("tender", row)
        buyer = row.get("buyer", {})
        external_id = str(_value(row, "ocid", "id", "noticeId"))
        title = str(_value(tender, "title", default=_value(row, "title")))
        if not external_id or not title:
            continue
        candidates.append(LeadCandidate(
            source="contracts_finder", external_id=external_id, title=title,
            source_url=str(_value(row, "uri", "url")), buyer=str(_value(buyer, "name")), country="UK",
            published_at=_parse_datetime(_value(row, "date", "publishedDate")),
            deadline_at=_parse_datetime(_value(tender, "tenderPeriod", default={}).get("endDate") if isinstance(tender.get("tenderPeriod"), dict) else None),
            text=_join_text(tender), raw=row,
        ))
    return candidates


async def collect_rss(config: dict) -> list[LeadCandidate]:
    url = config.get("feed_url")
    if not url:
        raise ValueError("RSS 数据源需要 feed_url")
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        response = await client.get(url, headers={"User-Agent": "WireMeshOPC/1.0 (+public-feed-monitor)"})
        response.raise_for_status()
    root = ET.fromstring(response.content)
    items = root.findall(".//item") + root.findall(".//{http://www.w3.org/2005/Atom}entry")
    candidates = []
    for item in items:
        def text(tag: str) -> str:
            node = item.find(tag) or item.find(f"{{http://www.w3.org/2005/Atom}}{tag}")
            return (node.text or "").strip() if node is not None else ""
        title = text("title")
        link = text("link")
        if not link:
            link_node = item.find("{http://www.w3.org/2005/Atom}link")
            link = link_node.attrib.get("href", "") if link_node is not None else ""
        description = text("description") or text("summary") or text("content")
        external_id = text("guid") or text("id") or link or title
        if title and external_id:
            candidates.append(LeadCandidate(source="rss", external_id=external_id, title=title, source_url=link, text=description, published_at=_parse_datetime(text("pubDate") or text("updated")), raw={"title": title, "link": link, "description": description}))
    return candidates


COLLECTORS = {"ted": collect_ted, "sam": collect_sam, "contracts_finder": collect_contracts_finder, "rss": collect_rss}


async def persist_candidates(db: AsyncSession, source: LeadSource, candidates: list[LeadCandidate]) -> dict[str, int]:
    created = 0
    duplicates = 0
    high_priority = 0
    config = json.loads(source.config_json or "{}")
    from app.services.model_provider import get_active_model
    model_config = await get_active_model(db, source.owner_id, "text")
    for candidate in candidates:
        dedupe_key = hashlib.sha256(f"{source.owner_id}:{candidate.source}:{candidate.external_id}".encode()).hexdigest()
        exists = await db.execute(select(OverseasLead.id).where(OverseasLead.dedupe_key == dedupe_key))
        if exists.scalar_one_or_none():
            duplicates += 1
            continue
        score, reasons, extracted = score_candidate(candidate, config)
        status = "HIGH_PRIORITY" if score >= 80 else "NEW" if score >= 40 else "ARCHIVED"
        from app.services.lead_enrichment import enrich_to_chinese
        enrichment = await enrich_to_chinese(candidate.title, candidate.text, candidate.buyer, candidate.country, model_config)
        lead = OverseasLead(
            owner_id=source.owner_id, source_id=source.id, source=candidate.source, external_id=candidate.external_id,
            dedupe_key=dedupe_key, source_url=candidate.source_url, title=candidate.title, buyer=candidate.buyer,
            country=candidate.country, language=candidate.language, published_at=candidate.published_at,
            deadline_at=candidate.deadline_at, budget=candidate.budget, currency=candidate.currency,
            raw_text=candidate.text, raw_json=json.dumps(candidate.raw, ensure_ascii=False),
            extracted_json=json.dumps(extracted, ensure_ascii=False), score=score,
            score_reasons_json=json.dumps(reasons, ensure_ascii=False), status=status,
            title_zh=enrichment["title_zh"], summary_zh=enrichment["summary_zh"],
            translation_status=enrichment["translation_status"], review_status="NEEDS_REVIEW",
        )
        db.add(lead)
        await db.flush()
        created += 1
        if score >= 80:
            high_priority += 1
            notification = Notification(
                owner_id=source.owner_id, category="OVERSEAS_LEAD", priority="HIGH",
                title=f"高优先级海外商机：{candidate.title[:100]}",
                body=f"来源：{candidate.source}；国家：{candidate.country or '未识别'}；评分：{score}；" + "；".join(reasons[:2]),
                entity_type="overseas_lead", entity_id=lead.id,
            )
            db.add(notification)
            await db.flush()
            from app.services.notifications import notify_email, notify_wecom
            base = config.get("platform_url", "")
            url = f"{base.rstrip('/')}/leads/{lead.id}" if base else ""
            channel_status = {"email": False, "wecom": False}
            try:
                channel_status["wecom"] = await notify_wecom(notification.title, notification.body, url)
                channel_status["email"] = await notify_email(notification.title, notification.body + (f"\n{url}" if url else ""))
            except Exception as exc:
                channel_status["error"] = str(exc)[:500]
            notification.channel_status_json = json.dumps(channel_status, ensure_ascii=False)
    return {"created": created, "duplicates": duplicates, "high_priority": high_priority}


async def run_source(db: AsyncSession, source: LeadSource) -> dict[str, int]:
    config = json.loads(source.config_json or "{}")
    collector = COLLECTORS.get(source.provider)
    if not collector:
        raise ValueError(f"不支持的数据源：{source.provider}")
    try:
        candidates = await collector(config)
        result = await persist_candidates(db, source, candidates)
        source.last_run_at = datetime.utcnow()
        source.last_status = "SUCCESS"
        source.last_error = ""
        await db.commit()
        return result
    except Exception as exc:
        source.last_run_at = datetime.utcnow()
        source.last_status = "FAILED"
        source.last_error = str(exc)[:2000]
        await db.commit()
        raise
