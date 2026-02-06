#!/bin/bash
# Telegram 机器人管理系统启动脚本 (Linux/Mac)

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║     🤖 Telegram 机器人管理系统 v1.0                          ║"
echo "║     前后端分离架构                                            ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# 检查 Python 是否安装
if ! command -v python3 &> /dev/null; then
    echo "❌ 错误: 未检测到 Python3，请先安装 Python 3.8+"
    exit 1
fi

# 检查虚拟环境
if [ ! -d "venv" ]; then
    echo "📦 创建虚拟环境..."
    python3 -m venv venv
fi

# 激活虚拟环境
source venv/bin/activate

# 安装依赖
echo "📥 检查并安装依赖..."
pip install -q -r requirements.txt

# 启动应用
echo ""
echo "🚀 启动应用..."
echo "📝 访问地址: http://localhost:5000"
echo "🛑 按 Ctrl+C 停止服务"
echo ""

python3 run.py
