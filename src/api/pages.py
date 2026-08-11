# ============== 页面路由蓝图 ==============
from flask import Blueprint, render_template, redirect, url_for, session

# 获取版本号
try:
    from web_app_inpatient import VERSION
except ImportError:
    VERSION = "1.0.1"

pages_bp = Blueprint('pages', __name__)


@pages_bp.route('/')
def index():
    """主页"""
    if session.get('user'):
        return render_template('inpatient_query.html', version=VERSION)
    return render_template('main.html', version=VERSION)


@pages_bp.route('/login')
@pages_bp.route('/login.html')
def login_page():
    """登录页面"""
    if session.get('user'):
        return redirect(url_for('pages.main_page'))
    return render_template('login.html', version=VERSION)


@pages_bp.route('/register')
@pages_bp.route('/register.html')
def register_page():
    """注册页面"""
    if session.get('user'):
        return redirect(url_for('pages.main_page'))
    return render_template('register.html', version=VERSION)


@pages_bp.route('/main')
def main_page():
    """主页面"""
    if not session.get('user'):
        return redirect(url_for('pages.login_page'))
    return render_template('inpatient_query.html', version=VERSION)


@pages_bp.route('/users')
def users_page():
    """用户管理页面"""
    if not session.get('user'):
        return redirect(url_for('pages.login_page'))
    return render_template('users.html', version=VERSION)
