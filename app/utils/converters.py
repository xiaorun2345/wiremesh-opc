"""单位转换工具函数"""


def mm_to_m(mm: float) -> float:
    """毫米转米"""
    return round(mm / 1000, 4)


def m_to_mm(m: float) -> int:
    """米转毫米"""
    return int(m * 1000)


def mm2_to_m2(mm2: float) -> float:
    """平方毫米转平方米"""
    return round(mm2 / 1_000_000, 4)


def m2_to_mm2(m2: float) -> float:
    """平方米转平方毫米"""
    return m2 * 1_000_000


def normalize_to_mm(value: float, unit: str) -> float:
    """将任意长度单位统一转换为毫米"""
    unit = unit.lower().strip()
    if unit in ("m", "米"):
        return value * 1000
    elif unit in ("cm", "厘米"):
        return value * 10
    elif unit in ("mm", "毫米"):
        return value
    return value  # 未知单位原样返回
