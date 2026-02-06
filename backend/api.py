"""
Flask API 服务 - 后端接口
"""
import asyncio
import os
import random
import threading
from datetime import datetime
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from functools import wraps
from werkzeug.utils import secure_filename
import time

from telethon import functions, errors

from .config_manager import config_manager
from .account_manager import account_manager
from .telegram_service import init_telegram_service
from .worker import init_message_worker
from .db_manager import db_manager
from .logger_manager import logger_manager


# 创建 Flask 应用
# 使用 `/static` 作为静态资源前缀，避免与 `/api/*` 路由冲突（POST 请求被静态路由拦截会返回 405）
app = Flask(__name__, static_folder='../frontend', static_url_path='/static')
CORS(app)

# 全局变量
telegram_service = None
message_worker = None
monitor_task = None
event_loop = None
background_loop = None  # 后台事件循环
background_thread = None  # 后台线程
monitor_listen_task = None  # 监听任务
monitor_watchdog_task = None  # 监听保活任务
listeners_ready = False  # 防止重复绑定监听器
listeners_client_id = None  # 绑定监听器的客户端标识
monitor_message_handler = None  # 监听回调引用
monitor_groups_cache = {
    'checked_at': 0,
    'configured': False,
    'ok': None,
    'missing': []
}


def _run_event_loop(loop):
    """在后台线程中运行事件循环"""
    asyncio.set_event_loop(loop)
    loop.run_forever()


def _get_background_loop():
    """获取或创建后台事件循环"""
    global background_loop, background_thread
    
    if background_loop is None or background_loop.is_closed():
        background_loop = asyncio.new_event_loop()
        background_thread = threading.Thread(target=_run_event_loop, args=(background_loop,), daemon=True)
        background_thread.start()
        logger_manager.info("✅ [后台]：已启动事件循环线程")
    
    return background_loop


@app.route('/')
def index():
    """主页面"""
    return app.send_static_file('index.html')

@app.route('/<path:filename>')
def serve_static(filename):
    """提供前端静态文件"""
    # 如果请求路径以 'static/' 开头，说明客户端在访问由
    # Flask 配置的静态 URL 前缀。去掉该前缀后由 Flask 在
    # `static_folder` 下查找真实文件，避免查找到不存在的
    # `../frontend/static/...` 路径导致 404。
    if filename.startswith('static/'):
        return app.send_static_file(filename[len('static/'):])
    return app.send_static_file(filename)


def run_async(func):
    """Async handler wrapper."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            # Ensure we are not already inside a running loop
            try:
                asyncio.get_running_loop()
            except RuntimeError:
                pass
            else:
                raise RuntimeError("Cannot use run_async from within an async context")

            loop = _get_background_loop()
            future = asyncio.run_coroutine_threadsafe(func(*args, **kwargs), loop)
            return future.result()
        except Exception as e:
            logger_manager.error(f"ERROR async handler failed: {e}")
            import traceback
            traceback.print_exc()
            return {'error': str(e)}, 500
    return wrapper


# ============================================================
# 1. 系统管理接口
# ============================================================

@app.route('/api/system/status', methods=['GET'])
def get_system_status():
    """获取系统状态"""
    try:
        monitor_status = db_manager.get_account_status('monitor')
        senders_status = db_manager.get_all_accounts_status()

        # 脚本运行状态由后台监听任务决定（monitor_listen_task）
        running = False
        try:
            running = True if (monitor_listen_task and not monitor_listen_task.done()) else False
        except Exception:
            running = False

        return jsonify({
            'status': 'running' if running else 'stopped',
            'monitor': monitor_status,
            'senders': [s for s in senders_status if s['session_name'] != 'monitor'],
            'queue_size': message_worker.get_queue_size() if message_worker else 0,
            'worker_running': True if (message_worker and message_worker.is_running) else False,
            'worker_count': len(message_worker.workers) if (message_worker and message_worker.is_running) else 0,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        logger_manager.error(f"❌ 获取系统状态失败: {e}")
        return {'error': str(e)}, 500


@app.route('/api/system/stats', methods=['GET'])
def get_system_stats():
    """获取系统统计"""
    try:
        days = request.args.get('days', 7, type=int)
        stats = db_manager.get_message_stats(days=days)
        
        # 汇总统计
        total_messages = sum(s['message_count'] for s in stats)
        senders = set(s['sender_name'] for s in stats)
        
        return jsonify({
            'total_messages': total_messages,
            'total_senders': len(senders),
            'days': days,
            'stats': stats,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        logger_manager.error(f"❌ 获取统计信息失败: {e}")
        return {'error': str(e)}, 500



@app.route('/api/system/health', methods=['GET'])
def get_system_health():
    """System health: live clients vs DB online status."""
    try:
        # Online accounts from DB
        db_statuses = db_manager.get_all_accounts_status()
        db_active = [s for s in db_statuses if s.get('is_active')]

        db_active_senders = [s for s in db_active if s.get('session_name') != 'monitor']
        db_active_sender_names = {s.get('session_name') for s in db_active_senders}

        # Live clients in memory
        live_sender_names = set(account_manager.sender_clients.keys())

        stale_senders = sorted(list(db_active_sender_names - live_sender_names))
        live_missing_in_db = sorted(list(live_sender_names - db_active_sender_names))

        monitor_db_active = any(
            s.get('session_name') == 'monitor' and s.get('is_active')
            for s in db_active
        )
        monitor_live_active = True if account_manager.monitor_client else False

        return jsonify({
            'timestamp': datetime.now().isoformat(),
            'monitor': {
                'db_active': monitor_db_active,
                'live_active': monitor_live_active
            },
            'senders': {
                'db_active_count': len(db_active_senders),
                'live_active_count': len(live_sender_names),
                'stale_in_db': stale_senders,
                'live_missing_in_db': live_missing_in_db
            }
        })
    except Exception as e:
        logger_manager.error(f"ERROR get_system_health failed: {e}")
        return {'error': str(e)}, 500


@app.route('/api/config/all', methods=['GET'])
def get_all_config():
    """获取所有配置"""
    try:
        return jsonify(config_manager.get_all_config())
    except Exception as e:
        logger_manager.error(f"❌ 获取配置失败: {e}")
        return {'error': str(e)}, 500


@app.route('/api/config/telegram', methods=['GET', 'POST'])
def manage_telegram_config():
    """管理 Telegram 配置"""
    try:
        if request.method == 'GET':
            from dataclasses import asdict
            return jsonify(asdict(config_manager.telegram_config))
        
        else:  # POST
            data = request.get_json()
            config_manager.update_telegram_config(**data)
            return jsonify({'message': '✅ Telegram 配置已更新'})
    except Exception as e:
        logger_manager.error(f"❌ Telegram 配置管理失败: {e}")
        return {'error': str(e)}, 500


@app.route('/api/config/proxy', methods=['GET', 'POST'])
def manage_proxy_config():
    """管理代理配置"""
    try:
        if request.method == 'GET':
            from dataclasses import asdict
            return jsonify(asdict(config_manager.proxy_config))
        
        else:  # POST
            data = request.get_json()
            config_manager.update_proxy_config(**data)
            return jsonify({'message': '✅ 代理配置已更新'})
    except Exception as e:
        logger_manager.error(f"❌ 代理配置管理失败: {e}")
        return {'error': str(e)}, 500


@app.route('/api/config/filter', methods=['GET', 'POST'])
def manage_filter_config():
    """管理过滤配置"""
    try:
        if request.method == 'GET':
            from dataclasses import asdict
            return jsonify(asdict(config_manager.filter_config))
        
        else:  # POST
            data = request.get_json()
            config_manager.update_filter_config(**data)
            return jsonify({'message': '✅ 过滤配置已更新'})
    except Exception as e:
        logger_manager.error(f"❌ 过滤配置管理失败: {e}")
        return {'error': str(e)}, 500


@app.route('/api/config/system', methods=['GET', 'POST'])
def manage_system_config():
    """管理系统配置"""
    try:
        if request.method == 'GET':
            from dataclasses import asdict
            return jsonify(asdict(config_manager.system_config))
        
        else:  # POST
            data = request.get_json()
            config_manager.update_system_config(**data)
            return jsonify({'message': '✅ 系统配置已更新'})
    except Exception as e:
        logger_manager.error(f"❌ 系统配置管理失败: {e}")
        return {'error': str(e)}, 500


# ============================================================
# 3. 监控号管理接口
# ============================================================

@app.route('/api/monitor/login', methods=['POST'])
@run_async
async def monitor_login():
    """监控号登录"""
    try:
        success = await account_manager.login_monitor()
        if success:
            return jsonify({'message': '✅ 监控号已登录', 'status': 'active'})
        else:
            return jsonify({'error': '❌ 监控号登录失败'}), 400
    except Exception as e:
        logger_manager.error(f"❌ 监控号登录异常: {e}")
        return {'error': str(e)}, 500


@app.route('/api/monitor/logout', methods=['POST'])
@run_async
async def monitor_logout():
    """监控号离线"""
    try:
        success = await account_manager.logout_monitor()
        if success:
            return jsonify({'message': '✅ 监控号已离线'})
        else:
            return jsonify({'error': '❌ 监控号离线失败'}), 400
    except Exception as e:
        logger_manager.error(f"❌ 监控号离线异常: {e}")
        return {'error': str(e)}, 500


@app.route('/api/monitor/status', methods=['GET'])
def get_monitor_status():
    """获取监控号状态"""
    try:
        status = account_manager.get_monitor_status()
        listening = True if (monitor_listen_task and not monitor_listen_task.done()) else False
        force_check = str(request.args.get('check', '')).lower() in ('1', 'true', 'yes')

        # 仅在显式请求时检查监控号是否仍在源群
        try:
            need_check = (
                account_manager.monitor_client
                and force_check
            )
            if need_check:
                loop = _get_background_loop()
                future = asyncio.run_coroutine_threadsafe(_check_monitor_source_groups_async(), loop)
                try:
                    result = future.result(timeout=10)
                    monitor_groups_cache.update(result)
                except Exception as e:
                    logger_manager.warning(f"⚠️ 源群检查超时或失败: {e}")
        except Exception:
            pass
        # Check if any .session exists under root/monitor directory
        try:
            session_dir = os.path.join(os.getcwd(), 'monitor')
            if os.path.isdir(session_dir):
                session_exists = any(
                    name.endswith('.session') for name in os.listdir(session_dir)
                )
            else:
                session_exists = False
        except Exception:
            session_exists = False

        if status:
            status['session_file_exists'] = session_exists
            status['listening'] = listening
            status['source_groups_configured'] = monitor_groups_cache.get('configured', False)
            status['source_groups_ok'] = monitor_groups_cache.get('ok')
            status['source_groups_missing'] = monitor_groups_cache.get('missing', [])
            return jsonify(status)
        else:
            return jsonify({
                'status': 'offline',
                'session_file_exists': session_exists,
                'listening': listening,
                'source_groups_configured': monitor_groups_cache.get('configured', False),
                'source_groups_ok': monitor_groups_cache.get('ok'),
                'source_groups_missing': monitor_groups_cache.get('missing', [])
            })
    except Exception as e:
        logger_manager.error(f"❌ 获取监控号状态失败: {e}")
        return {'error': str(e)}, 500


@app.route('/api/monitor/refresh', methods=['POST'])
@run_async
async def refresh_monitor_status():
    """实时刷新监控号状态（发请求并写回数据库）"""
    try:
        status = await account_manager.refresh_monitor_status()

        # 检查 session 文件是否存在
        try:
            session_dir = os.path.join(os.getcwd(), 'monitor')
            if os.path.isdir(session_dir):
                session_exists = any(
                    name.endswith('.session') for name in os.listdir(session_dir)
                )
            else:
                session_exists = False
        except Exception:
            session_exists = False

        # 监听状态
        listening = True if (monitor_listen_task and not monitor_listen_task.done()) else False

        # 主动检查源群状态
        groups_result = await _check_monitor_source_groups_async()
        monitor_groups_cache.update(groups_result)

        if status:
            status['session_file_exists'] = session_exists
            status['listening'] = listening
            status['source_groups_configured'] = monitor_groups_cache.get('configured', False)
            status['source_groups_ok'] = monitor_groups_cache.get('ok')
            status['source_groups_missing'] = monitor_groups_cache.get('missing', [])
            return jsonify(status)
        else:
            return jsonify({
                'status': 'offline',
                'session_file_exists': session_exists,
                'listening': listening,
                'source_groups_configured': monitor_groups_cache.get('configured', False),
                'source_groups_ok': monitor_groups_cache.get('ok'),
                'source_groups_missing': monitor_groups_cache.get('missing', [])
            })
    except Exception as e:
        logger_manager.error(f"❌ 刷新监控号状态失败: {e}")
        return {'error': str(e)}, 500


async def _check_monitor_source_groups_async():
    """检查监控号是否仍在所有源群"""
    result = {
        'checked_at': datetime.now().timestamp(),
        'configured': False,
        'ok': None,
        'missing': []
    }
    if not account_manager.monitor_client:
        return result

    cfg = config_manager.telegram_config
    groups = cfg.source_groups or []
    result['configured'] = True if groups else False
    if not groups:
        result['ok'] = None
        return result

    missing = []
    for group in groups:
        try:
            entity = await account_manager.monitor_client.get_entity(group)
            await account_manager.monitor_client(
                functions.channels.GetParticipantRequest(
                    channel=entity, participant='me'
                )
            )
        except errors.UserNotParticipantError:
            missing.append(group)
        except Exception:
            missing.append(group)

    result['missing'] = missing
    result['ok'] = True if len(missing) == 0 else False
    return result


@app.route('/api/monitor/start-listen', methods=['POST'])
def start_monitor_listen():
    """在后台启动监控号监听（会启动消息工人，克隆号需单独登录）"""
    global monitor_listen_task
    try:
        # 如果已在运行，返回提示
        if monitor_listen_task and not monitor_listen_task.done():
            return jsonify({'message': '✅ 监听已在运行'}), 400

        loop = _get_background_loop()

        future = asyncio.run_coroutine_threadsafe(_start_monitor_listener_async(), loop)
        try:
            result = future.result(timeout=30)
            return jsonify(result)
        except Exception as e:
            logger_manager.error(f"❌ 提交启动监听任务失败: {e}")
            return {'error': str(e)}, 500
    except Exception as e:
        logger_manager.error(f"❌ 启动监听失败: {e}")
        return {'error': str(e)}, 500


@app.route('/api/monitor/stop-listen', methods=['POST'])
def stop_monitor_listen():
    """停止监控号的监听任务（不离线账号）"""
    global monitor_listen_task
    try:
        loop = _get_background_loop()

        future = asyncio.run_coroutine_threadsafe(_stop_monitor_listener_async(), loop)
        try:
            result = future.result(timeout=10)
            return jsonify(result)
        except Exception as e:
            logger_manager.error(f"❌ 提交停止监听任务失败: {e}")
            return {'error': str(e)}, 500
    except Exception as e:
        logger_manager.error(f"❌ 停止监听失败: {e}")
        return {'error': str(e)}, 500


async def _start_monitor_listener_async():
    """异步启动仅监听任务"""
    global monitor_listen_task, monitor_watchdog_task, listeners_ready, listeners_client_id
    try:
        # 确保监控号已登录
        if not account_manager.monitor_client:
            success = await account_manager.login_monitor()
            if not success:
                return {'error': '❌ 监控号登录失败'}

        client = account_manager.monitor_client

        # 如果监控号客户端更换，重置监听器标记
        if listeners_client_id != id(client):
            listeners_ready = False
            listeners_client_id = id(client)

        # 确保监控号已连接
        try:
            is_connected = client.is_connected() if hasattr(client, 'is_connected') else True
        except Exception:
            is_connected = True
        if not is_connected:
            timeout_sec = getattr(config_manager.system_config, 'login_timeout_sec', 30)
            await asyncio.wait_for(client.connect(), timeout=timeout_sec)

        # 源群未配置，直接提示
        if not config_manager.telegram_config.source_groups:
            return {'error': '❌ 未配置源群，请先设置 source_groups'}

        # 确保消息队列与工人已启动（否则监听到消息也不会处理）
        if not message_worker:
            return {'error': '❌ 消息工人未初始化'}
        if message_worker.msg_queue is None:
            await message_worker.init_queue(config_manager.system_config.msg_queue_size)
        if not message_worker.is_running:
            await message_worker.start_workers()
        else:
            logger_manager.info("ℹ️ [工人]：工人已在运行")

        await _setup_listeners()
        monitor_listen_task = asyncio.create_task(_run_monitor_listener())
        if not monitor_watchdog_task or monitor_watchdog_task.done():
            monitor_watchdog_task = asyncio.create_task(_monitor_watchdog())
        logger_manager.info('✅ [监听]：监控监听已启动')
        return {'message': '✅ 监听已启动'}
    except Exception as e:
        logger_manager.error(f"❌ 启动监听任务失败: {e}")
        return {'error': str(e)}


async def _stop_monitor_listener_async():
    """异步停止仅监听任务（不离线监控号）"""
    global monitor_listen_task, monitor_watchdog_task, listeners_ready, monitor_message_handler
    try:
        if monitor_listen_task and not monitor_listen_task.done():
            monitor_listen_task.cancel()
            try:
                await monitor_listen_task
            except asyncio.CancelledError:
                pass
        if monitor_watchdog_task and not monitor_watchdog_task.done():
            monitor_watchdog_task.cancel()
            try:
                await monitor_watchdog_task
            except asyncio.CancelledError:
                pass

        # 清理监听器，避免重复绑定
        if account_manager.monitor_client and monitor_message_handler:
            try:
                account_manager.monitor_client.remove_event_handler(monitor_message_handler)
            except Exception:
                pass
            monitor_message_handler = None

        if message_worker and message_worker.is_running:
            await message_worker.stop_workers()
        logger_manager.info('✅ [监听]：监控监听已停止')
        monitor_listen_task = None
        monitor_watchdog_task = None
        listeners_ready = False
        return {'message': '✅ 监听已停止'}
    except Exception as e:
        logger_manager.error(f"❌ 停止监听任务失败: {e}")
        return {'error': str(e)}




@app.route('/api/monitor/join-alert-group', methods=['POST'])
@run_async
async def monitor_join_alert_group():
    'Join the configured alert group for the monitor account.'
    try:
        if not account_manager.monitor_client:
            return {'error': 'monitor not logged in'}, 400
        cfg = config_manager.telegram_config
        if not cfg.alert_group:
            return {'error': 'alert_group not configured'}, 400
        await account_manager.monitor_client(functions.channels.JoinChannelRequest(
            channel=cfg.alert_group
        ))
        return jsonify({'message': 'ok'})
    except Exception as e:
        logger_manager.error(f"ERROR monitor join alert group failed: {e}")
        return {'error': str(e)}, 500


@app.route('/api/monitor/join-source-groups', methods=['POST'])
@run_async
async def monitor_join_source_groups():
    'Join the configured source groups for the monitor account.'
    try:
        if not account_manager.monitor_client:
            return {'error': 'monitor not logged in'}, 400
        cfg = config_manager.telegram_config
        if not cfg.source_groups:
            return {'error': 'source_groups not configured'}, 400

        joined = 0
        for group in cfg.source_groups:
            try:
                await account_manager.monitor_client(functions.channels.JoinChannelRequest(
                    channel=group
                ))
                joined += 1
            except Exception:
                pass
        return jsonify({'message': 'ok', 'joined': joined})
    except Exception as e:
        logger_manager.error(f"ERROR monitor join source groups failed: {e}")
        return {'error': str(e)}, 500
@app.route('/api/sessions/list', methods=['GET'])
def list_sessions():
    """列出 sessions 目录下的 .session 文件（不自动登录，仅列出）"""
    try:
        sess_dir = os.path.join(os.getcwd(), 'sessions')
        sessions = []
        if os.path.isdir(sess_dir):
            for fname in os.listdir(sess_dir):
                if fname.endswith('.session'):
                    # 返回会话名（去掉 .session 后缀）
                    sessions.append(fname[:-8])
        return jsonify({'sessions': sessions})
    except Exception as e:
        logger_manager.error(f"❌ 列出会话文件失败: {e}")
        return {'error': str(e)}, 500


# ============================================================
# 4. 克隆号管理接口
# ============================================================

@app.route('/api/senders/login-all', methods=['POST'])
@run_async
async def login_all_senders():
    """登录所有克隆号"""
    try:
        count = await account_manager.auto_login_senders()
        return jsonify({
            'message': f'✅ 成功登录 {count} 个克隆号',
            'count': count
        })
    except Exception as e:
        logger_manager.error(f"❌ 批量登录失败: {e}")
        return {'error': str(e)}, 500


@app.route('/api/senders/logout-all', methods=['POST'])
@run_async
async def logout_all_senders():
    """离线所有克隆号"""
    try:
        count = await account_manager.logout_all_senders()
        return jsonify({
            'message': f'✅ 成功离线 {count} 个克隆号',
            'count': count
        })
    except Exception as e:
        logger_manager.error(f"❌ 批量离线失败: {e}")
        return {'error': str(e)}, 500


@app.route('/api/senders/create/<session_name>', methods=['POST'])
@run_async
async def create_sender(session_name):
    """创建新克隆号会话（扫码登录）"""
    try:
        if not session_name or len(session_name.strip()) == 0:
            return {'error': '❌ 会话名称不能为空'}, 400
        
        # 检查会话是否已存在
        import os
        session_path = os.path.join('sessions', f'{session_name}.session')
        if os.path.exists(session_path):
            return {'error': f'❌ 会话 {session_name} 已存在，请使用其他名称'}, 400
        
        logger_manager.info(f"🔐 [克隆号创建]：开始创建会话 {session_name}，请扫码登录...")
        
        # 调用 account_manager 创建会话
        success = await account_manager.login_sender(session_name)
        
        if success:
            return jsonify({
                'message': f'✅ 克隆号 {session_name} 登录成功',
                'session_name': session_name
            })
        else:
            return {'error': f'❌ 克隆号 {session_name} 创建失败'}, 400
    except Exception as e:
        logger_manager.error(f"❌ 创建克隆号会话失败: {e}")
        return {'error': str(e)}, 500


@app.route('/api/senders/login/<session_name>', methods=['POST'])
@run_async
async def login_sender(session_name):
    """登录指定克隆号"""
    try:
        success = await account_manager.login_sender(session_name)
        if success:
            return jsonify({'message': f'✅ {session_name} 已登录'})
        else:
            return jsonify({'error': f'❌ {session_name} 登录失败或会话文件不存在'}), 400
    except Exception as e:
        logger_manager.error(f"❌ 登录克隆号失败: {e}")
        return {'error': str(e)}, 500


@app.route('/api/senders/logout/<session_name>', methods=['POST'])
@run_async
async def logout_sender(session_name):
    """离线指定克隆号"""
    try:
        success = await account_manager.logout_sender(session_name)
        if success:
            return jsonify({'message': f'✅ {session_name} 已离线'})
        else:
            return jsonify({'error': f'❌ {session_name} 离线失败'}), 400
    except Exception as e:
        logger_manager.error(f"❌ 离线克隆号失败: {e}")
        return {'error': str(e)}, 500


@app.route('/api/senders/status', methods=['GET'])
def get_senders_status():
    """获取所有克隆号状态"""
    try:
        status = account_manager.get_all_senders_status()
        return jsonify({'senders': status})
    except Exception as e:
        logger_manager.error(f"❌ 获取克隆号状态失败: {e}")
        return {'error': str(e)}, 500


async def _ensure_sender_avatar_path(session_name: str) -> str:
    """获取或下载克隆号头像缩略图，返回本地路径（不存在则返回空字符串）"""
    try:
        client = account_manager.get_sender_client(session_name)
        if not client:
            return ''

        try:
            is_connected = client.is_connected() if hasattr(client, 'is_connected') else True
        except Exception:
            is_connected = True
        if not is_connected:
            timeout_sec = getattr(config_manager.system_config, 'login_timeout_sec', 30)
            await asyncio.wait_for(client.connect(), timeout=timeout_sec)

        avatar_dir = os.path.join(os.getcwd(), 'temp_media', 'avatars')
        os.makedirs(avatar_dir, exist_ok=True)
        safe_name = secure_filename(session_name)
        if not safe_name:
            return ''
        avatar_path = os.path.join(avatar_dir, f"{safe_name}.jpg")

        # 缓存 5 分钟，避免频繁下载
        try:
            if os.path.exists(avatar_path):
                if time.time() - os.path.getmtime(avatar_path) < 300:
                    return avatar_path
        except Exception:
            pass

        # 下载头像（缩略图）
        try:
            await client.download_profile_photo('me', file=avatar_path, download_big=False)
        except Exception:
            return ''

        if os.path.exists(avatar_path) and os.path.getsize(avatar_path) > 0:
            return avatar_path
        return ''
    except Exception:
        return ''


async def _ensure_monitor_avatar_path() -> str:
    """获取或下载监控号头像缩略图，返回本地路径（不存在则返回空字符串）"""
    try:
        client = account_manager.monitor_client
        if not client:
            return ''

        try:
            is_connected = client.is_connected() if hasattr(client, 'is_connected') else True
        except Exception:
            is_connected = True
        if not is_connected:
            timeout_sec = getattr(config_manager.system_config, 'login_timeout_sec', 30)
            await asyncio.wait_for(client.connect(), timeout=timeout_sec)

        avatar_dir = os.path.join(os.getcwd(), 'temp_media', 'avatars')
        os.makedirs(avatar_dir, exist_ok=True)
        avatar_path = os.path.join(avatar_dir, "monitor.jpg")

        # 缓存 5 分钟，避免频繁下载
        try:
            if os.path.exists(avatar_path):
                if time.time() - os.path.getmtime(avatar_path) < 300:
                    return avatar_path
        except Exception:
            pass

        try:
            await client.download_profile_photo('me', file=avatar_path, download_big=False)
        except Exception:
            return ''

        if os.path.exists(avatar_path) and os.path.getsize(avatar_path) > 0:
            return avatar_path
        return ''
    except Exception:
        return ''

@app.route('/api/senders/avatar/<session_name>', methods=['GET'])
def get_sender_avatar(session_name):
    """获取克隆号头像缩略图"""
    try:
        loop = _get_background_loop()
        future = asyncio.run_coroutine_threadsafe(
            _ensure_sender_avatar_path(session_name),
            loop
        )
        avatar_path = future.result(timeout=20)
        if not avatar_path:
            return '', 404
        return send_file(avatar_path)
    except Exception as e:
        logger_manager.error(f"❌ 获取克隆号头像失败: {e}")
        return '', 404


@app.route('/api/monitor/avatar', methods=['GET'])
def get_monitor_avatar():
    """获取监控号头像缩略图"""
    try:
        loop = _get_background_loop()
        future = asyncio.run_coroutine_threadsafe(
            _ensure_monitor_avatar_path(),
            loop
        )
        avatar_path = future.result(timeout=20)
        if not avatar_path:
            return '', 404
        return send_file(avatar_path)
    except Exception as e:
        logger_manager.error(f"❌ 获取监控号头像失败: {e}")
        return '', 404


@app.route('/api/senders/update-profile/<session_name>', methods=['POST'])
@run_async
async def update_sender_profile(session_name):
    """更新克隆号资料（昵称/头像）"""
    try:
        if not telegram_service:
            return {'error': 'telegram_service 未初始化'}, 500
        data = request.get_json(silent=True) or {}
        name = data.get('name')
        random_name = data.get('random_name', True)
        random_photo = data.get('random_photo', True)

        ok, msg = await telegram_service.update_sender_profile(
            session_name,
            name=name,
            random_name=random_name,
            random_photo=random_photo
        )
        if ok:
            return jsonify({'message': msg})
        return {'error': msg}, 400
    except Exception as e:
        logger_manager.error(f"❌ 更新克隆号资料失败: {e}")
        return {'error': str(e)}, 500


@app.route('/api/senders/update-profile-manual/<session_name>', methods=['POST'])
def update_sender_profile_manual(session_name):
    """手动更新克隆号资料（昵称 + 上传头像）"""
    try:
        if not telegram_service:
            return {'error': 'telegram_service 未初始化'}, 500

        name = request.form.get('name', '').strip()
        photo = request.files.get('photo')

        if not name and not photo:
            return {'error': '昵称或头像至少提供一项'}, 400

        photo_path = None
        if photo:
            filename = secure_filename(photo.filename or '')
            if not filename:
                return {'error': '头像文件名无效'}, 400
            if not filename.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
                return {'error': '仅支持 jpg/png/webp 头像'}, 400

            tmp_dir = os.path.join(os.getcwd(), 'temp_media')
            os.makedirs(tmp_dir, exist_ok=True)
            photo_path = os.path.join(tmp_dir, f"{session_name}_{int(time.time())}_{filename}")
            photo.save(photo_path)

        loop = _get_background_loop()
        future = asyncio.run_coroutine_threadsafe(
            telegram_service.update_sender_profile_manual(
                session_name,
                name=name if name else None,
                photo_path=photo_path
            ),
            loop
        )
        ok, msg = future.result(timeout=60)

        # 清理临时文件
        if photo_path:
            try:
                os.remove(photo_path)
            except Exception:
                pass

        if ok:
            return jsonify({'message': msg})
        return {'error': msg}, 400
    except Exception as e:
        logger_manager.error(f"❌ 手动更新克隆号资料失败: {e}")
        return {'error': str(e)}, 500


@app.route('/api/monitor/update-profile-manual', methods=['POST'])
def update_monitor_profile_manual():
    """手动更新监控号资料（昵称 + 上传头像）"""
    try:
        if not telegram_service:
            return {'error': 'telegram_service 未初始化'}, 500

        name = request.form.get('name', '').strip()
        photo = request.files.get('photo')

        if not name and not photo:
            return {'error': '昵称或头像至少提供一项'}, 400

        photo_path = None
        if photo:
            filename = secure_filename(photo.filename or '')
            if not filename:
                return {'error': '头像文件名无效'}, 400
            if not filename.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
                return {'error': '仅支持 jpg/png/webp 头像'}, 400

            tmp_dir = os.path.join(os.getcwd(), 'temp_media')
            os.makedirs(tmp_dir, exist_ok=True)
            photo_path = os.path.join(tmp_dir, f"monitor_{int(time.time())}_{filename}")
            photo.save(photo_path)

        loop = _get_background_loop()
        future = asyncio.run_coroutine_threadsafe(
            telegram_service.update_monitor_profile_manual(
                name=name if name else None,
                photo_path=photo_path
            ),
            loop
        )
        ok, msg = future.result(timeout=60)

        if photo_path:
            try:
                os.remove(photo_path)
            except Exception:
                pass

        if ok:
            return jsonify({'message': msg})
        return {'error': msg}, 400
    except Exception as e:
        logger_manager.error(f"❌ 手动更新监控号资料失败: {e}")
        return {'error': str(e)}, 500


@app.route('/api/sessions/upload', methods=['POST'])
def upload_sessions():
    """上传 .session 文件到 sessions 目录（克隆号）"""
    try:
        if 'files' not in request.files:
            return {'error': '❌ 未找到上传文件'}, 400

        files = request.files.getlist('files')
        if not files:
            return {'error': '❌ 未选择文件'}, 400

        sess_dir = os.path.join(os.getcwd(), 'sessions')
        os.makedirs(sess_dir, exist_ok=True)

        saved = 0
        errors = []
        for f in files:
            filename = secure_filename(f.filename or '')
            if not filename:
                continue
            if not (filename.endswith('.session') or filename.endswith('.session-journal')):
                errors.append(f"跳过不支持的文件: {filename}")
                continue
            try:
                f.save(os.path.join(sess_dir, filename))
                saved += 1
            except Exception as e:
                errors.append(f"保存失败 {filename}: {e}")

        return jsonify({
            'message': f'✅ 已上传 {saved} 个会话文件',
            'saved': saved,
            'errors': errors
        })
    except Exception as e:
        logger_manager.error(f"❌ 上传会话文件失败: {e}")
        return {'error': str(e)}, 500


@app.route('/api/monitor/upload-sessions', methods=['POST'])
def upload_monitor_sessions():
    """上传 .session 文件到 monitor 目录（监控号）"""
    try:
        if 'files' not in request.files:
            return {'error': '❌ 未找到上传文件'}, 400

        files = request.files.getlist('files')
        if not files:
            return {'error': '❌ 未选择文件'}, 400
        if len(files) != 1:
            return {'error': '❌ 监控号只能上传一个 .session 文件，上传新文件会替换旧文件'}, 400

        sess_dir = os.path.join(os.getcwd(), 'monitor')
        os.makedirs(sess_dir, exist_ok=True)

        f = files[0]
        filename = secure_filename(f.filename or '')
        if not filename:
            return {'error': '❌ 文件名无效'}, 400
        if not filename.endswith('.session'):
            return {'error': '❌ 仅支持上传 .session 文件'}, 400

        # 删除旧的监控会话文件（替换逻辑）
        try:
            for name in os.listdir(sess_dir):
                if name.endswith('.session') or name.endswith('.session-journal'):
                    try:
                        os.remove(os.path.join(sess_dir, name))
                    except Exception:
                        pass
        except Exception:
            pass

        try:
            f.save(os.path.join(sess_dir, filename))
        except Exception as e:
            return {'error': f'❌ 保存失败: {e}'}, 500

        return jsonify({
            'message': '✅ 监控号会话已上传（已替换旧文件）',
            'saved': 1
        })
    except Exception as e:
        logger_manager.error(f"❌ 上传监控会话文件失败: {e}")
        return {'error': str(e)}, 500


@app.route('/api/senders/refresh', methods=['POST'])
@run_async
async def refresh_senders_status():
    """实时刷新所有克隆号状态（发请求并写回数据库）"""
    try:
        check_groups = str(request.args.get('check', '')).lower() in ('1', 'true', 'yes')
        status = await account_manager.refresh_senders_status()

        senders = [s for s in status if s.get('session_name') != 'monitor']
        if check_groups:
            # 逐个检查克隆号是否在目标群
            for sender in senders:
                name = sender.get('session_name')
                client = account_manager.get_sender_client(name)
                if not client:
                    sender['target_groups_configured'] = bool(config_manager.telegram_config.my_groups)
                    sender['target_groups_ok'] = None
                    sender['target_groups_missing'] = []
                    continue
                group_status = await _check_sender_target_groups_async(client)
                sender.update(group_status)

        return jsonify({'senders': senders})
    except Exception as e:
        logger_manager.error(f"❌ 刷新克隆号状态失败: {e}")
        return {'error': str(e)}, 500


async def _check_sender_target_groups_async(client):
    """检查克隆号是否仍在所有目标群"""
    result = {
        'target_groups_configured': False,
        'target_groups_ok': None,
        'target_groups_missing': []
    }

    cfg = config_manager.telegram_config
    groups = cfg.my_groups or []
    result['target_groups_configured'] = True if groups else False
    if not groups:
        return result

    missing = []
    for group in groups:
        try:
            entity = await client.get_entity(group)
            await client(
                functions.channels.GetParticipantRequest(
                    channel=entity, participant='me'
                )
            )
        except errors.UserNotParticipantError:
            missing.append(group)
        except Exception:
            missing.append(group)

    result['target_groups_missing'] = missing
    result['target_groups_ok'] = True if len(missing) == 0 else False
    return result


# ============================================================
# 5. 脚本控制接口
# ============================================================

@app.route('/api/script/start', methods=['POST'])
def start_script():
    """启动脚本（同步版本，在后台线程中运行异步逻辑）"""
    global monitor_listen_task
    try:
        # 检查是否已启动
        if monitor_listen_task and not monitor_listen_task.done():
            return jsonify({'error': '❌ 脚本已在运行中'}), 400
        
        # 获取后台事件循环
        loop = _get_background_loop()
        
        # 在后台循环中提交启动任务
        future = asyncio.run_coroutine_threadsafe(_start_script_async(), loop)
        
        # 等待启动完成（不要阻塞太久）
        try:
            result = future.result(timeout=30)
            return jsonify(result)
        except Exception as e:
            return {'error': str(e)}, 500
    except Exception as e:
        logger_manager.error(f"❌ 脚本启动失败: {e}")
        return {'error': str(e)}, 500


async def _start_script_async():
    """异步启动脚本逻辑"""
    global monitor_listen_task
    
    try:
        # 启动监控号
        if not account_manager.monitor_client:
            success = await account_manager.login_monitor()
            if not success:
                return {'error': '❌ 监控号登录失败'}
        
        logger_manager.info("✅ [脚本]：正在登录克隆号...")
        # 登录所有克隆号
        count = await account_manager.auto_login_senders()
        logger_manager.info(f"✅ [脚本]：已登录 {count} 个克隆号")

        # 启动消息处理器前，先确保克隆号已在目标群
        try:
            logger_manager.info("✅ [脚本]：正在检查克隆号是否在目标群...")
            await account_manager.ensure_all_senders_in_target_group()
            logger_manager.info("✅ [脚本]：克隆号目标群检查完成")
        except Exception as e:
            logger_manager.error(f"❌ [脚本]：克隆号目标群检查失败 {e}")
        
        # 启动消息工人
        logger_manager.info("✅ [脚本]：正在启动消息处理器...")
        await message_worker.init_queue(config_manager.system_config.msg_queue_size)
        await message_worker.start_workers()
        
        # 设置监听
        logger_manager.info("✅ [脚本]：正在设置事件监听...")
        await _setup_listeners()
        
        # 在后台启动监听任务
        monitor_listen_task = asyncio.create_task(_run_monitor_listener())
        
        logger_manager.info("✅ [脚本]：已启动，等待接收消息...")
        return {'message': '✅ 脚本已启动，开始监听消息'}
    except Exception as e:
        logger_manager.error(f"❌ 脚本启动失败: {e}")
        import traceback
        traceback.print_exc()
        return {'error': str(e)}


@app.route('/api/script/stop', methods=['POST'])
def stop_script():
    """停止脚本（同步版本，在后台线程中运行异步逻辑）"""
    global monitor_listen_task
    try:
        # 获取后台事件循环
        loop = _get_background_loop()
        
        # 在后台循环中提交停止任务
        future = asyncio.run_coroutine_threadsafe(_stop_script_async(), loop)
        
        # 等待停止完成
        try:
            result = future.result(timeout=10)
            return jsonify(result)
        except Exception as e:
            return {'error': str(e)}, 500
    except Exception as e:
        logger_manager.error(f"❌ 脚本停止失败: {e}")
        return {'error': str(e)}, 500


async def _stop_script_async():
    """异步停止脚本逻辑"""
    global monitor_listen_task
    try:
        # 停止监听任务
        if monitor_listen_task and not monitor_listen_task.done():
            monitor_listen_task.cancel()
            try:
                await monitor_listen_task
            except asyncio.CancelledError:
                pass
        
        # 停止消息处理
        await message_worker.stop_workers()
        await account_manager.logout_all_senders()
        
        logger_manager.info("✅ [脚本]：已停止")
        return {'message': '✅ 脚本已停止'}
    except Exception as e:
        logger_manager.error(f"❌ 脚本停止失败: {e}")
        return {'error': str(e)}


# ============================================================
# 6. 日志接口
# ============================================================

@app.route('/api/logs/recent', methods=['GET'])
def get_recent_logs():
    """获取最近的日志"""
    try:
        level = request.args.get('level', None)
        limit = request.args.get('limit', 100, type=int)
        logs = logger_manager.get_logs(level=level, limit=limit)
        return jsonify({'logs': logs})
    except Exception as e:
        logger_manager.error(f"❌ 获取日志失败: {e}")
        return {'error': str(e)}, 500


@app.route('/api/logs/files', methods=['GET'])
def get_log_files():
    """获取日志文件列表"""
    try:
        files = logger_manager.get_logs_by_date()
        return jsonify({'files': files})
    except Exception as e:
        logger_manager.error(f"❌ 获取日志文件列表失败: {e}")
        return {'error': str(e)}, 500


@app.route('/api/logs/file/<filename>', methods=['GET'])
def get_log_file(filename):
    """获取日志文件内容"""
    try:
        content = logger_manager.read_log_file(filename)
        return jsonify({'filename': filename, 'content': content})
    except Exception as e:
        logger_manager.error(f"❌ 读取日志文件失败: {e}")
        return {'error': str(e)}, 500


# ============================================================
# 辅助函数
# ============================================================

async def _setup_listeners():
    """设置事件监听"""
    global listeners_ready, monitor_message_handler
    from telethon import events
    
    if not account_manager.monitor_client:
        return

    if listeners_ready:
        return

    cfg = config_manager.telegram_config

    # 移除旧监听器（防止重复触发）
    if monitor_message_handler:
        try:
            account_manager.monitor_client.remove_event_handler(monitor_message_handler)
        except Exception:
            pass
        monitor_message_handler = None

    @account_manager.monitor_client.on(events.NewMessage(chats=cfg.source_groups))
    async def handle_new_message(event):
        try:
            chat_id = getattr(event, 'chat_id', None)
            sender_id = getattr(event, 'sender_id', None)
            msg_id = getattr(event, 'id', None)
            logger_manager.info(
                f"📥 [监控]：收到消息 chat={chat_id} sender={sender_id} msg_id={msg_id}"
            )
        except Exception:
            pass
        await message_worker.add_message(event)

    monitor_message_handler = handle_new_message
    
    logger_manager.info("✅ [监听]：已设置事件监听")
    listeners_ready = True


async def _run_monitor_listener():
    """在后台运行监听循环"""
    try:
        if not account_manager.monitor_client:
            logger_manager.error("❌ 监控号未连接")
            return

        backoff = 2
        while True:
            try:
                client = account_manager.monitor_client
                # 确保连接状态
                try:
                    is_connected = client.is_connected() if hasattr(client, 'is_connected') else True
                except Exception:
                    is_connected = True
                if not is_connected:
                    timeout_sec = getattr(config_manager.system_config, 'login_timeout_sec', 30)
                    await asyncio.wait_for(client.connect(), timeout=timeout_sec)

                logger_manager.info("✅ [监听]：开始监听消息...")
                # 持续运行直到断开连接或被取消
                await client.run_until_disconnected()

                logger_manager.warning("⚠️ [监听]：连接断开，准备重连...")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30)
            except asyncio.CancelledError:
                logger_manager.info("🛑 [监听]：监听已停止")
                break
            except Exception as e:
                logger_manager.error(f"❌ [监听]：监听出错: {e}")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30)
    except Exception as e:
        logger_manager.error(f"❌ [监听]：监听启动失败: {e}")


async def _monitor_watchdog():
    """监听保活：确保监控号连接、监听任务与工人持续运行"""
    global monitor_listen_task
    try:
        while True:
            await asyncio.sleep(10)
            if not account_manager.monitor_client:
                continue

            # 确保连接状态
            try:
                client = account_manager.monitor_client
                is_connected = client.is_connected() if hasattr(client, 'is_connected') else True
            except Exception:
                is_connected = True
            if not is_connected:
                try:
                    timeout_sec = getattr(config_manager.system_config, 'login_timeout_sec', 30)
                    await asyncio.wait_for(client.connect(), timeout=timeout_sec)
                except Exception as e:
                    logger_manager.warning(f"⚠️ [监听保活]：重连失败 {e}")
                    continue

            # 确保监听器存在
            if not listeners_ready:
                await _setup_listeners()

            # 确保监听任务在运行
            if not monitor_listen_task or monitor_listen_task.done():
                logger_manager.warning("⚠️ [监听保活]：监听任务已停止，正在重启")
                monitor_listen_task = asyncio.create_task(_run_monitor_listener())

            # 确保工人在运行
            if message_worker and not message_worker.is_running:
                try:
                    if message_worker.msg_queue is None:
                        await message_worker.init_queue(config_manager.system_config.msg_queue_size)
                    await message_worker.start_workers()
                except Exception as e:
                    logger_manager.warning(f"⚠️ [监听保活]：工人启动失败 {e}")
    except asyncio.CancelledError:
        pass


def init_api(loop=None):
    """初始化 API"""
    global telegram_service, message_worker, event_loop
    
    event_loop = loop
    telegram_service = init_telegram_service(account_manager)
    message_worker = init_message_worker(account_manager, telegram_service)
    
    # 初始化后台事件循环
    _get_background_loop()
    
    logger_manager.info("✅ [API]：已初始化")


if __name__ == '__main__':
    init_api()
    app.run(debug=False, host='0.0.0.0', port=5000)
