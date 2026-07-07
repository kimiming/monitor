"""
消息处理工人模块
"""
import asyncio
import os
import random
import re
import shutil
import time
from typing import List, Optional
from .config_manager import config_manager
from .db_manager import db_manager
from .logger_manager import logger


class MessageWorker:
    """消息处理工人"""
    
    def __init__(self, account_manager, telegram_service):
        self.account_manager = account_manager
        self.telegram_service = telegram_service
        self.msg_queue = None
        self.workers = []
        self.is_running = False
        self._last_sender_autologin_ts = 0
        self._auto_login_inflight = False
    
    async def init_queue(self, queue_size: int = 500):
        """初始化消息队列"""
        self.msg_queue = asyncio.Queue(maxsize=queue_size)
    
    async def start_workers(self):
        """启动消息处理工人"""
        try:
            if self.is_running:
                logger.warning("⚠️ [工人]：工人已在运行")
                return
            
            self.is_running = True
            cfg = config_manager.system_config
            
            for i in range(cfg.max_concurrent_tasks):
                task = asyncio.create_task(self._worker_loop(i))
                self.workers.append(task)
            
            logger.info(f"✅ [工人]：已启动 {cfg.max_concurrent_tasks} 个工人")
        except Exception as e:
            logger.error(f"❌ [工人启动失败]：{e}")
    
    async def stop_workers(self):
        """停止消息处理工人"""
        try:
            self.is_running = False
            
            # 取消所有工人任务
            for task in self.workers:
                task.cancel()
            
            # 等待任务完成
            if self.workers:
                await asyncio.gather(*self.workers, return_exceptions=True)
                self.workers.clear()
            
            logger.info("✅ [工人]：已停止所有工人")
        except Exception as e:
            logger.error(f"❌ [工人停止失败]：{e}")
    
    async def _worker_loop(self, worker_id: int):
        """工人循环"""
        # 初始化临时文件夹
        if os.path.exists('temp_media'):
            shutil.rmtree('temp_media', ignore_errors=True)
        os.makedirs('temp_media', exist_ok=True)
        
        logger.info(f"🔄 [工人 {worker_id}]：已启动")
        
        while self.is_running:
            try:
                # 获取消息 (设置超时防止阻塞)
                try:
                    event = await asyncio.wait_for(self.msg_queue.get(), timeout=5.0)
                except asyncio.TimeoutError:
                    continue
                
                try:
                    await self._process_message(event, worker_id)
                finally:
                    self.msg_queue.task_done()
            
            except asyncio.CancelledError:
                logger.info(f"🛑 [工人 {worker_id}]：已停止")
                break
            except Exception as e:
                logger.error(f"❌ [工人 {worker_id} 异常]：{e}")
                await asyncio.sleep(1)
    
    async def _process_message(self, event, worker_id: int):
        """处理单条消息"""
        try:
            msg = event.message
            
            # 检查文本过滤
            if msg.text:
                if self.telegram_service._should_filter_message(msg.text):
                    logger.info(f"🚫 [工人 {worker_id}]：消息被过滤")
                    return
            
            # 检查媒体过滤
            if self.telegram_service._should_skip_media(msg):
                logger.warning(f"⏭️ [工人 {worker_id}]：媒体过大被跳过")
                return
            
            # 获取源用户 ID
            source_user_id = None
            if hasattr(msg.from_id, 'user_id'):
                source_user_id = msg.from_id.user_id
            
            if not source_user_id:
                return

            # 获取源用户名（用于 @ 同步）
            source_username = None
            try:
                sender = getattr(event, 'sender', None)
                if sender and getattr(sender, 'username', None):
                    source_username = sender.username
                elif getattr(msg, 'sender', None) and getattr(msg.sender, 'username', None):
                    source_username = msg.sender.username
            except Exception:
                source_username = None
            
            # 获取或分配克隆号
            senders = self.account_manager.sender_clients
            if not senders:
                await self._ensure_senders_available()
                senders = self.account_manager.sender_clients
            if not senders:
                logger.warning(f"⚠️ [工人 {worker_id}]：没有可用的克隆号")
                return
            
            # 查询用户映射
            assigned_name = db_manager.get_user_mapping(source_user_id)
            
            if not assigned_name:
                # 优先使用 @ 用户名映射（如果存在）
                if source_username:
                    assigned_name = db_manager.get_sender_by_source_username(source_username)

                if not assigned_name:
                    # 随机分配（首次绑定）
                    assigned_name = random.choice(list(senders.keys()))

                db_manager.set_user_mapping(source_user_id, assigned_name, source_username or '')
                if source_username:
                    db_manager.set_username_mapping(source_username, assigned_name)
                logger.info(f"🔄 [工人 {worker_id}]：分配 {source_user_id} -> {assigned_name}")
            else:
                # 映射已存在，保持不变，仅更新用户名
                if source_username:
                    db_manager.set_user_mapping(source_user_id, assigned_name, source_username)
                    db_manager.set_username_mapping(source_username, assigned_name)

            if assigned_name not in senders:
                logger.warning(f"⚠️ [工人 {worker_id}]：映射克隆号离线 {assigned_name}，尝试唤醒登录")
                try:
                    woke = await self.account_manager.login_sender(assigned_name)
                except Exception:
                    woke = False
                if woke:
                    senders = self.account_manager.sender_clients
                else:
                    # 唤醒失败：解绑并重新分配
                    logger.warning(
                        f"⚠️ [工人 {worker_id}]：唤醒失败，解绑映射 {source_user_id} -> {assigned_name}"
                    )
                    try:
                        db_manager.delete_user_mapping(source_user_id)
                    except Exception:
                        pass

                    senders = self.account_manager.sender_clients
                    if not senders:
                        await self._ensure_senders_available()
                        senders = self.account_manager.sender_clients
                    if not senders:
                        logger.warning(f"⚠️ [工人 {worker_id}]：没有可用的克隆号")
                        return

                    assigned_name = random.choice(list(senders.keys()))
                    db_manager.set_user_mapping(source_user_id, assigned_name, source_username or '')
                    if source_username:
                        db_manager.set_username_mapping(source_username, assigned_name)
                    logger.info(
                        f"🔄 [工人 {worker_id}]：重新分配 {source_user_id} -> {assigned_name}"
                    )

            # 处理 @ 绑定：未建立映射的 @ 也触发唤醒+绑定
            mentions = self._extract_mentions(msg.text)
            if mentions:
                for uname in mentions:
                    if source_username and uname.lower() == source_username.lower():
                        continue
                    mapped = db_manager.get_sender_by_source_username(uname)
                    if not mapped:
                        if not senders:
                            await self._ensure_senders_available()
                            senders = self.account_manager.sender_clients
                        if not senders:
                            continue
                        choices = list(senders.keys())
                        if assigned_name in choices and len(choices) > 1:
                            choices.remove(assigned_name)
                        mapped = random.choice(choices)
                        db_manager.set_username_mapping(uname, mapped)
                        logger.info(f"🔄 [工人 {worker_id}]：@绑定 {uname} -> {mapped}")
                    else:
                        if mapped not in senders:
                            try:
                                woke = await self.account_manager.login_sender(mapped)
                            except Exception:
                                woke = False
                            if not woke:
                                if not senders:
                                    await self._ensure_senders_available()
                                    senders = self.account_manager.sender_clients
                                if senders:
                                    choices = list(senders.keys())
                                    if mapped in choices and len(choices) > 1:
                                        choices.remove(mapped)
                                    new_mapped = random.choice(choices)
                                    db_manager.set_username_mapping(uname, new_mapped)
                                    logger.info(f"🔄 [工人 {worker_id}]：@改绑 {uname} -> {new_mapped}")

            # 转发消息（带引用和 @ 同步）
            await self.telegram_service.forward_message(msg, assigned_name)
        
        except Exception as e:
            logger.error(f"❌ [处理消息失败]：{e}")

    def _extract_mentions(self, text: Optional[str]) -> List[str]:
        if not text:
            return []
        try:
            pattern = r'(?<![A-Za-z0-9_])@([A-Za-z0-9_]{3,32})'
            return list({m.lower() for m in re.findall(pattern, text)})
        except Exception:
            return []

    async def _ensure_senders_available(self):
        """在没有可用克隆号时，尝试自动恢复"""
        if self.account_manager.sender_clients:
            return True

        # 60 秒内只尝试一次，避免频繁自动登录
        now = time.time()
        if now - self._last_sender_autologin_ts < 60:
            return False

        if self._auto_login_inflight:
            return False

        self._auto_login_inflight = True
        self._last_sender_autologin_ts = now
        try:
            try:
                db_statuses = db_manager.get_all_accounts_status()
                db_active = [
                    s for s in db_statuses
                    if s.get('session_name') != 'monitor' and s.get('is_active')
                ]
                if db_active:
                    logger.warning(
                        f"⚠️ [工人]：数据库显示 {len(db_active)} 个克隆号在线，但内存无客户端，尝试自动登录..."
                    )
                else:
                    logger.warning("⚠️ [工人]：未检测到在线克隆号，尝试自动登录...")
            except Exception:
                logger.warning("⚠️ [工人]：无法读取账号状态，尝试自动登录...")

            count = await self.account_manager.auto_login_senders()
            if count > 0:
                logger.info(f"✅ [工人]：已自动登录 {count} 个克隆号")
                return True
            logger.warning("⚠️ [工人]：自动登录未发现可用克隆号")
            return False
        except Exception as e:
            logger.error(f"❌ [工人]：自动登录克隆号失败 {e}")
            return False
        finally:
            self._auto_login_inflight = False
    
    async def add_message(self, event):
        """添加消息到队列"""
        try:
            if not self.msg_queue:
                logger.warning("⚠️ [消息队列]：未初始化，消息被丢弃")
                return
            if not self.msg_queue.full():
                self.msg_queue.put_nowait(event)
        except asyncio.QueueFull:
            logger.warning("⚠️ [消息队列]：队列已满，消息被丢弃")
        except Exception as e:
            logger.error(f"❌ [添加消息失败]：{e}")
    
    def get_queue_size(self) -> int:
        """获取队列大小"""
        return self.msg_queue.qsize() if self.msg_queue else 0


# 全局消息工人实例 (需要在创建时传入)
message_worker = None


def init_message_worker(account_manager, telegram_service):
    """初始化消息工人"""
    global message_worker
    message_worker = MessageWorker(account_manager, telegram_service)
    return message_worker
