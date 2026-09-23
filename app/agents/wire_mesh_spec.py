from __future__ import annotations

"""Extract a normalized wire-mesh specification from parsed document text."""
import re

from app.core.agent.base_agent import AgentResult, AgentStatus, BaseAgent
from app.core.mcp.message import MCPMessage
from app.core.memory.redis_memory import TaskMemory


PRODUCT_ALIASES = {
    "welded_mesh": ("焊接网", "电焊网", "防护网", "welded mesh", "building mesh"),
    "fence_mesh": ("护栏网", "围栏网", "养殖围网", "fence", "farm fence"),
    "hexagonal_mesh": ("六角网", "鸡网", "hexagonal mesh", "chicken wire"),
    "screen_mesh": ("筛网", "矿筛网", "不锈钢网", "screen mesh", "woven mesh"),
    "expanded_mesh": ("钢板网", "冲孔网", "expanded mesh", "perforated mesh"),
}

MATERIAL_ALIASES = {
    "stainless_316": ("316", "sus316", "不锈钢316"),
    "stainless_304": ("304", "sus304", "不锈钢304"),
    "galvanized_steel": ("镀锌丝", "galvanized wire"),
    "low_carbon_steel": ("低碳钢", "铁丝", "low carbon steel"),
}

SURFACE_ALIASES = {
    "hot_dip_galvanized": ("热镀锌", "hot dip", "hot-dip"),
    "electro_galvanized": ("电镀锌", "electro galvanized"),
    "pvc_coated": ("浸塑", "pvc coated", "pvc coating"),
    "powder_coated": ("喷塑", "powder coated", "powder coating"),
}


def _first_alias(text: str, aliases: dict[str, tuple[str, ...]], default: str = "") -> str:
    lowered = text.lower()
    for value, words in aliases.items():
        if any(word.lower() in lowered for word in words):
            return value
    return default


def _number(text: str, patterns: tuple[str, ...]) -> float | None:
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return float(match.group(1))
    return None


def extract_wire_mesh_spec(text: str) -> tuple[dict, dict[str, float]]:
    normalized = text.replace("×", "x").replace("＊", "x")
    product_type = _first_alias(normalized, PRODUCT_ALIASES)
    material = _first_alias(normalized, MATERIAL_ALIASES)
    surface = _first_alias(normalized, SURFACE_ALIASES, "none")
    wire = _number(normalized, (
        r"(?:丝径|线径|wire\s*diameter)\s*[:：]?\s*(\d+(?:\.\d+)?)\s*mm",
        r"(?:φ|Φ)\s*(\d+(?:\.\d+)?)",
    ))
    mesh_match = re.search(
        r"(?:网孔|孔径|mesh(?:\s*size)?)\s*[:：]?\s*(\d+(?:\.\d+)?)\s*[xX]\s*(\d+(?:\.\d+)?)\s*mm",
        normalized, re.IGNORECASE,
    )
    mesh = float(mesh_match.group(1)) if mesh_match else None
    size_match = re.search(
        r"(?:尺寸|规格|size)?\s*[:：]?\s*(\d+(?:\.\d+)?)\s*[xX]\s*(\d+(?:\.\d+)?)\s*(?:m|米)\b",
        normalized, re.IGNORECASE,
    )
    width = float(size_match.group(1)) if size_match else None
    length = float(size_match.group(2)) if size_match else None
    quantity_area = _number(normalized, (
        r"(\d+(?:\.\d+)?)\s*(?:平方米|平米|m2|m²)",
    ))
    quantity = _number(normalized, (
        r"(?:数量|qty|quantity)\s*[:：]?\s*(\d+)",
        r"(\d+)\s*(?:片|卷|rolls?|pcs?)",
    ))
    if quantity is None and quantity_area and width and length:
        quantity = max(1, round(quantity_area / (width * length)))

    spec = {
        "product_type": product_type,
        "material": material,
        "wire_diameter_mm": wire,
        "mesh_size_mm": mesh,
        "width_m": width,
        "length_m": length,
        "quantity": int(quantity) if quantity else None,
        "quantity_area_m2": quantity_area,
        "surface_treatment": surface,
        "packaging": "export" if any(x in normalized.lower() for x in ("出口", "export")) else "pallet",
        "margin_rate": 0.15,
        "freight": 0.0,
        "currency": "CNY",
    }
    confidence = {
        key: (0.95 if value not in (None, "") else 0.0)
        for key, value in spec.items()
        if key not in ("margin_rate", "freight", "currency", "packaging")
    }
    return spec, confidence


class WireMeshSpecAgent(BaseAgent):
    name = "WireMeshSpecAgent"
    description = "丝网规格结构化与置信度门控"
    timeout_seconds = 60

    async def execute(self, message: MCPMessage) -> AgentResult:
        mem = TaskMemory(message.trace_id)
        text = await mem.get("extracted_text", "")
        vision_spec = await mem.get("vision_wire_mesh_spec", {})
        override = await mem.get("override_data", {})
        spec, confidence = extract_wire_mesh_spec(text)
        for key, value in vision_spec.items():
            if key in spec and value not in (None, ""):
                spec[key] = value
                confidence[key] = 0.9
        override_spec = override.get("wire_mesh_spec", override)
        for key in spec:
            if key in override_spec and override_spec[key] not in (None, ""):
                spec[key] = override_spec[key]
                confidence[key] = 1.0

        required = (
            "product_type", "material", "wire_diameter_mm", "mesh_size_mm",
            "width_m", "length_m", "quantity",
        )
        missing = [key for key in required if spec.get(key) in (None, "")]
        low_confidence = [key for key in required if confidence.get(key, 0) < 0.8]
        await mem.set("wire_mesh_spec", spec)
        await mem.set("wire_mesh_confidence", confidence)
        await mem.set("wire_mesh_missing_fields", missing)
        return AgentResult(
            agent_name=self.name,
            status=AgentStatus.SUCCESS,
            data={
                "spec": spec,
                "confidence": confidence,
                "missing_fields": missing,
                "need_human_review": bool(missing or low_confidence),
                "review_hint": "请确认以下丝网字段：" + "、".join(sorted(set(missing + low_confidence))),
            },
        )
