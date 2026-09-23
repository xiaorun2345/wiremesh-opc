from __future__ import annotations

from app.core.memory.redis_memory import TaskMemory, UserSessionMemory
from app.core.skill.quantity_skills import (
    WallAreaSkill, FloorAreaSkill, WaterElecSkill, WaterproofSkill
)
from loguru import logger


async def calculate_quantities(trace_id: str, user_id: str | None = None) -> dict:
    """
    工程量计算（纯规则引擎，禁止 LLM）。
    从 TaskMemory 读取解析结果，调用各 Skill 计算，写回 quantity_list。
    """
    mem = TaskMemory(trace_id)

    rooms        = await mem.get("rooms",        [])
    walls        = await mem.get("walls",        [])
    doors        = await mem.get("doors",        [])
    windows      = await mem.get("windows",      [])
    water_elec   = await mem.get("water_elec",   [])
    floor_height = await mem.get("floor_height") or 2800  # 防止 None 值
    materials    = await mem.get("materials",    [])

    # 读取用户偏好，覆盖默认值（优先级：解析结果 > 用户偏好 > 硬编码默认）
    if user_id:
        try:
            user_mem  = UserSessionMemory(user_id)
            prefs     = await user_mem.get_preferences()
            if prefs:
                if floor_height == 2800 and prefs.get("default_floor_height"):
                    floor_height = prefs["default_floor_height"]
                if not materials and prefs.get("preferred_material"):
                    materials = [prefs["preferred_material"]]
        except Exception as e:
            logger.debug(f"[QuantityCalc] 读取用户偏好失败（不影响计算）: {e}")

    # 调用各 Skill 计算
    wall_result       = WallAreaSkill().execute({
        "walls": walls, "doors": doors, "windows": windows,
        "floor_height": floor_height, "materials": materials,
    })
    floor_result      = FloorAreaSkill().execute({"rooms": rooms, "materials": materials})
    water_result      = WaterElecSkill().execute({"water_elec": water_elec})
    waterproof_result = WaterproofSkill().execute({"rooms": rooms, "floor_height": floor_height})

    quantity_list = {
        "wall":       wall_result,
        "floor":      floor_result,
        "water_elec": water_result,
        "waterproof": waterproof_result,
    }

    await mem.set("quantity_list", quantity_list)

    total = (
        wall_result.get("total_area_m2", 0) +
        floor_result.get("total_area_m2", 0) +
        waterproof_result.get("total_area_m2", 0)
    )
    logger.info(f"[QuantityCalc] 算量完成，合计面积 {total:.2f} m²，层高={floor_height}mm")
    return quantity_list
