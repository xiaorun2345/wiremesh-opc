from __future__ import annotations

import asyncio
import math
from loguru import logger

from app.core.agent.base_agent import BaseAgent, AgentResult, AgentStatus
from app.core.mcp.message import MCPMessage
from app.core.memory.redis_memory import TaskMemory
from app.services.minio_service import MinioService
from app.utils.file_utils import safe_temp_file, cleanup_temp_file


class CadParseAgent(BaseAgent):
    name = "CadParseAgent"
    description = "CAD 图纸解析（ezdxf，V1 支持标准 DXF/DWG）"
    timeout_seconds = 600  # CAD 解析可能较慢，给 10 分钟

    async def execute(self, message: MCPMessage) -> AgentResult:
        mem = TaskMemory(message.trace_id)
        file_id = await mem.get("file_id")

        data = MinioService().download(file_id)
        tmp_path = safe_temp_file(suffix=".dxf")
        try:
            with open(tmp_path, "wb") as f:
                f.write(data)
            result = await asyncio.get_event_loop().run_in_executor(
                None, self._parse_dxf, tmp_path
            )
        finally:
            cleanup_temp_file(tmp_path)

        await mem.set("rooms",      result["rooms"])
        await mem.set("walls",      result["walls"])
        await mem.set("doors",      result["doors"])
        await mem.set("windows",    result["windows"])
        await mem.set("water_elec", result["water_elec"])

        # 层高优先级：CAD 提取 > DecisionAgent 建议 > 用户偏好 > 默认 2800
        cad_floor_height = result.get("floor_height", 0)
        parse_params     = await mem.get("parse_params", {})
        hint_floor_height = parse_params.get("floor_height_hint", 0)
        final_floor_height = cad_floor_height or hint_floor_height or 2800
        await mem.set("floor_height", final_floor_height)

        logger.info(
            f"[CadParse] 房间={len(result['rooms'])}, 墙体段={len(result['walls'])}, "
            f"门={len(result['doors'])}, 窗={len(result['windows'])}, "
            f"水电={len(result['water_elec'])}, 层高={final_floor_height}mm"
        )
        return AgentResult(
            agent_name=self.name,
            status=AgentStatus.SUCCESS,
            data=result,
        )

    def _parse_dxf(self, file_path: str) -> dict:
        import ezdxf
        from ezdxf.math import BoundingBox2d, Vec2

        try:
            doc = ezdxf.readfile(file_path)
        except Exception:
            doc = ezdxf.recover.readfile(file_path)[0]

        msp = doc.modelspace()
        raw_walls, doors, windows, water_elec = [], [], [], []

        # 天正图层关键词扩充
        WALL_KW   = ("WALL", "墙", "QT", "DOTE", "S_WALL", "A-WALL")
        DOOR_KW   = ("DOOR", "门", "A-DOOR", "S_DOOR")
        WINDOW_KW = ("WINDOW", "窗", "A-WIND", "S_WIND")
        ELEC_KW   = ("ELEC", "水", "电", "WATER", "PIPE", "E-POWR", "P-PIPE")
        ROOM_KW   = ("ROOM", "房", "AREA", "空间", "A-AREA", "S_ROOM")

        for entity in msp:
            layer = (entity.dxf.layer or "").upper()

            if any(k in layer for k in WALL_KW):
                if entity.dxftype() == "LINE":
                    seg = self._line_to_segment(entity)
                    if seg:
                        raw_walls.append(seg)
                elif entity.dxftype() == "LWPOLYLINE":
                    segs = self._polyline_to_segments(entity)
                    raw_walls.extend(segs)

            elif any(k in layer for k in DOOR_KW):
                if entity.dxftype() in ("INSERT", "LINE", "ARC"):
                    doors.append(self._entity_bbox(entity))

            elif any(k in layer for k in WINDOW_KW):
                if entity.dxftype() in ("INSERT", "LINE"):
                    windows.append(self._entity_bbox(entity))

            elif any(k in layer for k in ELEC_KW):
                if entity.dxftype() == "INSERT":
                    water_elec.append({
                        "layer": layer,
                        "x": entity.dxf.insert.x,
                        "y": entity.dxf.insert.y,
                        "block": entity.dxf.name,
                    })

        # 墙体拓扑重构：把离散线段连接成连续墙体轮廓
        walls = self._reconstruct_wall_topology(raw_walls)

        # 房间推断：优先从 ROOM 图层封闭多段线，其次从墙体轮廓推断
        rooms = self._extract_rooms(msp, ROOM_KW)
        if not rooms and walls:
            rooms = self._infer_rooms_from_walls(walls)

        # 从标注文字提取层高
        floor_height = self._extract_floor_height(msp)

        return {
            "rooms":        rooms,
            "walls":        walls,
            "doors":        doors,
            "windows":      windows,
            "water_elec":   water_elec,
            "floor_height": floor_height,
        }

    # ── 线段提取 ──────────────────────────────────────────────

    def _line_to_segment(self, entity) -> dict | None:
        try:
            sx, sy = entity.dxf.start.x, entity.dxf.start.y
            ex, ey = entity.dxf.end.x,   entity.dxf.end.y
            length = math.hypot(ex - sx, ey - sy)
            if length < 10:  # 过滤极短线（< 10mm）
                return None
            return {
                "start":  [round(sx, 2), round(sy, 2)],
                "end":    [round(ex, 2), round(ey, 2)],
                "length": round(length),
            }
        except Exception:
            return None

    def _polyline_to_segments(self, entity) -> list[dict]:
        segs = []
        try:
            pts = list(entity.vertices())
            for i in range(len(pts) - 1):
                sx, sy = pts[i][0],   pts[i][1]
                ex, ey = pts[i+1][0], pts[i+1][1]
                length = math.hypot(ex - sx, ey - sy)
                if length >= 10:
                    segs.append({
                        "start":  [round(sx, 2), round(sy, 2)],
                        "end":    [round(ex, 2), round(ey, 2)],
                        "length": round(length),
                    })
            # 封闭多段线：最后一段连回起点
            if entity.is_closed and len(pts) >= 2:
                sx, sy = pts[-1][0], pts[-1][1]
                ex, ey = pts[0][0],  pts[0][1]
                length = math.hypot(ex - sx, ey - sy)
                if length >= 10:
                    segs.append({
                        "start":  [round(sx, 2), round(sy, 2)],
                        "end":    [round(ex, 2), round(ey, 2)],
                        "length": round(length),
                    })
        except Exception:
            pass
        return segs

    # ── 墙体拓扑重构 ──────────────────────────────────────────

    def _reconstruct_wall_topology(self, raw_walls: list[dict]) -> list[dict]:
        """
        把离散线段按端点连接成连续墙体链。
        容差 50mm 内的端点视为同一节点。
        """
        if not raw_walls:
            return []

        TOLERANCE = 50  # mm

        def pt_key(pt: list) -> tuple:
            """把坐标量化到容差格，用于快速匹配"""
            return (round(pt[0] / TOLERANCE), round(pt[1] / TOLERANCE))

        # 建立端点 → 线段索引的邻接表
        adjacency: dict[tuple, list[int]] = {}
        for i, seg in enumerate(raw_walls):
            if not seg:
                continue
            for pt in (seg["start"], seg["end"]):
                key = pt_key(pt)
                adjacency.setdefault(key, []).append(i)

        visited = set()
        chains = []

        for start_idx in range(len(raw_walls)):
            if start_idx in visited or not raw_walls[start_idx]:
                continue

            # BFS 连接相邻线段
            chain_indices = []
            queue = [start_idx]
            while queue:
                idx = queue.pop(0)
                if idx in visited:
                    continue
                visited.add(idx)
                chain_indices.append(idx)
                seg = raw_walls[idx]
                for pt in (seg["start"], seg["end"]):
                    for neighbor in adjacency.get(pt_key(pt), []):
                        if neighbor not in visited:
                            queue.append(neighbor)

            if chain_indices:
                total_length = sum(raw_walls[i]["length"] for i in chain_indices if raw_walls[i])
                chains.append({
                    "segments":     [raw_walls[i] for i in chain_indices if raw_walls[i]],
                    "total_length": round(total_length),
                    "segment_count": len(chain_indices),
                })

        return chains

    # ── 房间提取 ──────────────────────────────────────────────

    def _extract_rooms(self, msp, room_kw: tuple) -> list[dict]:
        rooms = []
        try:
            from ezdxf.math import BoundingBox2d
            for entity in msp:
                if entity.dxftype() != "LWPOLYLINE" or not entity.is_closed:
                    continue
                layer = (entity.dxf.layer or "").upper()
                if not any(k in layer for k in room_kw):
                    continue
                pts = list(entity.vertices())
                if len(pts) < 3:
                    continue
                try:
                    bbox = BoundingBox2d(pts)
                except TypeError:
                    # ezdxf < 1.3 兼容：vertices() 返回元组而非 Vec2
                    from ezdxf.math import Vec2
                    bbox = BoundingBox2d([Vec2(p[0], p[1]) for p in pts])
                area_m2 = round(bbox.size.x * bbox.size.y / 1e6, 2)
                if area_m2 < 0.5:  # 过滤 < 0.5m² 的极小区域
                    continue
                # 用 shoelace 公式计算多边形真实面积（比 bbox 更准确）
                real_area = self._polygon_area(pts)
                rooms.append({
                    "width":  round(bbox.size.x),
                    "height": round(bbox.size.y),
                    "area":   round(real_area / 1e6, 2),  # mm² → m²
                    "layer":  layer,
                    "name":   self._guess_room_name(layer),
                })
        except Exception as e:
            logger.warning(f"房间提取失败: {e}")
        return rooms

    def _infer_rooms_from_walls(self, walls: list[dict]) -> list[dict]:
        """当没有 ROOM 图层时，从墙体链的包围盒推断房间（粗略估算）"""
        if not walls:
            return []
        all_pts = []
        for wall in walls:
            for seg in wall.get("segments", []):
                all_pts.extend([seg["start"], seg["end"]])
        if not all_pts:
            return []
        xs = [p[0] for p in all_pts]
        ys = [p[1] for p in all_pts]
        w = max(xs) - min(xs)
        h = max(ys) - min(ys)
        area = round(w * h / 1e6, 2)
        if area < 1:
            return []
        return [{"width": round(w), "height": round(h), "area": area, "layer": "INFERRED", "name": "整体空间"}]

    # ── 层高提取 ──────────────────────────────────────────────

    def _extract_floor_height(self, msp) -> int:
        """从标注文字中提取层高，如 '2800' 或 '层高=2800'"""
        import re
        for entity in msp:
            if entity.dxftype() not in ("TEXT", "MTEXT"):
                continue
            try:
                text = entity.dxf.text if entity.dxftype() == "TEXT" else entity.text
                text = (text or "").replace(" ", "")
                # 匹配 "层高2800" "H=2800" "h=2800mm" 等格式
                m = re.search(r"(?:层高|H=|h=|净高)[\s=:：]*(\d{3,4})", text, re.IGNORECASE)
                if m:
                    h = int(m.group(1))
                    if 2000 <= h <= 6000:  # 合理层高范围
                        return h
            except Exception:
                continue
        return 2800  # 默认层高

    # ── 工具函数 ──────────────────────────────────────────────

    def _polygon_area(self, pts: list) -> float:
        """Shoelace 公式计算多边形面积（mm²）"""
        n = len(pts)
        area = 0.0
        for i in range(n):
            j = (i + 1) % n
            area += pts[i][0] * pts[j][1]
            area -= pts[j][0] * pts[i][1]
        return abs(area) / 2

    def _guess_room_name(self, layer: str) -> str:
        """从图层名猜测房间类型"""
        mapping = {
            "卧室": "卧室", "BEDROOM": "卧室",
            "客厅": "客厅", "LIVING": "客厅",
            "厨房": "厨房", "KITCHEN": "厨房",
            "卫生间": "卫生间", "TOILET": "卫生间", "BATH": "卫生间",
            "阳台": "阳台", "BALCONY": "阳台",
            "书房": "书房", "STUDY": "书房",
            "餐厅": "餐厅", "DINING": "餐厅",
        }
        for key, name in mapping.items():
            if key in layer:
                return name
        return "未知房间"

    def _entity_bbox(self, entity) -> dict:
        try:
            return {"x": entity.dxf.insert.x, "y": entity.dxf.insert.y}
        except Exception:
            return {}
