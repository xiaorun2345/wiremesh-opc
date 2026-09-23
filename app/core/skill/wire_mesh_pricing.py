from __future__ import annotations

"""Deterministic wire-mesh pricing rules.

The LLM may extract or normalize specification fields, but it never supplies
prices. Every monetary value in a quote is calculated here from explicit
catalogs and formulas.
"""
from dataclasses import asdict, dataclass


MATERIAL_PRICE_PER_KG = {
    "low_carbon_steel": 4.60,
    "galvanized_steel": 5.40,
    "stainless_304": 15.80,
    "stainless_316": 23.50,
}

PROCESS_PRICE_PER_M2 = {
    "welded_mesh": 4.20,
    "fence_mesh": 5.80,
    "hexagonal_mesh": 3.60,
    "screen_mesh": 7.50,
    "expanded_mesh": 6.80,
}

SURFACE_PRICE_PER_KG = {
    "none": 0.0,
    "electro_galvanized": 0.65,
    "hot_dip_galvanized": 1.15,
    "pvc_coated": 1.45,
    "powder_coated": 1.75,
}

PACKAGING_PRICE_PER_M2 = {
    "bulk": 0.25,
    "pallet": 0.75,
    "export": 1.20,
}

PRODUCT_WEIGHT_FACTOR = {
    "welded_mesh": 1.00,
    "fence_mesh": 1.08,
    "hexagonal_mesh": 0.82,
    "screen_mesh": 1.12,
    "expanded_mesh": 1.18,
}


@dataclass(frozen=True)
class WireMeshSpec:
    product_type: str
    material: str
    wire_diameter_mm: float
    mesh_size_mm: float
    width_m: float
    length_m: float
    quantity: int
    surface_treatment: str = "none"
    packaging: str = "export"
    margin_rate: float = 0.15
    freight: float = 0.0
    currency: str = "CNY"

    @property
    def total_area_m2(self) -> float:
        return self.width_m * self.length_m * self.quantity


def validate_spec(spec: WireMeshSpec) -> list[str]:
    errors = []
    if spec.product_type not in PROCESS_PRICE_PER_M2:
        errors.append("unsupported product_type")
    if spec.material not in MATERIAL_PRICE_PER_KG:
        errors.append("unsupported material")
    if spec.surface_treatment not in SURFACE_PRICE_PER_KG:
        errors.append("unsupported surface_treatment")
    if spec.packaging not in PACKAGING_PRICE_PER_M2:
        errors.append("unsupported packaging")
    if spec.wire_diameter_mm <= 0 or spec.mesh_size_mm <= 0:
        errors.append("wire diameter and mesh size must be positive")
    if spec.width_m <= 0 or spec.length_m <= 0 or spec.quantity <= 0:
        errors.append("dimensions and quantity must be positive")
    if not 0.05 <= spec.margin_rate <= 0.50:
        errors.append("margin_rate must be between 0.05 and 0.50")
    return errors


def calculate_quote(spec: WireMeshSpec, catalog: dict | None = None) -> dict:
    errors = validate_spec(spec)
    if errors:
        raise ValueError("; ".join(errors))

    # Steel wire theoretical weight: kg/m = d² / 162.2. A square mesh has
    # approximately 2 / aperture_m metres of wire per square metre.
    wire_kg_per_m = spec.wire_diameter_mm ** 2 / 162.2
    wire_length_per_m2 = 2.0 / (spec.mesh_size_mm / 1000.0)
    factor = PRODUCT_WEIGHT_FACTOR[spec.product_type]
    weight_per_m2 = wire_kg_per_m * wire_length_per_m2 * factor
    total_area = spec.total_area_m2
    total_weight = weight_per_m2 * total_area

    catalog = catalog or {}
    material_prices = {**MATERIAL_PRICE_PER_KG, **catalog.get("material", {})}
    process_prices = {**PROCESS_PRICE_PER_M2, **catalog.get("process", {})}
    surface_prices = {**SURFACE_PRICE_PER_KG, **catalog.get("surface", {})}
    packaging_prices = {**PACKAGING_PRICE_PER_M2, **catalog.get("packaging", {})}
    material_cost = total_weight * material_prices[spec.material]
    processing_cost = total_area * process_prices[spec.product_type]
    surface_cost = total_weight * surface_prices[spec.surface_treatment]
    packaging_cost = total_area * packaging_prices[spec.packaging]
    cost_total = material_cost + processing_cost + surface_cost + packaging_cost + spec.freight
    quote_total = cost_total / (1.0 - spec.margin_rate)

    def money(value: float) -> float:
        return round(value, 2)

    return {
        "spec": asdict(spec),
        "area_m2": round(total_area, 3),
        "weight_per_m2_kg": round(weight_per_m2, 4),
        "total_weight_kg": round(total_weight, 2),
        "costs": {
            "material": money(material_cost),
            "processing": money(processing_cost),
            "surface": money(surface_cost),
            "packaging": money(packaging_cost),
            "freight": money(spec.freight),
            "total": money(cost_total),
        },
        "margin_rate": spec.margin_rate,
        "quote_total": money(quote_total),
        "unit_price_m2": money(quote_total / total_area),
        "currency": spec.currency,
        "formula_version": "wire-mesh-v1",
    }
