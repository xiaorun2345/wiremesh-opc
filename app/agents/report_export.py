import io
import uuid
from datetime import datetime
from loguru import logger
from jinja2 import Environment, BaseLoader
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.chart import PieChart, BarChart, Reference
from openpyxl.chart.series import DataPoint
from openpyxl.chart.label import DataLabelList

from app.core.memory.redis_memory import TaskMemory
from app.core.skill.price_catalog import build_cost_summary, build_room_details
from app.services.minio_service import MinioService
from app.models.report import Report
from config.settings import settings

PDF_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><title>{{ report_title }}</title>
<style>
  body { font-family: "Microsoft YaHei", sans-serif; margin: 40px; color: #333; }
  h1 { color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }
  h2 { color: #2980b9; margin-top: 30px; }
  h3 { color: #34495e; margin-top: 20px; }
  table { width: 100%; border-collapse: collapse; margin: 15px 0; }
  th { background: #3498db; color: white; padding: 10px; text-align: left; }
  td { padding: 8px 10px; border-bottom: 1px solid #eee; }
  tr:nth-child(even) { background: #f8f9fa; }
  .issue { color: #e74c3c; font-weight: bold; }
  .pass  { color: #27ae60; font-weight: bold; }
  .total { font-weight: bold; background: #e8f4fd; }
  .footer { margin-top: 40px; color: #999; font-size: 12px; }
  .company { color: #666; font-size: 14px; margin-bottom: 5px; }
</style></head>
<body>
{% if company %}<p class="company">{{ company }}</p>{% endif %}
<h1>{{ report_title }}</h1>
<p>任务编号：{{ task_id }} &nbsp;|&nbsp; 生成时间：{{ generated_at }}</p>

<h2>一、费用汇总</h2>
<table>
  <tr><th>项目</th><th>工程量</th><th>单位</th><th>单价（元）</th><th>合计（元）</th></tr>
{% for cat in cost_summary.categories %}
  <tr>
    <td>{{ cat.name }}</td>
    <td>{{ cat.quantity }}</td>
    <td>{{ cat.unit }}</td>
    <td>{% if cat.unit_price > 0 %}{{ cat.unit_price }}{% else %}—{% endif %}</td>
    <td><b>{{ cat.total }}</b></td>
  </tr>
{% if cat.details %}
{% for d in cat.details %}
  <tr style="color:#666;">
    <td>&nbsp;&nbsp;&nbsp;&nbsp;{{ d.name }}</td>
    <td>{{ d.quantity }}</td>
    <td>{{ d.unit }}</td>
    <td>{{ d.unit_price }}</td>
    <td>{{ d.total }}</td>
  </tr>
{% endfor %}
{% endif %}
{% endfor %}
  <tr class="total">
    <td><b>总计</b></td>
    <td></td>
    <td></td>
    <td></td>
    <td><b>{{ cost_summary.grand_total }} 元</b></td>
  </tr>
</table>

<h2>二、工程量清单</h2>
<h3>2.1 墙面</h3>
<table>
  <tr><th>项目</th><th>数值</th><th>单位</th></tr>
  <tr><td>墙面毛面积</td><td>{{ qty.wall.gross_area_m2 | default(0) }}</td><td>m²</td></tr>
  <tr><td>扣除门洞</td><td>{{ qty.wall.door_deduction_m2 | default(0) }}</td><td>m²</td></tr>
  <tr><td>扣除窗洞</td><td>{{ qty.wall.window_deduction_m2 | default(0) }}</td><td>m²</td></tr>
  <tr><td>墙面净面积</td><td>{{ qty.wall.net_area_m2 | default(0) }}</td><td>m²</td></tr>
  <tr><td>损耗系数</td><td>{{ qty.wall.loss_factor | default(1.0) }}</td><td></td></tr>
  <tr><td><b>合计面积</b></td><td><b>{{ qty.wall.total_area_m2 | default(0) }}</b></td><td>m²</td></tr>
</table>

<h3>2.2 地面</h3>
<table>
  <tr><th>项目</th><th>数值</th><th>单位</th></tr>
  <tr><td>地面净面积</td><td>{{ qty.floor.net_area_m2 | default(0) }}</td><td>m²</td></tr>
  <tr><td>损耗系数</td><td>{{ qty.floor.loss_factor | default(1.0) }}</td><td></td></tr>
  <tr><td><b>合计面积</b></td><td><b>{{ qty.floor.total_area_m2 | default(0) }}</b></td><td>m²</td></tr>
</table>

<h3>2.3 水电点位</h3>
<table>
  <tr><th>类型</th><th>数量</th><th>单位</th></tr>
  <tr><td>强电点位</td><td>{{ qty.water_elec.strong_elec | default(0) }}</td><td>个</td></tr>
  <tr><td>弱电点位</td><td>{{ qty.water_elec.weak_elec | default(0) }}</td><td>个</td></tr>
  <tr><td>给水点位</td><td>{{ qty.water_elec.water_supply | default(0) }}</td><td>个</td></tr>
  <tr><td>排水点位</td><td>{{ qty.water_elec.drainage | default(0) }}</td><td>个</td></tr>
  <tr><td><b>合计</b></td><td><b>{{ qty.water_elec.total_points | default(0) }}</b></td><td>个</td></tr>
</table>

<h3>2.4 防水</h3>
<table>
  <tr><th>项目</th><th>数值</th><th>单位</th></tr>
  <tr><td>防水地面面积</td><td>{{ qty.waterproof.floor_area_m2 | default(0) }}</td><td>m²</td></tr>
  <tr><td>防水墙面面积</td><td>{{ qty.waterproof.wall_area_m2 | default(0) }}</td><td>m²</td></tr>
  <tr><td><b>防水总面积</b></td><td><b>{{ qty.waterproof.total_area_m2 | default(0) }}</b></td><td>m²</td></tr>
</table>

{% if room_details %}
<h2>三、房间面积明细</h2>
<table>
  <tr><th>房间名称</th><th>面积（m²）</th><th>估算费用（元）</th></tr>
{% for room in room_details %}
  <tr>
    <td>{{ room.name }}</td>
    <td>{{ room.area_m2 }}</td>
    <td>{{ room.estimated_cost }}</td>
  </tr>
{% endfor %}
</table>
{% endif %}

<h2>四、合规审核结论</h2>
{% if compliance.passed %}
<p class="pass">[通过] 审核通过，未发现合规问题。</p>
{% else %}
<p class="issue">[问题] 发现 {{ compliance.issues | length }} 条合规问题：</p>
<table>
  <tr><th style="width:40%;">问题描述</th><th style="width:35%;">整改建议</th><th style="width:25%;">依据条文</th></tr>
{% for item in compliance.issues %}
  {% if item is mapping %}
  <tr>
    <td class="issue">{{ item.issue }}</td>
    <td>{{ item.suggestion or '—' }}</td>
    <td style="font-size:11px;color:#718096;">{{ item.ref or '—' }}</td>
  </tr>
  {% else %}
  <tr><td class="issue" colspan="3">{{ item }}</td></tr>
  {% endif %}
{% endfor %}
</table>
{% endif %}

<div class="footer">
  <p>本报告由 AI 算量平台自动生成，仅供参考，不作为法律依据。</p>
</div>
</body></html>
"""


async def export_report(trace_id: str) -> dict:
    """
    报告导出（Excel + PDF）。
    从 TaskMemory 读取算量、合规和价格结果，生成带图表的完整报告并上传 MinIO，写入数据库。
    """
    mem = TaskMemory(trace_id)
    quantity_list  = await mem.get("quantity_list",     {})
    compliance     = await mem.get("compliance_report", {"passed": True, "issues": []})
    price_list     = await mem.get("price_list",        None)  # 可选覆盖价格
    rooms          = await mem.get("rooms",             [])

    # 构建费用汇总和房间明细
    cost_summary  = build_cost_summary(quantity_list, override_prices=price_list)
    room_details  = build_room_details(rooms)

    minio = MinioService()

    # 生成 Excel（含图表）
    excel_data = _build_excel(quantity_list, cost_summary, room_details, compliance, trace_id)
    excel_path = f"reports/{trace_id}/report.xlsx"
    minio.upload(excel_path, excel_data, "report.xlsx")

    # 生成 PDF
    html_data = _build_html(quantity_list, cost_summary, room_details, compliance, trace_id)
    pdf_data = _html_to_pdf(html_data)
    pdf_path  = f"reports/{trace_id}/report.pdf"
    minio.upload(pdf_path, pdf_data, "report.pdf")

    # 写入 reports 表
    import app.utils.db as db_module
    async with db_module.AsyncSessionLocal() as db:
        report = Report(
            id=str(uuid.uuid4()),
            task_id=trace_id,
            pdf_path=pdf_path,
            excel_path=excel_path,
        )
        db.add(report)
        await db.commit()

    logger.info(f"[ReportExport] 报告生成完成: {trace_id}, 总费用={cost_summary['grand_total']}元")
    return {"pdf_path": pdf_path, "excel_path": excel_path, "grand_total": cost_summary["grand_total"]}


def _build_html(qty: dict, cost_summary: dict, room_details: list, compliance: dict, task_id: str) -> str:
    env = Environment(loader=BaseLoader())
    tmpl = env.from_string(PDF_TEMPLATE)
    return tmpl.render(
        task_id=task_id,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        report_title=settings.REPORT_TITLE,
        company=settings.REPORT_COMPANY if settings.REPORT_COMPANY else None,
        qty=qty,
        cost_summary=cost_summary,
        room_details=room_details,
        compliance=compliance,
    )


def _html_to_pdf(html_content: str) -> bytes:
    """将 HTML 转换为真正的 PDF 文件（使用 reportlab，支持中文，优化排版审美）"""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.lib.colors import HexColor
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from bs4 import BeautifulSoup
        import re
        import os

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=25*mm,
            rightMargin=25*mm,
            topMargin=25*mm,
            bottomMargin=25*mm,
        )

        story = []
        styles = getSampleStyleSheet()

        # 注册中文字体
        font_registered = False
        font_candidates = [
            ("C:/Windows/Fonts/msyh.ttc", "msyh", 0),       # 微软雅黑
            ("C:/Windows/Fonts/simhei.ttf", "simhei", 0),    # 黑体
            ("C:/Windows/Fonts/simsun.ttc", "simsun", 0),    # 宋体
        ]
        for font_path, font_name, font_index in font_candidates:
            if os.path.exists(font_path):
                try:
                    pdfmetrics.registerFont(TTFont(font_name, font_path, subfontIndex=font_index))
                    font_registered = True
                    break
                except Exception:
                    continue

        if not font_registered:
            font_name = "Helvetica"

        # 颜色定义（与 Excel 统一）
        TITLE_COLOR = HexColor('#2B5E3B')  # 深森林绿
        HEADING_COLOR = HexColor('#2B5E3B')
        SUBHEADING_COLOR = HexColor('#5C6A6E')
        BODY_COLOR = HexColor('#1E2A2E')
        HEADER_BG = HexColor('#f7fafc')
        ROW_ALT_BG = HexColor('#F9F7F3')  # 浅米色
        BORDER_COLOR = HexColor('#D4DCD9')  # 浅灰绿
        TOTAL_BG = HexColor('#E8F0EB')  # 浅绿
        ISSUE_COLOR = HexColor('#e53e3e')
        PASS_COLOR = HexColor('#38a169')

        # 标题样式
        styles.add(ParagraphStyle(
            name='RptTitle',
            parent=styles['Title'],
            fontName=font_name,
            fontSize=20,
            spaceAfter=6*mm,
            textColor=TITLE_COLOR,
            alignment=TA_LEFT,
        ))

        # 一级标题（章节）
        styles.add(ParagraphStyle(
            name='RptHeading1',
            parent=styles['Heading1'],
            fontName=font_name,
            fontSize=14,
            spaceBefore=8*mm,
            spaceAfter=4*mm,
            textColor=HEADING_COLOR,
            borderWidth=0,
            borderPadding=0,
        ))

        # 二级标题
        styles.add(ParagraphStyle(
            name='RptHeading2',
            parent=styles['Heading2'],
            fontName=font_name,
            fontSize=11,
            spaceBefore=5*mm,
            spaceAfter=3*mm,
            textColor=SUBHEADING_COLOR,
        ))

        # 正文
        styles.add(ParagraphStyle(
            name='RptBody',
            parent=styles['Normal'],
            fontName=font_name,
            fontSize=10,
            spaceAfter=2*mm,
            leading=16,
            textColor=BODY_COLOR,
        ))

        # 任务信息
        styles.add(ParagraphStyle(
            name='RptTaskInfo',
            parent=styles['Normal'],
            fontName=font_name,
            fontSize=9,
            spaceAfter=6*mm,
            textColor=HexColor('#718096'),
        ))

        # 通过/问题
        styles.add(ParagraphStyle(
            name='RptPass',
            parent=styles['Normal'],
            fontName=font_name,
            fontSize=10,
            spaceAfter=3*mm,
            textColor=PASS_COLOR,
        ))
        styles.add(ParagraphStyle(
            name='RptIssue',
            parent=styles['Normal'],
            fontName=font_name,
            fontSize=10,
            spaceAfter=3*mm,
            textColor=ISSUE_COLOR,
        ))

        # 页脚
        styles.add(ParagraphStyle(
            name='RptFooter',
            parent=styles['Normal'],
            fontName=font_name,
            fontSize=8,
            textColor=HexColor('#a0aec0'),
            alignment=TA_CENTER,
        ))

        # 智能解析 HTML
        soup = BeautifulSoup(html_content, 'html.parser')

        # 标题
        title = settings.REPORT_TITLE or "装修算量与审核报告"
        story.append(Paragraph(title, styles['RptTitle']))
        story.append(Spacer(1, 2*mm))

        # 任务信息（分割线效果）
        task_info = soup.find('p')
        if task_info:
            story.append(Paragraph(task_info.get_text(), styles['RptTaskInfo']))
            # 添加一条细线
            line_table = Table([['']], colWidths=[150*mm])
            line_table.setStyle(TableStyle([
                ('LINEBELOW', (0, 0), (-1, 0), 0.5, BORDER_COLOR),
                ('TOPPADDING', (0, 0), (-1, 0), 0),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 5*mm),
            ]))
            story.append(line_table)

        # 处理章节
        for element in soup.find_all(['h2', 'h3', 'table', 'p']):
            if element.name == 'h2':
                story.append(Paragraph(element.get_text(), styles['RptHeading1']))
            elif element.name == 'h3':
                story.append(Paragraph(element.get_text(), styles['RptHeading2']))
            elif element.name == 'table':
                # 解析表格并应用优化样式
                rows_data = []
                for tr in element.find_all('tr'):
                    row = []
                    for cell in tr.find_all(['th', 'td']):
                        row.append(cell.get_text().strip() or "—")
                    if row:
                        rows_data.append(row)

                if rows_data:
                    max_cols = max(len(r) for r in rows_data)
                    for r in rows_data:
                        while len(r) < max_cols:
                            r.append("—")

                    # 列宽自适应（合规审核表格特殊处理）
                    is_compliance_table = any('问题描述' in str(r[0]) or '整改建议' in str(r[0]) for r in rows_data[:1])
                    if is_compliance_table and max_cols == 3:
                        # 合规审核：40% / 35% / 25%
                        table_width = 155*mm
                        col_widths = [table_width * 0.40, table_width * 0.35, table_width * 0.25]
                    else:
                        # 普通表格：均分
                        col_width = 35*mm
                        table_width = min(max_cols * col_width, 155*mm)
                        col_widths = [table_width / max_cols] * max_cols

                    table = Table(rows_data, colWidths=col_widths, repeatRows=1)

                    # 构建表格样式（极简风格：水平线为主）
                    table_style = [
                        # 表头样式
                        ('BACKGROUND', (0, 0), (-1, 0), HEADER_BG),
                        ('TEXTCOLOR', (0, 0), (-1, 0), HexColor('#5F6B7A')),
                        ('FONTNAME', (0, 0), (-1, 0), font_name),
                        ('FONTSIZE', (0, 0), (-1, 0), 9),
                        ('FONTWEIGHT', (0, 0), (-1, 0), 'BOLD'),
                        ('ALIGN', (0, 0), (-1, 0), 'LEFT'),
                        ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),

                        # 内容样式
                        ('FONTNAME', (0, 1), (-1, -1), font_name),
                        ('FONTSIZE', (0, 1), (-1, -1), 9),
                        ('TEXTCOLOR', (0, 1), (-1, -1), BODY_COLOR),
                        ('VALIGN', (0, 1), (-1, -1), 'MIDDLE'),

                        # 对齐：最后一列（数字/金额）右对齐，其余左对齐
                        ('ALIGN', (max_cols - 1, 1), (max_cols - 1, -1), 'RIGHT'),

                        # 边框：仅水平线
                        ('LINEBELOW', (0, 0), (-1, 0), 1, BORDER_COLOR),  # 表头下
                        ('LINEBELOW', (0, 1), (-1, -1), 0.5, BORDER_COLOR),  # 行间
                        ('LINEBELOW', (0, -1), (-1, -1), 1, BORDER_COLOR),  # 表尾

                        # 间距
                        ('TOPPADDING', (0, 0), (-1, -1), 10),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
                        ('LEFTPADDING', (0, 0), (-1, -1), 12),
                        ('RIGHTPADDING', (0, 0), (-1, -1), 12),
                        ('WORDWRAP', (0, 0), (-1, -1), True),
                    ]

                    # 斑马纹（极浅灰交替）
                    for i in range(1, len(rows_data)):
                        if i % 2 == 0:
                            table_style.append(('BACKGROUND', (0, i), (-1, i), ROW_ALT_BG))

                    # 检测"总计"行
                    for i, row in enumerate(rows_data):
                        if any('总计' in str(cell) or '合计' in str(cell) for cell in row):
                            table_style.extend([
                                ('BACKGROUND', (0, i), (-1, i), TOTAL_BG),
                                ('FONTWEIGHT', (0, i), (-1, i), 'BOLD'),
                                ('FONTSIZE', (0, i), (-1, i), 10),
                            ])

                    table.setStyle(TableStyle(table_style))
                    story.append(table)
                    story.append(Spacer(1, 4*mm))
            elif element.name == 'p':
                text = element.get_text().strip()
                if text:
                    cls = element.get('class', [])
                    if 'pass' in cls:
                        story.append(Paragraph(f"[通过] {text}", styles['RptPass']))
                    elif 'issue' in cls:
                        story.append(Paragraph(f"[问题] {text}", styles['RptIssue']))
                    else:
                        story.append(Paragraph(text, styles['RptBody']))
                    story.append(Spacer(1, 2*mm))

        # 页脚（留白 + 免责声明）
        story.append(Spacer(1, 8*mm))
        line_table2 = Table([['']], colWidths=[150*mm])
        line_table2.setStyle(TableStyle([
            ('LINEABOVE', (0, 0), (-1, 0), 0.5, BORDER_COLOR),
            ('TOPPADDING', (0, 0), (-1, 0), 5*mm),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 0),
        ]))
        story.append(line_table2)
        story.append(Spacer(1, 3*mm))
        story.append(Paragraph("本报告由 AI 算量平台自动生成，仅供参考，不作为法律依据。", styles['RptFooter']))

        doc.build(story)
        return buffer.getvalue()

    except Exception as e:
        logger.error(f"PDF 转换失败: {e}")
        return html_content.encode("utf-8")


# ─── Excel 样式常量（装修行业配色）────────────────────────────────
# 主色：深森林绿 #2B5E3B
# 辅色：暖木色 #D9B48B
# 强调色：暖橙 #E89F3E
# 背景：米白 #F2E8D5 / 浅米 #F9F7F3
# 边框：浅灰绿 #D4DCD9

HEADER_FONT = Font(bold=True, color="FFFFFF", size=12)
HEADER_FILL = PatternFill("solid", fgColor="2B5E3B")  # 深森林绿表头
TITLE_FONT  = Font(bold=True, size=14, color="2B5E3B")  # 深绿标题
SUBTITLE_FONT = Font(bold=True, size=11, color="5C6A6E")  # 浅灰副标题
TOTAL_FILL  = PatternFill("solid", fgColor="E8F0EB")  # 浅绿总计行
TOTAL_FONT = Font(bold=True, size=11, color="2B5E3B")
BORDER_COLOR = "D4DCD9"  # 浅灰绿边框
ROW_ALT_FILL = PatternFill("solid", fgColor="F9F7F3")  # 斑马纹浅米
BORDER      = Border(
    bottom=Side(style='thin', color=BORDER_COLOR),
)
HEADER_BORDER = Border(
    bottom=Side(style='medium', color="2B5E3B"),
)

# 图表配色
CHART_COLORS = [
    "2B5E3B",  # 深森林绿（主材费）
    "5B8A62",  # 中绿（人工费）
    "8EAA8C",  # 浅绿（辅材费）
    "D9B48B",  # 暖木色（设计/管理费）
    "E89F3E",  # 暖橙（其他/意外）
]


def _apply_header(ws, row: int, headers: list):
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=row, column=col, value=h)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = Border(
            left=Side(style='thin', color=BORDER_COLOR),
            right=Side(style='thin', color=BORDER_COLOR),
            top=Side(style='thin', color=BORDER_COLOR),
            bottom=Side(style='medium', color="1A3D26"),
        )
    ws.row_dimensions[row].height = 28


def _apply_border(ws, start_row: int, end_row: int, max_col: int, alt_rows: bool = True):
    for r in range(start_row, end_row + 1):
        for c in range(1, max_col + 1):
            cell = ws.cell(row=r, column=c)
            cell.border = Border(bottom=Side(style='thin', color=BORDER_COLOR))
            if alt_rows and (r - start_row) % 2 == 1:
                cell.fill = ROW_ALT_FILL
        ws.row_dimensions[r].height = 26


def _build_excel(qty: dict, cost_summary: dict, room_details: list, compliance: dict, task_id: str) -> bytes:
    wb = Workbook()

    # ── Sheet 1: 工程量清单 ──────────────────────────────────────
    ws1 = wb.active
    ws1.title = "工程量清单"
    ws1.sheet_properties.pageSetUpPr.fitToPage = True
    ws1.cell(row=1, column=1, value="工程量清单").font = TITLE_FONT
    ws1.cell(row=2, column=1, value=f"任务编号：{task_id}  |  生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}").font = Font(size=10, color="5C6A6E")

    row = 4
    _apply_header(ws1, row, ["分类", "项目", "数值", "单位"])
    row += 1

    # 墙面
    wall = qty.get("wall", {})
    for label, key in [("墙面毛面积", "gross_area_m2"), ("扣除门洞", "door_deduction_m2"), ("扣除窗洞", "window_deduction_m2"), ("墙面净面积", "net_area_m2"), ("合计面积（含损耗）", "total_area_m2")]:
        ws1.cell(row=row, column=1, value="墙面")
        ws1.cell(row=row, column=2, value=label)
        ws1.cell(row=row, column=3, value=wall.get(key, 0))
        ws1.cell(row=row, column=4, value="m²")
        ws1.cell(row=row, column=3).number_format = '#,##0.00'
        ws1.cell(row=row, column=3).alignment = Alignment(horizontal='right')
        row += 1

    # 地面
    floor = qty.get("floor", {})
    for label, key in [("地面净面积", "net_area_m2"), ("合计面积（含损耗）", "total_area_m2")]:
        ws1.cell(row=row, column=1, value="地面")
        ws1.cell(row=row, column=2, value=label)
        ws1.cell(row=row, column=3, value=floor.get(key, 0))
        ws1.cell(row=row, column=4, value="m²")
        ws1.cell(row=row, column=3).number_format = '#,##0.00'
        ws1.cell(row=row, column=3).alignment = Alignment(horizontal='right')
        row += 1

    # 水电
    we = qty.get("water_elec", {})
    for label, key in [("强电点位", "strong_elec"), ("弱电点位", "weak_elec"), ("给水点位", "water_supply"), ("排水点位", "drainage"), ("合计", "total_points")]:
        ws1.cell(row=row, column=1, value="水电")
        ws1.cell(row=row, column=2, value=label)
        ws1.cell(row=row, column=3, value=we.get(key, 0))
        ws1.cell(row=row, column=4, value="个")
        ws1.cell(row=row, column=3).alignment = Alignment(horizontal='right')
        row += 1

    # 防水
    wp = qty.get("waterproof", {})
    for label, key in [("防水地面面积", "floor_area_m2"), ("防水墙面面积", "wall_area_m2"), ("防水总面积", "total_area_m2")]:
        ws1.cell(row=row, column=1, value="防水")
        ws1.cell(row=row, column=2, value=label)
        ws1.cell(row=row, column=3, value=wp.get(key, 0))
        ws1.cell(row=row, column=4, value="m²")
        ws1.cell(row=row, column=3).number_format = '#,##0.00'
        ws1.cell(row=row, column=3).alignment = Alignment(horizontal='right')
        row += 1

    _apply_border(ws1, 4, row - 1, 4)
    ws1.column_dimensions['A'].width = 14
    ws1.column_dimensions['B'].width = 24
    ws1.column_dimensions['C'].width = 16
    ws1.column_dimensions['D'].width = 10

    # ── Sheet 2: 费用汇总 ────────────────────────────────────────
    ws2 = wb.create_sheet("费用汇总")
    ws2.sheet_properties.pageSetUpPr.fitToPage = True
    ws2.cell(row=1, column=1, value="费用汇总表").font = TITLE_FONT
    ws2.cell(row=2, column=1, value=f"任务编号：{task_id}").font = Font(size=10, color="5C6A6E")

    row = 4
    _apply_header(ws2, row, ["项目", "工程量", "单位", "单价（元）", "合计（元）"])
    row += 1

    data_start_row = row
    for cat in cost_summary["categories"]:
        ws2.cell(row=row, column=1, value=cat["name"])
        ws2.cell(row=row, column=2, value=cat["quantity"])
        ws2.cell(row=row, column=3, value=cat["unit"])
        ws2.cell(row=row, column=4, value=cat["unit_price"] if cat["unit_price"] > 0 else "—")
        ws2.cell(row=row, column=5, value=cat["total"])
        ws2.cell(row=row, column=2).number_format = '#,##0.00'
        ws2.cell(row=row, column=4).number_format = '#,##0.00'
        ws2.cell(row=row, column=5).number_format = '¥#,##0.00'
        ws2.cell(row=row, column=5).font = Font(bold=True, color="1E2A2E")
        # 数字右对齐
        for c in [2, 4, 5]:
            ws2.cell(row=row, column=c).alignment = Alignment(horizontal='right')
        row += 1

        # 水电分项展开
        if "details" in cat:
            for d in cat["details"]:
                ws2.cell(row=row, column=1, value=f"  {d['name']}")
                ws2.cell(row=row, column=2, value=d["quantity"])
                ws2.cell(row=row, column=3, value=d["unit"])
                ws2.cell(row=row, column=4, value=d["unit_price"])
                ws2.cell(row=row, column=5, value=d["total"])
                ws2.cell(row=row, column=2).number_format = '#,##0'
                ws2.cell(row=row, column=4).number_format = '¥#,##0'
                ws2.cell(row=row, column=5).number_format = '¥#,##0'
                for c in [1, 2, 3, 4, 5]:
                    ws2.cell(row=row, column=c).font = Font(size=10, color="5C6A6E")
                for c in [2, 4, 5]:
                    ws2.cell(row=row, column=c).alignment = Alignment(horizontal='right')
                row += 1

    data_end_row = row - 1

    # 总计行
    ws2.cell(row=row, column=1, value="总计").font = TOTAL_FONT
    ws2.cell(row=row, column=5, value=cost_summary["grand_total"]).font = Font(bold=True, size=12, color="E89F3E")
    ws2.cell(row=row, column=5).number_format = '¥#,##0.00'
    ws2.cell(row=row, column=5).alignment = Alignment(horizontal='right')
    for c in range(1, 6):
        ws2.cell(row=row, column=c).fill = TOTAL_FILL
        ws2.cell(row=row, column=c).border = Border(
            top=Side(style='medium', color="2B5E3B"),
            bottom=Side(style='medium', color="2B5E3B"),
        )

    _apply_border(ws2, 4, row, 5, alt_rows=False)
    ws2.column_dimensions['A'].width = 18
    ws2.column_dimensions['B'].width = 15
    ws2.column_dimensions['C'].width = 10
    ws2.column_dimensions['D'].width = 15
    ws2.column_dimensions['E'].width = 18

    # ── Sheet 2 图表 1: 费用构成饼图（圆环图风格）─────────────────
    pie = PieChart()
    pie.title = "费用构成"
    pie.style = 10

    cats = Reference(ws2, min_col=1, min_row=data_start_row, max_row=data_end_row)
    data = Reference(ws2, min_col=5, min_row=data_start_row, max_row=data_end_row)
    pie.add_data(data, titles_from_data=False)
    pie.set_categories(cats)
    pie.dataLabels = DataLabelList()
    pie.dataLabels.showPercent = True
    pie.dataLabels.showVal = False
    pie.dataLabels.font = Font(size=9, color="1E2A2E")

    # 应用装修配色
    for i, color in enumerate(CHART_COLORS[:len(cost_summary["categories"])]):
        pie.series[0].data_points.append(DataPoint(idx=i, explosion=3))

    ws2.add_chart(pie, "G4")

    # ── Sheet 2 图表 2: 费用对比柱状图 ──────────────────────────
    bar = BarChart()
    bar.title = "各分类费用对比"
    bar.style = 10
    bar.shape = 4
    bar.gapWidth = 60  # 柱形较宽

    cats2 = Reference(ws2, min_col=1, min_row=data_start_row, max_row=data_end_row)
    data2 = Reference(ws2, min_col=5, min_row=data_start_row, max_row=data_end_row)
    bar.add_data(data2, titles_from_data=False)
    bar.set_categories(cats2)
    bar.dataLabels = DataLabelList()
    bar.dataLabels.showVal = True
    bar.dataLabels.number_format = '¥#,##0'
    bar.dataLabels.font = Font(size=9, color="1E2A2E")

    ws2.add_chart(bar, "G20")

    # ── Sheet 3: 房间面积明细 ────────────────────────────────────
    ws3 = wb.create_sheet("房间明细")
    ws3.cell(row=1, column=1, value="房间面积明细").font = TITLE_FONT

    if room_details:
        row = 3
        _apply_header(ws3, row, ["房间名称", "面积（m²）", "估算费用（元）"])
        row += 1
        for room in room_details:
            ws3.cell(row=row, column=1, value=room["name"])
            ws3.cell(row=row, column=2, value=room["area_m2"])
            ws3.cell(row=row, column=3, value=room["estimated_cost"])
            ws3.cell(row=row, column=2).number_format = '#,##0.00'
            ws3.cell(row=row, column=3).number_format = '¥#,##0.00'
            ws3.cell(row=row, column=2).alignment = Alignment(horizontal='right')
            ws3.cell(row=row, column=3).alignment = Alignment(horizontal='right')
            ws3.cell(row=row, column=3).font = Font(bold=True, color="1E2A2E")
            row += 1
        _apply_border(ws3, 3, row - 1, 3)

        # 房间面积饼图
        if len(room_details) > 1:
            room_pie = PieChart()
            room_pie.title = "房间面积分布"
            room_pie.style = 10
            room_cats = Reference(ws3, min_col=1, min_row=4, max_row=row - 1)
            room_data = Reference(ws3, min_col=2, min_row=4, max_row=row - 1)
            room_pie.add_data(room_data, titles_from_data=False)
            room_pie.set_categories(room_cats)
            room_pie.dataLabels = DataLabelList()
            room_pie.dataLabels.showPercent = True
            room_pie.dataLabels.font = Font(size=9, color="1E2A2E")
            ws3.add_chart(room_pie, "E3")
    else:
        ws3.cell(row=3, column=1, value="无房间数据").font = Font(color="999999")

    ws3.column_dimensions['A'].width = 20
    ws3.column_dimensions['B'].width = 18
    ws3.column_dimensions['C'].width = 22

    # ── Sheet 4: 合规审核 ────────────────────────────────────────
    ws4 = wb.create_sheet("合规审核")
    ws4.cell(row=1, column=1, value="合规审核").font = TITLE_FONT
    ws4.cell(row=2, column=1, value="结论：" + ("通过" if compliance.get("passed") else "不通过")).font = Font(bold=True, color="38a169" if compliance.get("passed") else "e53e3e", size=11)

    issues = compliance.get("issues", [])
    if issues:
        row = 4
        _apply_header(ws4, row, ["#", "问题描述", "整改建议", "依据条文"])
        row += 1
        for i, issue in enumerate(issues, 1):
            if isinstance(issue, dict):
                ws4.cell(row=row, column=1, value=i)
                ws4.cell(row=row, column=2, value=issue.get("issue", ""))
                ws4.cell(row=row, column=3, value=issue.get("suggestion", ""))
                ws4.cell(row=row, column=4, value=issue.get("ref", ""))
            else:
                ws4.cell(row=row, column=1, value=i)
                ws4.cell(row=row, column=2, value=str(issue))
            row += 1
        _apply_border(ws4, 4, row - 1, 4)
    else:
        ws4.cell(row=4, column=1, value="未发现合规问题").font = Font(color="38a169")

    ws4.column_dimensions['A'].width = 5
    ws4.column_dimensions['B'].width = 45
    ws4.column_dimensions['C'].width = 45
    ws4.column_dimensions['D'].width = 25

    # 隐藏网格线
    for ws in [ws1, ws2, ws3, ws4]:
        ws.sheet_view.showGridLines = False

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
