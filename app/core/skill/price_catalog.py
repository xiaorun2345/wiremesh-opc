from __future__ import annotations

"""
价格目录模块
============
提供默认单价表和费用计算逻辑。
支持通过 override_prices 覆盖默认单价。
"""

# 默认单价表（元）
DEFAULT_PRICE_CATALOG = {
    "wall": {
        "unit": "m²",
        "unit_price": 120,
        "description": "墙面工程（含基层处理、腻子、涂料）",
    },
    "floor": {
        "unit": "m²",
        "unit_price": 150,
        "description": "地面工程（含找平、地砖/地板铺设）",
    },
    "waterproof": {
        "unit": "m²",
        "unit_price": 85,
        "description": "防水工程（含基层处理、防水涂料）",
    },
    "water_elec": {
        "strong_elec": {"unit": "个", "unit_price": 120, "description": "强电点位"},
        "weak_elec": {"unit": "个", "unit_price": 100, "description": "弱电点位"},
        "water_supply": {"unit": "个", "unit_price": 150, "description": "给水点位"},
        "drainage": {"unit": "个", "unit_price": 130, "description": "排水点位"},
    },
}


def get_unit_price(category: str, sub_key: str | None = None, override_prices: dict | None = None) -> dict:
    """
    获取某项工程的单价信息。

    Args:
        category: 分类（wall/floor/waterproof/water_elec）
        sub_key: 子分类（仅 water_elec 需要，如 strong_elec）
        override_prices: 覆盖单价（从 TaskMemory.price_list 传入）

    Returns:
        {"unit": str, "unit_price": float, "description": str}
    """
    # 优先使用覆盖价格
    if override_prices and category in override_prices:
        override = override_prices[category]
        if sub_key and isinstance(override, dict) and sub_key in override:
            item = override[sub_key]
            return {
                "unit": item.get("unit", "个"),
                "unit_price": float(item.get("unit_price", 0)),
                "description": item.get("description", ""),
            }
        elif isinstance(override, dict) and "unit_price" in override:
            return {
                "unit": override.get("unit", DEFAULT_PRICE_CATALOG[category].get("unit", "m²")),
                "unit_price": float(override["unit_price"]),
                "description": override.get("description", DEFAULT_PRICE_CATALOG[category].get("description", "")),
            }

    # 使用默认价格
    catalog = DEFAULT_PRICE_CATALOG.get(category, {})
    if sub_key and isinstance(catalog, dict) and sub_key in catalog:
        return catalog[sub_key].copy()
    return catalog.copy()


def build_cost_summary(quantity_list: dict, override_prices: dict | None = None) -> dict:
    """
    构建完整费用汇总表。

    Args:
        quantity_list: 工程量清单（从 TaskMemory.quantity_list 读取）
        override_prices: 覆盖单价表

    Returns:
        {
            "categories": [
                {"name": "墙面工程", "quantity": xx, "unit": "m²", "unit_price": xx, "total": xx},
                ...
            ],
            "water_elec_details": [
                {"name": "强电点位", "quantity": xx, "unit": "个", "unit_price": xx, "total": xx},
                ...
            ],
            "grand_total": 总计金额,
        }
    """
    categories = []
    grand_total = 0.0

    # 墙面工程
    wall_qty = quantity_list.get("wall", {})
    wall_price = get_unit_price("wall", override_prices=override_prices)
    wall_area = wall_qty.get("total_area_m2", 0)
    wall_total = round(wall_area * wall_price["unit_price"], 2)
    categories.append({
        "name": "墙面工程",
        "quantity": wall_area,
        "unit": wall_price["unit"],
        "unit_price": wall_price["unit_price"],
        "total": wall_total,
        "description": wall_price["description"],
    })
    grand_total += wall_total

    # 地面工程
    floor_qty = quantity_list.get("floor", {})
    floor_price = get_unit_price("floor", override_prices=override_prices)
    floor_area = floor_qty.get("total_area_m2", 0)
    floor_total = round(floor_area * floor_price["unit_price"], 2)
    categories.append({
        "name": "地面工程",
        "quantity": floor_area,
        "unit": floor_price["unit"],
        "unit_price": floor_price["unit_price"],
        "total": floor_total,
        "description": floor_price["description"],
    })
    grand_total += floor_total

    # 防水工程
    waterproof_qty = quantity_list.get("waterproof", {})
    waterproof_price = get_unit_price("waterproof", override_prices=override_prices)
    waterproof_area = waterproof_qty.get("total_area_m2", 0)
    waterproof_total = round(waterproof_area * waterproof_price["unit_price"], 2)
    categories.append({
        "name": "防水工程",
        "quantity": waterproof_area,
        "unit": waterproof_price["unit"],
        "unit_price": waterproof_price["unit_price"],
        "total": waterproof_total,
        "description": waterproof_price["description"],
    })
    grand_total += waterproof_total

    # 水电工程（细分）
    water_elec_details = []
    water_elec_qty = quantity_list.get("water_elec", {})
    water_elec_sub_keys = ["strong_elec", "weak_elec", "water_supply", "drainage"]
    water_elec_labels = {"strong_elec": "强电点位", "weak_elec": "弱电点位", "water_supply": "给水点位", "drainage": "排水点位"}

    water_elec_total = 0.0
    for sub_key in water_elec_sub_keys:
        count = water_elec_qty.get(sub_key, 0)
        if count <= 0:
            continue
        price_info = get_unit_price("water_elec", sub_key=sub_key, override_prices=override_prices)
        sub_total = round(count * price_info["unit_price"], 2)
        water_elec_details.append({
            "name": water_elec_labels[sub_key],
            "quantity": count,
            "unit": price_info["unit"],
            "unit_price": price_info["unit_price"],
            "total": sub_total,
            "description": price_info["description"],
        })
        water_elec_total += sub_total

    # 水电工程汇总
    if water_elec_details:
        categories.append({
            "name": "水电工程",
            "quantity": sum(d["quantity"] for d in water_elec_details),
            "unit": "个",
            "unit_price": 0,  # 水电分项单价不同，不显示统一单价
            "total": round(water_elec_total, 2),
            "description": "含强电、弱电、给水、排水",
            "details": water_elec_details,
        })
        grand_total += water_elec_total

    return {
        "categories": categories,
        "water_elec_details": water_elec_details,
        "grand_total": round(grand_total, 2),
    }


def build_room_details(rooms: list) -> list:
    """
    构建房间面积明细表。

    Args:
        rooms: 房间列表（从 TaskMemory.rooms 读取）

    Returns:
        [{"name": str, "area_m2": float, "estimated_cost": float}, ...]
    """
    floor_price = get_unit_price("floor")
    details = []
    for room in rooms:
        area = room.get("area", 0)
        name = room.get("layer") or room.get("name") or "未知房间"
        cost = round(area * floor_price["unit_price"], 2)
        details.append({
            "name": name,
            "area_m2": round(area, 2),
            "estimated_cost": cost,
        })
    return details
