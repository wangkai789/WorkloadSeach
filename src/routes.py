# ============== 路由兼容入口 ==============
#
# 本模块已重构为兼容代理，不再直接定义路由。
# 实际路由由 src/api/ 下的蓝图提供。
#
# 保留本模块的原因：
# 1. 外部可能有代码直接调用 init_routes() / get_query_history() / set_query_history()
# 2. 保持数据库导入路径兼容（from routes import init_routes）
#
# 新的应用入口使用 create_app()，内部直接注册蓝图，详见 src/main.py

import os
import sys

# 全局变量（保持向后兼容）
query_history = []


def get_query_history():
    """获取查询历史（兼容外部调用）"""
    # 从蓝图存储读取
    try:
        from .api.history import get_history_store
        return get_history_store()
    except ImportError:
        from api.history import get_history_store
        return get_history_store()


def set_query_history(history):
    """设置查询历史（兼容外部调用）"""
    global query_history
    query_history = history
    # 同步到蓝图存储
    try:
        from .api.history import set_history_store
        set_history_store(history)
    except ImportError:
        from api.history import set_history_store
        set_history_store(history)


def init_routes(app):
    """
    初始化所有路由（兼容入口）
    
    已在 src/main.py 中通过蓝图自动注册，
    本函数仅保留向后兼容，不再重复注册路由。
    
    若需要迁移到纯蓝图架构，可移除本函数的调用。
    """
    # 已迁移到蓝图，无需重复注册
    # 此处仅同步历史状态
    from database import load_history
    set_query_history(load_history())
    print("[ROUTES] 兼容入口已加载，历史状态已同步")


# ---------- 兼容导出 ----------
# 确保 auth.py 中引用的常量仍在 routes 命名空间下
QUERY_TYPES = {
    'sp': ('主任医师', 'Search_Doctor_SP_Workload'),
    'ap': ('副主任医师', 'Search_Doctor_AP_Workload'),
    'nurse': ('护士', 'Search_Nurse_Workload'),
    'anes': ('麻醉师', 'Search_Anes_Workload')
}

# 导出常量供外部使用（保持向后兼容）
from .database import query_data, save_history_record, load_history, clear_history_db, QUERY_TYPES
