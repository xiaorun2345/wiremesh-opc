"""图片内容分析器 — 基于 OpenCV 的本地分类，< 500ms，不调 LLM"""
import io
import math
import cv2
import numpy as np
from loguru import logger


class ImageAnalyzer:
    """
    分类图片内容为三种类型：
    - document_scan: 文档扫描件（文字为主，> 15% 文字覆盖率）
    - structural_blueprint: 结构图/平面图（线条密集，直线占比高，2-15% 文字）
    - rendering_photo: 效果图/照片（色彩丰富，曲线/有机边缘为主）

    所有操作均为本地 OpenCV/PIL 计算，总耗时 < 500ms。
    """

    # 分类阈值
    TEXT_HIGH = 0.15      # 文字覆盖率 > 15% → 文档
    TEXT_LOW = 0.02       # 文字覆盖率 < 2%  → 照片/效果图（配合低边缘密度）
    EDGE_BLUEPRINT_MIN = 0.05   # 边缘密度下限（结构图）
    LINE_STRAIGHT_RATIO = 0.60  # 直线占比 > 60% → 结构图
    COLOR_VARIANCE_THRESHOLD = 30  # 色彩方差阈值

    def classify(self, image_data: bytes) -> dict:
        """
        分类图片内容类型。
        返回: {"content_type": str, "confidence": float, "metrics": dict}
        """
        import cv2
        from PIL import Image

        # Phase 1: PIL 元数据
        try:
            pil_img = Image.open(io.BytesIO(image_data))
            width, height = pil_img.size
            aspect_ratio = max(width, height) / min(width, height)
            mode = pil_img.mode  # RGB, L, P 等
        except Exception as e:
            logger.warning(f"[ImageAnalyzer] PIL 解析失败: {e}")
            return self._fallback_result("document_scan", 0.5)

        # Phase 2: OpenCV 结构分析
        try:
            nparr = np.frombuffer(image_data, np.uint8)
            cv_img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if cv_img is None:
                return self._fallback_result("document_scan", 0.5)

            gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
            h, w = gray.shape[:2]
            total_pixels = w * h

            # 2a. 色彩分析（使用灰度图方差，非 RGB 通道方差）
            color_variance = float(np.std(gray))

            # 2b. 边缘检测
            edges = cv2.Canny(gray, 50, 150)
            edge_density = cv2.countNonZero(edges) / total_pixels

            # 2c. 直线检测（Hough）
            lines = cv2.HoughLines(edges, 1, np.pi / 180, threshold=80)
            line_count = len(lines) if lines is not None else 0
            # 归一化到图像面积
            line_density = line_count / max(total_pixels / 10000, 1)

            # 2d. 轮廓分析（矩形度）
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            rect_ratio = self._measure_rectangularity(contours)

        except Exception as e:
            logger.warning(f"[ImageAnalyzer] OpenCV 分析失败: {e}")
            return self._fallback_result("document_scan", 0.5)

        # Phase 3: OCR 文字密度估算（快速，非完整 OCR）
        text_density = self._estimate_text_coverage(gray, w, h)

        # 计算三类得分
        doc_score = self._calc_doc_score(text_density, edge_density, rect_ratio)
        blueprint_score = self._calc_blueprint_score(text_density, edge_density, line_density, rect_ratio, color_variance)
        rendering_score = self._calc_rendering_score(text_density, edge_density, color_variance)

        # 决策
        scores = {
            "document_scan": doc_score,
            "structural_blueprint": blueprint_score,
            "rendering_photo": rendering_score,
        }
        best_type = max(scores, key=scores.get)
        total_score = sum(scores.values())
        confidence = scores[best_type] / total_score if total_score > 0 else 0.5

        metrics = {
            "text_density": round(text_density, 4),
            "edge_density": round(edge_density, 4),
            "line_density": round(line_density, 4),
            "rect_ratio": round(rect_ratio, 4),
            "color_variance": round(color_variance, 2),
            "image_size": f"{width}x{height}",
        }

        logger.info(
            f"[ImageAnalyzer] 分类={best_type}, 置信度={confidence:.0%}, "
            f"文字={text_density:.1%}, 边缘={edge_density:.1%}, 直线密度={line_density:.2f}"
        )

        return {
            "content_type": best_type,
            "confidence": round(confidence, 4),
            "metrics": metrics,
        }

    def _measure_rectangularity(self, contours: list) -> float:
        """
        测量轮廓的矩形度：矩形轮廓面积 / 总轮廓面积。
        结构图通常有大量矩形（房间、门窗），矩形度高。
        """
        if not contours:
            return 0.0

        total_area = sum(cv2.contourArea(c) for c in contours)
        if total_area == 0:
            return 0.0

        rect_area = 0.0
        for c in contours:
            area = cv2.contourArea(c)
            if area < 50:  # 过滤噪声
                continue
            _, radius = cv2.minEnclosingCircle(c)
            circle_area = math.pi * radius * 2 if radius > 0 else 0
            if circle_area > 0:
                # 矩形度近似：轮廓面积 / 最小外接圆面积
                rect_area += min(area / circle_area, 1.0) * area

        return rect_area / total_area

    def _estimate_text_coverage(self, gray: np.ndarray, w: int, h: int) -> float:
        """
        快速估算文字覆盖率。
        使用自适应阈值找文字类矩形 blob，测量面积占比。
        比完整 OCR 快得多，足够用于分类。
        """
        import cv2

        # 自适应阈值（模拟 OCR 的文字区域检测）
        adaptive = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                         cv2.THRESH_BINARY_INV, blockSize=15, C=8)

        # 形态学闭运算连接文字笔画
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        closed = cv2.morphologyEx(adaptive, cv2.MORPH_CLOSE, kernel, iterations=2)

        # 找连通区域
        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        text_area = 0
        total_pixels = w * h
        for c in contours:
            area = cv2.contourArea(c)
            # 文字区域通常较小（10-5000 像素）
            if 10 < area < 5000:
                x, y, cw, ch = cv2.boundingRect(c)
                aspect = cw / ch if ch > 0 else 0
                # 文字的宽高比通常在 0.1-10 之间（排除极长极窄的线条）
                if 0.1 < aspect < 10:
                    text_area += area

        return text_area / total_pixels if total_pixels > 0 else 0.0

    def _calc_doc_score(self, text_density: float, edge_density: float, rect_ratio: float) -> float:
        """文档扫描件得分：文字密度主导"""
        # 文字覆盖率 > 10% 强烈指示文档
        text_score = min(text_density / 0.10, 1.0)
        # 文档通常边缘密度中等，不会太高
        edge_score = max(0, 1 - edge_density / 0.15)
        return text_score * 0.7 + edge_score * 0.2 + (1 - rect_ratio) * 0.1

    def _calc_blueprint_score(self, text_density: float, edge_density: float,
                              line_density: float, rect_ratio: float, color_var: float) -> float:
        """结构图得分：高直线密度 + 高边缘密度 + 低色彩方差"""
        # 直线密度是结构图最强指标（> 5 强烈指示结构图）
        line_score = min(line_density / 10.0, 1.0)

        # 边缘密度在 3%-15% 之间最像结构图
        edge_score = 1.0 - abs(edge_density - 0.07) / 0.07
        edge_score = max(0, edge_score)

        # 低文字（结构图文字少）
        text_score = max(0, 1 - text_density / 0.03)

        # 灰度方差中等（黑白图方差高，彩色图方差也高，结构图适中）
        # 黑白结构图的灰度方差通常在 50-120 之间
        if 40 < color_var < 130:
            color_score = 0.5  # 中性
        elif color_var < 40:
            color_score = 0.8  # 低方差（均匀灰度）
        else:
            color_score = 0.2  # 极高方差（照片/效果图）

        return line_score * 0.45 + edge_score * 0.30 + text_score * 0.10 + color_score * 0.15

    def _calc_rendering_score(self, text_density: float, edge_density: float, color_var: float) -> float:
        """效果图/照片得分：低文字 + 低/无边缘 + 高色彩"""
        text_score = max(0, 1 - text_density / 0.05)
        # 效果图可能有中等边缘（但不像结构图那么密集规则）
        edge_score = max(0, 1 - abs(edge_density - 0.03) / 0.03) if edge_density < 0.06 else 0
        color_score = min(color_var / 50, 1.0)
        return text_score * 0.3 + edge_score * 0.2 + color_score * 0.5

    def _fallback_result(self, content_type: str, confidence: float) -> dict:
        """分析失败时的降级结果"""
        return {
            "content_type": content_type,
            "confidence": confidence,
            "metrics": {"error": "analysis_failed"},
        }
