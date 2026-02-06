@echo off
REM Telegram 机器人管理系统启动脚本 (Windows)
chcp 65001 >nul
cls
echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║     🤖 Telegram 机器人管理系统 v1.0                          ║
echo ║     前后端分离架构                                            ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.

REM 检查 Python 是否安装
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 错误: 未检测到 Python，请先安装 Python 3.8+
    pause
    exit /b 1
)

REM 检查虚拟环境
if not exist venv (
    echo 📦 创建虚拟环境...
    python -m venv venv
)

REM 激活虚拟环境
call venv\Scripts\activate.bat

REM 安装依赖
echo 📥 检查并安装依赖...
pip install -q -r requirements.txt

REM 启动应用
echo.
echo 🚀 启动应用...
echo 📝 访问地址: http://localhost:5000
echo 🛑 按 Ctrl+C 停止服务
echo.

python run.py

pause
