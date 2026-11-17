# ============== 查询蓝图 ==============
import os
import traceback

from flask import Blueprint, request, jsonify, send_file, session

# 导入模块（根据运行环境选择方式）
try:
    from ..config import get_output_dir
    from ..database import query_data, save_history_record, load_history, QUERY_TYPES, query_patients_by_doctor, query_patients_by_nurse, query_patients_by_dept, query_patients_by_diag
    from ..export import xlsx_to_pdf
    from ..dingtalk import send_file_to_dingtalk
    from ..feishu import send_file_to_feishu
except ImportError:
    from config import get_output_dir
    from database import query_data, save_history_record, load_history, QUERY_TYPES, query_patients_by_doctor, query_patients_by_nurse, query_patients_by_dept, query_patients_by_diag
    from export import xlsx_to_pdf
    from dingtalk import send_file_to_dingtalk
    from feishu import send_file_to_feishu

# 导入公共装饰器与响应封装
try:
    from ..utils import login_required, ok_response, fail_response
except ImportError:
    from utils import login_required, ok_response, fail_response

query_bp = Blueprint('query', __name__)

# 各查询类型的中文列名映射（按顺序）
COLUMN_HEADERS = {
    'nurse': ['年度', '姓名', '质控护士', '责任护士'],
    'sp': ['年度', '申报职称', '姓名','主任（副主任）医师-出院人数','主治医师-出院人数','手术操作','三四级手术'],
    'ap': ['年度', '申报职称', '姓名','主治医师-出院人数','住院医师-出院人数','手术操作','三四级手术'],
    'anes': ['年度', '姓名', '麻醉量']
}


def _sync_history():
    """将历史记录同步到 history 蓝图内存存储（延迟导入避免循环依赖）"""
    try:
        from .history import set_history_store as _set
    except ImportError:
        from api.history import set_history_store as _set
    _set(load_history())


@query_bp.route('/api/reports/inpatient-workload', methods=['POST'])
@login_required
def create_inpatient_workload_report():
    """
    住院工作量查询（按职称：主任/副主任医师、护士、麻醉师，需登录）
    ---
    tags:
      - 报表
    consumes:
      - application/x-www-form-urlencoded
    parameters:
      - in: formData
        name: name
        type: string
        required: true
        description: 查询姓名
      - in: formData
        name: employee_id
        type: string
        description: 员工编号，缺省时用于历史记录标识
      - in: formData
        name: query_type
        type: string
        required: true
        enum: [sp, ap, nurse, anes]
        description: sp=主任医师 ap=副主任医师 nurse=护士 anes=麻醉师
      - in: formData
        name: start_date
        type: string
        example: "2026-01-01"
      - in: formData
        name: end_date
        type: string
        example: "2026-12-31"
    responses:
      200:
        description: 查询结果（columns/rows 及生成的 xlsx/pdf 路径）
      400:
        description: 参数缺失或查询失败
    """
    try:
        name = request.form.get('name', '').strip()
        employee_id = request.form.get('employee_id', '').strip()
        query_type = request.form.get('query_type', '').strip()
        start_date = request.form.get('start_date', '').strip()
        end_date = request.form.get('end_date', '').strip()

        if not name:
            return fail_response('请输入查询姓名')
        if not query_type:
            return fail_response('请选择查询类型')

        columns, rows, result = query_data(name, query_type, start_date, end_date)

        if columns is None:
            return fail_response(result)
    except Exception as e:
        traceback.print_exc()
        return fail_response(f'查询失败: {str(e)}')

    # 生成PDF
    pdf_path = None
    try:
        pdf_path = xlsx_to_pdf(result)
    except Exception as e:
        print(f"生成PDF失败: {e}")

    # 保存历史
    type_name = QUERY_TYPES.get(query_type, (query_type, ''))[0]
    emp_id = employee_id if employee_id else name
    save_history_record(emp_id, name, type_name, start_date, end_date, os.path.basename(result), result, len(rows))
    _sync_history()

    msg = f'查询完成！共 {len(rows)} 条记录'
    if pdf_path:
        msg += f'\nPDF已导出到: {pdf_path}'

    # 确保columns是列表
    columns_list = list(columns) if columns else []

    # 根据查询类型获取中文列名映射
    display_columns = COLUMN_HEADERS.get(query_type, columns_list)

    # 转换rows为嵌套数组（按display_columns顺序）
    rows_data = []
    for row in rows:
        row_list = [str(cell) if cell is not None else '' for cell in row]
        rows_data.append(row_list)

    return ok_response(
        msg,
        output_file=result,
        pdf_path=pdf_path,
        columns=display_columns,  # 使用中文列名
        rows=rows_data,           # 嵌套数组：[["2018","司马海娟","710","0"], ...]
        row_count=len(rows),
        title=type_name
    )


@query_bp.route('/api/reports/patients/by-doctor', methods=['POST'])
@login_required
def create_patients_by_doctor_report():
    """
    按医生姓名查询其名下患者列表（需登录）
    ---
    tags:
      - 患者查询
    consumes:
      - application/x-www-form-urlencoded
    parameters:
      - in: formData
        name: name
        type: string
        required: true
        description: 医生姓名
      - in: formData
        name: start_date
        type: string
        example: "2026-01-01"
      - in: formData
        name: end_date
        type: string
        example: "2026-12-31"
    responses:
      200:
        description: 患者列表（columns/rows 及生成的 xlsx/pdf 路径）
      400:
        description: 未输入姓名或未查到数据
    """
    try:
        doctor_name = request.form.get('name', '').strip()
        start_date = request.form.get('start_date', '').strip()
        end_date = request.form.get('end_date', '').strip()

        if not doctor_name:
            return fail_response('请输入医生姓名')

        columns, rows, output_file, error = query_patients_by_doctor(
            doctor_name, start_date, end_date
        )

        if columns is None:
            return fail_response(error)

        # 转换 rows 为嵌套列表（JSON 序列化友好）
        rows_data = [
            [str(cell) if cell is not None else '' for cell in row]
            for row in rows
        ]

        # 患者查询不生成PDF，只保留Excel（避免大结果集时PDF生成拖慢响应）
        pdf_path = None

        # 保存到历史记录
        output_name = os.path.basename(output_file) if output_file else ''
        save_history_record(doctor_name, doctor_name, '医生患者查询', start_date, end_date, output_name, output_file or '', len(rows))
        _sync_history()

        return ok_response(
            f'查询完成！共 {len(rows)} 条记录',
            columns=list(columns),
            rows=rows_data,
            row_count=len(rows),
            output_file=output_file,
            pdf_path=pdf_path
        )

    except Exception as e:
        traceback.print_exc()
        return fail_response(f'查询失败: {str(e)}')


@query_bp.route('/api/reports/patients/by-nurse', methods=['POST'])
@login_required
def create_patients_by_nurse_report():
    """
    按护士姓名查询其名下患者列表（需登录）
    ---
    tags:
      - 患者查询
    consumes:
      - application/x-www-form-urlencoded
    parameters:
      - in: formData
        name: name
        type: string
        required: true
        description: 护士姓名
      - in: formData
        name: query_type
        type: string
        enum: [nurse, quality]
        description: nurse=责任护士，其他值（含留空）=质控护士
      - in: formData
        name: start_date
        type: string
        example: "2026-01-01"
      - in: formData
        name: end_date
        type: string
        example: "2026-12-31"
    responses:
      200:
        description: 患者列表（columns/rows 及生成的 xlsx/pdf 路径）
      400:
        description: 未输入姓名或未查到数据
    """
    try:
        nurse_name = request.form.get('name', '').strip()
        query_type = request.form.get('query_type', '').strip()
        start_date = request.form.get('start_date', '').strip()
        end_date = request.form.get('end_date', '').strip()

        if not nurse_name:
            return fail_response('请输入护士姓名')

        columns, rows, output_file, error = query_patients_by_nurse(
            nurse_name, start_date, end_date, query_type
        )

        if columns is None:
            return fail_response(error)

        # 转换 rows 为嵌套列表（JSON 序列化友好）
        rows_data = [
            [str(cell) if cell is not None else '' for cell in row]
            for row in rows
        ]

        # 患者查询不生成PDF，只保留Excel（避免大结果集时PDF生成拖慢响应）
        pdf_path = None

        # 保存到历史记录
        type_name = '责任护士患者查询' if query_type == 'nurse' else '质控护士患者查询'
        output_name = os.path.basename(output_file) if output_file else ''
        save_history_record(nurse_name, nurse_name, type_name, start_date, end_date, output_name, output_file or '', len(rows))
        _sync_history()

        return ok_response(
            f'查询完成！共 {len(rows)} 条记录',
            columns=list(columns),
            rows=rows_data,
            row_count=len(rows),
            output_file=output_file,
            pdf_path=pdf_path
        )

    except Exception as e:
        traceback.print_exc()
        return fail_response(f'查询失败: {str(e)}')


@query_bp.route('/api/reports/patients/by-dept', methods=['POST'])
@login_required
def create_patients_by_dept_report():
    """
    按科室查询患者列表（需登录）
    ---
    tags:
      - 患者查询
    consumes:
      - application/x-www-form-urlencoded
    parameters:
      - in: formData
        name: name
        type: string
        required: true
        description: 科室名称
      - in: formData
        name: start_date
        type: string
        example: "2026-01-01"
      - in: formData
        name: end_date
        type: string
        example: "2026-12-31"
    responses:
      200:
        description: 患者列表（columns/rows 及生成的 xlsx/pdf 路径）
      400:
        description: 未输入科室名称或未查到数据
    """
    try:
        dept_name = request.form.get('name', '').strip()
        start_date = request.form.get('start_date', '').strip()
        end_date = request.form.get('end_date', '').strip()

        if not dept_name:
            return fail_response('请输入科室名称')

        columns, rows, output_file, error = query_patients_by_dept(
            dept_name, start_date, end_date
        )

        if columns is None:
            return fail_response(error)

        # 转换 rows 为嵌套列表（JSON 序列化友好）
        rows_data = [
            [str(cell) if cell is not None else '' for cell in row]
            for row in rows
        ]

        # 患者查询不生成PDF，只保留Excel（避免大结果集时PDF生成拖慢响应）
        pdf_path = None

        # 保存到历史记录
        output_name = os.path.basename(output_file) if output_file else ''
        save_history_record(dept_name, dept_name, '科室患者查询', start_date, end_date, output_name, output_file or '', len(rows))
        _sync_history()

        return ok_response(
            f'查询完成！共 {len(rows)} 条记录',
            columns=list(columns),
            rows=rows_data,
            row_count=len(rows),
            output_file=output_file,
            pdf_path=pdf_path
        )

    except Exception as e:
        traceback.print_exc()
        return fail_response(f'查询失败: {str(e)}')


@query_bp.route('/api/reports/patients/by-diag', methods=['POST'])
@login_required
def create_patients_by_diag_report():
    """
    按诊断查询患者列表（需登录）
    ---
    tags:
      - 患者查询
    consumes:
      - application/x-www-form-urlencoded
    parameters:
      - in: formData
        name: name
        type: string
        required: true
        description: 诊断名称（关键字）
      - in: formData
        name: start_date
        type: string
        example: "2026-01-01"
      - in: formData
        name: end_date
        type: string
        example: "2026-12-31"
    responses:
      200:
        description: 患者列表（columns/rows 及生成的 xlsx/pdf 路径）
      400:
        description: 未输入诊断名称或未查到数据
    """
    try:
        diag_name = request.form.get('name', '').strip()
        start_date = request.form.get('start_date', '').strip()
        end_date = request.form.get('end_date', '').strip()

        if not diag_name:
            return fail_response('请输入诊断名称')

        columns, rows, output_file, error = query_patients_by_diag(
            diag_name, start_date, end_date
        )

        if columns is None:
            return fail_response(error)

        # 转换 rows 为嵌套列表（JSON 序列化友好）
        rows_data = [
            [str(cell) if cell is not None else '' for cell in row]
            for row in rows
        ]

        # 患者查询不生成PDF，只保留Excel（避免大结果集时PDF生成拖慢响应）
        pdf_path = None

        # 保存到历史记录
        output_name = os.path.basename(output_file) if output_file else ''
        save_history_record(diag_name, diag_name, '诊断患者查询', start_date, end_date, output_name, output_file or '', len(rows))
        _sync_history()

        return ok_response(
            f'查询完成！共 {len(rows)} 条记录',
            columns=list(columns),
            rows=rows_data,
            row_count=len(rows),
            output_file=output_file,
            pdf_path=pdf_path
        )

    except Exception as e:
        traceback.print_exc()
        return fail_response(f'查询失败: {str(e)}')


@query_bp.route('/api/files/xlsx', methods=['GET'])
@login_required
def download_xlsx_file():
    """
    下载XLSX文件（需登录）
    ---
    tags:
      - 文件
    parameters:
      - in: query
        name: path
        type: string
        required: true
        description: 服务器本机的 xlsx 文件绝对路径
    produces:
      - application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
    responses:
      200:
        description: 文件内容
      404:
        description: 文件不存在
    """
    file_path = request.args.get('path', '')
    if not file_path or not os.path.exists(file_path):
        return "文件不存在", 404
    return send_file(file_path, as_attachment=True, download_name=os.path.basename(file_path))


@query_bp.route('/api/files/pdf-conversions', methods=['POST'])
@login_required
def create_pdf_conversion():
    """
    将XLSX转换为PDF（需登录）
    ---
    tags:
      - 文件
    consumes:
      - application/x-www-form-urlencoded
    parameters:
      - in: formData
        name: path
        type: string
        required: true
        description: 服务器本机的 xlsx 文件绝对路径
    responses:
      200:
        description: 生成的 pdf 路径
      400:
        description: 文件不存在或转换失败
    """
    file_path = request.form.get('path', '')
    if not file_path or not os.path.exists(file_path):
        return fail_response('文件不存在')
    try:
        pdf_path = xlsx_to_pdf(file_path)
        if pdf_path:
            return ok_response(f'PDF已导出到: {pdf_path}', pdf_path=pdf_path)
        return fail_response('Excel文件为空')
    except Exception as e:
        return fail_response(f'转换PDF失败: {str(e)}')


@query_bp.route('/api/files/dingtalk-deliveries', methods=['POST'])
@login_required
def create_dingtalk_delivery():
    """
    发送文件到钉钉（需登录）
    ---
    tags:
      - 文件
    consumes:
      - application/json
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [file_path]
          properties:
            file_path:
              type: string
              description: 服务器本机的文件绝对路径
            employee_id:
              type: string
              description: 钉钉推送目标员工编号，缺省时取当前会话用户
    responses:
      200:
        description: 发送成功
      400:
        description: 发送失败
    """
    try:
        data = request.get_json()
        file_path = data.get('file_path', '')
        # 优先使用前端传来的employee_id，否则从session获取
        employee_id = data.get('employee_id') or session.get('user', {}).get('employee_id')

        success, message = send_file_to_dingtalk(file_path, xlsx_to_pdf, employee_id)
        return ok_response(message) if success else fail_response(message)
    except Exception as e:
        return fail_response(f'发送失败: {str(e)}')


@query_bp.route('/api/files/feishu-deliveries', methods=['POST'])
@login_required
def create_feishu_delivery():
    """
    发送文件到飞书（需登录）
    ---
    tags:
      - 文件
    consumes:
      - application/json
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [file_path]
          properties:
            file_path:
              type: string
              description: 服务器本机的文件绝对路径
            receive_id:
              type: string
              description: 飞书接收方 ID，缺省用 config.json 里的 feishu.default_receive_id
            receive_id_type:
              type: string
              enum: [open_id, user_id, union_id, email, chat_id]
              description: 接收方 ID 类型，缺省用配置里的 receive_id_type
    responses:
      200:
        description: 发送成功
      400:
        description: 发送失败
    """
    try:
        data = request.get_json(silent=True) or {}
        file_path = data.get('file_path', '')
        if not file_path:
            return fail_response('缺少 file_path')
        if not os.path.exists(file_path):
            return fail_response(f'文件不存在: {file_path}')

        success, message = send_file_to_feishu(
            file_path,
            xlsx_to_pdf,
            receive_id=data.get('receive_id') or None,
            receive_id_type=data.get('receive_id_type') or None,
        )
        return ok_response(message) if success else fail_response(message)
    except Exception as e:
        return fail_response(f'发送失败: {str(e)}')


@query_bp.route('/api/system/output-dir/open', methods=['POST'])
@login_required
def open_output_dir():
    """
    在服务器本机打开输出目录（需登录）
    ---
    tags:
      - 系统
    responses:
      200:
        description: 已打开（仅在服务器本机生效）
      400:
        description: 打开失败
    """
    try:
        os.makedirs(get_output_dir(), exist_ok=True)
        os.startfile(get_output_dir())
        return ok_response('')
    except Exception as e:
        return fail_response(str(e))


@query_bp.route('/api/system/pdf-dir/open', methods=['POST'])
@login_required
def open_pdf_dir():
    """
    在服务器本机打开PDF目录（需登录）
    ---
    tags:
      - 系统
    responses:
      200:
        description: 已打开（仅在服务器本机生效）
      400:
        description: 打开失败
    """
    try:
        pdf_dir = os.path.join(get_output_dir(), 'pdf')
        os.makedirs(pdf_dir, exist_ok=True)
        os.startfile(pdf_dir)
        return ok_response('')
    except Exception as e:
        return fail_response(str(e))


@query_bp.route('/api/system/pdf/open', methods=['POST'])
@login_required
def open_pdf_file():
    """
    在服务器本机打开指定PDF文件（需登录）
    ---
    tags:
      - 系统
    consumes:
      - application/x-www-form-urlencoded
    parameters:
      - in: formData
        name: path
        type: string
        required: true
        description: 服务器本机的 pdf 文件绝对路径
    responses:
      200:
        description: 已打开（仅在服务器本机生效）
      400:
        description: 路径为空或文件不存在
    """
    file_path = request.form.get('path', '')
    if not file_path:
        return fail_response('文件路径为空')
    try:
        if not os.path.exists(file_path):
            return fail_response('PDF文件不存在')
        os.startfile(file_path)
        return ok_response('')
    except Exception as e:
        return fail_response(str(e))
