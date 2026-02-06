"""
诊断脚本 - 检查环境和依赖
"""
import os
import sys
import platform
import subprocess
from pathlib import Path


def print_header(text):
    """打印标题"""
    print(f"\n{'=' * 60}")
    print(f"  {text}")
    print(f"{'=' * 60}\n")


def print_section(text):
    """打印小标题"""
    print(f"\n{'─' * 60}")
    print(f"  {text}")
    print(f"{'─' * 60}\n")


def check_python():
    """检查 Python 版本"""
    print_section("Python 环境检查")
    
    version = sys.version_info
    print(f"✅ Python 版本: {version.major}.{version.minor}.{version.micro}")
    
    if version.major >= 3 and version.minor >= 8:
        print("✅ Python 版本满足要求 (3.8+)")
        return True
    else:
        print("❌ Python 版本太低，需要 3.8+")
        return False


def check_pip():
    """检查 pip"""
    print_section("pip 检查")
    
    try:
        result = subprocess.run([sys.executable, "-m", "pip", "--version"], 
                              capture_output=True, text=True)
        print(f"✅ {result.stdout.strip()}")
        return True
    except Exception as e:
        print(f"❌ pip 检查失败: {e}")
        return False


def check_dependencies():
    """检查已安装的依赖"""
    print_section("依赖包检查")
    
    required_packages = {
        'telethon': '1.29+',
        'flask': '2.3+',
        'flask_cors': '4.0+',
        'socks': '1.7+',
    }
    
    all_ok = True
    for package, version in required_packages.items():
        try:
            __import__(package)
            print(f"✅ {package.ljust(20)} 已安装")
        except ImportError:
            print(f"❌ {package.ljust(20)} 未安装 (需要: {version})")
            all_ok = False
    
    return all_ok


def check_directories():
    """检查必要的目录"""
    print_section("目录检查")
    
    required_dirs = [
        'sessions',
        'logs',
        'profile_photos',
        'temp_media',
    ]
    
    for dir_name in required_dirs:
        if os.path.exists(dir_name):
            print(f"✅ {dir_name.ljust(20)} 存在")
        else:
            print(f"⚠️  {dir_name.ljust(20)} 不存在，将在运行时创建")


def check_config():
    """检查配置文件"""
    print_section("配置文件检查")
    
    if os.path.exists('config.json'):
        print("✅ config.json 存在")
        return True
    elif os.path.exists('config.example.json'):
        print("⚠️  config.json 不存在，但存在 config.example.json")
        print("💡 建议: 复制 config.example.json 为 config.json 并修改参数")
        return False
    else:
        print("⚠️  配置文件不存在，程序将使用默认配置")
        return False


def check_sessions():
    """检查会话文件"""
    print_section("会话文件检查")
    
    if os.path.exists('sessions'):
        session_files = [f for f in os.listdir('sessions') if f.endswith('.session')]
        if session_files:
            print(f"✅ 找到 {len(session_files)} 个会话文件:")
            for f in session_files:
                print(f"   - {f}")
            return True
        else:
            print("⚠️  sessions 目录为空")
            print("💡 建议: 将 Telegram 会话文件放入 sessions 目录")
            return False
    else:
        print("⚠️  sessions 目录不存在")
        return False


def check_port():
    """检查端口是否被占用"""
    print_section("端口检查")
    
    try:
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('127.0.0.1', 5000))
        sock.close()
        
        if result == 0:
            print("❌ 端口 5000 已被占用")
            print("💡 建议: 关闭占用端口的程序，或修改 run.py 中的端口")
            return False
        else:
            print("✅ 端口 5000 未被占用")
            return True
    except Exception as e:
        print(f"⚠️  无法检查端口: {e}")
        return None


def check_system():
    """检查系统信息"""
    print_section("系统信息")
    
    print(f"操作系统: {platform.system()} {platform.release()}")
    print(f"处理器: {platform.processor()}")
    print(f"Python 可执行文件: {sys.executable}")
    print(f"工作目录: {os.getcwd()}")


def check_network():
    """检查网络连接"""
    print_section("网络连接检查")
    
    try:
        import socket
        # 尝试连接到 Telegram
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex(('149.154.160.1', 443))  # Telegram IP
        sock.close()
        
        if result == 0:
            print("✅ 可以访问 Telegram 服务器")
            return True
        else:
            print("⚠️  无法连接到 Telegram 服务器")
            print("💡 建议: 检查网络连接或配置代理")
            return False
    except Exception as e:
        print(f"⚠️  网络检查失败: {e}")
        return False


def generate_report():
    """生成诊断报告"""
    print_header("🔍 Telegram 机器人管理系统 - 诊断报告")
    
    results = {}
    
    # 检查项
    results['python'] = check_python()
    results['pip'] = check_pip()
    results['dependencies'] = check_dependencies()
    check_directories()
    results['config'] = check_config()
    results['sessions'] = check_sessions()
    results['port'] = check_port()
    check_system()
    results['network'] = check_network()
    
    # 总结
    print_section("诊断总结")
    
    critical_issues = []
    if not results['python']:
        critical_issues.append("Python 版本太低")
    if not results['pip']:
        critical_issues.append("pip 不可用")
    if not results['dependencies']:
        critical_issues.append("缺少必要的依赖包")
    
    warnings = []
    if not results['config']:
        warnings.append("配置文件不存在")
    if not results['sessions']:
        warnings.append("没有会话文件")
    if not results['port']:
        warnings.append("端口 5000 已被占用")
    if not results['network']:
        warnings.append("无法连接到 Telegram")
    
    # 显示结果
    if critical_issues:
        print("🚨 严重问题 (必须解决):")
        for issue in critical_issues:
            print(f"  ❌ {issue}")
        print("\n请解决这些问题后再运行系统。\n")
        return False
    else:
        print("✅ 没有发现严重问题\n")
    
    if warnings:
        print("⚠️  警告 (建议解决):")
        for warning in warnings:
            print(f"  ⚠️  {warning}")
        print()
    
    return True


def suggest_next_steps():
    """建议下一步行动"""
    print_section("下一步行动")
    
    print("""
1. 安装依赖 (如果有问题):
   pip install -r requirements.txt

2. 配置参数:
   - 复制或编辑 config.json
   - 设置 Telegram API ID 和 Hash
   - 配置监控群和源群

3. 添加会话文件:
   - 将 .session 文件放入 sessions/ 目录

4. 启动系统:
   python run.py
   或
   start.bat (Windows)
   或
   ./start.sh (Linux/Mac)

5. 访问管理界面:
   http://localhost:5000

更多信息请查看 QUICKSTART.md
""")


def main():
    """主函数"""
    try:
        ok = generate_report()
        suggest_next_steps()
        
        print_section("诊断完成")
        
        if ok:
            print("✅ 系统环境良好，可以启动应用！\n")
            print("运行: python run.py\n")
            return 0
        else:
            print("❌ 存在严重问题，请先解决。\n")
            return 1
    
    except Exception as e:
        print(f"\n❌ 诊断过程出错: {e}\n")
        return 2


if __name__ == '__main__':
    exit_code = main()
    
    # 暂停，方便查看结果
    if sys.platform == 'win32':
        input("\n按 Enter 键退出...")
    
    sys.exit(exit_code)
