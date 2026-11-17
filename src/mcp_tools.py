# ============== MCP 工具业务实现 ==============
"""东华住院工作量查询系统 —— MCP 工具的纯业务实现。

只调用 src 下已有的查询函数，把结果整理成 JSON 友好的字典，不依赖 mcp SDK，
因此可以脱离 MCP 直接调用或测试。

约定：
- 每个函数都返回 dict；
- 成功：{'ok': True, ...}，业务上的「没查到数据」返回 ok=True 且 total=0；
- 失败：{'ok': False, 'error': '可读的原因'}。
"""
from __future__ import annotations

import datetime
import decimal

try:
    from .config import get_db_config, get_output_dir, load_config
    from .database import (
        QUERY_TYPES,
        get_connection,
        query_data,
        query_patients_by_dept,
        query_patients_by_diag,
        query_patients_by_doctor,
        query_patients_by_nurse,
    )
except ImportError:  # MCP 入口把 src 目录加入了 sys.path
    from config import get_db_config, get_output_dir, load_config
    from database import (
        QUERY_TYPES,
        get_connection,
        query_data,
        query_patients_by_dept,
        query_patients_by_diag,
        query_patients_by_doctor,
        query_patients_by_nurse,
    )

# 患者查询可选类型
PATIENT_KINDS = {
    'doctor': '按医生查询患者',
    'nurse': '按护士查询患者',
    'dept': '按科室查询患者',
    'diag': '按诊断查询患者',
}

# 单次返回给模型的最大行数，避免一次查询把几十万行塞进上下文
MAX_ROWS_DEFAULT = 200
MAX_ROWS_LIMIT = 2000

_configured = False


def _ensure_config():
    """首次调用时加载 config.json（与 Web 端读取的是同一个文件）。"""
    global _configured
    if not _configured:
        load_config()
        _configured = True


def _jsonable(value):
    """把 pyodbc 返回的 Decimal / datetime / bytes 转成可 JSON 序列化的值。"""
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, datetime.datetime):
        return value.strftime('%Y-%m-%d %H:%M:%S')
    if isinstance(value, (datetime.date, datetime.time)):
        return value.isoformat()
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).decode('utf-8', 'replace')
    return str(value)


def _rows_to_lists(rows):
    return [[_jsonable(cell) for cell in row] for row in rows]


def _resolve_period(start_date, end_date):
    """与 Web 端一致：缺省时取本月 1 日到今天。"""
    today = datetime.datetime.now()
    return (
        start_date or today.replace(day=1).strftime('%Y-%m-%d'),
        end_date or today.strftime('%Y-%m-%d'),
    )


def _check_type(query_type):
    query_type = str(query_type or '').strip().lower()
    if query_type not in QUERY_TYPES:
        options = '、'.join(f'{key}={value[0]}' for key, value in QUERY_TYPES.items())
        return None, f'query_type 无效：{query_type or "空"}，可选 {options}'
    return query_type, None


def query_inpatient_workload(name, query_type, start_date=None, end_date=None):
    """住院工作量查询（主任医师 / 副主任医师 / 护士 / 麻醉师）。"""
    _ensure_config()
    name = str(name or '').strip()
    if not name:
        return {'ok': False, 'error': '缺少 name（被查询人姓名）'}

    query_type, error = _check_type(query_type)
    if error:
        return {'ok': False, 'error': error}

    start_date, end_date = _resolve_period(start_date, end_date)
    columns, rows, result = query_data(name, query_type, start_date, end_date, save_excel=False)
    if columns is None:
        return {
            'ok': False,
            'error': result,
            'name': name,
            'query_type': query_type,
            'start_date': start_date,
            'end_date': end_date,
        }

    return {
        'ok': True,
        'name': name,
        'query_type': query_type,
        'type_name': QUERY_TYPES[query_type][0],
        'start_date': start_date,
        'end_date': end_date,
        'columns': [str(column) for column in columns],
        'rows': _rows_to_lists(rows),
        'total': len(rows),
    }


def query_outpatient_workload(employee_id, name='', start_date=None, end_date=None):
    """门诊工作量查询（调用 Search_Doctor_OPWorkload，按员工编号）。"""
    _ensure_config()
    employee_id = str(employee_id or '').strip()
    if not employee_id:
        return {'ok': False, 'error': '缺少 employee_id（员工编号），门诊查询必须提供'}

    name = str(name or '').strip()
    start_date, end_date = _resolve_period(start_date, end_date)

    try:
        from .clinic_query import query_clinic_data
    except ImportError:
        from clinic_query import query_clinic_data

    result_df, total = query_clinic_data(employee_id, name, start_date, end_date)
    if result_df is None:
        return {
            'ok': False,
            'error': total,
            'employee_id': employee_id,
            'start_date': start_date,
            'end_date': end_date,
        }

    columns = [str(column) for column in result_df.columns]
    rows = _rows_to_lists(result_df.itertuples(index=False, name=None))

    return {
        'ok': True,
        'employee_id': employee_id,
        'name': name,
        'start_date': start_date,
        'end_date': end_date,
        'columns': columns,
        'rows': rows,
        'total': len(rows),
        'record_count': total,
    }


def query_patients(kind, name, start_date=None, end_date=None, nurse_type='nurse',
                   limit=MAX_ROWS_DEFAULT, save_excel=False):
    """患者明细查询：按医生 / 护士 / 科室 / 诊断。"""
    _ensure_config()
    kind = str(kind or '').strip().lower()
    name = str(name or '').strip()
    if kind not in PATIENT_KINDS:
        return {'ok': False, 'error': f'kind 无效，可选 {"、".join(PATIENT_KINDS)}'}
    if not name:
        return {'ok': False, 'error': '缺少 name（医生 / 护士 / 科室 / 诊断名称）'}

    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = MAX_ROWS_DEFAULT
    limit = max(1, min(limit, MAX_ROWS_LIMIT))

    start_date, end_date = _resolve_period(start_date, end_date)

    if kind == 'doctor':
        columns, rows, output_file, error = query_patients_by_doctor(
            name, start_date, end_date, save_excel=save_excel)
    elif kind == 'nurse':
        columns, rows, output_file, error = query_patients_by_nurse(
            name, start_date, end_date, nurse_type, save_excel=save_excel)
    elif kind == 'dept':
        columns, rows, output_file, error = query_patients_by_dept(
            name, start_date, end_date, save_excel=save_excel)
    else:
        columns, rows, output_file, error = query_patients_by_diag(
            name, start_date, end_date, save_excel=save_excel)

    if columns is None:
        return {'ok': False, 'error': error, 'kind': kind, 'name': name}

    total = len(rows)
    payload = {
        'ok': True,
        'kind': kind,
        'kind_name': PATIENT_KINDS[kind],
        'name': name,
        'start_date': start_date,
        'end_date': end_date,
        'columns': [str(column) for column in columns],
        'rows': _rows_to_lists(rows[:limit]),
        'total': total,
        'returned': min(total, limit),
        'truncated': total > limit,
        'excel_path': output_file,
    }
    if not rows and error:
        payload['message'] = error
    return payload


def generate_workload_report(name, query_type, start_date=None, end_date=None, with_pdf=True):
    """生成住院工作量报表文件（xlsx，可选再转 pdf）。"""
    _ensure_config()
    name = str(name or '').strip()
    if not name:
        return {'ok': False, 'error': '缺少 name（被查询人姓名）'}

    query_type, error = _check_type(query_type)
    if error:
        return {'ok': False, 'error': error}

    start_date, end_date = _resolve_period(start_date, end_date)
    columns, rows, excel_path = query_data(name, query_type, start_date, end_date, save_excel=True)
    if columns is None:
        return {'ok': False, 'error': excel_path, 'name': name, 'query_type': query_type}

    pdf_path = None
    pdf_error = None
    if with_pdf:
        try:
            try:
                from .export import xlsx_to_pdf
            except ImportError:
                from export import xlsx_to_pdf
            pdf_path = xlsx_to_pdf(excel_path)
        except Exception as exc:  # PDF 只是附加产物，失败不影响 Excel 结果
            pdf_error = str(exc)

    payload = {
        'ok': True,
        'name': name,
        'query_type': query_type,
        'type_name': QUERY_TYPES[query_type][0],
        'start_date': start_date,
        'end_date': end_date,
        'total': len(rows),
        'columns': [str(column) for column in columns],
        'excel_path': excel_path,
        'pdf_path': pdf_path,
    }
    if pdf_error:
        payload['pdf_error'] = pdf_error
    return payload


def database_status():
    """检查配置与数据库连通性，便于客户端排障。"""
    _ensure_config()
    config = get_db_config() or {}
    payload = {
        'ok': True,
        'server': config.get('server'),
        'port': config.get('port'),
        'database': config.get('database'),
        'user': config.get('user'),
        'output_dir': get_output_dir(),
        'connected': False,
    }
    try:
        conn = get_connection()
        conn.close()
        payload['connected'] = True
    except Exception as exc:
        payload['ok'] = False
        payload['error'] = str(exc)
    return payload
