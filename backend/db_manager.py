"""
数据库管理模块
"""
import sqlite3
import os
from typing import List, Tuple, Optional
from threading import Lock


class DBManager:
    """数据库管理器"""
    
    def __init__(self, db_file: str = 'personality_recycle.db'):
        self.db_file = db_file
        self.lock = Lock()
        self.init_db()
    
    def init_db(self):
        """初始化数据库"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # 用户映射表：源用户 -> 分配的克隆号
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_mapping (
                    source_user_id INTEGER PRIMARY KEY,
                    assigned_sender_name TEXT,
                    source_username TEXT,
                    last_active INTEGER
                )
            ''')

            # 迁移逻辑：如果旧版本表缺少新列，则添加之（向后兼容）
            try:
                cursor.execute("PRAGMA table_info(user_mapping)")
                cols = [r[1] for r in cursor.fetchall()]
                if 'source_username' not in cols:
                    cursor.execute("ALTER TABLE user_mapping ADD COLUMN source_username TEXT DEFAULT ''")
            except Exception:
                pass
            
            # 账号初始化状态表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS account_init_status (
                    session_name TEXT PRIMARY KEY,
                    initialized INTEGER,
                    created_time INTEGER,
                    last_used INTEGER
                )
            ''')

            # 迁移逻辑：如果旧版本表缺少新列，则添加之（向后兼容）
            try:
                cursor.execute("PRAGMA table_info(account_init_status)")
                cols = [r[1] for r in cursor.fetchall()]
                if 'created_time' not in cols:
                    cursor.execute("ALTER TABLE account_init_status ADD COLUMN created_time INTEGER DEFAULT 0")
                if 'last_used' not in cols:
                    cursor.execute("ALTER TABLE account_init_status ADD COLUMN last_used INTEGER DEFAULT 0")
            except Exception:
                # 忽略迁移错误，后续操作仍可继续
                pass
            
            # 账号登录状态表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS account_status (
                    session_name TEXT PRIMARY KEY,
                    is_active INTEGER,
                    phone_number TEXT,
                    user_id INTEGER,
                    username TEXT,
                    display_name TEXT,
                    login_time INTEGER,
                    last_check_time INTEGER
                )
            ''')

            # 迁移逻辑：如果旧版本表缺少新列，则添加之（向后兼容）
            try:
                cursor.execute("PRAGMA table_info(account_status)")
                cols = [r[1] for r in cursor.fetchall()]
                if 'username' not in cols:
                    cursor.execute("ALTER TABLE account_status ADD COLUMN username TEXT DEFAULT ''")
                if 'display_name' not in cols:
                    cursor.execute("ALTER TABLE account_status ADD COLUMN display_name TEXT DEFAULT ''")
            except Exception:
                pass
            
            # 消息统计表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS message_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sender_name TEXT,
                    target_group TEXT,
                    message_count INTEGER DEFAULT 0,
                    last_forward_time INTEGER,
                    created_date TEXT
                )
            ''')

            # 转发消息映射表：源消息 -> 目标消息（用于回复同步）
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS message_mapping (
                    source_chat_id INTEGER,
                    source_msg_id INTEGER,
                    target_group TEXT,
                    target_msg_id INTEGER,
                    sender_name TEXT,
                    created_time INTEGER,
                    PRIMARY KEY (source_chat_id, source_msg_id, target_group)
                )
            ''')

            # 登录失败记录（用于自动登录跳过）
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS login_failures (
                    session_name TEXT PRIMARY KEY,
                    fail_count INTEGER DEFAULT 0,
                    last_error TEXT,
                    last_fail_time INTEGER
                )
            ''')

            # 用户名映射表：源用户名 -> 分配的克隆号（用于 @ 同步，未发言用户）
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS username_mapping (
                    source_username TEXT PRIMARY KEY,
                    assigned_sender_name TEXT,
                    last_active INTEGER
                )
            ''')
            
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"❌ 数据库初始化失败: {e}")
    
    def _get_connection(self):
        """获取数据库连接"""
        # 增加 timeout 并启用 WAL 模式，设置 busy_timeout 以在数据库被锁时等待
        conn = sqlite3.connect(self.db_file, check_same_thread=False, timeout=30)
        conn.execute('PRAGMA journal_mode=WAL')
        try:
            # busy_timeout 用毫秒
            conn.execute('PRAGMA busy_timeout = 30000')
        except Exception:
            pass
        return conn
    
    # ========== 用户映射操作 ==========
    def get_user_mapping(self, source_user_id: int) -> Optional[str]:
        """获取源用户分配的克隆号"""
        with self.lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT assigned_sender_name FROM user_mapping WHERE source_user_id=?", 
                             (source_user_id,))
                result = cursor.fetchone()
                conn.close()
                return result[0] if result else None
            except Exception as e:
                print(f"❌ 查询用户映射失败: {e}")
                return None
    
    def set_user_mapping(self, source_user_id: int, sender_name: str, source_username: str = ''):
        """设置源用户的克隆号映射"""
        import time
        with self.lock:
            try:
                norm_username = (source_username or '').lstrip('@').lower()
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute("INSERT OR REPLACE INTO user_mapping VALUES (?, ?, ?, ?)", 
                             (source_user_id, sender_name, norm_username, int(time.time())))
                conn.commit()
                conn.close()
            except Exception as e:
                print(f"❌ 设置用户映射失败: {e}")
    
    def delete_user_mapping(self, source_user_id: int):
        """删除用户映射"""
        with self.lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute("DELETE FROM user_mapping WHERE source_user_id=?", 
                             (source_user_id,))
                conn.commit()
                conn.close()
            except Exception as e:
                print(f"❌ 删除用户映射失败: {e}")

    def get_sender_by_source_username(self, source_username: str) -> Optional[str]:
        """根据源用户用户名获取对应克隆号会话名"""
        if not source_username:
            return None
        with self.lock:
            try:
                norm = source_username.lstrip('@').lower()
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT assigned_sender_name FROM user_mapping WHERE lower(source_username)=?",
                             (norm,))
                result = cursor.fetchone()
                if not result:
                    cursor.execute("SELECT assigned_sender_name FROM username_mapping WHERE lower(source_username)=?",
                                 (norm,))
                    result = cursor.fetchone()
                conn.close()
                return result[0] if result else None
            except Exception as e:
                print(f"❌ 查询用户名映射失败: {e}")
                return None

    def set_username_mapping(self, source_username: str, sender_name: str):
        """设置源用户名的克隆号映射（用于 @ 同步）"""
        import time
        if not source_username:
            return
        with self.lock:
            try:
                norm = source_username.lstrip('@').lower()
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT OR REPLACE INTO username_mapping VALUES (?, ?, ?)",
                    (norm, sender_name, int(time.time()))
                )
                conn.commit()
                conn.close()
            except Exception as e:
                print(f"❌ 设置用户名映射失败: {e}")
    
    # ========== 账号初始化状态操作 ==========
    def is_account_initialized(self, session_name: str) -> bool:
        """检查账号是否已初始化"""
        with self.lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT initialized FROM account_init_status WHERE session_name=?", 
                             (session_name,))
                result = cursor.fetchone()
                conn.close()
                return result[0] if result else 0
            except Exception as e:
                print(f"❌ 查询初始化状态失败: {e}")
                return False
    
    def mark_account_initialized(self, session_name: str):
        """标记账号为已初始化"""
        import time
        with self.lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute("INSERT OR REPLACE INTO account_init_status VALUES (?, ?, ?, ?)", 
                             (session_name, 1, int(time.time()), int(time.time())))
                conn.commit()
                conn.close()
            except Exception as e:
                print(f"❌ 标记初始化失败: {e}")
    
    # ========== 账号状态操作 ==========
    def update_account_status(self, session_name: str, is_active: bool,
                             phone_number: str = '', user_id: int = 0,
                             username: str = '', display_name: str = ''):
        """更新账号状态"""
        import time
        with self.lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO account_status 
                    (session_name, is_active, phone_number, user_id, username, display_name, login_time, last_check_time)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    session_name,
                    1 if is_active else 0,
                    phone_number,
                    user_id,
                    username,
                    display_name,
                    int(time.time()),
                    int(time.time())
                ))
                conn.commit()
                conn.close()
            except Exception as e:
                print(f"❌ 更新账号状态失败: {e}")
    
    def get_account_status(self, session_name: str) -> Optional[dict]:
        """获取账号状态"""
        with self.lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT session_name, is_active, phone_number, user_id, username, display_name, login_time, last_check_time
                    FROM account_status WHERE session_name=?
                """, (session_name,))
                result = cursor.fetchone()
                conn.close()
                if result:
                    return {
                        'session_name': result[0],
                        'is_active': bool(result[1]),
                        'phone_number': result[2],
                        'user_id': result[3],
                        'username': result[4],
                        'display_name': result[5],
                        'login_time': result[6],
                        'last_check_time': result[7]
                    }
                return None
            except Exception as e:
                print(f"❌ 获取账号状态失败: {e}")
                return None
    
    def get_all_accounts_status(self) -> List[dict]:
        """获取所有账号状态"""
        with self.lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT session_name, is_active, phone_number, user_id, username, display_name, login_time, last_check_time
                    FROM account_status
                """)
                results = cursor.fetchall()
                conn.close()
                return [{
                    'session_name': r[0],
                    'is_active': bool(r[1]),
                    'phone_number': r[2],
                    'user_id': r[3],
                    'username': r[4],
                    'display_name': r[5],
                    'login_time': r[6],
                    'last_check_time': r[7]
                } for r in results]
            except Exception as e:
                print(f"❌ 获取所有账号状态失败: {e}")
                return []
    
    def remove_account_status(self, session_name: str):
        """移除账号状态"""
        with self.lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute("DELETE FROM account_status WHERE session_name=?", 
                             (session_name,))
                conn.commit()
                conn.close()
            except Exception as e:
                print(f"❌ 移除账号状态失败: {e}")
    
    # ========== 消息统计操作 ==========
    def record_message_forward(self, sender_name: str, target_group: str):
        """记录消息转发"""
        import time
        from datetime import date
        with self.lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                today = str(date.today())
                
                cursor.execute("""
                    SELECT id, message_count FROM message_stats 
                    WHERE sender_name=? AND target_group=? AND created_date=?
                """, (sender_name, target_group, today))
                result = cursor.fetchone()
                
                if result:
                    cursor.execute("""
                        UPDATE message_stats 
                        SET message_count=?, last_forward_time=?
                        WHERE id=?
                    """, (result[1] + 1, int(time.time()), result[0]))
                else:
                    cursor.execute("""
                        INSERT INTO message_stats 
                        (sender_name, target_group, message_count, last_forward_time, created_date)
                        VALUES (?, ?, ?, ?, ?)
                    """, (sender_name, target_group, 1, int(time.time()), today))
                
                conn.commit()
                conn.close()
            except Exception as e:
                print(f"❌ 记录消息转发失败: {e}")

    # ========== 消息映射操作 ==========
    def record_message_mapping(self, source_chat_id: int, source_msg_id: int,
                               target_group: str, target_msg_id: int, sender_name: str):
        """记录源消息与目标消息的映射关系"""
        import time
        with self.lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO message_mapping
                    (source_chat_id, source_msg_id, target_group, target_msg_id, sender_name, created_time)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (source_chat_id, source_msg_id, target_group, target_msg_id, sender_name, int(time.time())))
                conn.commit()
                conn.close()
            except Exception as e:
                print(f"❌ 记录消息映射失败: {e}")

    def get_target_message_id(self, source_chat_id: int, source_msg_id: int,
                              target_group: str) -> Optional[int]:
        """获取目标群中对应的消息 ID（用于回复同步）"""
        with self.lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT target_msg_id FROM message_mapping
                    WHERE source_chat_id=? AND source_msg_id=? AND target_group=?
                """, (source_chat_id, source_msg_id, target_group))
                result = cursor.fetchone()
                conn.close()
                return int(result[0]) if result else None
            except Exception as e:
                print(f"❌ 查询消息映射失败: {e}")
                return None
    
    def get_message_stats(self, days: int = 7) -> List[dict]:
        """获取消息统计"""
        from datetime import datetime, timedelta
        with self.lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                start_date = (datetime.now() - timedelta(days=days)).date()
                
                cursor.execute("""
                    SELECT sender_name, target_group, message_count, last_forward_time, created_date
                    FROM message_stats 
                    WHERE created_date >= ?
                    ORDER BY created_date DESC
                """, (str(start_date),))
                results = cursor.fetchall()
                conn.close()
                
                return [{
                    'sender_name': r[0],
                    'target_group': r[1],
                    'message_count': r[2],
                    'last_forward_time': r[3],
                    'created_date': r[4]
                } for r in results]
            except Exception as e:
                print(f"❌ 获取消息统计失败: {e}")
                return []


    # ========== 登录失败记录 ==========
    def record_login_failure(self, session_name: str, error_msg: str):
        """记录登录失败（用于后续自动登录跳过）"""
        import time
        with self.lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT fail_count FROM login_failures WHERE session_name=?", (session_name,))
                result = cursor.fetchone()
                if result:
                    cursor.execute("""
                        UPDATE login_failures
                        SET fail_count=?, last_error=?, last_fail_time=?
                        WHERE session_name=?
                    """, (result[0] + 1, error_msg, int(time.time()), session_name))
                else:
                    cursor.execute("""
                        INSERT INTO login_failures
                        (session_name, fail_count, last_error, last_fail_time)
                        VALUES (?, ?, ?, ?)
                    """, (session_name, 1, error_msg, int(time.time())))
                conn.commit()
                conn.close()
            except Exception as e:
                print(f"❌ 记录登录失败出错: {e}")

    def clear_login_failure(self, session_name: str):
        """清除登录失败记录"""
        with self.lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute("DELETE FROM login_failures WHERE session_name=?", (session_name,))
                conn.commit()
                conn.close()
            except Exception as e:
                print(f"❌ 清除登录失败记录出错: {e}")

    def get_login_failures(self) -> List[dict]:
        """获取登录失败记录"""
        with self.lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT session_name, fail_count, last_error, last_fail_time FROM login_failures")
                results = cursor.fetchall()
                conn.close()
                return [{
                    'session_name': r[0],
                    'fail_count': r[1],
                    'last_error': r[2],
                    'last_fail_time': r[3]
                } for r in results]
            except Exception as e:
                print(f"❌ 获取登录失败记录出错: {e}")
                return []

# 全局数据库管理器实例
db_manager = DBManager()
