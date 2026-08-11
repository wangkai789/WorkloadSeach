# ============== 门诊查询蓝图 ==============
import os
import glob
import traceback

from flask import Blueprint, request

# 导入模块（根据运行环境选择方式）
try:
    from ..config import get_clinic_data_dir
    from ..database import save_history_record, load_history
    from ..export import xlsx_to_pdf
    from ..clinic_query import query_clinic_data, export_clinic_to_xlsx
except ImportError:
    from config import get_clinic_data_dir
    from database import save_history_record, load_history
    from export import xlsx_to_pdf
    from clinic_query import query_clinic_data, export_clinic_to_xlsx

# 导入公共装饰器与响应封装
try:
    from ..utils import login_required, ok_response, fail_response
except ImportError:
    from utils import login_required, ok_response, fail_response

clinic_bp = Blueprint('clinic', __name__)


@clinic_bp.route('/api/clinic-report-files', methods=['GET'])
@login_required
def list_clinic_report_files():
    """
    获取门诊数据目录下的报表文件（需登录）
    ---
    tags:
      - 门诊
    responses:
      200:
        description: 匹配 *医生组*报表*.xlsx 的文件名列表
    """
    data_dir = get_clinic_data_dir()
    if not data_dir or not os.path.exists(data_dir):
        return ok_response('', files=[])

    pattern = os.path.join(data_dir, '*医生组*报表*.xlsx')
    files = [os.path.basename(f) for f in glob.glob(pattern)]
    return ok_response('', files=sorted(files))


@clinic_bp.route('/api/reports/outpatient-workload', methods=['POST'])
@login_required
def create_outpatient_workload_report():
    """
    门诊工作量查询（需登录）
    ---
    tags:
      - 门诊
    consumes:
      - application/x-www-form-urlencoded
    parameters:
      - in: formData
        name: doctor_name
        type: string
        required: true
      - in: formData
        name: employee_id
        type: string
        description: 员工编号，用于历史记录标识
    responses:
      200:
        description: 门诊人次数据（data/total 及生成的 xlsx/pdf 路径）
      400:
        description: 未输入医生姓名或查询失败
    """
    try:
        doctor_name = request.form.get('doctor_name', '').strip()
        employee_id = request.form.get('employee_id', '').strip()
        if not doctor_name:
            return fail_response('请输入医生姓名')

        result, total = query_clinic_data(doctor_name)
        if result is None:
            return fail_response(total)

        # 将DataFrame转换为列表
        data_list = result.to_dict('records')

        # 生成Excel文件
        xlsx_path = None
        pdf_path = None
        try:
            xlsx_path = export_clinic_to_xlsx(doctor_name, result)
            # 生成PDF
            try:
                pdf_path = xlsx_to_pdf(xlsx_path)
            except Exception as e:
                print(f"生成PDF失败: {e}")
        except Exception as e:
            print(f"导出Excel失败: {e}")

        msg = f'查询完成！共 {total} 条记录'
        if xlsx_path:
            msg += f'\n文件已导出到: {xlsx_path}'

        # 保存历史记录
        if xlsx_path:
            save_history_record(
                employee_id, doctor_name, '门诊查询', '', '',
                os.path.basename(xlsx_path), xlsx_path, total
            )
            # 延迟导入避免循环依赖
            try:
                from .history import set_history_store as _set
            except ImportError:
                from api.history import set_history_store as _set
            _set(load_history())

        return ok_response(
            msg,
            data=data_list,
            total=total,
            xlsx_path=xlsx_path,
            pdf_path=pdf_path
        )
    except Exception as e:
        traceback.print_exc()
        return fail_response(f'查询失败: {str(e)}')
