# ============== 认证模块 ==============
import os
import sys
import sqlite3
import hashlib
from datetime import datetime

# 获取用户数据库路径
def get_users_db():
    """获取用户数据库路径"""
    if getattr(sys, 'frozen', False):
        return os.path.join(os.path.dirname(sys.executable), 'Ldhcc.db')
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'dist', 'Ldhcc.db')


def init_users_db():
    """初始化用户数据库"""
    try:
        conn = sqlite3.connect(get_users_db())
        
        # 检查表是否存在
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        table_exists = cursor.fetchone() is not None
        
        if table_exists:
            # 检查是否需要迁移（旧结构没有employee_id列）
            cursor.execute("PRAGMA table_info(users)")
            columns = [col[1] for col in cursor.fetchall()]
            
            # 迁移旧表到新结构
            if 'employee_id' not in columns:
                print("检测到旧数据库结构，正在迁移...")
                
                # SQLite不支持直接添加UNIQUE列，需要重建表
                # 1. 备份旧数据
                cursor.execute("SELECT * FROM users")
                old_data = cursor.fetchall()
                cursor.execute("SELECT * FROM users LIMIT 0")
                old_columns = [desc[0] for desc in cursor.description]
                
                # 2. 创建新表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS users_new (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        employee_id TEXT,
                        username TEXT NOT NULL,
                        password TEXT NOT NULL,
                        phone TEXT,
                        title TEXT,
                        start_date TEXT DEFAULT '2026-01-01',
                        end_date TEXT DEFAULT '2026-12-31',
                        dingtalk_userid TEXT,
                        created_at TEXT NOT NULL
                    )
                ''')
                
                # 3. 迁移数据
                for row in old_data:
                    row_dict = dict(zip(old_columns, row))
                    cursor.execute('''
                        INSERT INTO users_new (id, employee_id, username, password, phone, title, start_date, end_date, dingtalk_userid, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        row_dict.get('id'),
                        row_dict.get('username'),  # 复制username到employee_id
                        row_dict.get('username'),
                        row_dict.get('password'),
                        row_dict.get('phone', ''),
                        row_dict.get('title', ''),
                        row_dict.get('start_date', '2026-01-01'),
                        row_dict.get('end_date', '2026-12-31'),
                        row_dict.get('dingtalk_userid', ''),
                        row_dict.get('created_at', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                    ))
                
                # 4. 删除旧表，重命名新表
                conn.execute("DROP TABLE users")
                conn.execute("ALTER TABLE users_new RENAME TO users")
                conn.commit()
                print("数据库迁移完成")
            else:
                # 表已存在但可能缺少部分列，添加缺失的列
                if 'phone' not in columns:
                    cursor.execute("ALTER TABLE users ADD COLUMN phone TEXT")
                if 'title' not in columns:
                    cursor.execute("ALTER TABLE users ADD COLUMN title TEXT")
                if 'start_date' not in columns:
                    cursor.execute("ALTER TABLE users ADD COLUMN start_date TEXT DEFAULT '2026-01-01'")
                if 'end_date' not in columns:
                    cursor.execute("ALTER TABLE users ADD COLUMN end_date TEXT DEFAULT '2026-12-31'")
                if 'dingtalk_userid' not in columns:
                    cursor.execute("ALTER TABLE users ADD COLUMN dingtalk_userid TEXT")
                conn.commit()
        else:
            # 创建新表
            conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    employee_id TEXT UNIQUE NOT NULL,
                    username TEXT NOT NULL,
                    password TEXT NOT NULL,
                    phone TEXT,
                    title TEXT,
                    start_date TEXT DEFAULT '2026-01-01',
                    end_date TEXT DEFAULT '2026-12-31',
                    dingtalk_userid TEXT,
                    created_at TEXT NOT NULL
                )
            ''')
            conn.commit()
        
        conn.close()
        return True
    except Exception as e:
        print(f"初始化用户数据库失败: {e}")
        return False


def hash_password(password):
    """密码哈希"""
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(password, hashed):
    """验证密码"""
    return hash_password(password) == hashed


def register_user(employee_id, name, password, phone='', title='', start_date='2026-01-01', end_date='2026-12-31'):
    """注册用户"""
    if not employee_id or not name or not password:
        return False, "员工编号、姓名和密码不能为空"
    
    if len(password) < 6:
        return False, "密码至少6个字符"
    
    try:
        conn = sqlite3.connect(get_users_db())
        cursor = conn.cursor()
        
        # 检查员工编号是否存在
        cursor.execute('SELECT id FROM users WHERE employee_id = ?', (employee_id,))
        if cursor.fetchone():
            conn.close()
            return False, "员工编号已存在"
        
        # 创建用户
        cursor.execute(
            '''INSERT INTO users (employee_id, username, password, phone, title, start_date, end_date, dingtalk_userid, created_at) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (employee_id, name, hash_password(password), phone, title, start_date, end_date, '', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        )
        conn.commit()
        user_id = cursor.lastrowid
        conn.close()
        return True, "注册成功", user_id
    except Exception as e:
        print(f"注册失败: {e}")
        return False, f"注册失败: {str(e)}", None


def login_user(username, password):
    """登录验证（支持员工编号或姓名登录）"""
    if not username or not password:
        return False, None, "用户名和密码不能为空"
    
    try:
        conn = sqlite3.connect(get_users_db())
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute(
            'SELECT id, employee_id, username, phone, title, start_date, end_date, dingtalk_userid, password FROM users WHERE employee_id = ? OR username = ?', 
            (username, username)
        )
        user = cursor.fetchone()
        conn.close()
        
        if not user:
            return False, None, "用户名或密码错误"
        
        if not verify_password(password, user['password']):
            return False, None, "用户名或密码错误"
        
        user_info = {
            'id': user['id'],
            'employee_id': user['employee_id'],
            'username': user['username'],
            'phone': user['phone'],
            'title': user['title'],
            'start_date': user['start_date'],
            'end_date': user['end_date'],
            'dingtalk_userid': user['dingtalk_userid']
        }
        return True, user_info, "登录成功"
    except Exception as e:
        print(f"登录失败: {e}")
        return False, None, f"登录失败: {str(e)}"


def get_user_by_id(user_id):
    """根据ID获取用户信息"""
    try:
        conn = sqlite3.connect(get_users_db())
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            'SELECT id, employee_id, username, phone, title, start_date, end_date, dingtalk_userid FROM users WHERE id = ?',
            (user_id,)
        )
        user = cursor.fetchone()
        conn.close()
        if user:
            return {
                'id': user['id'],
                'employee_id': user['employee_id'],
                'username': user['username'],
                'phone': user['phone'],
                'title': user['title'],
                'start_date': user['start_date'],
                'end_date': user['end_date'],
                'dingtalk_userid': user['dingtalk_userid']
            }
        return None
    except Exception as e:
        print(f"获取用户信息失败: {e}")
        return None


def get_all_users():
    """获取所有用户列表（按创建日期字段 created_at 倒序，同一时间按 id 倒序）"""
    try:
        conn = sqlite3.connect(get_users_db())
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            'SELECT id, employee_id, username, phone, title, start_date, end_date, '
            'dingtalk_userid, created_at FROM users ORDER BY created_at DESC, id DESC'
        )
        users = cursor.fetchall()
        conn.close()
        return [dict(user) for user in users]
    except Exception as e:
        print(f"获取用户列表失败: {e}")
        return []


def delete_user(user_id):
    """删除用户"""
    try:
        conn = sqlite3.connect(get_users_db())
        cursor = conn.cursor()
        cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
        conn.commit()
        conn.close()
        return True, "删除成功"
    except Exception as e:
        print(f"删除用户失败: {e}")
        return False, f"删除失败: {str(e)}"


def update_user(user_id, employee_id=None, username=None, password=None, phone=None, title=None, start_date=None, end_date=None):
    """更新用户信息"""
    try:
        conn = sqlite3.connect(get_users_db())
        cursor = conn.cursor()
        
        # 构建更新语句
        updates = []
        params = []
        
        if employee_id is not None:
            # 检查员工编号是否被其他用户使用
            cursor.execute('SELECT id FROM users WHERE employee_id = ? AND id != ?', (employee_id, user_id))
            if cursor.fetchone():
                conn.close()
                return False, "员工编号已被其他用户使用"
            updates.append('employee_id = ?')
            params.append(employee_id)
        
        if username is not None:
            updates.append('username = ?')
            params.append(username)
        
        if password is not None:
            if len(password) < 6:
                conn.close()
                return False, "密码至少6个字符"
            updates.append('password = ?')
            params.append(hash_password(password))
        
        if phone is not None:
            updates.append('phone = ?')
            params.append(phone)
        
        if title is not None:
            updates.append('title = ?')
            params.append(title)
        
        if start_date is not None:
            updates.append('start_date = ?')
            params.append(start_date)
        
        if end_date is not None:
            updates.append('end_date = ?')
            params.append(end_date)
        
        if not updates:
            conn.close()
            return False, "没有要更新的字段"
        
        params.append(user_id)
        cursor.execute(f"UPDATE users SET {', '.join(updates)} WHERE id = ?", params)
        conn.commit()
        conn.close()
        return True, "更新成功"
    except Exception as e:
        print(f"更新用户失败: {e}")
        return False, f"更新失败: {str(e)}"


def update_dingtalk_userid(user_id, dingtalk_userid):
    """更新用户的钉钉用户ID"""
    try:
        conn = sqlite3.connect(get_users_db())
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET dingtalk_userid = ? WHERE id = ?', (dingtalk_userid, user_id))
        conn.commit()
        conn.close()
        return True, "更新成功"
    except Exception as e:
        print(f"更新钉钉用户ID失败: {e}")
        return False, f"更新失败: {str(e)}"


def get_dingtalk_userid_by_employee_id(employee_id):
    """根据员工编号获取钉钉用户ID"""
    try:
        conn = sqlite3.connect(get_users_db())
        cursor = conn.cursor()
        cursor.execute('SELECT dingtalk_userid FROM users WHERE employee_id = ?', (employee_id,))
        result = cursor.fetchone()
        conn.close()
        if result and result[0]:
            return result[0]
        return None
    except Exception as e:
        print(f"获取钉钉用户ID失败: {e}")
        return None


def create_default_admin():
    """创建默认管理员账户"""
    try:
        conn = sqlite3.connect(get_users_db())
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM users WHERE employee_id = ?', ('admin',))
        if not cursor.fetchone():
            cursor.execute(
                '''INSERT INTO users (employee_id, username, password, phone, title, start_date, end_date, created_at) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                ('admin', '管理员', hash_password('admin123'), '', '管理员', '2026-01-01', '2026-12-31', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            )
            conn.commit()
            print("默认管理员账户已创建: admin / admin123")
        conn.close()
    except Exception as e:
        print(f"创建默认账户失败: {e}")
