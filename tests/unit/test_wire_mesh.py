import pytest

from app.core.skill.wire_mesh_pricing import WireMeshSpec, calculate_quote
from app.services.wire_mesh_service import build_quote, match_factories


def sample_spec(**overrides) -> WireMeshSpec:
    data = {
        "product_type": "welded_mesh",
        "material": "low_carbon_steel",
        "wire_diameter_mm": 3.5,
        "mesh_size_mm": 50.0,
        "width_m": 2.0,
        "length_m": 3.0,
        "quantity": 100,
        "surface_treatment": "hot_dip_galvanized",
        "packaging": "export",
        "margin_rate": 0.15,
        "freight": 800.0,
    }
    data.update(overrides)
    return WireMeshSpec(**data)


def test_quote_is_deterministic_and_cost_based():
    first = calculate_quote(sample_spec())
    second = calculate_quote(sample_spec())
    assert first == second
    assert first["area_m2"] == 600.0
    assert first["quote_total"] > first["costs"]["total"]
    assert first["unit_price_m2"] == pytest.approx(first["quote_total"] / 600, abs=0.01)


def test_larger_wire_increases_weight_and_price():
    thin = calculate_quote(sample_spec(wire_diameter_mm=2.5))
    thick = calculate_quote(sample_spec(wire_diameter_mm=4.0))
    assert thick["total_weight_kg"] > thin["total_weight_kg"]
    assert thick["quote_total"] > thin["quote_total"]


def test_smaller_aperture_increases_wire_consumption():
    dense = calculate_quote(sample_spec(mesh_size_mm=25))
    open_mesh = calculate_quote(sample_spec(mesh_size_mm=100))
    assert dense["weight_per_m2_kg"] > open_mesh["weight_per_m2_kg"]


def test_invalid_margin_is_rejected():
    with pytest.raises(ValueError, match="margin_rate"):
        calculate_quote(sample_spec(margin_rate=0.9))


def test_factory_matching_requires_product_capability():
    matches = match_factories(sample_spec(product_type="screen_mesh"))
    assert matches
    assert matches[0]["id"] == "factory-xinyuan"


def test_build_quote_contains_factory_recommendations():
    quote = build_quote(sample_spec())
    assert quote["factory_matches"]
    assert quote["formula_version"] == "wire-mesh-v1"


def test_v2_route_calculates_before_compliance_check():
    from app.v2.core.orchestrator_v2 import OrchestratorV2

    for route in OrchestratorV2.DAG_ROUTES.values():
        assert route.index("WireMeshSpecAgent") < route.index("WireMeshQuote")
        assert route.index("WireMeshQuote") < route.index("WireMeshReport")


def test_extracts_chinese_wire_mesh_spec():
    from app.agents.wire_mesh_spec import extract_wire_mesh_spec

    spec, confidence = extract_wire_mesh_spec(
        "建筑防护网，低碳钢丝，丝径 3.5mm，网孔 50x50mm，尺寸 2x3m，数量 100片，热镀锌，出口包装"
    )
    assert spec["product_type"] == "welded_mesh"
    assert spec["material"] == "low_carbon_steel"
    assert spec["wire_diameter_mm"] == 3.5
    assert spec["mesh_size_mm"] == 50
    assert spec["width_m"] == 2
    assert spec["length_m"] == 3
    assert spec["quantity"] == 100
    assert spec["surface_treatment"] == "hot_dip_galvanized"
    assert confidence["quantity"] > 0.8


def test_generates_quote_pdf_and_excel():
    from app.services.wire_mesh_report import build_quote_excel, build_quote_pdf

    quote = build_quote(sample_spec())
    pdf = build_quote_pdf(quote, "QT-TEST")
    excel = build_quote_excel(quote, "QT-TEST")
    assert pdf.startswith(b"%PDF")
    assert excel.startswith(b"PK")
    assert len(pdf) > 1000
    assert len(excel) > 1000
