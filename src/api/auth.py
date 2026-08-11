# ============== 认证蓝图 ==============
from flask import Blueprint, request, jsonify, session

# 导入认证模块（根据运行环境选择方式）
try:
    from ..auth import login_user
except ImportError:
    from auth import login_user

# 导入公共响应封装
try:
    from ..utils import ok_response, fail_response
except ImportError:
    from utils import ok_response, fail_response

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/api/session', methods=['POST'])
def create_session():
    """
    登录（创建会话）
    ---
    tags:
      - 会话
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [username, password]
          properties:
            username:
              type: string
              example: admin
            password:
              type: string
              example: admin123
    responses:
      200:
        description: 登录成功
      401:
        description: 用户名或密码错误
    """
    username = request.json.get('username', '').strip()
    password = request.json.get('password', '')

    success, user, message = login_user(username, password)

    if success:
        session['user'] = user
        return ok_response(message, user=user)
    return fail_response(message, 401)


@auth_bp.route('/api/session', methods=['DELETE'])
def delete_session():
    """
    登出（删除会话）
    ---
    tags:
      - 会话
    responses:
      200:
        description: 已退出登录
    """
    session.pop('user', None)
    return ok_response('已退出登录')


@auth_bp.route('/api/session', methods=['GET'])
def get_session():
    """
    查询当前会话状态
    ---
    tags:
      - 会话
    responses:
      200:
        description: 当前登录状态
        schema:
          type: object
          properties:
            logged_in:
              type: boolean
            user:
              type: object
    """
    user = session.get('user')
    if user:
        return jsonify({'logged_in': True, 'user': user})
    return jsonify({'logged_in': False})
