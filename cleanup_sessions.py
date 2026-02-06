"""
清理旧的会话文件 - 用于重新登录
"""
import os
import glob
import shutil

def cleanup_sessions():
    """删除所有旧的会话文件"""
    
    # 删除 sessions 文件夹中的所有会话
    sessions_dir = 'sessions'
    if os.path.exists(sessions_dir):
        for file in glob.glob(os.path.join(sessions_dir, '*.session*')):
            try:
                os.remove(file)
                print(f"✓ 删除会话: {file}")
            except Exception as e:
                print(f"✗ 删除失败: {file} - {e}")
    
    # 删除根目录中的 monitor.session
    if os.path.exists('monitor.session'):
        try:
            os.remove('monitor.session')
            print(f"✓ 删除会话: monitor.session")
        except Exception as e:
            print(f"✗ 删除失败: monitor.session - {e}")
    
    # 清空数据库中的登录状态
    try:
        from backend.db_manager import db_manager
        
        # 重置所有账户的状态为未激活
        import sqlite3
        conn = sqlite3.connect('bot.db')
        cursor = conn.cursor()
        
        cursor.execute('UPDATE account_status SET is_active = 0, last_checked = NULL')
        cursor.execute('DELETE FROM account_init_status')
        conn.commit()
        conn.close()
        
        print("✓ 清除数据库中的账户状态")
    except Exception as e:
        print(f"✗ 清除数据库失败: {e}")
    
    print("\n✅ 会话清理完成！请重新登录账户。")

if __name__ == '__main__':
    cleanup_sessions()
