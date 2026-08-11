# ============== API 蓝图包 ==============
# 本包按业务域拆分路由，保持职责单一。全部 JSON 接口统一以 /api/ 开头，
# 采用资源化路径 + 语义正确的 HTTP 动词（GET 查询 / POST 创建或触发副作用动作 /
# PUT 整体替换 / DELETE 删除），响应统一通过 utils.py 的 ok_response / fail_response 封装。
#
# 注册顺序：
#   1. pages   - 页面路由（/、/login、/register、/main、/users，非 JSON 接口，不受本规范约束）
#   2. auth    - 会话 API（POST/DELETE/GET /api/session）
#   3. users   - 用户管理 API（/api/users、/api/users/<id>、/api/users/<id>/dingtalk；
#                POST /api/users 同时承担注册功能）
#   4. config  - 配置 API（GET/PUT /api/config、POST /api/config/test-connection）
#   5. query   - 报表/文件/系统动作 API（/api/reports/inpatient-workload、
#                /api/reports/patients/by-doctor、/api/reports/patients/by-nurse、
#                /api/files/*、/api/system/*）
#   6. history - 历史 API（GET/DELETE /api/history、DELETE /api/history/<index>、
#                GET /api/history/export）
#   7. clinic  - 门诊 API（/api/clinic-report-files、/api/reports/outpatient-workload）
#
# 注意事项：
#   - 全局状态 query_history 仍通过 routes.py 的 get_query_history / set_query_history 访问
#   - utils.py 提供公共装饰器和响应封装

from .pages import pages_bp
from .auth import auth_bp
from .users import users_bp
from .config_bp import config_bp
from .query import query_bp
from .history import history_bp
from .clinic import clinic_bp

# 暴露所有蓝图列表，方便 main.py 统一注册
ALL_BLUEPRINTS = [
    pages_bp,
    auth_bp,
    users_bp,
    config_bp,
    query_bp,
    history_bp,
    clinic_bp,
]
