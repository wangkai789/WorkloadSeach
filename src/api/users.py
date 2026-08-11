# ============== 用户管理蓝图 ==============
from flask import Blueprint, request

# 导入认证模块（根据运行环境选择方式）
try:
    from ..auth import (
        get_all_users, delete_user, update_user, get_user_by_id,
        register_user, update_dingtalk_userid
    )
except ImportError:
    from auth import (
        get_all_users, delete_user, update_user, get_user_by_id,
        register_user, update_dingtalk_userid
    )

# 导入公共装饰器与响应封装
try:
    from ..utils import login_required, ok_response, fail_response, not_found_response
except ImportError:
    from utils import login_required, ok_response, fail_response, not_found_response

users_bp = Blueprint('users', __name__)


@users_bp.route('/api/users', methods=['POST'])
def create_user():
    """
    注册（创建用户），无需登录
    ---
    tags:
      - 用户管理
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [employee_id, username, password]
          properties:
            employee_id:
              type: string
            username:
              type: string
            password:
              type: string
            phone:
              type: string
            title:
              type: string
              description: 职称，如 主任医师/副主任医师/护士/麻醉师
            start_date:
              type: string
              example: "2026-01-01"
            end_date:
              type: string
              example: "2026-12-31"
    responses:
      200:
        description: 注册成功
    """
    data = request.json
    employee_id = data.get('employee_id', '').strip()
    username = data.get('username', '').strip()
    password = data.get('password', '')
    phone = data.get('phone', '').strip()
    title = data.get('title', '').strip()
    start_date = data.get('start_date', '2026-01-01').strip()
    end_date = data.get('end_date', '2026-12-31').strip()

    success, message, user_id = register_user(
        employee_id, username, password, phone, title, start_date, end_date
    )

    if success:
        return ok_response(message, user_id=user_id)
    return fail_response(message)


@users_bp.route('/api/users', methods=['GET'])
@login_required
def list_users():
    """
    获取用户列表（需登录）
    ---
    tags:
      - 用户管理
    responses:
      200:
        description: 用户列表
      401:
        description: 未登录
    """
    users = get_all_users()
    return ok_response('', users=users)


@users_bp.route('/api/users/<int:user_id>', methods=['GET'])
@login_required
def get_user(user_id):
    """
    根据ID获取用户信息（需登录）
    ---
    tags:
      - 用户管理
    parameters:
      - in: path
        name: user_id
        type: integer
        required: true
    responses:
      200:
        description: 用户信息
      404:
        description: 用户不存在
    """
    user = get_user_by_id(user_id)
    if user:
        return ok_response('', user=user)
    return not_found_response('用户不存在')


@users_bp.route('/api/users/<int:user_id>', methods=['PUT'])
@login_required
def replace_user(user_id):
    """
    更新用户（需登录）
    ---
    tags:
      - 用户管理
    parameters:
      - in: path
        name: user_id
        type: integer
        required: true
      - in: body
        name: body
        schema:
          type: object
          properties:
            employee_id:
              type: string
            username:
              type: string
            password:
              type: string
            phone:
              type: string
            title:
              type: string
            start_date:
              type: string
            end_date:
              type: string
    responses:
      200:
        description: 更新成功
    """
    data = request.json
    employee_id = data.get('employee_id')
    username = data.get('username')
    password = data.get('password')
    phone = data.get('phone')
    title = data.get('title')
    start_date = data.get('start_date')
    end_date = data.get('end_date')

    success, message = update_user(
        user_id, employee_id, username, password, phone, title, start_date, end_date
    )
    return ok_response(message) if success else fail_response(message)


@users_bp.route('/api/users/<int:user_id>', methods=['DELETE'])
@login_required
def remove_user(user_id):
    """
    删除用户（需登录）
    ---
    tags:
      - 用户管理
    parameters:
      - in: path
        name: user_id
        type: integer
        required: true
    responses:
      200:
        description: 删除成功
    """
    success, message = delete_user(user_id)
    return ok_response(message) if success else fail_response(message)


@users_bp.route('/api/users/<int:user_id>/dingtalk', methods=['PUT'])
@login_required
def replace_user_dingtalk(user_id):
    """
    更新用户钉钉ID（需登录）
    ---
    tags:
      - 用户管理
    parameters:
      - in: path
        name: user_id
        type: integer
        required: true
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [dingtalk_userid]
          properties:
            dingtalk_userid:
              type: string
    responses:
      200:
        description: 更新成功
    """
    dingtalk_userid = request.json.get('dingtalk_userid', '').strip()
    success, message = update_dingtalk_userid(user_id, dingtalk_userid)
    return ok_response(message) if success else fail_response(message)
