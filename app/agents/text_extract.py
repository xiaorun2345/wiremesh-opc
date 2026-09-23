from __future__ import annotations

"""
TextExtractAgent — 自适应多模式文本提取
========================================
模式路由：
  fast    → 仅 pdfplumber（电子PDF，50ms/页）
  standard → MinerU 1x（普通扫描件，300ms/页）
  deep    → MinerU 2x + 双引擎共识（模糊/复杂图纸，800ms/页）
  hybrid  → 逐页质量检测，动态选引擎（混合文档）

质量判定规则：
  - 可提取文本 > 50 字符/页 → 电子PDF → fast
  - 图片 DPI > 200 → 清晰扫描 → standard
  - 图片 DPI < 200 或噪点多 → 模糊 → deep
  - 部分页有文本、部分页纯图 → 混合 → hybrid
"""
import re
import time
import asyncio
import httpx
from pathlib import Path
from loguru import logger

from app.core.agent.base_agent import BaseAgent, AgentResult, AgentStatus
from app.core.mcp.message import MCPMessage
from app.core.memory.redis_memory import TaskMemory
from app.services.minio_service import MinioService
from app.utils.file_utils import safe_temp_file, cleanup_temp_file
from app.utils.converters import normalize_to_mm
from config.settings import settings


# 共识阈值
CONSENSUS_PASS = 0.85
CONSENSUS_WARN = 0.60
DIMENSION_TOLERANCE = 2.0  # mm

# 质量判定阈值
TEXT_PER_PAGE_THRESHOLD = 50  # 每页字符数
DPI_THRESHOLD = 200


class TextExtractAgent(BaseAgent):
    name = "TextExtractAgent"
    description = "自适应文本提取（fast/standard/deep/hybrid 四模式）"
    timeout_seconds = 600

    async def execute(self, message: MCPMessage) -> AgentResult:
        mem = TaskMemory(message.trace_id)
        file_id = await mem.get("file_id")
        file_type = await mem.get("file_type", "pdf")

        # 图片直接走 MinerU + OCR
        if file_type in ("jpg", "jpeg", "png"):
            return await self._handle_image(mem, file_id, file_type)

        # PDF：质量检测 → 模式路由
        data = MinioService().download(file_id)
        tmp_path = safe_temp_file(suffix=".pdf")
        try:
            with open(tmp_path, "wb") as f:
                f.write(data)

            # ── 质量检测 ────────────────────────────────────
            quality = await asyncio.to_thread(self._detect_pdf_quality, tmp_path)
            mode = quality["mode"]
            await mem.set("extract_mode", mode)
            await mem.set("quality_report", quality)

            logger.info(f"[TextExtract] 质量={quality['summary']}, 模式={mode}")

            # ── 按模式执行 ──────────────────────────────────
            if mode == "fast":
                return await self._mode_fast(tmp_path, mem)
            elif mode == "standard":
                return await self._mode_standard(tmp_path, mem)
            elif mode == "deep":
                return await self._mode_deep(tmp_path, mem)
            else:  # hybrid
                return await self._mode_hybrid(tmp_path, mem, data)

        finally:
            cleanup_temp_file(tmp_path)

    # ── 图片处理 ─────────────────────────────────────────────

    async def _handle_image(self, mem: TaskMemory, file_id: str, file_type: str) -> AgentResult:
        """图片直接 MinerU + OCR 降级，混合内容时不覆盖 VisionParseAgent 的结构数据"""
        data = MinioService().download(file_id)
        tmp_path = safe_temp_file(suffix=f".{file_type}")
        try:
            with open(tmp_path, "wb") as f:
                f.write(data)

            text = ""
            # MinerU 主引擎
            try:
                result = await self._extract_with_mineru(tmp_path)
                text = result.get("text", "")
            except Exception as e:
                logger.warning(f"[MinerU] 图片提取失败: {e}")

            # OCR 降级
            if not text.strip():
                try:
                    result = await asyncio.to_thread(self._extract_with_ocr, tmp_path)
                    text = result.get("text", "")
                except Exception as e:
                    logger.warning(f"[OCR] 提取失败: {e}")

        finally:
            cleanup_temp_file(tmp_path)

        dims = self._extract_dimensions(text)
        materials = self._extract_materials(text)

        # 混合内容感知：如果 VisionParseAgent 已先执行，只补充文字/尺寸/材料数据
        existing_rooms = await mem.get("rooms", [])
        if existing_rooms:
            logger.info("[TextExtract] 检测到 VisionParseAgent 已执行，只补充文字数据")
            # 合并 materials（去重）
            existing_materials = await mem.get("materials", [])
            if existing_materials:
                materials = list(set(materials + existing_materials))

        await mem.set("extracted_text", text)
        await mem.set("extracted_tables", [])
        await mem.set("dimensions", dims)
        await mem.set("materials", materials)
        await mem.set("extract_mode", "standard")

        return AgentResult(
            agent_name=self.name,
            status=AgentStatus.SUCCESS,
            data={"dimensions_count": len(dims), "materials_count": len(materials), "consensus_status": "passed"},
        )

    # ── PDF 质量检测 ─────────────────────────────────────────

    def _detect_pdf_quality(self, file_path: str) -> dict:
        """
        检测 PDF 页面质量，决定解析模式（使用 pdfplumber）

        返回:
        {
            "mode": "fast|standard|deep|hybrid",
            "summary": str,
            "pages": [{"page": 0, "type": "text|image|mixed", "char_count": int}, ...]
        }
        """
        import pdfplumber

        page_results = []
        text_pages = 0
        image_pages = 0
        mixed_pages = 0

        with pdfplumber.open(file_path) as pdf:
            for i, page in enumerate(pdf.pages):
                text = page.extract_text() or ""
                char_count = len(text.strip())

                # 检测页面是否有图片
                imgs = page.images
                has_images = len(imgs) > 0

                # 分类
                if char_count > TEXT_PER_PAGE_THRESHOLD and not has_images:
                    page_type = "text"
                    text_pages += 1
                elif has_images and char_count < TEXT_PER_PAGE_THRESHOLD:
                    page_type = "image"
                    image_pages += 1
                else:
                    page_type = "mixed"
                    mixed_pages += 1

                page_results.append({
                    "page": i,
                    "type": page_type,
                    "char_count": char_count,
                })

        total = len(page_results)
        if total == 0:
            return {"mode": "fast", "summary": "空PDF", "pages": []}

        # 决策逻辑
        text_ratio = text_pages / total
        image_ratio = image_pages / total
        mixed_ratio = mixed_pages / total

        if text_ratio > 0.8:
            mode = "fast"
            summary = f"电子PDF（{text_pages}/{total} 文本页）"
        elif mixed_ratio > 0.3:
            mode = "hybrid"
            summary = f"混合文档（{mixed_pages}/{total} 混合页）"
        elif image_ratio > 0.5:
            mode = "deep"
            summary = f"图片密集（{image_pages}/{total} 图片页）"
        else:
            mode = "standard"
            summary = f"普通文档（{text_pages}文本/{image_pages}图片）"

        return {"mode": mode, "summary": summary, "pages": page_results}

    # ── fast 模式 ────────────────────────────────────────────

    async def _mode_fast(self, file_path: str, mem: TaskMemory) -> AgentResult:
        """fast：仅 pdfplumber，50ms/页"""
        result = await asyncio.to_thread(self._extract_with_pdfplumber, file_path)
        text = result.get("text", "")
        tables = result.get("tables", [])

        dims = self._extract_dimensions(text)
        materials = self._extract_materials(text)

        await mem.set("extracted_text", text)
        await mem.set("extracted_tables", tables)
        await mem.set("dimensions", dims)
        await mem.set("materials", materials)

        return AgentResult(
            agent_name=self.name,
            status=AgentStatus.SUCCESS,
            data={"dimensions_count": len(dims), "materials_count": len(materials), "consensus_status": "passed"},
        )

    # ── standard 模式 ────────────────────────────────────────

    async def _mode_standard(self, file_path: str, mem: TaskMemory) -> AgentResult:
        """standard：仅 MinerU 1x，300ms/页"""
        try:
            result = await self._extract_with_mineru(file_path)
            text = result.get("text", "")
        except Exception as e:
            logger.warning(f"[MinerU] 失败，降级 pdfplumber: {e}")
            result = await asyncio.to_thread(self._extract_with_pdfplumber, file_path)
            text = result.get("text", "")

        dims = self._extract_dimensions(text)
        materials = self._extract_materials(text)

        await mem.set("extracted_text", text)
        await mem.set("extracted_tables", result.get("tables", []))
        await mem.set("dimensions", dims)
        await mem.set("materials", materials)

        return AgentResult(
            agent_name=self.name,
            status=AgentStatus.SUCCESS,
            data={"dimensions_count": len(dims), "materials_count": len(materials), "consensus_status": "passed"},
        )

    # ── deep 模式 ────────────────────────────────────────────

    async def _mode_deep(self, file_path: str, mem: TaskMemory) -> AgentResult:
        """deep：MinerU + pdfplumber 双引擎共识，800ms/页"""
        mineru_task = self._extract_with_mineru(file_path)
        pdfplumber_task = asyncio.to_thread(self._extract_with_pdfplumber, file_path)

        mineru_result = None
        pdfplumber_result = None

        try:
            mineru_result = await mineru_task
        except Exception as e:
            logger.warning(f"[MinerU] deep 模式失败: {e}")

        try:
            pdfplumber_result = await pdfplumber_task
        except Exception as e:
            logger.warning(f"[pdfplumber] deep 模式失败: {e}")

        # 兜底
        if not mineru_result and not pdfplumber_result:
            raise RuntimeError("deep 模式双引擎均失败")

        mineru_text = mineru_result.get("text", "") if mineru_result else ""
        pdfplumber_text = pdfplumber_result.get("text", "") if pdfplumber_result else ""

        mineru_dims = self._extract_dimensions(mineru_text)
        pdfplumber_dims = self._extract_dimensions(pdfplumber_text)
        materials = self._extract_materials(mineru_text or pdfplumber_text)

        # 共识计算
        consensus_score, diff_items = self._compute_consensus(mineru_dims, pdfplumber_dims)

        # 用 MinerU 结果
        final_text = mineru_text if mineru_text else pdfplumber_text
        final_dims = mineru_dims if mineru_dims else pdfplumber_dims

        await mem.set("extracted_text", final_text)
        await mem.set("extracted_tables", mineru_result.get("tables", []) if mineru_result else [])
        await mem.set("dimensions", final_dims)
        await mem.set("materials", materials)
        await mem.set("consensus_score", consensus_score)
        await mem.set("consensus_diffs", diff_items)

        logger.info(f"[TextExtract] deep 模式共识分={consensus_score:.0%}, 差异={len(diff_items)}")

        if consensus_score < CONSENSUS_WARN:
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.SUCCESS,
                data={
                    "dimensions_count": len(final_dims),
                    "materials_count": len(materials),
                    "consensus_score": consensus_score,
                    "consensus_status": "failed",
                    "need_human_review": True,
                    "review_hint": f"deep模式共识分 {consensus_score:.0%} < 60%，请核对",
                },
            )
        elif consensus_score < CONSENSUS_PASS:
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.SUCCESS,
                data={
                    "dimensions_count": len(final_dims),
                    "materials_count": len(materials),
                    "consensus_score": consensus_score,
                    "consensus_status": "warning",
                },
            )
        else:
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.SUCCESS,
                data={
                    "dimensions_count": len(final_dims),
                    "materials_count": len(materials),
                    "consensus_score": consensus_score,
                    "consensus_status": "passed",
                },
            )

    # ── hybrid 模式 ──────────────────────────────────────────

    async def _mode_hybrid(self, file_path: str, mem: TaskMemory, file_data: bytes) -> AgentResult:
        """hybrid：逐页按内容类型动态选引擎"""
        import pdfplumber
        from app.utils.image_analyzer import ImageAnalyzer

        all_text = ""
        all_tables = []
        blueprint_pages = []  # 暂存结构图页的图片数据
        photo_pages = []      # 暂存效果图页的图片数据

        with pdfplumber.open(file_path) as pdf:
            for i, page in enumerate(pdf.pages):
                text = page.extract_text() or ""
                imgs = page.images

                if len(text.strip()) > TEXT_PER_PAGE_THRESHOLD and not imgs:
                    # 纯文本页 → pdfplumber 快速提取
                    all_text += text + "\n"
                    tables = page.extract_tables()
                    if tables:
                        all_tables.extend(tables)
                elif imgs:
                    # 有图片页 → 提取图片并分类
                    page_image_data = await asyncio.to_thread(self._extract_page_image, page, file_path)
                    if page_image_data:
                        analysis = ImageAnalyzer().classify(page_image_data)
                        content_type = analysis["content_type"]
                        logger.info(f"[hybrid] 页 {i}: {content_type} (置信度={analysis['confidence']:.0%})")

                        if content_type == "structural_blueprint":
                            blueprint_pages.append((i, page_image_data, text))
                        elif content_type == "rendering_photo":
                            photo_pages.append((i, page_image_data, text))
                        else:
                            # document_scan 或混合 → MinerU OCR
                            ocr_text = await self._ocr_page_from_bytes(page_image_data)
                            all_text += ocr_text + "\n"
                    else:
                        # 图片提取失败，用文本兜底
                        all_text += text + "\n"
                else:
                    # 无图片但文字少 → 可能是扫描页，尝试 OCR
                    page_image_data = await asyncio.to_thread(self._render_page_to_image, page, file_path)
                    if page_image_data:
                        ocr_text = await self._ocr_page_from_bytes(page_image_data)
                        all_text += ocr_text + "\n"
                    else:
                        all_text += text + "\n"

        # 合并文字结果
        dims = self._extract_dimensions(all_text)
        materials = self._extract_materials(all_text)

        await mem.set("extracted_text", all_text)
        await mem.set("extracted_tables", all_tables)
        await mem.set("dimensions", dims)
        await mem.set("materials", materials)

        # 记录需要 VisionParseAgent 处理的页面
        needs_vision = False
        if blueprint_pages or photo_pages:
            needs_vision = True
            await mem.set("pdf_vision_pages", {
                "blueprints": len(blueprint_pages),
                "photos": len(photo_pages),
                "total_pages": len(blueprint_pages) + len(photo_pages),
            })
            # 保存第一张结构图供 VisionParseAgent 使用
            if blueprint_pages:
                await mem.set("pdf_blueprint_image", blueprint_pages[0][1])
            elif photo_pages:
                await mem.set("pdf_blueprint_image", photo_pages[0][1])

            logger.info(f"[hybrid] 发现 {len(blueprint_pages)} 张结构图 + {len(photo_pages)} 张效果图，需要 VisionParseAgent")

        return AgentResult(
            agent_name=self.name,
            status=AgentStatus.SUCCESS,
            data={
                "dimensions_count": len(dims),
                "materials_count": len(materials),
                "consensus_status": "passed",
                "needs_vision_parse": needs_vision,
            },
        )

    def _extract_page_image(self, page, file_path: str) -> bytes | None:
        """从 PDF 页面提取嵌入的图片数据（原始字节）"""
        try:
            import io
            from PIL import Image

            # 尝试从页面的图片对象中提取
            if hasattr(page, 'images') and page.images:
                # 取第一张图片
                img_obj = page.images[0]
                # pdfplumber 的图片对象可能有 stream 数据
                if hasattr(img_obj, 'stream') and img_obj.stream:
                    return img_obj.stream.get_data()
        except Exception as e:
            logger.debug(f"[TextExtract] 提取页面图片失败: {e}")

        # 降级：将页面渲染为图片
        return self._render_page_to_image(page, file_path)

    def _render_page_to_image(self, page, file_path: str) -> bytes | None:
        """将 PDF 页面渲染为 PNG 图片"""
        try:
            import fitz  # PyMuPDF

            doc = fitz.open(file_path)
            page_idx = page.page_number if hasattr(page, 'page_number') else 0
            pdf_page = doc[page_idx]
            pix = pdf_page.get_pixmap(dpi=200)
            image_data = pix.tobytes("png")
            doc.close()
            return image_data
        except ImportError:
            logger.debug("[TextExtract] PyMuPDF 未安装，无法渲染页面")
            return None
        except Exception as e:
            logger.debug(f"[TextExtract] 渲染页面失败: {e}")
            return None

    async def _ocr_page_from_bytes(self, image_data: bytes) -> str:
        """从图片字节数据提取文字"""
        import tempfile
        import cv2
        import numpy as np

        tmp_path = None
        try:
            # 先尝试 MinerU
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                f.write(image_data)
                tmp_path = f.name

            result = await self._extract_with_mineru(tmp_path)
            text = result.get("text", "")
            if text.strip():
                return text

            # MinerU 失败，用 OCR 降级
            return await asyncio.to_thread(self._extract_with_ocr, tmp_path).get("text", "")
        except Exception as e:
            logger.warning(f"[TextExtract] 页面 OCR 失败: {e}")
            return ""
        finally:
            if tmp_path:
                cleanup_temp_file(tmp_path)

    # ── MinerU API 提取 ──────────────────────────────────────

    async def _extract_with_mineru(self, file_path: str) -> dict:
        """使用 MinerU v4 API 提取"""
        if not settings.MINERU_API_KEY:
            raise ValueError("MINERU_API_KEY 未配置")

        headers = {
            "Authorization": f"Bearer {settings.MINERU_API_KEY}",
        }

        # 步骤1：创建任务并上传文件
        async with httpx.AsyncClient(timeout=30) as client:
            with open(file_path, "rb") as f:
                resp = await client.post(
                    "https://mineru.net/api/v4/extract/task",
                    headers=headers,
                    files={"file": (Path(file_path).name, f, "application/pdf")},
                    data={"model_version": "pipeline"},
                )
            resp.raise_for_status()
            data = resp.json()["data"]
            task_id = data["task_id"]

        logger.info(f"[MinerU] 任务: {task_id}")

        # 步骤2：轮询任务状态
        result_data = await self._poll_task_status_v4(task_id, headers, timeout=300, poll_interval=5)

        # 步骤3：下载结果
        full_zip_url = result_data.get("full_zip_url")
        if full_zip_url:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(full_zip_url)
                resp.raise_for_status()
                # 解压获取 markdown
                import zipfile
                import io
                with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
                    # 读取 full.md
                    for name in z.namelist():
                        if name.endswith("full.md"):
                            text = z.read(name).decode("utf-8")
                            logger.info(f"[MinerU] 提取 {len(text)} 字符")
                            return {"text": text, "tables": [], "result_url": full_zip_url}

        return {"text": "", "tables": []}

    async def _poll_task_status_v4(self, task_id: str, headers: dict, timeout: int = 300, poll_interval: int = 5) -> dict:
        """轮询 v4 API 任务状态"""
        start_time = time.time()
        async with httpx.AsyncClient(timeout=30) as client:
            while True:
                if time.time() - start_time > timeout:
                    raise TimeoutError(f"MinerU 超时（{timeout}s）")

                resp = await client.get(
                    f"https://mineru.net/api/v4/extract/task/{task_id}",
                    headers=headers,
                )
                resp.raise_for_status()
                d = resp.json().get("data", {})
                state = d.get("state", "")

                if state == "done":
                    return d
                elif state == "failed":
                    raise RuntimeError(f"MinerU 失败: {d.get('error', '未知')}")
                else:
                    logger.debug(f"[MinerU] 状态: {state}")
                    await asyncio.sleep(poll_interval)

    # ── pdfplumber 本地提取 ──────────────────────────────────

    def _extract_with_pdfplumber(self, file_path: str) -> dict:
        """pdfplumber 本地快速提取"""
        import pdfplumber
        text = ""
        tables = []
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text += (page.extract_text() or "") + "\n"
                page_tables = page.extract_tables()
                if page_tables:
                    tables.extend(page_tables)
        logger.info(f"[pdfplumber] 提取 {len(text)} 字符, {len(tables)} 表格")
        return {"text": text, "tables": tables}

    # ── OCR 降级（图片专用）───────────────────────────────────

    def _extract_with_ocr(self, file_path: str) -> dict:
        """图片 OCR 降级"""
        import cv2

        img = cv2.imread(file_path)
        if img is None:
            return {"text": "", "tables": []}

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        try:
            import pytesseract
            tesseract_cmd = getattr(settings, 'TESSERACT_CMD', None)
            if tesseract_cmd:
                pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
            text = pytesseract.image_to_string(gray, lang='chi_sim+eng')
            if text.strip():
                logger.info(f"[OCR] pytesseract 提取 {len(text)} 字符")
                return {"text": text, "tables": []}
        except Exception:
            pass

        try:
            from paddleocr import PaddleOCR
            ocr = PaddleOCR(use_angle_cls=True, lang='ch', show_log=False)
            result = ocr.ocr(gray, cls=True)
            texts = []
            if result and result[0]:
                for line in result[0]:
                    if line and len(line) >= 2:
                        texts.append(line[1][0])
            text = "\n".join(texts)
            if text.strip():
                logger.info(f"[OCR] PaddleOCR 提取 {len(text)} 字符")
                return {"text": text, "tables": []}
        except Exception:
            pass

        return {"text": "", "tables": []}

    # ── 尺寸提取 ──────────────────────────────────────────────

    def _extract_dimensions(self, text: str) -> list[dict]:
        results = []
        for m in re.finditer(r"(\d+(?:\.\d+)?)\s*[×xX]\s*(\d+(?:\.\d+)?)\s*(mm|cm|m|米|毫米)", text, re.IGNORECASE):
            v1, v2, unit = float(m.group(1)), float(m.group(2)), m.group(3)
            results.append({"type": "composite", "values": [normalize_to_mm(v1, unit), normalize_to_mm(v2, unit)], "unit": "mm"})
        for m in re.finditer(r"(\d+(?:\.\d+)?)\s*[-~]\s*(\d+(?:\.\d+)?)\s*(mm|cm|m|米|毫米)", text, re.IGNORECASE):
            v1, v2, unit = float(m.group(1)), float(m.group(2)), m.group(3)
            results.append({"type": "range", "values": [normalize_to_mm(v1, unit), normalize_to_mm(v2, unit)], "unit": "mm"})
        for m in re.finditer(r"(\d+(?:\.\d+)?)\s*(mm|cm|m|米|毫米)", text, re.IGNORECASE):
            v, unit = float(m.group(1)), m.group(2)
            mm_val = normalize_to_mm(v, unit)
            if 10 <= mm_val <= 100_000:
                results.append({"type": "single", "value": mm_val, "unit": "mm"})
        return results

    # ── 材料关键词 ───────────────────────────────────────────

    def _extract_materials(self, text: str) -> list[str]:
        keywords = ["瓷砖", "涂料", "壁纸", "防水", "石膏板", "木地板", "大理石",
                    "水电", "强电", "弱电", "给水", "排水", "地漏"]
        return [kw for kw in keywords if kw in text]

    # ── 双引擎共识计算 ───────────────────────────────────────

    def _compute_consensus(self, dims_a: list[dict], dims_b: list[dict]) -> tuple[float, list[dict]]:
        """
        双引擎尺寸共识计算
        容差 ±2mm 匹配，共识分 = 匹配数 / 总唯一尺寸数
        """
        values_a = self._flatten_dimensions(dims_a)
        values_b = self._flatten_dimensions(dims_b)

        if not values_a and not values_b:
            return 1.0, []

        matched_a = set()
        matched_b = set()
        for i, va in enumerate(values_a):
            for j, vb in enumerate(values_b):
                if j in matched_b:
                    continue
                if abs(va - vb) <= DIMENSION_TOLERANCE:
                    matched_a.add(i)
                    matched_b.add(j)
                    break

        all_values = set(round(v / 5) * 5 for v in values_a + values_b)
        total_unique = len(all_values) if all_values else 1
        consensus_score = len(matched_a) / total_unique

        diffs = []
        for i, v in enumerate(values_a):
            if i not in matched_a:
                diffs.append({"value_mm": v, "source": "mineru_only"})
        for j, v in enumerate(values_b):
            if j not in matched_b:
                diffs.append({"value_mm": v, "source": "pdfplumber_only"})

        return consensus_score, diffs

    def _flatten_dimensions(self, dims: list[dict]) -> list[float]:
        values = []
        for d in dims:
            if d.get("type") == "single":
                values.append(d["value"])
            elif d.get("type") in ("composite", "range"):
                values.extend(d.get("values", []))
        return values
