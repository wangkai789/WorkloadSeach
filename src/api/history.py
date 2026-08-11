# ============== 历史记录蓝图 ==============
import os
import traceback
from datetime import datetime

from flask import Blueprint, jsonify, make_response

# 导入模块（根据运行环境选择方式）
try:
    from ..database import load_history, clear_history_db
    from ..export import export_history_to_xlsx
except ImportError:
    from database import load_history, clear_history_db
    from export import export_history_to_xlsx

# 导入公共装饰器与响应封装
try:
    from ..utils import login_required, ok_response, not_found_response
except ImportError:
    from utils import login_required, ok_response, not_found_response

# 引用全局历史状态（由 routes.py 管理）
# 蓝图通过 _get_history / _set_history 间接访问
_history = []


def get_history_store():
    """获取当前历史记录列表"""
    return _history


def set_history_store(history):
    """设置历史记录列表"""
    global _history
    _history = history


history_bp = Blueprint('history', __name__)


def _remove_record_files(record):
    """删除历史记录关联的 xlsx/pdf 文件"""
    try:
        output_path = record.get('output_path', '')
        if output_path and os.path.exists(output_path):
            os.remove(output_path)
        pdf_path = output_path.replace('\\xls\\', '\\pdf\\').replace('/xls/', '/pdf/').replace('.xlsx', '.pdf')
        if pdf_path and os.path.exists(pdf_path):
            os.remove(pdf_path)
    except Exception as e:
        print(f"删除文件失败: {e}")


@history_bp.route('/api/history', methods=['GET'])
@login_required
def list_history():
    """
    获取查询历史（需登录）
    ---
    tags:
      - 历史记录
    responses:
      200:
        description: 历史记录列表
    """
    return jsonify({'history': get_history_store()})


@history_bp.route('/api/history', methods=['DELETE'])
@login_required
def clear_history():
    """
    清空历史记录（同时删除关联的 xlsx/pdf 文件，需登录）
    ---
    tags:
      - 历史记录
    responses:
      200:
        description: 已清空
    """
    for record in get_history_store():
        _remove_record_files(record)
    clear_history_db()
    set_history_store([])
    return ok_response('')


@history_bp.route('/api/history/<int:index>', methods=['DELETE'])
@login_required
def delete_history_record(index):
    """
    删除单条历史记录（同时删除关联的 xlsx/pdf 文件，需登录）
    ---
    tags:
      - 历史记录
    parameters:
      - in: path
        name: index
        type: integer
        required: true
        description: 记录在历史列表中的下标
    responses:
      200:
        description: 已删除
      404:
        description: 记录不存在
    """
    history = get_history_store()
    if 0 <= index < len(history):
        record = history[index]
        _remove_record_files(record)
        history.pop(index)
        return ok_response('')
    return not_found_response('记录不存在')


@history_bp.route('/api/history/export', methods=['GET'])
@login_required
def export_history():
    """
    导出历史记录为XLSX（需登录）
    ---
    tags:
      - 历史记录
    produces:
      - application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
    responses:
      200:
        description: xlsx 文件内容
      400:
        description: 没有历史记录可导出
    """
    history = get_history_store()
    if not history:
        return "没有历史记录可导出", 400

    try:
        buffer = export_history_to_xlsx(history)
        response = make_response(buffer.getvalue())
        response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        filename = f'query_history_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    except Exception as e:
        traceback.print_exc()
        print(f"导出XLS错误: {e}")
        return f"导出XLS失败: {str(e)}", 500
