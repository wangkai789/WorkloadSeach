# ============== 公共工具模块 ==============
# 提供跨蓝图共享的装饰器、响应封装和常量定义

from functools import wraps
from flask import session, jsonify


# ---------- 响应封装 ----------

def ok_response(message: str, **kwargs):
    """统一成功响应结构"""
    data = {'success': True, 'message': message}
    data.update(kwargs)
    return jsonify(data)


def fail_response(message: str, status_code: int = 400, **kwargs):
    """统一失败响应结构"""
    data = {'success': False, 'message': message}
    data.update(kwargs)
    return jsonify(data), status_code


def require_login_response():
    """统一返回需要登录的响应（401）"""
    return fail_response('请先登录', 401, require_login=True)


def not_found_response(message: str = '资源不存在'):
    """统一返回资源不存在的响应（404）"""
    return fail_response(message, 404)


# ---------- 装饰器 ----------

def login_required(f):
    """登录验证装饰器：全部蓝图统一使用本版本"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user'):
            return require_login_response()
        return f(*args, **kwargs)
    return decorated_function
