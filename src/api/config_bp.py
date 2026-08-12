# ============== 配置蓝图 ==============
import os

from flask import Blueprint, request, jsonify

# 导入配置模块（根据运行环境选择方式）
try:
    from ..config import (
        get_db_config, get_data_warehouse_config, get_output_dir, get_xls_dir, get_pdf_dir,
        save_config_to_file, get_clinic_data_dir, get_clinic_reports
    )
except ImportError:
    from config import (
        get_db_config, get_data_warehouse_config, get_output_dir, get_xls_dir, get_pdf_dir,
        save_config_to_file, get_clinic_data_dir, get_clinic_reports
    )

# 导入公共装饰器与响应封装
try:
    from ..utils import login_required, ok_response, fail_response
except ImportError:
    from utils import login_required, ok_response, fail_response

# 导入数据库访问接口
try:
    from ..database import test_data_warehouse_connection as test_dw_connection
except ImportError:
    from database import test_data_warehouse_connection as test_dw_connection

config_bp = Blueprint('config', __name__)


@config_bp.route('/api/config', methods=['GET'])
@login_required
def get_config():
    """
    获取配置信息（需登录）
    ---
    tags:
      - 配置
    responses:
      200:
        description: 当前数据库连接与目录配置
    """
    db_config = get_db_config()
    data_warehouse_config = get_data_warehouse_config()
    return jsonify({
        'server': db_config.get('server', ''),
        'port': db_config.get('port', ''),
        'user': db_config.get('user', ''),
        'database': db_config.get('database', ''),
        'data_warehouse': {
            'driver': data_warehouse_config.get('driver', ''),
            'server': data_warehouse_config.get('server', ''),
            'port': data_warehouse_config.get('port', ''),
            'namespace': data_warehouse_config.get('namespace', ''),
            'user': data_warehouse_config.get('user', '')
        },
        'output_dir': get_output_dir(),
        'xls_dir': get_xls_dir(),
        'pdf_dir': get_pdf_dir(),
        'clinic_data_dir': get_clinic_data_dir(),
        'clinic_reports': get_clinic_reports()
    })


@config_bp.route('/api/config', methods=['PUT'])
@login_required
def replace_config():
    """
    保存配置（整体替换，需登录）
    ---
    tags:
      - 配置
    consumes:
      - application/x-www-form-urlencoded
    parameters:
      - in: formData
        name: server
        type: string
        required: true
      - in: formData
        name: port
        type: string
        required: true
      - in: formData
        name: user
        type: string
        required: true
      - in: formData
        name: password
        type: string
      - in: formData
        name: database
        type: string
        required: true
      - in: formData
        name: output_dir
        type: string
        required: true
      - in: formData
        name: xls_dir
        type: string
      - in: formData
        name: pdf_dir
        type: string
      - in: formData
        name: clinic_data_dir
        type: string
      - in: formData
        name: clinic_reports
        type: string
        description: 逗号或 JSON 分隔的报表文件名列表
    responses:
      200:
        description: 配置保存成功
      400:
        description: 缺少必填字段或输出目录创建失败
    """
    current_db_config = get_db_config()
    current_warehouse_config = get_data_warehouse_config()
    server = request.form.get('server', '').strip()
    port = request.form.get('port', '').strip()
    user = request.form.get('user', '').strip()
    password = request.form.get('password', '').strip() or current_db_config.get('password', '')
    database = request.form.get('database', '').strip()
    output_dir = request.form.get('output_dir', '').strip()
    xls_dir = request.form.get('xls_dir', '').strip()
    pdf_dir = request.form.get('pdf_dir', '').strip()
    clinic_data_dir = request.form.get('clinic_data_dir', '').strip()
    clinic_reports = request.form.get('clinic_reports', '').strip()
    warehouse_driver = request.form.get('warehouse_driver', '').strip()
    warehouse_server = request.form.get('warehouse_server', '').strip()
    warehouse_port = request.form.get('warehouse_port', '').strip()
    warehouse_namespace = request.form.get('warehouse_namespace', '').strip()
    warehouse_user = request.form.get('warehouse_user', '').strip()
    warehouse_password = request.form.get('warehouse_password', '').strip()

    if not all([server, port, user, database, output_dir]):
        return fail_response('请填写完整配置信息')

    data_warehouse = None
    if any([warehouse_driver, warehouse_server, warehouse_port, warehouse_namespace, warehouse_user, warehouse_password]):
        if not all([warehouse_driver, warehouse_server, warehouse_port, warehouse_namespace, warehouse_user]):
            return fail_response('请填写完整东华数据仓库配置')
        data_warehouse = {
            'driver': warehouse_driver,
            'server': warehouse_server,
            'port': warehouse_port,
            'namespace': warehouse_namespace,
            'user': warehouse_user,
            'password': warehouse_password or current_warehouse_config.get('password', '')
        }

    try:
        os.makedirs(output_dir, exist_ok=True)
    except Exception as e:
        return fail_response(f'创建输出目录失败: {str(e)}')

    success = save_config_to_file(
        server, port, user, password, database, output_dir,
        xls_dir, pdf_dir, clinic_data_dir, clinic_reports, data_warehouse
    )
    return ok_response('配置保存成功') if success else fail_response('配置保存失败')


@config_bp.route('/api/config/test-connection', methods=['POST'])
@login_required
def test_config_connection():
    """
    测试数据库连接（需登录）
    ---
    tags:
      - 配置
    consumes:
      - application/x-www-form-urlencoded
    parameters:
      - in: formData
        name: server
        type: string
        required: true
      - in: formData
        name: port
        type: string
        default: "1433"
      - in: formData
        name: user
        type: string
        required: true
      - in: formData
        name: password
        type: string
      - in: formData
        name: database
        type: string
        required: true
    responses:
      200:
        description: 数据库连接成功
      400:
        description: 连接失败（含具体原因提示）
    """
    import pyodbc
    try:
        server = request.form.get('server', '').strip()
        port = request.form.get('port', '').strip() or '1433'
        user = request.form.get('user', '').strip()
        password = request.form.get('password', '').strip()
        database = request.form.get('database', '').strip()

        if not all([server, user, database]):
            return fail_response('请填写服务器、用户名和数据库名')

        conn_str = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={server},{port};"
            f"DATABASE={database};"
            f"UID={user};PWD={password};"
            f"Encrypt=no;TrustServerCertificate=yes;"
            f"Connection Timeout=10;"
        )
        conn = pyodbc.connect(conn_str)
        conn.close()
        return ok_response('数据库连接成功！')
    except pyodbc.Error as e:
        error_msg = str(e)
        if '18456' in error_msg:
            hint = f"用户 '{user}' 登录失败。请检查用户名/密码是否正确，以及SQL Server是否启用了混合身份验证模式。"
        elif '53' in error_msg or '10061' in error_msg:
            hint = f"无法连接到服务器 {server}:{port}。请检查服务器地址、端口，以及SQL Server服务是否已启动。"
        elif '18452' in error_msg:
            hint = "服务器不允许使用SQL Server身份验证，请启用混合身份验证模式。"
        else:
            hint = f"连接失败: {error_msg}"
        return fail_response(hint)
    except Exception as e:
        return fail_response(f'测试连接失败: {str(e)}')


@config_bp.route('/api/config/data-warehouse/test-connection', methods=['POST'])
@login_required
def test_data_warehouse_connection():
    """测试东华数据仓库连接（需登录）"""
    try:
        test_dw_connection()
        return ok_response('东华数据仓库连接成功')
    except Exception as e:
        return fail_response(str(e))
