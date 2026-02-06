"""
账号管理模块 - 监控号和克隆号的登录/离线
"""
import os
import glob
import asyncio
from typing import Dict, List, Optional
from telethon import TelegramClient, errors, functions
from .config_manager import config_manager
from .db_manager import db_manager
from .logger_manager import logger


class AccountManager:
    """账号管理器"""
    
    def __init__(self):
        self.monitor_client = None
        self.sender_clients: Dict[str, TelegramClient] = {}
        self.is_running = False
    
    def _get_proxy_config(self):
        """获取代理配置
        
        逻辑：
        - use_proxy=False：尝试使用系统代理（Windows 系统代理、环境变量等）
        - use_proxy=True：使用手动配置的代理
        """
        import socks
        cfg = config_manager.proxy_config
        
        if not cfg.use_proxy:
            # use_proxy=False 时，自动尝试系统代理
            # 检查环境变量中是否有代理配置
            import os
            http_proxy = os.environ.get('HTTP_PROXY') or os.environ.get('http_proxy')
            https_proxy = os.environ.get('HTTPS_PROXY') or os.environ.get('https_proxy')
            
            if http_proxy or https_proxy:
                logger.info(f"✅ 使用系统代理：{http_proxy or https_proxy}")
            
            # 返回 None，让 Telethon 使用系统默认代理
            return None
        
        # 手动配置的代理
        logger.info(f"✅ 使用手动配置代理：{cfg.proxy_host}:{cfg.proxy_port}")
        return {
            'proxy_type': socks.SOCKS5,
            'addr': cfg.proxy_host,
            'port': cfg.proxy_port,
            'username': cfg.proxy_username if cfg.proxy_username else None,
            'password': cfg.proxy_password if cfg.proxy_password else None,
            'rdns': True
        }
    
    async def login_monitor(self) -> bool:
        """登录监控号"""
        try:
            cfg = config_manager.telegram_config
            proxy = self._get_proxy_config()

            # Store monitor sessions under a root-level "monitor" folder.
            session_dir = os.path.join(os.getcwd(), 'monitor')
            try:
                os.makedirs(session_dir, exist_ok=True)
            except Exception:
                pass

            # Prefer an existing .session file in the monitor folder.
            session_files = []
            try:
                session_files = [
                    os.path.join(session_dir, name)
                    for name in os.listdir(session_dir)
                    if name.endswith('.session')
                ]
            except Exception:
                session_files = []

            if session_files:
                # Use the first (sorted) session file found.
                session_path = sorted(session_files)[0]
            else:
                # Fall back to creating a default session file.
                session_path = os.path.join(session_dir, 'monitor.session')

            self.monitor_client = TelegramClient(
                session_path,
                cfg.monitor_account_id,
                cfg.monitor_api_hash,
                proxy=proxy
            )

            timeout_sec = getattr(config_manager.system_config, 'login_timeout_sec', 30)
            await asyncio.wait_for(self.monitor_client.connect(), timeout=timeout_sec)
            if not await self.monitor_client.is_user_authorized():
                logger.error("❌ [监控号登录失败]：需要输入手机号或 bot token")
                try:
                    db_manager.record_login_failure('monitor', 'need phone or bot token')
                except Exception:
                    pass
                try:
                    await self.monitor_client.disconnect()
                except Exception:
                    pass
                self.monitor_client = None
                return False

            me = await asyncio.wait_for(self.monitor_client.get_me(), timeout=timeout_sec)
            monitor_phone = f"+{me.phone}" if me.phone else "未知号码"
            monitor_username = f"@{me.username}" if getattr(me, 'username', None) else ""
            name_parts = [p for p in [getattr(me, 'first_name', None), getattr(me, 'last_name', None)] if p]
            monitor_display_name = " ".join(name_parts) if name_parts else ""
            
            # 更新数据库
            db_manager.update_account_status(
                'monitor',
                True,
                monitor_phone,
                me.id,
                monitor_username,
                monitor_display_name
            )
            
            try:
                db_manager.clear_login_failure('monitor')
            except Exception:
                pass
            logger.info(f"✅ [监控号登录]：{monitor_phone} (ID: {me.id})")
            
            # 加入所有必要的群组
            await self._ensure_monitor_in_groups()
            
            return True
        except asyncio.TimeoutError:
            logger.error("❌ [监控号登录超时]")
            try:
                db_manager.record_login_failure('monitor', 'login timeout')
            except Exception:
                pass
            try:
                if self.monitor_client:
                    await self.monitor_client.disconnect()
            except Exception:
                pass
            self.monitor_client = None
            return False
        except Exception as e:
            logger.error(f"❌ [监控号登录失败]：{e}")
            try:
                db_manager.record_login_failure('monitor', str(e))
            except Exception:
                pass
            return False
    
    async def logout_monitor(self) -> bool:
        """离线监控号"""
        try:
            if self.monitor_client:
                await self.monitor_client.disconnect()
                self.monitor_client = None
                db_manager.remove_account_status('monitor')
                logger.info("✅ [监控号]：已离线")
                return True

            # 内存中没有客户端，但数据库状态显示在线，做一次清理
            try:
                if db_manager.get_account_status('monitor'):
                    db_manager.remove_account_status('monitor')
                    logger.warning("⚠️ [监控号状态异常]：数据库显示在线，已清理")
                    return True
            except Exception as e:
                logger.warning(f"⚠️ [监控号状态异常]：清理失败 {e}")

            return False
        except Exception as e:
            logger.error(f"❌ [监控号离线失败]：{e}")
            return False

    async def _ensure_monitor_in_groups(self):
        """确保监控号加入所有必要的群组"""
        if not self.monitor_client:
            return
        
        cfg = config_manager.telegram_config
        
        # 加入警告群
        try:
            await self.monitor_client(functions.channels.JoinChannelRequest(
                channel=cfg.alert_group
            ))
            logger.info(f"✅ [监控号]：已加入警告群 {cfg.alert_group}")
        except Exception as e:
            logger.warning(f"⚠️ [监控号]：加入警告群失败 {e}")
        
        # 加入所有源群
        for group in cfg.source_groups:
            try:
                entity = await self.monitor_client.get_entity(group)
                try:
                    await self.monitor_client(functions.channels.GetParticipantRequest(
                        channel=entity, participant='me'
                    ))
                    logger.info(f"✅ [监控号]：已在源群 {group}")
                except errors.UserNotParticipantError:
                    await self.monitor_client(functions.channels.JoinChannelRequest(
                        channel=entity
                    ))
                    logger.info(f"✅ [监控号]：已加入源群 {group}")
            except Exception as e:
                logger.error(f"❌ [监控号]：加入源群 {group} 失败 {e}")
    
    async def login_sender(self, session_name: str) -> bool:
        """登录克隆号"""
        try:
            session_path = os.path.join('sessions', f'{session_name}.session')
            
            if not os.path.exists(session_path):
                logger.error(f"❌ [克隆号]：会话文件不存在 {session_path}")
                return False
            
            cfg = config_manager.telegram_config
            proxy = self._get_proxy_config()
            
            client = TelegramClient(
                session_path,
                cfg.shared_api_id,
                cfg.shared_api_hash,
                proxy=proxy
            )

            timeout_sec = getattr(config_manager.system_config, 'login_timeout_sec', 30)
            await asyncio.wait_for(client.connect(), timeout=timeout_sec)
            if not await client.is_user_authorized():
                logger.error(f"❌ [克隆号登录失败]：{session_name} 需要输入手机号或 bot token")
                try:
                    db_manager.record_login_failure(session_name, "need phone or bot token")
                except Exception:
                    pass
                try:
                    await client.disconnect()
                except Exception:
                    pass
                return False

            me = await asyncio.wait_for(client.get_me(), timeout=timeout_sec)
            
            self.sender_clients[session_name] = client
            
            # 更新数据库
            sender_username = f"@{me.username}" if getattr(me, 'username', None) else ""
            name_parts = [p for p in [getattr(me, 'first_name', None), getattr(me, 'last_name', None)] if p]
            sender_display_name = " ".join(name_parts) if name_parts else ""
            db_manager.update_account_status(
                session_name,
                True,
                f"+{me.phone}",
                me.id,
                sender_username,
                sender_display_name
            )
            
            # 登录成功，清理失败记录
            try:
                db_manager.clear_login_failure(session_name)
            except Exception:
                pass

            logger.info(f"✅ [克隆号登录]：{session_name} (Phone: +{me.phone}, ID: {me.id})")
            
            # 确保克隆号在目标群
            await self._ensure_sender_in_target_groups(session_name, client)

            # 不再自动修改克隆号资料（昵称、头像）
            
            return True
        except asyncio.TimeoutError:
            logger.error(f"❌ [克隆号登录超时]：{session_name}")
            try:
                db_manager.record_login_failure(session_name, "login timeout")
            except Exception:
                pass
            try:
                await client.disconnect()
            except Exception:
                pass
            if session_name in self.sender_clients:
                del self.sender_clients[session_name]
            return False
        except Exception as e:
            logger.error(f"❌ [克隆号登录失败]：{session_name} - {e}")
            try:
                db_manager.record_login_failure(session_name, str(e))
            except Exception:
                pass
            if session_name in self.sender_clients:
                del self.sender_clients[session_name]
            return False
    
    async def logout_sender(self, session_name: str) -> bool:
        """离线克隆号"""
        try:
            if session_name in self.sender_clients:
                client = self.sender_clients[session_name]
                await client.disconnect()
                del self.sender_clients[session_name]
                db_manager.remove_account_status(session_name)
                logger.info(f"✅ [克隆号]：已离线 {session_name}")
                return True
            return False
        except Exception as e:
            logger.error(f"❌ [克隆号离线失败]：{session_name} - {e}")
            return False
    
    async def _ensure_sender_in_target_group(self, session_name: str, client: TelegramClient, target_group: str):
        """确保克隆号在目标群"""
        try:
            # 检查是否在目标群
            is_in = False
            async for dialog in client.iter_dialogs():
                if dialog.entity.username and \
                   dialog.entity.username.lower() == target_group.lower().replace('@', ''):
                    is_in = True
                    break
            
            if not is_in:
                logger.info(f"⏳ [克隆号]：{session_name} 正在加入目标群 {target_group}")
                try:
                    await client(functions.channels.JoinChannelRequest(channel=target_group))
                    await asyncio.sleep(2)
                    logger.info(f"✅ [克隆号]：{session_name} 已加入目标群 {target_group}")
                except Exception as e:
                    logger.error(f"❌ [克隆号]：{session_name} 加入目标群 {target_group} 失败 {e}")
            else:
                logger.info(f"✅ [克隆号]：{session_name} 已在目标群 {target_group}")
        except Exception as e:
            logger.error(f"❌ [克隆号]：确保在目标群失败 {e}")

    async def _ensure_sender_in_target_groups(self, session_name: str, client: TelegramClient):
        """确保克隆号在所有目标群"""
        cfg = config_manager.telegram_config
        for group in cfg.my_groups:
            await self._ensure_sender_in_target_group(session_name, client, group)

    async def ensure_all_senders_in_target_group(self) -> None:
        """确保所有已登录克隆号都在目标群"""
        if not self.sender_clients:
            return
        for session_name, client in list(self.sender_clients.items()):
            await self._ensure_sender_in_target_groups(session_name, client)
    
    async def auto_login_senders(self) -> int:
        """自动登录所有克隆号"""
        try:
            session_files = glob.glob(os.path.join('sessions', '*.session'))
            success_count = 0
            try:
                failed = {f['session_name'] for f in db_manager.get_login_failures()}
            except Exception:
                failed = set()
            
            for session_path in session_files:
                session_name = os.path.splitext(os.path.basename(session_path))[0]
                if session_name in failed:
                    logger.warning(f"⚠️ [自动登录]：跳过失败账号 {session_name}")
                    continue
                if await self.login_sender(session_name):
                    success_count += 1
            
            logger.info(f"📊 [自动登录]：成功登录 {success_count}/{len(session_files)} 个克隆号")
            return success_count
        except Exception as e:
            logger.error(f"❌ [自动登录失败]：{e}")
            return 0
    
    async def logout_all_senders(self) -> int:
        """离线所有克隆号"""
        try:
            session_names = list(self.sender_clients.keys())
            live_count = len(session_names)

            for session_name in session_names:
                await self.logout_sender(session_name)

            cleared = 0
            if live_count == 0:
                try:
                    statuses = db_manager.get_all_accounts_status()
                    stale_names = [
                        s['session_name'] for s in statuses
                        if s.get('session_name') != 'monitor'
                    ]
                    for name in stale_names:
                        db_manager.remove_account_status(name)
                    cleared = len(stale_names)
                    if cleared:
                        logger.warning(
                            f"⚠️ [账号状态清理]：数据库中有 {cleared} 个已在线账号，但内存无客户端，已清理"
                        )
                except Exception as e:
                    logger.warning(f"⚠️ [账号状态清理]：失败 {e}")

            count = live_count if live_count > 0 else cleared
            logger.info(f"✅ [批量离线]：已离线 {count} 个克隆号")
            return count
        except Exception as e:
            logger.error(f"❌ [批量离线失败]：{e}")
            return 0


    def get_monitor_status(self) -> Optional[Dict]:
        """获取监控号状态"""
        return db_manager.get_account_status('monitor')
    
    def get_all_senders_status(self) -> List[Dict]:
        """获取所有克隆号状态"""
        return db_manager.get_all_accounts_status()
    
    def get_sender_client(self, session_name: str) -> Optional[TelegramClient]:
        """获取克隆号客户端"""
        return self.sender_clients.get(session_name)
    
    def is_sender_active(self, session_name: str) -> bool:
        """检查克隆号是否在线"""
        return session_name in self.sender_clients

    async def refresh_monitor_status(self) -> Optional[Dict]:
        """实时刷新监控号状态（发起网络请求并写回数据库）"""
        try:
            if not self.monitor_client:
                try:
                    if db_manager.get_account_status('monitor'):
                        db_manager.remove_account_status('monitor')
                except Exception:
                    pass
                return db_manager.get_account_status('monitor')

            client = self.monitor_client
            timeout_sec = getattr(config_manager.system_config, 'login_timeout_sec', 30)

            try:
                is_connected = client.is_connected() if hasattr(client, 'is_connected') else True
            except Exception:
                is_connected = True
            if not is_connected:
                await asyncio.wait_for(client.connect(), timeout=timeout_sec)

            if not await client.is_user_authorized():
                try:
                    await client.disconnect()
                except Exception:
                    pass
                self.monitor_client = None
                db_manager.remove_account_status('monitor')
                return None

            me = await asyncio.wait_for(client.get_me(), timeout=timeout_sec)
            monitor_phone = f"+{me.phone}" if me.phone else "未知号码"
            monitor_username = f"@{me.username}" if getattr(me, 'username', None) else ""
            name_parts = [p for p in [getattr(me, 'first_name', None), getattr(me, 'last_name', None)] if p]
            monitor_display_name = " ".join(name_parts) if name_parts else ""

            db_manager.update_account_status(
                'monitor',
                True,
                monitor_phone,
                me.id,
                monitor_username,
                monitor_display_name
            )
            return db_manager.get_account_status('monitor')
        except Exception as e:
            logger.error(f"❌ [监控号刷新失败]：{e}")
            return db_manager.get_account_status('monitor')

    async def refresh_senders_status(self) -> List[Dict]:
        """实时刷新克隆号状态（发起网络请求并写回数据库）"""
        timeout_sec = getattr(config_manager.system_config, 'login_timeout_sec', 30)
        for session_name, client in list(self.sender_clients.items()):
            try:
                try:
                    is_connected = client.is_connected() if hasattr(client, 'is_connected') else True
                except Exception:
                    is_connected = True
                if not is_connected:
                    await asyncio.wait_for(client.connect(), timeout=timeout_sec)

                if not await client.is_user_authorized():
                    try:
                        await client.disconnect()
                    except Exception:
                        pass
                    if session_name in self.sender_clients:
                        del self.sender_clients[session_name]
                    db_manager.remove_account_status(session_name)
                    continue

                me = await asyncio.wait_for(client.get_me(), timeout=timeout_sec)
                sender_username = f"@{me.username}" if getattr(me, 'username', None) else ""
                name_parts = [p for p in [getattr(me, 'first_name', None), getattr(me, 'last_name', None)] if p]
                sender_display_name = " ".join(name_parts) if name_parts else ""

                db_manager.update_account_status(
                    session_name,
                    True,
                    f"+{me.phone}" if me.phone else "",
                    me.id,
                    sender_username,
                    sender_display_name
                )
            except Exception as e:
                logger.warning(f"⚠️ [克隆号刷新失败]：{session_name} - {e}")

        # 清理数据库中“在线但无内存客户端”的记录
        try:
            statuses = db_manager.get_all_accounts_status()
            live_names = set(self.sender_clients.keys())
            for s in statuses:
                if s.get('session_name') == 'monitor':
                    continue
                if s.get('session_name') not in live_names:
                    db_manager.remove_account_status(s.get('session_name'))
        except Exception:
            pass

        return db_manager.get_all_accounts_status()



# 全局账号管理器实例
account_manager = AccountManager()
