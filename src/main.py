# ============== 主入口 ==============
import os
import sys

# 添加src目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask

# 导入配置
from config import load_config, get_db_config, get_output_dir

# 导入数据库模块（加载历史记录）
from database import load_history

# 导入蓝图包
from api import ALL_BLUEPRINTS, pages_bp

# 导入历史状态同步（兼容 routes.py）
from api.history import set_history_store


def create_app():
    """创建Flask应用（应用工厂）"""
    app = Flask(__name__)
    app.secret_key = 'dhcc_inpatient_query_2024_secret_key'  # Session密钥

    # ---------- 路径配置 ----------
    if getattr(sys, 'frozen', False):
        APP_DIR = os.path.dirname(sys.executable)
        TEMPLATES_DIR = os.path.join(APP_DIR, 'templates')
        if os.path.exists(TEMPLATES_DIR):
            app.template_folder = TEMPLATES_DIR
    else:
        app.template_folder = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), '..', 'templates'
        )

    # ---------- 注册蓝图 ----------
    for bp in ALL_BLUEPRINTS:
        app.register_blueprint(bp)
        print(f"[APP] 已注册蓝图: {bp.name}")

    return app


def main():
    """主函数"""
    # 加载配置
    load_config()

    # 加载历史记录并同步到蓝图存储
    history = load_history()
    set_history_store(history)

    # 创建应用
    app = create_app()

    # 打印启动信息
    db_config = get_db_config()
    print("=" * 50)
    print("东华住院工作量查询 Web服务")
    print(f"服务器: {db_config.get('server', 'N/A')}")
    print(f"数据库: {db_config.get('database', 'N/A')}")
    print(f"输出目录: {get_output_dir()}")
    print("=" * 50)

    # 启动服务
    app.run(host='0.0.0.0', port=5003, debug=True)


if __name__ == '__main__':
    main()
