# 门诊查询模块
import pandas as pd
import os
import shutil
import time
from datetime import datetime
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side


def get_clinic_data_dir():
    """获取门诊数据目录"""
    from src.config import get_clinic_data_dir
    return get_clinic_data_dir()


def get_clinic_reports():
    """获取门诊报表文件列表"""
    from src.config import get_clinic_reports
    return get_clinic_reports()


def query_clinic_data(doctor_name):
    """
    查询门诊数据
    返回: (结果DataFrame, 总记录数) 或 (None, 错误信息)
    """
    data_dir = get_clinic_data_dir()
    files = get_clinic_reports()

    yearly_data = {}

    for filename in files:
        filepath = os.path.join(data_dir, filename)
        try:
            year = filename[:4]
            if filename.startswith('202601-04.15'):
                period = '202601~04.15'
            else:
                period = year

            if year.isdigit() and 2019 <= int(year) <= 2022:
                header_row = 2
            else:
                header_row = 4

            df = pd.read_excel(filepath, header=header_row)
            df.columns = [str(col).strip() for col in df.columns]

            column_rename = {
                '入院人数': '入院人次',
                '出院人数': '出院人次',
                '出院患者占床日': '出院患者占用床日数'
            }
            df.rename(columns=column_rename, inplace=True)

            doctor_col = None
            for col in df.columns:
                if col == '医生':
                    doctor_col = col
                    break

            if doctor_col:
                mask = df[doctor_col].astype(str).str.strip() == doctor_name.strip()
                if mask.any():
                    matched = df[mask].copy()

                    if period not in yearly_data:
                        yearly_data[period] = {
                            '期间': period,
                            '医师姓名': doctor_name,
                            '门诊人次': 0
                        }

                    outpatient_no_zero = pd.to_numeric(matched['门诊人次(不含零费用)'], errors='coerce')
                    outpatient = pd.to_numeric(matched['门诊人次'], errors='coerce')

                    if outpatient_no_zero.notna().any() and outpatient_no_zero.sum() > 0:
                        yearly_data[period]['门诊人次'] += outpatient_no_zero.sum()
                    else:
                        yearly_data[period]['门诊人次'] += outpatient.sum()

        except Exception as e:
            print(f"读取 {filename} 出错: {e}")

    if yearly_data:
        result_df = pd.DataFrame(list(yearly_data.values()))
        result_df = result_df.sort_values('期间')

        cols = ['期间', '医师姓名', '门诊人次']
        result_df = result_df[cols]

        total_row = pd.DataFrame([{
            '期间': '合计',
            '医师姓名': '',
            '门诊人次': result_df['门诊人次'].sum()
        }])
        result_df = pd.concat([result_df, total_row], ignore_index=True)

        return result_df, len(yearly_data)

    return None, '未找到任何记录'


def export_clinic_to_xlsx(doctor_name, result_df):
    """导出门诊查询结果到Excel"""
    from src.config import get_xls_dir

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
