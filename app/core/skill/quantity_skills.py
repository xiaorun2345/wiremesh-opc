import math
from app.core.skill.base_skill import BaseSkill


class WallAreaSkill(BaseSkill):
    """
    墙面面积计量规则（W-01 ~ W-06）
    严禁在此调用任何 LLM。
    """
    name = "WallAreaSkill"

    def execute(self, data: dict) -> dict:
        walls        = data.get("walls", [])
        doors        = data.get("doors", [])
        windows      = data.get("windows", [])
        floor_height = data.get("floor_height") or 2800  # mm，防止 None 值
        materials    = data.get("materials", [])

        from loguru import logger
        logger.debug(f"[WallAreaSkill] floor_height={floor_height}, type={type(floor_height)}")
        logger.debug(f"[WallAreaSkill] walls={walls[:2] if isinstance(walls, list) and len(walls) > 2 else walls}")

        h_m = floor_height / 1000  # mm → m

        # W-01: 墙面面积 = 墙长 × 墙高
        # 兼容三种 walls 格式：
        #   1. CadParseAgent 链结构：[{"segments": [...], "total_length": 5000}]
        #   2. 旧单线段格式：[{"length": 5000}]
        #   3. VisionParseAgent 数字格式：0 或 整数（总长度 mm）
        gross_area = 0.0
        if isinstance(walls, (int, float)):
            # VisionParseAgent 返回数字时，视为总墙长 mm
            gross_area = (walls / 1000) * h_m
        else:
            for wall in walls:
                if not isinstance(wall, dict):
                    continue
                if "total_length" in wall:          # CadParseAgent 链结构
                    length_mm = wall["total_length"] or 0  # 防止 None 值
                elif "segments" in wall:            # 链结构但无 total_length
                    length_mm = sum(s.get("length", 0) or 0 for s in wall.get("segments", []))
                else:                               # 旧单线段格式
                    length_mm = wall.get("length", 0) or 0  # 防止 None 值
                gross_area += (length_mm / 1000) * h_m

        # W-02: 扣除门洞（默认门宽 900mm × 门高 2100mm）
        door_deduction = len(doors) * (0.9 * 2.1)

        # W-03: 扣除窗洞（默认窗宽 1500mm × 窗高 1200mm）
        window_deduction = len(windows) * (1.5 * 1.2)

        # W-04: 不扣踢脚线（高度 ≤ 300mm）
        net_area = max(0.0, gross_area - door_deduction - window_deduction)

        # W-05/W-06: 损耗系数
        loss_factor = 1.05 if "瓷砖" in materials else 1.0
        total_area = round(net_area * loss_factor, 2)

        return {
            "gross_area_m2":        round(gross_area, 2),
            "door_deduction_m2":    round(door_deduction, 2),
            "window_deduction_m2":  round(window_deduction, 2),
            "net_area_m2":          round(net_area, 2),
            "loss_factor":          loss_factor,
            "total_area_m2":        total_area,
        }


class FloorAreaSkill(BaseSkill):
    """
    地面面积计量规则（F-01 ~ F-05）
    """
    name = "FloorAreaSkill"

    def execute(self, data: dict) -> dict:
        rooms    = data.get("rooms", [])
        materials = data.get("materials", [])

        total = 0.0
        room_details = []
        for room in rooms:
            area = room.get("area", 0)  # 已是 m²
            # F-02: 不扣柱墩（≤ 0.3m²），F-03: 扣独立柱（> 0.3m²）
            # 简化：V1 不处理柱，直接用净面积
            room_details.append({"name": room.get("layer", "未知"), "area_m2": round(area, 2)})
            total += area

        # F-05: 损耗系数
        is_irregular = any(r.get("area", 0) < 5 for r in rooms)
        loss_factor = 1.05 if is_irregular else 1.03
        if "瓷砖" not in (materials or []):
            loss_factor = 1.0

        total_with_loss = round(total * loss_factor, 2)

        return {
            "rooms":         room_details,
            "net_area_m2":   round(total, 2),
            "loss_factor":   loss_factor,
            "total_area_m2": total_with_loss,
        }


class WaterElecSkill(BaseSkill):
    """
    水电点位计量规则（E-01 ~ E-05）
    """
    name = "WaterElecSkill"

    # 图层关键词 → 类型映射
    LAYER_MAP = {
        "strong_elec":  ["ELEC", "强电", "插座", "开关", "灯"],
        "weak_elec":    ["弱电", "网络", "电视", "电话", "DATA"],
        "water_supply": ["给水", "冷水", "热水", "WATER"],
        "drainage":     ["排水", "地漏", "DRAIN"],
    }

    def execute(self, data: dict) -> dict:
        water_elec = data.get("water_elec", [])

        counts = {"strong_elec": 0, "weak_elec": 0, "water_supply": 0, "drainage": 0}

        for point in water_elec:
            layer = (point.get("layer") or "").upper()
            for category, keywords in self.LAYER_MAP.items():
                if any(kw.upper() in layer for kw in keywords):
                    counts[category] += 1
                    break

        return {
            "strong_elec":  counts["strong_elec"],
            "weak_elec":    counts["weak_elec"],
            "water_supply": counts["water_supply"],
            "drainage":     counts["drainage"],
            "total_points": sum(counts.values()),
        }


class WaterproofSkill(BaseSkill):
    """
    防水面积计量规则（P-01 ~ P-06）
    """
    name = "WaterproofSkill"

    # 需要防水的房间关键词（含淋浴）
    WET_ROOMS = ["卫生间", "厕所", "浴室", "淋浴", "TOILET", "BATH", "WC", "SHOWER",
                 "厨房", "KITCHEN", "阳台", "BALCONY"]

    WALL_UPTURN_MM = 300    # 普通上翻高度
    SHOWER_UPTURN_MM = 1800 # 淋浴区上翻高度

    def execute(self, data: dict) -> dict:
        rooms        = data.get("rooms", [])
        floor_height = data.get("floor_height") or 2800  # 防止 None 值

        total_floor = 0.0
        total_wall  = 0.0
        details = []

        for room in rooms:
            layer = (room.get("layer") or room.get("name") or "").upper()
            is_wet = any(kw.upper() in layer for kw in self.WET_ROOMS)
            if not is_wet:
                continue

            floor_area = room.get("area", 0)
            # 估算周长（假设正方形）
            perimeter = 4 * math.sqrt(floor_area) if floor_area > 0 else 0

            is_shower = any(k in layer for k in ["淋浴", "SHOWER"])
            upturn_h = self.SHOWER_UPTURN_MM / 1000 if is_shower else self.WALL_UPTURN_MM / 1000
            wall_area = perimeter * upturn_h

            total_floor += floor_area
            total_wall  += wall_area
            details.append({
                "room":        layer,
                "floor_m2":    round(floor_area, 2),
                "wall_m2":     round(wall_area, 2),
                "upturn_mm":   self.SHOWER_UPTURN_MM if is_shower else self.WALL_UPTURN_MM,
            })

        return {
            "details":       details,
            "floor_area_m2": round(total_floor, 2),
            "wall_area_m2":  round(total_wall, 2),
            "total_area_m2": round(total_floor + total_wall, 2),
        }
