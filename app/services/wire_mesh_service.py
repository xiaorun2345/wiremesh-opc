from __future__ import annotations

"""Wire-mesh quote and factory-matching application service."""
from app.core.skill.wire_mesh_pricing import WireMeshSpec, calculate_quote


FACTORIES = [
    {
        "id": "factory-hengtai",
        "name": "安平恒泰丝网厂",
        "products": {"welded_mesh", "fence_mesh"},
        "surfaces": {"hot_dip_galvanized", "pvc_coated", "powder_coated"},
        "lead_days": 13,
        "on_time_rate": 0.96,
        "quality_score": 94,
    },
    {
        "id": "factory-xinyuan",
        "name": "河北鑫源金属网业",
        "products": {"screen_mesh", "welded_mesh", "expanded_mesh"},
        "surfaces": {"none", "electro_galvanized", "hot_dip_galvanized"},
        "lead_days": 16,
        "on_time_rate": 0.93,
        "quality_score": 91,
    },
    {
        "id": "factory-huachen",
        "name": "安平华辰护栏厂",
        "products": {"fence_mesh", "hexagonal_mesh"},
        "surfaces": {"hot_dip_galvanized", "pvc_coated", "powder_coated"},
        "lead_days": 11,
        "on_time_rate": 0.91,
        "quality_score": 88,
    },
]


def match_factories(spec: WireMeshSpec, factories: list[dict] | None = None) -> list[dict]:
    matches = []
    for factory in factories or FACTORIES:
        product_match = spec.product_type in factory["products"]
        surface_match = spec.surface_treatment in factory["surfaces"]
        score = (
            (45 if product_match else 0)
            + (20 if surface_match else 0)
            + factory["quality_score"] * 0.2
            + factory["on_time_rate"] * 15
        )
        if not product_match:
            continue
        matches.append({
            "id": factory["id"],
            "name": factory["name"],
            "score": round(score, 1),
            "lead_days": factory["lead_days"],
            "on_time_rate": factory["on_time_rate"],
            "quality_score": factory["quality_score"],
            "surface_match": surface_match,
        })
    return sorted(matches, key=lambda item: (-item["score"], item["lead_days"]))


def build_quote(spec: WireMeshSpec, catalog: dict | None = None, factories: list[dict] | None = None) -> dict:
    quote = calculate_quote(spec, catalog=catalog)
    quote["factory_matches"] = match_factories(spec, factories=factories)
    quote["warnings"] = []
    if not quote["factory_matches"]:
        quote["warnings"].append("没有找到完整匹配的合作工厂")
    if quote["margin_rate"] < 0.12:
        quote["warnings"].append("毛利率低于 12% 内部控制线")
    return quote


async def build_quote_from_db(db, owner_id: str, spec: WireMeshSpec) -> dict:
    """Build a quote using active database price rules and factory profiles."""
    import json
    from sqlalchemy import select
    from app.models.opc import Factory, PriceRule

    price_rows = await db.execute(select(PriceRule).where(PriceRule.owner_id == owner_id, PriceRule.is_active == 1))
    catalog: dict[str, dict[str, float]] = {}
    for row in price_rows.scalars().all():
        catalog.setdefault(row.category, {})[row.item_key] = row.unit_price

    factory_rows = await db.execute(select(Factory).where(Factory.owner_id == owner_id, Factory.status == "ACTIVE"))
    factories = []
    for row in factory_rows.scalars().all():
        factories.append({
            "id": row.id, "name": row.name,
            "products": set(json.loads(row.products_json or "[]")),
            "surfaces": set(json.loads(row.surfaces_json or "[]")),
            "lead_days": row.lead_days, "on_time_rate": row.on_time_rate,
            "quality_score": row.quality_score,
        })
    return build_quote(spec, catalog=catalog, factories=factories or None)
