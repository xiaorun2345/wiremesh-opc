import asyncio
import base64
import json
from loguru import logger

from app.core.agent.base_agent import BaseAgent, AgentResult, AgentStatus
from app.core.mcp.message import MCPMessage
from app.core.memory.redis_memory import TaskMemory
from app.services.minio_service import MinioService
from config.settings import settings


class VisionParseAgent(BaseAgent):
    name = "VisionParseAgent"
    description = "图片图纸视觉解析（多模态视觉 + OCR 双引擎）"

    # OCR 引擎懒加载缓存
    _paddleocr_instance = None

    async def execute(self, message: MCPMessage) -> AgentResult:
        mem = TaskMemory(message.trace_id)
        from_pdf = message.payload.get("from_pdf", False)

        if from_pdf:
            return await self._parse_pdf_pages(mem, message.trace_id)

        file_id = await mem.get("file_id")
        content_type = await mem.get("image_content_type", "unknown")

        data = MinioService().download(file_id)

        # 多模态 + OCR 降级
        result = await self._parse_with_fallback(data, content_type, message.trace_id)

        # 写入结构化数据
        await self._write_to_memory(mem, result)

        logger.info(f"[VisionParse] 解析完成，房间={len(result.get('rooms', []))}, 墙体={len(result.get('walls', []))}")
        return AgentResult(
            agent_name=self.name,
            status=AgentStatus.SUCCESS,
            data=result,
        )

    async def _parse_pdf_pages(self, mem: TaskMemory, trace_id: str) -> AgentResult:
        """解析 PDF 中的结构图/效果图页面"""
        pdf_image = await mem.get("pdf_blueprint_image")
        vision_pages = await mem.get("pdf_vision_pages", {})

        if not pdf_image:
            logger.warning("[VisionParse] 未找到 PDF 页面图片数据")
            empty = self._empty_result()
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.SUCCESS,
                data=empty,
            )

        content_type = await mem.get("image_content_type", "structural_blueprint")

        # 多模态 + OCR 降级
        result = await self._parse_with_fallback(pdf_image, content_type, trace_id)

        # 合并到现有数据（不覆盖 TextExtractAgent 已写入的文字数据）
        existing_rooms = await mem.get("rooms", [])
        existing_walls = await mem.get("walls", [])

        if existing_rooms or existing_walls:
            result["rooms"] = existing_rooms + result.get("rooms", [])
            result["walls"] = existing_walls + result.get("walls", [])
            logger.info(f"[VisionParse] 合并数据：房间={len(result['rooms'])}, 墙体={len(result['walls'])}")

        await self._write_to_memory(mem, result)

        logger.info(f"[VisionParse] PDF 页面解析完成，房间={len(result.get('rooms', []))}, 墙体={len(result.get('walls', []))}")
        return AgentResult(
            agent_name=self.name,
            status=AgentStatus.SUCCESS,
            data={**result, "pdf_vision_pages": vision_pages},
        )

    async def _parse_with_fallback(self, image_data: bytes, content_type: str, trace_id: str) -> dict:
        """优先多模态 LLM，失败降级 OCR + 文字 LLM"""
        try:
            result = await self._call_multimodal_vision(image_data, content_type, trace_id)
            logger.info(f"[VisionParse] 多模态解析成功，房间={len(result.get('rooms', []))}")
            result["_parse_method"] = "multimodal"
            result["_vision_quality_score"] = self._calc_quality_score(result)
            return result
        except Exception as e:
            logger.warning(f"[VisionParse] 多模态解析失败，降级到 OCR: {e}")
            result = await self._call_llm_fallback(image_data, content_type, trace_id)
            result["_parse_method"] = "ocr_fallback"
            result["_vision_quality_score"] = self._calc_quality_score(result) * 0.7  # 降级路径质量打折
            return result

    async def _write_to_memory(self, mem: TaskMemory, result: dict):
        """统一写入 TaskMemory，避免各方法重复"""
        wire_spec = result.get("wire_mesh_spec", {})
        if wire_spec:
            await mem.set("vision_wire_mesh_spec", wire_spec)
        raw_text = result.get("raw_text", "")
        if raw_text:
            await mem.set("extracted_text", raw_text)
        await mem.set("rooms",        result.get("rooms", []))
        await mem.set("walls",        result.get("walls", []))
        await mem.set("doors",        result.get("doors", []))
        await mem.set("windows",      result.get("windows", []))
        await mem.set("water_elec",   result.get("water_elec", []))
        await mem.set("floor_height", result.get("floor_height") or 2800)  # 防止 None 值
        await mem.set("dimensions",   result.get("dimensions", []))
        await mem.set("materials",    result.get("materials", []))
        await mem.set("vision_quality_score", result.get("_vision_quality_score", 0.5))

    def _calc_quality_score(self, result: dict) -> float:
        """
        计算视觉解析质量评分（0-1）。
        基于有内容的丰富度：房间数、墙体数、尺寸数。
        """
        wire_spec = result.get("wire_mesh_spec", {})
        if wire_spec:
            required = ("product_type", "material", "wire_diameter_mm", "mesh_size_mm", "width_m", "length_m", "quantity")
            return round(sum(wire_spec.get(key) not in (None, "") for key in required) / len(required), 2)
        rooms = len(result.get("rooms", []))
        walls = len(result.get("walls", []))
        dims = len(result.get("dimensions", []))

        # 房间权重 0.4，墙体权重 0.4，尺寸权重 0.2
        room_score = min(rooms / 5.0, 1.0)  # ≥5 个房间满分
        wall_score = min(walls / 3.0, 1.0)  # ≥3 面墙满分
        dim_score = min(dims / 5.0, 1.0)    # ≥5 个尺寸满分

        return round(room_score * 0.4 + wall_score * 0.4 + dim_score * 0.2, 2)

    @staticmethod
    def _empty_result() -> dict:
        return {
            "rooms": [], "walls": [], "doors": [], "windows": [],
            "water_elec": [], "floor_height": 2800,
            "dimensions": [], "materials": [],
            "_parse_method": "none", "_vision_quality_score": 0.0,
        }

    async def _call_multimodal_vision(self, image_data: bytes, content_type: str, trace_id: str) -> dict:
        """发送实际图片到多模态 LLM 进行视觉解析"""
        import httpx
        import asyncio as aio

        b64 = base64.b64encode(image_data).decode()
        mime = "image/png" if image_data[:4] == b'\x89PNG' else "image/jpeg"

        prompt = self._build_vision_prompt(content_type)

        last_error = None
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=120) as client:
                    resp = await client.post(
                        f"{settings.MULTIMODAL_BASE_URL}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {settings.MULTIMODAL_API_KEY}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": settings.MULTIMODAL_MODEL,
                            "max_tokens": settings.MULTIMODAL_MAX_TOKENS,
                            "messages": [{
                                "role": "user",
                                "content": [
                                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                                    {"type": "text", "text": prompt},
                                ]
                            }],
                        },
                    )
                    resp.raise_for_status()
                    text = resp.json()["choices"][0]["message"]["content"]
                    logger.info(f"[VisionParse] Multimodal LLM 响应长度: {len(text)} 字符")
                    return self._safe_parse_json(text)
            except httpx.HTTPStatusError as e:
                last_error = e
                if e.response.status_code == 429 and attempt < 2:
                    wait = 5 * (attempt + 1)
                    logger.warning(f"[VisionParse] 速率限制，{wait}s 后重试 ({attempt+1}/2)")
                    await aio.sleep(wait)
                else:
                    break
            except Exception as e:
                last_error = e
                break

        logger.error(f"[VisionParse] Multimodal 调用失败: {last_error}")
        raise last_error

    def _build_vision_prompt(self, content_type: str) -> str:
        """构建丝网图纸/询盘视觉解析 Prompt。"""
        return """你是丝网行业技术工程师。请读取图片中的产品图、尺寸标注、材料说明、数量、包装和贸易信息。
严格返回 JSON，不要解释。不能确定的字段必须为 null，不得猜测价格。

枚举值：
- product_type: welded_mesh / fence_mesh / hexagonal_mesh / screen_mesh / expanded_mesh
- material: low_carbon_steel / galvanized_steel / stainless_304 / stainless_316
- surface_treatment: none / electro_galvanized / hot_dip_galvanized / pvc_coated / powder_coated
- packaging: bulk / pallet / export

输出格式：
{
  "raw_text": "图中可见文字的完整转录",
  "wire_mesh_spec": {
    "product_type": null,
    "material": null,
    "wire_diameter_mm": null,
    "mesh_size_mm": null,
    "width_m": null,
    "length_m": null,
    "quantity": null,
    "quantity_area_m2": null,
    "surface_treatment": "none",
    "packaging": "pallet",
    "margin_rate": 0.15,
    "freight": 0,
    "currency": "CNY"
  },
  "confidence": {
    "product_type": 0.0,
    "material": 0.0,
    "wire_diameter_mm": 0.0,
    "mesh_size_mm": 0.0,
    "width_m": 0.0,
    "length_m": 0.0,
    "quantity": 0.0
  },
  "rooms": [], "walls": [], "doors": [], "windows": [], "water_elec": [],
  "floor_height": 0, "dimensions": [], "materials": []
}"""

    async def _call_llm_fallback(self, data: bytes, content_type: str, trace_id: str) -> dict:
        """降级路径：OCR 提取文字 + 文字 LLM 分析"""
        ocr_text = await asyncio.get_event_loop().run_in_executor(
            None, self._extract_text_ocr, data
        )
        return await self._call_text_llm(ocr_text, content_type, trace_id)

    def _extract_text_ocr(self, data: bytes) -> str:
        """使用 OCR 从图片提取文字，失败时返回图片元信息"""
        import cv2
        import numpy as np

        nparr = np.frombuffer(data, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return ""

        h, w = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # 尝试 pytesseract
        try:
            import pytesseract
            tesseract_cmd = getattr(settings, 'TESSERACT_CMD', None)
            if tesseract_cmd:
                pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
            text = pytesseract.image_to_string(gray, lang='chi_sim+eng')
            if text.strip():
                logger.info(f"[VisionParse] pytesseract OCR 提取到 {len(text)} 字符")
                return text
        except Exception as e:
            logger.debug(f"[VisionParse] pytesseract 不可用: {e}")

        # 尝试 PaddleOCR（懒加载缓存实例）
        try:
            paddleocr = self._get_paddleocr()
            if paddleocr:
                result = paddleocr.ocr(gray, cls=True)
                texts = []
                if result and result[0]:
                    for line in result[0]:
                        if line and len(line) >= 2:
                            texts.append(line[1][0])
                text = "\n".join(texts)
                if text.strip():
                    logger.info(f"[VisionParse] PaddleOCR 提取到 {len(text)} 字符")
                    return text
        except Exception as e:
            logger.debug(f"[VisionParse] PaddleOCR 不可用: {e}")

        # 降级：返回图片元信息 + OpenCV 分析
        logger.warning(f"[VisionParse] OCR 引擎均不可用，使用图片元信息降级")
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        line_density = cv2.countNonZero(binary) / (w * h)
        lines = cv2.HoughLines(binary, 1, np.pi/180, threshold=100)
        line_count = len(lines) if lines is not None else 0

        return f"（OCR 引擎未安装）图片尺寸：{w}x{h}px，线条密度：{line_density:.2%}，检测到直线数：{line_count}。请提取丝网产品规格。"

    def _get_paddleocr(self):
        """懒加载 PaddleOCR 单例，避免每次初始化加载模型"""
        if VisionParseAgent._paddleocr_instance is None:
            try:
                from paddleocr import PaddleOCR
                VisionParseAgent._paddleocr_instance = PaddleOCR(
                    use_angle_cls=True, lang='ch', show_log=False
                )
                logger.info("[VisionParse] PaddleOCR 实例已初始化")
            except Exception as e:
                logger.debug(f"[VisionParse] PaddleOCR 加载失败: {e}")
                return None
        return VisionParseAgent._paddleocr_instance

    async def _call_text_llm(self, ocr_text: str, content_type: str, trace_id: str) -> dict:
        """调用文字 LLM 分析 OCR 结果（降级路径）"""
        import httpx
        import asyncio as aio

        prompt = self._build_vision_prompt(content_type) + f"""

以下是 OCR 提取的原始文字，请优先依据文字填写字段：
{ocr_text if ocr_text else "（未提取到有效文字）"}
"""

        last_error = None
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=120) as client:
                    resp = await client.post(
                        f"{settings.LLM_BASE_URL}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {settings.LLM_API_KEY}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": settings.LLM_MODEL,
                            "max_tokens": settings.LLM_MAX_TOKENS,
                            "messages": [{"role": "user", "content": prompt}],
                        },
                    )
                    resp.raise_for_status()
                    text = resp.json()["choices"][0]["message"]["content"]
                    logger.info(f"[VisionParse] LLM 响应长度: {len(text)} 字符")
                    return self._safe_parse_json(text)
            except httpx.HTTPStatusError as e:
                last_error = e
                if e.response.status_code == 429 and attempt < 2:
                    wait = 5 * (attempt + 1)
                    logger.warning(f"[VisionParse] 速率限制，{wait}s 后重试 ({attempt+1}/2)")
                    await aio.sleep(wait)
                else:
                    break
            except Exception as e:
                last_error = e
                break

        logger.error(f"[VisionParse] LLM 调用失败: {last_error}")
        raise last_error

    def _safe_parse_json(self, text: str) -> dict:
        import json
        import re

        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                result = json.loads(match.group())
                # rooms 类型校验（防止 null）
                if not isinstance(result.get("rooms"), list):
                    result["rooms"] = []
                # walls 格式兼容转换（防止 null/数字）
                if result.get("walls") is None or not isinstance(result.get("walls"), (list, int, float)):
                    result["walls"] = []
                elif isinstance(result.get("walls"), (int, float)):
                    total = int(result["walls"])
                    result["walls"] = [{"segments": [], "total_length": total}] if total > 0 else []
                # water_elec 格式兼容转换（防止 null）
                if result.get("water_elec") is None:
                    result["water_elec"] = []
                elif isinstance(result.get("water_elec"), dict):
                    we = result["water_elec"]
                    pts = []
                    for layer, count in we.items():
                        if isinstance(count, (int, float)) and count > 0:
                            for _ in range(int(count)):
                                pts.append({"layer": layer, "x": 0, "y": 0, "type": layer})
                    result["water_elec"] = pts
                # 其他字段类型校验（防止 null）
                if not isinstance(result.get("doors"), list):
                    result["doors"] = []
                if not isinstance(result.get("windows"), list):
                    result["windows"] = []
                if not isinstance(result.get("dimensions"), list):
                    result["dimensions"] = []
                if not isinstance(result.get("materials"), list):
                    result["materials"] = []
                # floor_height 防止 null
                if not isinstance(result.get("floor_height"), (int, float)) or result.get("floor_height") is None:
                    result["floor_height"] = 2800
                return result
            except Exception:
                pass
        logger.warning("LLM 返回结果无法解析为 JSON，返回空结构")
        return self._empty_result()
