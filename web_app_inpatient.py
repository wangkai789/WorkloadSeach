# ============== 东华住院工作量查询 Web服务 ==============
# 主入口文件

VERSION = "2.1"  # 版本号

import os
import sys

# 设置路径
if getattr(sys, 'frozen', False):
    APP_DIR = os.path.dirname(sys.executable)
    TEMPLATES_DIR = os.path.join(APP_DIR, 'templates')
    sys.path.insert(0, APP_DIR)
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, os.path.join(APP_DIR, 'src'))

from flask import Flask
from flasgger import Swagger
from src.config import load_config, get_db_config, get_output_dir
from src.database import load_history
from src.auth import init_users_db, create_default_admin
from src.api import ALL_BLUEPRINTS
from src.api.history import set_history_store

app = Flask(__name__)
app.secret_key = 'dhcc_inpatient_query_2024_secret_key'  # Session密钥

# 路径配置
if getattr(sys, 'frozen', False):
    if os.path.exists(TEMPLATES_DIR):
        app.template_folder = TEMPLATES_DIR
    else:
        app.template_folder = os.path.join(APP_DIR, 'templates')

# Swagger UI（/apidocs/）：仅收录 /api/ 下的 JSON 接口，页面路由不纳入文档
swagger_config = {
    **Swagger.DEFAULT_CONFIG,
    'specs': [
        {
            'endpoint': 'apispec',
            'route': '/apispec.json',
            'rule_filter': lambda rule: rule.rule.startswith('/api/'),
            'model_filter': lambda tag: True,
        }
    ],
    'specs_route': '/apidocs/',
}
swagger_template = {
    'swagger': '2.0',
    'info': {
        'title': '东华住院工作量查询 API',
        'description': '住院/门诊工作量查询、患者查询、用户管理等接口文档',
        'version': VERSION,
    },
}
Swagger(app, config=swagger_config, template=swagger_template)

# 初始化
load_config()

# 加载历史记录并同步到蓝图存储
history = load_history()
set_history_store(history)

# 初始化用户数据库
init_users_db()
create_default_admin()

# 注册所有蓝图
for bp in ALL_BLUEPRINTS:
    app.register_blueprint(bp)
    print(f"[APP] 已注册蓝图: {bp.name}")

if __name__ == '__main__':
    db_config = get_db_config()
    print("=" * 50)
    print(f"东华住院工作量查询 Web服务 v{VERSION}")
    print(f"服务器: {db_config.get('server', 'N/A')}")
    print(f"数据库: {db_config.get('database', 'N/A')}")
    print(f"输出目录: {get_output_dir()}")
    print("=" * 50)
    print("默认账户: admin / admin123")
    print("=" * 50)
    app.run(host='0.0.0.0', port=5003, debug=True)
