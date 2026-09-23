"""数据验证工具函数"""


def validate_dimension_mm(value: float) -> bool:
    """验证尺寸是否在合理范围内（10mm ~ 100m）"""
    return 10 <= value <= 100_000


def validate_area_m2(value: float) -> bool:
    """验证面积是否合理（0.1m² ~ 10000m²）"""
    return 0.1 <= value <= 10_000


def validate_floor_height_mm(value: int) -> bool:
    """验证层高是否合理（2000mm ~ 6000mm）"""
    return 2_000 <= value <= 6_000


def validate_file_size(size_bytes: int, max_mb: int = 100) -> bool:
    """验证文件大小是否在限制内"""
    return 0 < size_bytes <= max_mb * 1024 * 1024


def clamp(value: float, min_val: float, max_val: float) -> float:
    """将值限制在 [min_val, max_val] 范围内"""
    return max(min_val, min(max_val, value))
