# ============== 导出模块 ==============
import os
import io

# 导入配置（根据运行环境选择方式）
try:
    from .config import get_pdf_dir
except ImportError:
    from config import get_pdf_dir


# reportlab 的 Table 是把所有行一次性排版进内存再分页，行数一大耗时会线性甚至更快增长
# （实测 3000 行约 9.7 秒，5万+行的科室/诊断查询外推超过 2 分钟），而且几万行的 PDF
# 本身也没有实际可读性（数千页）。超过该行数阈值时跳过 PDF 生成，只保留 Excel 导出。
PDF_ROW_LIMIT = 5000


def xlsx_to_pdf(xlsx_path):
    """将xlsx文件转换为PDF；数据行数超过 PDF_ROW_LIMIT 时跳过（返回 None），避免超大结果集卡住请求"""
    import re
    import openpyxl
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    pdfmetrics.registerFont(TTFont('SimHei', 'C:/Windows/Fonts/simhei.ttf'))

    pdf_dir = get_pdf_dir()
    os.makedirs(pdf_dir, exist_ok=True)

    # read_only 模式打开，且先用 max_row（O(1)，不遍历）判断是否超过阈值，
    # 避免超大结果集时把全部行读进内存转换一遍之后才发现要跳过（曾实测白白多花 40+ 秒）。
    wb = openpyxl.load_workbook(xlsx_path, read_only=True)
    ws = wb.active
    row_count = (ws.max_row or 1) - 1  # 减去表头行

    if row_count <= 0:
        wb.close()
        return None

    if row_count > PDF_ROW_LIMIT:
        print(f"数据行数 {row_count} 超过 {PDF_ROW_LIMIT}，跳过PDF生成（仅保留Excel）: {xlsx_path}")
        wb.close()
        return None

    data = [[str(cell) if cell else '' for cell in row] for row in ws.iter_rows(values_only=True)]
    wb.close()

    col_count = len(data[0])
    page_size = landscape(A4) if col_count > 5 else A4
    
    xlsx_name = os.path.basename(xlsx_path).replace('.xlsx', '')
    title_name = ''.join(re.findall(r'[\u4e00-\u9fa5]+', xlsx_name))
    pdf_path = os.path.join(pdf_dir, f'{xlsx_name}.pdf')
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontName='SimHei', fontSize=16, alignment=1)
    
    doc = SimpleDocTemplate(pdf_path, pagesize=page_size)
    elements = [
        Paragraph(title_name, title_style),
        Paragraph('<br/>', styles['Normal']),
        Table(data, colWidths=[(page_size[0] - 80) / col_count] * col_count)
    ]
    elements[-1].setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#667eea')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, -1), 'SimHei'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f5f5')]),
    ]))
    
    doc.build(elements)
    return pdf_path


def export_history_to_xlsx(query_history):
    """导出历史记录为XLSX"""
    import openpyxl
    from openpyxl.styles import Font, Alignment, PatternFill
    
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "查询历史"
    
    headers = ['序号', '员工编号', '姓名', '查询类型', '开始日期', '结束日期', '记录数', '查询时间', '文件路径']
    header_fill = PatternFill(start_color='667eea', end_color='667eea', fill_type='solid')
    header_font = Font(bold=True, color='FFFFFF')
    
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal='center', vertical='center')
    
    for i, record in enumerate(query_history, 2):
        ws.cell(row=i, column=1, value=i-1)
        ws.cell(row=i, column=2, value=record.get('employee_id', ''))
        ws.cell(row=i, column=3, value=record.get('name', ''))
        ws.cell(row=i, column=4, value=record.get('query_type', ''))
        ws.cell(row=i, column=5, value=record.get('start_date', ''))
        ws.cell(row=i, column=6, value=record.get('end_date', ''))
        ws.cell(row=i, column=7, value=record.get('row_count', ''))
        ws.cell(row=i, column=8, value=record.get('query_time', ''))
        ws.cell(row=i, column=9, value=record.get('output_path', ''))
    
    widths = {'A': 8, 'B': 15, 'C': 15, 'D': 12, 'E': 12, 'F': 12, 'G': 10, 'H': 20, 'I': 50}
    for col, width in widths.items():
        ws.column_dimensions[col].width = width
    
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer
