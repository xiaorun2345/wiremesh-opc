from __future__ import annotations

"""
装修国标条文兜底数据
====================
当 ChromaDB RAG 不可用时，使用内置条文作为兜底。
LLM 根据这些条文判断合规性，并返回对应的条文编号。
"""

# 常用装修国标条文（按领域分类）
COMPLIANCE_STANDARDS = {
    "waterproof": [
        {
            "id": "GB50327-2001-6.3.4",
            "standard_name": "GB50327-2001",
            "section": "第6.3.4条",
            "content": "卫生间、浴室墙面防水层高度不应低于1.8m，厨房间墙面防水层高度不应低于0.3m。",
            "keywords": ["防水", "卫生间", "浴室", "墙面", "1.8m", "厨房", "0.3m"],
        },
        {
            "id": "GB50210-2018-7.2.3",
            "standard_name": "GB50210-2018",
            "section": "第7.2.3条",
            "content": "有防水要求的楼地面工程，防水层完成后应进行蓄水试验，蓄水深度不应小于20mm，蓄水时间不应少于24h。",
            "keywords": ["防水", "蓄水试验", "楼地面", "24h"],
        },
        {
            "id": "GB50327-2001-6.3.6",
            "standard_name": "GB50327-2001",
            "section": "第6.3.6条",
            "content": "防水层施工完成后，应进行淋水或蓄水检验，不得有渗漏现象。",
            "keywords": ["防水层", "检验", "渗漏"],
        },
    ],
    "electrical": [
        {
            "id": "GB50303-2015-5.1.2",
            "standard_name": "GB50303-2015",
            "section": "第5.1.2条",
            "content": "住宅配电箱应设置漏电保护装置，漏电保护器动作电流不应大于30mA，动作时间不应大于0.1s。",
            "keywords": ["漏电保护", "配电箱", "30mA", "0.1s"],
        },
        {
            "id": "GB50303-2015-12.3.4",
            "standard_name": "GB50303-2015",
            "section": "第12.3.4条",
            "content": "厨房、卫生间等潮湿场所的插座应采用防溅型插座，安装高度不应低于1.5m。",
            "keywords": ["厨房", "卫生间", "防溅插座", "潮湿"],
        },
        {
            "id": "GB50303-2015-6.2.1",
            "standard_name": "GB50303-2015",
            "section": "第6.2.1条",
            "content": "住宅电气线路应采用铜芯导线，照明回路导线截面不应小于1.5mm²，插座回路导线截面不应小于2.5mm²。",
            "keywords": ["铜芯导线", "1.5mm²", "2.5mm²", "照明", "插座"],
        },
    ],
    "plumbing": [
        {
            "id": "GB50242-2002-4.2.1",
            "standard_name": "GB50242-2002",
            "section": "第4.2.1条",
            "content": "给水管道必须采用与管材相适应的管件，生活给水系统所涉及的材料必须达到饮用水卫生标准。",
            "keywords": ["给水管道", "管件", "饮用水", "卫生标准"],
        },
        {
            "id": "GB50242-2002-5.2.3",
            "standard_name": "GB50242-2002",
            "section": "第5.2.3条",
            "content": "排水管道安装完成后，应进行通球试验，排水应畅通，无堵塞、无渗漏。",
            "keywords": ["排水管道", "通球试验", "畅通", "渗漏"],
        },
    ],
    "general": [
        {
            "id": "GB50210-2018-3.3.2",
            "standard_name": "GB50210-2018",
            "section": "第3.3.2条",
            "content": "墙面抹灰工程中，不同材料基体交接处表面的抹灰，应采取防止开裂的加强措施。",
            "keywords": ["抹灰", "开裂", "加强措施"],
        },
        {
            "id": "GB50210-2018-4.2.5",
            "standard_name": "GB50210-2018",
            "section": "第4.2.5条",
            "content": "饰面砖粘贴应牢固，满贴法施工的饰面砖工程应无空鼓、无裂缝。",
            "keywords": ["饰面砖", "粘贴", "空鼓", "裂缝"],
        },
    ],
}


def get_all_standards() -> list:
    """获取所有国标条文（扁平化列表）"""
    all_standards = []
    for category, standards in COMPLIANCE_STANDARDS.items():
        all_standards.extend(standards)
    return all_standards


def get_standards_by_category(category: str) -> list:
    """按类别获取国标条文"""
    return COMPLIANCE_STANDARDS.get(category, [])


def get_standard_by_id(standard_id: str) -> dict | None:
    """根据条文 ID 查找条文"""
    for standards in COMPLIANCE_STANDARDS.values():
        for s in standards:
            if s["id"] == standard_id:
                return s
    return None


def format_standard_ref(standard: dict) -> str:
    """格式化条文引用为 '标准名 + 条款号' 格式"""
    return f"{standard['standard_name']} {standard['section']}"
