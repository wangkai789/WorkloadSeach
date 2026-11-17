# 门诊查询模块
import pandas as pd
import os
import shutil
import time
from datetime import datetime
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side

try:
    from .database import get_connection
except ImportError:
    from database import get_connection


def get_clinic_data_dir():
    """获取门诊数据目录"""
    from src.config import get_clinic_data_dir
    return get_clinic_data_dir()


def get_clinic_reports():
    """获取门诊报表文件列表"""
    from src.config import get_clinic_reports
    return get_clinic_reports()


def _period_overlaps(period_start, period_end, start_date=None, end_date=None):
    if not start_date and not end_date:
        return True
    if start_date and period_end < start_date:
        return False
    if end_date and period_start > end_date:
        return False
    return True


def _get_report_period(filename):
    year = filename[:4]
    if filename.startswith('202601-04.15'):
        return '202601~04.15', '2026-01-01', '2026-04-15'
    if year.isdigit():
        return year, f'{year}-01-01', f'{year}-12-31'
    return year, '', ''


def _find_column(columns, candidates):
    """按常见中文/英文列名查找存储过程返回列。"""
    normalized = {str(column).strip(): column for column in columns}
    for candidate in candidates:
        if candidate in normalized:
            return normalized[candidate]
    for column in columns:
        column_text = str(column).strip()
        if any(candidate in column_text for candidate in candidates):
            return column
    return None


def query_clinic_data(employee_id, doctor_name='', start_date=None, end_date=None):
    """
    按员工编号调用 Search_Doctor_OPWorkload 查询门诊数据。
    返回: (结果DataFrame, 总记录数) 或 (None, 错误信息)
    """
    employee_id = str(employee_id or '').strip()
    if not employee_id:
        return None, '未找到员工编号，无法查询门诊数据'

    if not start_date or not end_date:
        today = datetime.now()
        start_date = start_date or today.replace(day=1).strftime('%Y-%m-%d')
        end_date = end_date or today.strftime('%Y-%m-%d')

    conn = None
    try:
        conn = get_connection()
        # 该门诊存储过程可能访问其他数据库/服务器，避免隐式事务触发 MSDTC。
        conn.autocommit = True
        cursor = conn.cursor()
        procedure = 'Search_Doctor_OPWorkload'
        sql = f'EXEC dhcc.dbo.{procedure} @datefrom=?, @dateto=?, @EmployeeID=?'
        print(f'[调用存储过程] dhcc.dbo.{procedure}', flush=True)
        print(
            f"[存储过程参数] EXEC dhcc.dbo.{procedure} "
            f"@datefrom='{start_date}', @dateto='{end_date}', @EmployeeID=N'{employee_id}'",
            flush=True
        )
        cursor.execute(sql, (start_date, end_date, employee_id))
        if not cursor.description:
            return None, '门诊查询未返回数据列'

        columns = [column[0] for column in cursor.description]
        rows = cursor.fetchall()
    except Exception as e:
        print(f'门诊数据库查询错误: {e}')
        return None, f'门诊数据库查询错误: {str(e)}'
    finally:
        if conn:
            conn.close()

    if not rows:
        return None, f'未找到员工 [{employee_id}] 的门诊数据'

    raw_df = pd.DataFrame.from_records(rows, columns=columns)
    period_col = _find_column(columns, ['期间', '年度', '日期', '统计日期', 'year', 'date'])
    doctor_col = _find_column(columns, ['医师姓名', '医生', '医生姓名', 'doctorName', 'doctor'])
    outpatient_col = _find_column(columns, [
        '门诊人次(不含零费用)', '门诊人次', '门诊量', '门诊工作量',
        'outpatient_count', 'outpatient'
    ])

    if outpatient_col is None:
        return None, 'Search_Doctor_OPWorkload 未返回门诊人次字段'

    result_df = pd.DataFrame({
        '期间': raw_df[period_col] if period_col else range(1, len(raw_df) + 1),
        '医师姓名': raw_df[doctor_col] if doctor_col else doctor_name,
        '门诊人次': pd.to_numeric(raw_df[outpatient_col], errors='coerce').fillna(0)
    })
    result_df['医师姓名'] = result_df['医师姓名'].fillna(doctor_name).astype(str).str.strip()
    result_df = result_df[['期间', '医师姓名', '门诊人次']]

    total_row = pd.DataFrame([{
        '期间': '合计',
        '医师姓名': '',
        '门诊人次': result_df['门诊人次'].sum()
    }])
    result_df = pd.concat([result_df, total_row], ignore_index=True)
    return result_df, len(raw_df)


def export_clinic_to_xlsx(doctor_name, result_df):
    """导出门诊查询结果到Excel"""
    try:
        from .config import get_xls_dir
    except ImportError:
        from config import get_xls_dir

    xls_dir = get_xls_dir()
    os.makedirs(xls_dir, exist_ok=True)

    output_file = os.path.join(xls_dir, f'{doctor_name}_门诊查询_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx')
    temp_file = output_file.replace('.xlsx', '_temp.xlsx')

    if os.path.exists(output_file):
        try:
            os.remove(output_file)
        except:
            time.sleep(1)
            try:
                os.remove(output_file)
            except:
                pass

    wb = Workbook()
    ws = wb.active

    thin = Side(style='thin', color='000000')
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    headers = list(result_df.columns)
    for col_idx, header in enumerate(headers, 1):
        cell = ws.cell(1, col_idx, str(header))
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal='center', vertical='center')
        cell.border = border

    for row_idx, row in result_df.iterrows():
        for col_idx, value in enumerate(row, 1):
            cell = ws.cell(row_idx + 2, col_idx, value)
            cell.alignment = Alignment(horizontal='center', vertical='center')
            cell.border = border

    ws.column_dimensions['A'].width = 14
    ws.column_dimensions['B'].width = 12
    ws.column_dimensions['C'].width = 16

    wb.save(temp_file)

    time.sleep(1)
    for _ in range(3):
        if os.path.exists(output_file):
            try:
                os.remove(output_file)
                break
            except:
                time.sleep(0.5)
        else:
            break

    shutil.move(temp_file, output_file)
    return output_file
