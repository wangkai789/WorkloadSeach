# ============== 数据库模块 ==============
import os
import sys
import sqlite3
from datetime import datetime

# 导入配置（根据运行环境选择方式）
try:
    from .config import get_db_config, get_data_warehouse_config, get_xls_dir
except ImportError:
    from config import get_db_config, get_data_warehouse_config, get_xls_dir

# 类型映射
QUERY_TYPES = {
    'sp': ('主任医师', 'Search_Doctor_SP_Workload'),
    'ap': ('副主任医师', 'Search_Doctor_AP_Workload'),
    'nurse': ('护士', 'Search_Nurse_Workload'),
    'anes': ('麻醉师', 'Search_Anes_Workload')
}

# ===== 患者查询存储过程（所有申报职称统一调用） =====
PATIENT_SP_NAME = 'Search_Patient'

# ===== 按科室查询患者存储过程 =====
DEPT_PATIENT_SP_NAME = 'Search_DeptPatient'

# ===== 按诊断查询患者存储过程 =====
DIAG_PATIENT_SP_NAME = 'Search_DiagPatient'

# 数据验证规则
VALIDATION_RULES = {
    'sp': {'keywords': ['主任', '副主任', '主治', '出院', '手术', '三四', '操作']},
    'ap': {'keywords': ['主治', '出院', '住院', '手术', '三四', '操作']},
    'nurse': {'keywords': ['质控', '责任']},
    'anes': {'keywords': ['麻醉']}
}


def get_history_db():
    """获取历史数据库路径"""
    import sys
    if getattr(sys, 'frozen', False):
        return os.path.join(os.path.dirname(sys.executable), 'Ldhcc.db')
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'dist', 'Ldhcc.db')


def get_connection():
    """获取数据库连接"""
    import pyodbc
    db_config = get_db_config()
    conn_str = (
        f"DRIVER={{ODBC Driver 17 for SQL Server}};"
        f"SERVER={db_config['server']},{db_config['port']};"
        f"DATABASE={db_config['database']};"
        f"UID={db_config['user']};PWD={db_config['password']};"
        f"Encrypt=no;TrustServerCertificate=yes;"
        f"Connection Timeout=10;"
    )
    try:
        return pyodbc.connect(conn_str)
    except pyodbc.Error as e:
        error_msg = str(e)
        # 针对常见错误提供更友好的提示
        if '18456' in error_msg:
            raise pyodbc.Error(
                f"用户 '{db_config['user']}' 登录失败 (错误18456)。"
                f"请检查：1) 用户名/密码是否正确；2) SQL Server是否启用了混合身份验证模式；"
                f"3) 该用户是否已被启用且未被锁定。"
            ) from e
        elif '53' in error_msg or '10061' in error_msg:
            raise pyodbc.Error(
                f"无法连接到服务器 {db_config['server']}:{db_config['port']}。"
                f"请检查：1) 服务器地址和端口是否正确；2) SQL Server服务是否已启动；"
                f"3) 防火墙是否允许该端口访问。"
            ) from e
        elif '18452' in error_msg:
            raise pyodbc.Error(
                f"登录失败：服务器不允许使用SQL Server身份验证。"
                f"请在SQL Server中启用混合身份验证模式(Windows和SQL Server身份验证)。"
            ) from e
        else:
            raise


def _build_data_warehouse_conn_str(config):
    """构建东华数据仓库ODBC连接字符串"""
    driver = config.get('driver', 'InterSystems IRIS')
    server = config.get('server', '')
    port = config.get('port', '')
    namespace = config.get('namespace', '')
    user = config.get('user', '')
    password = config.get('password', '')

    if not all([driver, server, port, namespace, user]):
        raise ValueError('东华数据仓库配置不完整，请检查驱动、服务器、端口、模式和用户名')

    return (
        f"DRIVER={{{driver}}};"
        f"SERVER={server};"
        f"PORT={port};"
        f"DATABASE={namespace};"
        f"UID={user};PWD={password};"
        f"Connection Timeout=10;"
    )


def _format_data_warehouse_error(error, config):
    """格式化东华数据仓库连接错误"""
    error_msg = str(error)
    driver = config.get('driver', 'InterSystems IRIS')
    server = config.get('server', '')
    port = config.get('port', '')

    if 'Data source name not found' in error_msg or 'IM002' in error_msg:
        return f"未找到 ODBC 驱动 '{driver}'，请检查 InterSystems IRIS ODBC 驱动是否已安装。"
    if 'HYT00' in error_msg or 'timeout' in error_msg.lower():
        return f"连接 {server}:{port} 超时，请检查网络、端口和数据仓库服务状态。"
    return f'东华数据仓库连接失败: {error_msg}'


def get_data_warehouse_connection():
    """获取东华数据仓库连接"""
    import pyodbc

    config = get_data_warehouse_config()
    conn_str = _build_data_warehouse_conn_str(config)

    try:
        return pyodbc.connect(conn_str)
    except pyodbc.Error as e:
        raise pyodbc.Error(_format_data_warehouse_error(e, config)) from e


def test_data_warehouse_connection():
    """测试东华数据仓库连接"""
    conn = get_data_warehouse_connection()
    conn.close()
    return True


def query_data_warehouse(sql, params=None):
    """
    执行东华数据仓库查询。

    参数:
        sql: 参数化SQL语句
        params: SQL参数，按pyodbc参数顺序传入

    返回:
        (columns, rows, error)
        - columns: list[str] 列名，非查询语句或失败时为空列表/None
        - rows:    list[tuple] 数据行，非查询语句时为空列表
        - error:   str or None
    """
    import pyodbc

    conn = None
    try:
        conn = get_data_warehouse_connection()
        cursor = conn.cursor()
        cursor.execute(sql, params or [])

        if cursor.description:
            columns = [col[0] for col in cursor.description]
            rows = cursor.fetchall()
        else:
            conn.commit()
            columns = []
            rows = []

        return columns, rows, None
    except pyodbc.Error as e:
        error_msg = str(e)
        print(f"东华数据仓库查询错误: {error_msg}")
        return None, None, f"东华数据仓库查询错误: {error_msg}"
    except Exception as e:
        print(f"东华数据仓库查询错误: {e}")
        return None, None, f"东华数据仓库查询错误: {str(e)}"
    finally:
        if conn:
            conn.close()


def init_history_db():
    """初始化历史记录数据库"""
    try:
        conn = sqlite3.connect(get_history_db())
        conn.execute('''
            CREATE TABLE IF NOT EXISTS query_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id TEXT,
                name TEXT NOT NULL, query_type TEXT NOT NULL,
                start_date TEXT, end_date TEXT,
                output_file TEXT, output_path TEXT,
                query_time TEXT NOT NULL, row_count INTEGER DEFAULT 0
            )
        ''')
        # 如果employee_id列不存在，则添加
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(query_history)")
        columns = [row[1] for row in cursor.fetchall()]
        if 'employee_id' not in columns:
            conn.execute("ALTER TABLE query_history ADD COLUMN employee_id TEXT")
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"初始化历史数据库失败: {e}")


def load_history():
    """从 SQLite 加载查询历史"""
    try:
        init_history_db()
        conn = sqlite3.connect(get_history_db())
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            'SELECT employee_id, name, query_type, start_date, end_date, output_file, output_path, query_time, row_count '
            'FROM query_history ORDER BY id DESC LIMIT 100'
        ).fetchall()
        conn.close()
        return [dict(row) for row in rows]
    except Exception as e:
        print(f"加载历史记录失败: {e}")
        return []


def save_history_record(employee_id, name, query_type, start_date, end_date, output_file, output_path, row_count):
    """保存单条查询历史到 SQLite"""
    try:
        init_history_db()
        conn = sqlite3.connect(get_history_db())
        conn.execute('''
            INSERT INTO query_history (employee_id, name, query_type, start_date, end_date, output_file, output_path, query_time, row_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (employee_id, name, query_type, start_date, end_date, output_file, output_path, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), row_count))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"保存历史记录失败: {e}")
        return False


def clear_history_db():
    """清空 SQLite 历史记录"""
    try:
        init_history_db()
        conn = sqlite3.connect(get_history_db())
        conn.execute('DELETE FROM query_history')
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"清空历史记录失败: {e}")
        return False


def _validate_data(columns, rows, query_type, type_name):
    """验证查询结果是否有效"""
    if not rows:
        return f"未找到 {type_name} 的数据"
    
    keywords = VALIDATION_RULES.get(query_type, {}).get('keywords', [])
    if not keywords:
        return None
    
    # 找出需要检查的列索引
    key_cols = []
    for idx, col in enumerate(columns):
        col_str = str(col)
        if all(k in col_str for k in keywords[:2]) or \
           (len(keywords) >= 4 and any(k in col_str for k in keywords[2:])):
            key_cols.append(idx)
    
    if not key_cols:
        return None
    
    # 检查是否全部为0
    for row in rows:
        for col_idx in key_cols:
            if row[col_idx] and row[col_idx] != 0:
                return None
    
    return f"未找到 {type_name} 的有效数据"


def _write_excel(columns, rows, sheet_title, output_file):
    """将查询结果写入Excel文件"""
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, Border, Side

    wb = Workbook()
    ws = wb.active
    ws.title = sheet_title
    thin = Side(style='thin', color='000000')
    # 样式对象在整张表内复用（openpyxl 按值序列化，多个单元格共享同一实例是安全的），
    # 避免为每个单元格都新建 Font/Alignment，这在大结果集下是主要的性能瓶颈之一。
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    header_font = Font(bold=True)
    center_align = Alignment(horizontal='center', vertical='center', wrap_text=True)

    # 列宽随写入过程一次性统计，不再写完后回读单元格重新计算（避免整表再扫一遍）。
    col_count = len(columns)
    max_lengths = [max(len(str(header)), 8) for header in columns]

    # 写入表头（表头只有几列，逐格设样式开销可忽略不计）
    ws.append([str(header) for header in columns])
    for col_idx in range(1, col_count + 1):
        cell = ws.cell(1, col_idx)
        cell.font = header_font
        cell.alignment = center_align
        cell.border = border

    # 写入数据：实测对每个数据单元格逐一设置边框+居中样式是大结果集下的主要性能
    # 瓶颈（5万行×19列从 154s 降到 27s），因此数据区改为整行批量写入，不再逐格设样式。
    for row in rows:
        row_values = list(row)
        ws.append(row_values)
        for col_idx, value in enumerate(row_values):
            length = len(str(value)) if value is not None else 0
            if length > max_lengths[col_idx]:
                max_lengths[col_idx] = length

    # 调整列宽
    for col_idx in range(1, col_count + 1):
        col_letter = chr(64 + col_idx) if col_idx <= 26 else f"A{chr(64 + col_idx - 26)}"
        ws.column_dimensions[col_letter].width = max(8, min(max_lengths[col_idx - 1] + 2, 40))

    ws.row_dimensions[1].height = 30
    wb.save(output_file)


def _save_query_excel(columns, rows, name, type_name, start_date, end_date):
    """生成查询结果Excel文件并返回文件路径"""
    xls_dir = get_xls_dir()
    os.makedirs(xls_dir, exist_ok=True)
    date_range = f"{start_date.replace('-', '')}_{end_date.replace('-', '')}"
    output_file = os.path.join(xls_dir, f"{name}_{type_name}_{date_range}.xlsx")
    _write_excel(columns, rows, type_name, output_file)
    return output_file


def query_data(name, query_type, start_date=None, end_date=None):
    """执行查询"""
    import pyodbc

    type_name, proc_name = QUERY_TYPES.get(query_type, (query_type, ''))

    # 默认日期
    if not start_date or not end_date:
        today = datetime.now()
        start_date = today.replace(day=1).strftime('%Y-%m-%d')
        end_date = today.strftime('%Y-%m-%d')

    print(f"执行查询: {type_name} - {name}, 日期范围: {start_date} ~ {end_date}")

    try:
        conn = get_connection()
        cursor = conn.cursor()
        sql = f"EXEC dhcc.dbo.{proc_name} @doctorName=?, @datefrom=?, @dateto=?"
        print(f"[存储过程] EXEC dhcc.dbo.{proc_name} @doctorName=N'{name}', @datefrom='{start_date}', @dateto='{end_date}'")
        cursor.execute(sql, (name, start_date, end_date))
        columns = [col[0] for col in cursor.description]
        rows = cursor.fetchall()
        conn.close()
    except pyodbc.Error as e:
        print(f"数据库错误: {e}")
        return None, None, f"数据库错误: {str(e)}"
    except Exception as e:
        print(f"查询错误: {e}")
        return None, None, f"查询错误: {str(e)}"

    # 验证数据
    error = _validate_data(columns, rows, query_type, f"{type_name}[{name}]")
    if error:
        return None, None, error

    # 保存到Excel
    output_file = _save_query_excel(columns, rows, name, type_name, start_date, end_date)

    return columns, rows, output_file


def query_patients_by_doctor(doctor_name, start_date=None, end_date=None):
    """
    按医生姓名查询患者列表
    
    参数:
        doctor_name: 医生姓名
        start_date: 开始日期 (YYYY-MM-DD)
        end_date:   结束日期 (YYYY-MM-DD)
    
    返回:
        (columns, rows, output_file, error)
        - columns:     list[str] 列名, 查询失败时为 None
        - rows:        list[tuple] 数据行
        - output_file: 生成的Excel文件路径, 无数据或失败时为 None
        - error:       str or None
    """
    import pyodbc

    if not start_date or not end_date:
        today = datetime.now()
        start_date = today.replace(day=1).strftime('%Y-%m-%d')
        end_date = today.strftime('%Y-%m-%d')

    print(f"执行患者查询: 医生={doctor_name}, 日期={start_date}~{end_date}")

    try:
        conn = get_connection()
        cursor = conn.cursor()
        sql = f"EXEC dhcc.dbo.Search_Patient_doctor @name=?, @datefrom=?, @dateto=?"
        print(f"[存储过程] EXEC dhcc.dbo.Search_Patient_doctor @name=N'{doctor_name}', @datefrom='{start_date}', @dateto='{end_date}'")
        cursor.execute(sql, (doctor_name, start_date, end_date))
        columns = [col[0] for col in cursor.description] if cursor.description else []
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return columns, [], None, f"未找到医生 [{doctor_name}] 的患者数据"

        output_file = _save_query_excel(columns, rows, doctor_name, '医生患者查询', start_date, end_date)
        return columns, rows, output_file, None

    except pyodbc.Error as e:
        error_msg = str(e)
        print(f"患者查询数据库错误: {error_msg}")
        return None, None, None, f"数据库错误: {error_msg}"
    except Exception as e:
        print(f"患者查询错误: {e}")
        return None, None, None, f"查询错误: {str(e)}"


def query_patients_by_nurse(nurse_name, start_date=None, end_date=None, query_type=None):
    """
    按护士姓名查询患者列表
    
    参数:
        nurse_name: 护士姓名
        start_date: 开始日期 (YYYY-MM-DD)
        end_date:   结束日期 (YYYY-MM-DD)
        query_type: 查询类型 ('nurse'=责任护士, 'quality'=质控护士)
    
    返回:
        (columns, rows, output_file, error)
        - columns:     list[str] 列名, 查询失败时为 None
        - rows:        list[tuple] 数据行
        - output_file: 生成的Excel文件路径, 无数据或失败时为 None
        - error:       str or None
    """
    import pyodbc

    if not start_date or not end_date:
        today = datetime.now()
        start_date = today.replace(day=1).strftime('%Y-%m-%d')
        end_date = today.strftime('%Y-%m-%d')

    type_name = '责任护士' if query_type == 'nurse' else '质控护士'

    print(f"执行护士患者查询: 类型={type_name}, 护士={nurse_name}, 日期={start_date}~{end_date}")

    try:
        conn = get_connection()
        cursor = conn.cursor()
        sql = f"EXEC dhcc.dbo.{PATIENT_SP_NAME} @name=?, @datefrom=?, @dateto=?"
        print(f"[存储过程] EXEC dhcc.dbo.{PATIENT_SP_NAME} @name=N'{nurse_name}', @datefrom='{start_date}', @dateto='{end_date}'")
        cursor.execute(sql, (nurse_name, start_date, end_date))
        columns = [col[0] for col in cursor.description] if cursor.description else []
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return columns, [], None, f"未找到{type_name} [{nurse_name}] 的患者数据"

        output_file = _save_query_excel(columns, rows, nurse_name, f'{type_name}患者查询', start_date, end_date)
        return columns, rows, output_file, None

    except pyodbc.Error as e:
        error_msg = str(e)
        print(f"护士患者查询数据库错误: {error_msg}")
        return None, None, None, f"数据库错误: {error_msg}"
    except Exception as e:
        print(f"护士患者查询错误: {e}")
        return None, None, None, f"查询错误: {str(e)}"


def query_patients_by_dept(dept_name, start_date=None, end_date=None):
    """
    按科室查询患者列表

    参数:
        dept_name: 科室名称
        start_date: 开始日期 (YYYY-MM-DD)
        end_date:   结束日期 (YYYY-MM-DD)

    返回:
        (columns, rows, output_file, error)
        - columns:     list[str] 列名, 查询失败时为 None
        - rows:        list[tuple] 数据行
        - output_file: 生成的Excel文件路径, 无数据或失败时为 None
        - error:       str or None
    """
    import pyodbc

    if not start_date or not end_date:
        today = datetime.now()
        start_date = today.replace(day=1).strftime('%Y-%m-%d')
        end_date = today.strftime('%Y-%m-%d')

    print(f"执行科室患者查询: 科室={dept_name}, 日期={start_date}~{end_date}")

    try:
        conn = get_connection()
        cursor = conn.cursor()
        sql = f"EXEC dhcc.dbo.{DEPT_PATIENT_SP_NAME} @DeptName=?, @datefrom=?, @dateto=?"
        print(f"[存储过程] EXEC dhcc.dbo.{DEPT_PATIENT_SP_NAME} @DeptName=N'{dept_name}', @datefrom='{start_date}', @dateto='{end_date}'")
        cursor.execute(sql, (dept_name, start_date, end_date))
        columns = [col[0] for col in cursor.description] if cursor.description else []
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return columns, [], None, f"未找到科室 [{dept_name}] 的患者数据"

        output_file = _save_query_excel(columns, rows, dept_name, '科室患者查询', start_date, end_date)
        return columns, rows, output_file, None

    except pyodbc.Error as e:
        error_msg = str(e)
        print(f"科室患者查询数据库错误: {error_msg}")
        return None, None, None, f"数据库错误: {error_msg}"
    except Exception as e:
        print(f"科室患者查询错误: {e}")
        return None, None, None, f"查询错误: {str(e)}"


def query_patients_by_diag(diag_name, start_date=None, end_date=None):
    """
    按诊断查询患者列表

    参数:
        diag_name:  诊断名称（关键字）
        start_date: 开始日期 (YYYY-MM-DD)
        end_date:   结束日期 (YYYY-MM-DD)

    返回:
        (columns, rows, output_file, error)
        - columns:     list[str] 列名, 查询失败时为 None
        - rows:        list[tuple] 数据行
        - output_file: 生成的Excel文件路径, 无数据或失败时为 None
        - error:       str or None
    """
    import pyodbc

    if not start_date or not end_date:
        today = datetime.now()
        start_date = today.replace(day=1).strftime('%Y-%m-%d')
        end_date = today.strftime('%Y-%m-%d')

    print(f"执行诊断患者查询: 诊断={diag_name}, 日期={start_date}~{end_date}")

    try:
        conn = get_connection()
        cursor = conn.cursor()
        sql = f"EXEC dhcc.dbo.{DIAG_PATIENT_SP_NAME} @DiagName=?, @datefrom=?, @dateto=?"
        print(f"[存储过程] EXEC dhcc.dbo.{DIAG_PATIENT_SP_NAME} @DiagName=N'{diag_name}', @datefrom='{start_date}', @dateto='{end_date}'")
        cursor.execute(sql, (diag_name, start_date, end_date))
        columns = [col[0] for col in cursor.description] if cursor.description else []
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return columns, [], None, f"未找到诊断 [{diag_name}] 的患者数据"

        output_file = _save_query_excel(columns, rows, diag_name, '诊断患者查询', start_date, end_date)
        return columns, rows, output_file, None

    except pyodbc.Error as e:
        error_msg = str(e)
        print(f"诊断患者查询数据库错误: {error_msg}")
        return None, None, None, f"数据库错误: {error_msg}"
    except Exception as e:
        print(f"诊断患者查询错误: {e}")
        return None, None, None, f"查询错误: {str(e)}"
