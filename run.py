"""
主启动文件 - 运行后端 API 服务
前端管理系统启动脚本的逻辑：
1. 启动服务 (python run.py)
2. 打开管理面板 (http://localhost:5000)
3. 登录账号（监控号和克隆号）
4. 设置配置
5. 点击"启动脚本"按钮
"""
import os
import sys
from pathlib import Path

# 添加项目路径到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from backend.config_manager import config_manager
from backend.account_manager import account_manager
from backend.telegram_service import init_telegram_service
from backend.worker import init_message_worker
from backend.logger_manager import logger_manager
from backend.api import app, init_api


def run_flask_app():
    """运行 Flask 应用"""
    try:
        logger_manager.info("🚀 [Flask]：启动 API 服务...")
        logger_manager.info("📝 [Flask]：访问地址: http://localhost:5000")
        logger_manager.info("📋 [说明]：请在管理面板中登录账号，设置配置，然后点击'启动脚本'按钮")
        app.run(
            debug=False,
            host='0.0.0.0',
            port=5000,
            use_reloader=False,
            threaded=True
        )
    except Exception as e:
        logger_manager.error(f"❌ Flask 启动失败: {e}")


def main():
    """主函数"""
    print("""
    ╔══════════════════════════════════════════════════════════════╗
    ║     🤖 Telegram 机器人管理系统 v1.0                          ║
    ║     前后端分离架构                                            ║
    ╚══════════════════════════════════════════════════════════════╝
    """)

    # 创建必要的目录
    for folder in ['sessions', 'logs', 'profile_photos', 'temp_media', 'configs']:
        os.makedirs(folder, exist_ok=True)

    try:
        # 初始化 API
        logger_manager.info("📡 [初始化]：正在初始化 API...")
        init_api()

        # 初始化 Telegram 服务
        from backend.telegram_service import telegram_service as ts
        from backend.worker import message_worker as mw

        logger_manager.info("✅ [初始化]：系统已初始化完毕")

        # 启动 Flask 应用
        logger_manager.info("🚀 [启动]：启动后端服务...")
        run_flask_app()

    except KeyboardInterrupt:
        logger_manager.info("🛑 [停止]：用户中断，系统正在关闭...")
    except Exception as e:
        logger_manager.error(f"❌ [错误]：系统启动失败 {e}")
        import traceback
        traceback.print_exc()
    finally:
        logger_manager.info("✅ [关闭]：系统已安全关闭")


if __name__ == '__main__':
    main()
