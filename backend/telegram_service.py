"""
Telegram 业务逻辑模块
"""
import asyncio
import re
import os
import random
import shutil
from typing import Optional, Callable
from telethon import events, errors, functions
from .config_manager import config_manager
from .db_manager import db_manager
from .logger_manager import logger


class TelegramService:
    """Telegram 服务"""
    
    def __init__(self, account_manager):
        self.account_manager = account_manager
        self.msg_queue = None
        self.message_handler = None
    
    async def init_sender_profile(self, client, session_name: str):
        """初始化克隆号的个人资料"""
        try:
            # 检查是否已初始化
            if db_manager.is_account_initialized(session_name):
                return
            
            # 更新昵称
            new_name = session_name
            if os.path.exists('name.txt'):
                with open('name.txt', 'r', encoding='utf-8') as f:
                    names = [line.strip() for line in f if line.strip()]
                    if names:
                        new_name = random.choice(names)
            
            await client(functions.account.UpdateProfileRequest(first_name=new_name))
            logger.info(f"📝 [克隆号]：{session_name} 昵称已更新为 {new_name}")
            
            # 更新头像
            photo_folder = 'profile_photos'
            if os.path.exists(photo_folder):
                photo_list = [
                    os.path.join(photo_folder, f)
                    for f in os.listdir(photo_folder)
                    if f.lower().endswith(('.jpg', '.jpeg', '.png'))
                ]

                if photo_list:
                    chosen_photo = random.choice(photo_list)
                    try:
                        file = await client.upload_file(chosen_photo)
                        await client(functions.photos.UploadProfilePhotoRequest(file=file))
                        logger.info(f"📸 [克隆号]：{session_name} 头像已更新")
                    except Exception as e:
                        logger.warning(f"⚠️ [克隆号]：{session_name} 更新头像失败 {e}")
            
            # 标记为已初始化
            db_manager.mark_account_initialized(session_name)
        except Exception as e:
            logger.error(f"❌ [克隆号]：初始化失败 {session_name} - {e}")

    async def update_sender_profile(self, session_name: str, name: Optional[str] = None,
                                    random_name: bool = True, random_photo: bool = True) -> (bool, str):
        """更新克隆号昵称和头像（可选择随机）"""
        try:
            client = self.account_manager.get_sender_client(session_name)
            if not client:
                return False, "克隆号未登录"

            # 更新昵称
            new_name = name
            if not new_name and random_name:
                if os.path.exists('name.txt'):
                    with open('name.txt', 'r', encoding='utf-8') as f:
                        names = [line.strip() for line in f if line.strip()]
                        if names:
                            new_name = random.choice(names)
            if not new_name:
                new_name = session_name

            try:
                await client(functions.account.UpdateProfileRequest(first_name=new_name))
                logger.info(f"📝 [克隆号]：{session_name} 昵称已更新为 {new_name}")
            except Exception as e:
                logger.warning(f"⚠️ [克隆号]：{session_name} 更新昵称失败 {e}")

            # 更新头像
            if random_photo:
                photo_folder = 'profile_photos'
                if os.path.exists(photo_folder):
                    photo_list = [
                        os.path.join(photo_folder, f)
                        for f in os.listdir(photo_folder)
                        if f.lower().endswith(('.jpg', '.jpeg', '.png'))
                    ]

                    if photo_list:
                        chosen_photo = random.choice(photo_list)
                        try:
                            file = await client.upload_file(chosen_photo)
                            await client(functions.photos.UploadProfilePhotoRequest(file=file))
                            logger.info(f"📸 [克隆号]：{session_name} 头像已更新")
                        except Exception as e:
                            logger.warning(f"⚠️ [克隆号]：{session_name} 更新头像失败 {e}")
                else:
                    logger.warning(f"⚠️ [克隆号]：头像目录不存在 {photo_folder}")

            return True, "✅ 已更新克隆号资料"
        except Exception as e:
            logger.error(f"❌ [克隆号]：更新资料失败 {session_name} - {e}")
            return False, f"更新失败: {e}"

    async def update_sender_profile_manual(self, session_name: str, name: Optional[str] = None,
                                           photo_path: Optional[str] = None) -> (bool, str):
        """手动更新克隆号昵称和头像（头像为上传文件）"""
        try:
            client = self.account_manager.get_sender_client(session_name)
            if not client:
                return False, "克隆号未登录"

            if not name and not photo_path:
                return False, "未提供昵称或头像"

            if name:
                try:
                    await client(functions.account.UpdateProfileRequest(first_name=name))
                    logger.info(f"📝 [克隆号]：{session_name} 昵称已更新为 {name}")
                except Exception as e:
                    logger.warning(f"⚠️ [克隆号]：{session_name} 更新昵称失败 {e}")

            if photo_path:
                try:
                    file = await client.upload_file(photo_path)
                    await client(functions.photos.UploadProfilePhotoRequest(file=file))
                    logger.info(f"📸 [克隆号]：{session_name} 头像已更新")
                except Exception as e:
                    logger.warning(f"⚠️ [克隆号]：{session_name} 更新头像失败 {e}")

            return True, "✅ 已更新克隆号资料"
        except Exception as e:
            logger.error(f"❌ [克隆号]：手动更新资料失败 {session_name} - {e}")
            return False, f"更新失败: {e}"

    async def update_monitor_profile_manual(self, name: Optional[str] = None,
                                            photo_path: Optional[str] = None) -> (bool, str):
        """手动更新监控号昵称和头像（头像为上传文件）"""
        try:
            client = self.account_manager.monitor_client
            if not client:
                return False, "监控号未登录"

            if not name and not photo_path:
                return False, "未提供昵称或头像"

            if name:
                try:
                    await client(functions.account.UpdateProfileRequest(first_name=name))
                    logger.info(f"📝 [监控号]：昵称已更新为 {name}")
                except Exception as e:
                    logger.warning(f"⚠️ [监控号]：更新昵称失败 {e}")

            if photo_path:
                try:
                    file = await client.upload_file(photo_path)
                    await client(functions.photos.UploadProfilePhotoRequest(file=file))
                    logger.info("📸 [监控号]：头像已更新")
                except Exception as e:
                    logger.warning(f"⚠️ [监控号]：更新头像失败 {e}")

            return True, "✅ 已更新监控号资料"
        except Exception as e:
            logger.error(f"❌ [监控号]：手动更新资料失败 - {e}")
            return False, f"更新失败: {e}"
    
    def _should_filter_message(self, text: str) -> bool:
        """检查消息是否应该被过滤"""
        if not text:
            return False
        
        cfg = config_manager.filter_config
        
        # 检查关键词
        for kw in cfg.keywords:
            if kw.lower() in text.lower():
                return True
        
        return False
    
    def _should_skip_media(self, message) -> bool:
        """检查是否应该跳过媒体"""
        if not message.media:
            return False
        
        try:
            cfg = config_manager.filter_config
            size = 0
            
            if hasattr(message.media, 'document'):
                size = message.media.document.size
            
            if size > cfg.max_file_size_mb * 1024 * 1024:
                return True
        except Exception:
            pass
        
        return False
    
    async def send_alert(self, message: str):
        """发送警报到警告群"""
        try:
            if not self.account_manager.monitor_client:
                return
            
            import time
            cfg = config_manager.telegram_config
            alert_msg = f"⚠️ **系统实时警报**\n\n{message}\n\n⏰ {time.strftime('%Y-%m-%d %H:%M:%S')}"
            
            await self.account_manager.monitor_client.send_message(
                cfg.alert_group, alert_msg
            )
            logger.info("📢 [警告群]：警报已发送")
        except Exception as e:
            logger.error(f"❌ [警告群]：发送失败 {e}")
    
    async def forward_message(self, message, sender_name: str) -> bool:
        """转发消息到目标群"""
        try:
            client = self.account_manager.get_sender_client(sender_name)
            if not client:
                logger.warning(f"⚠️ [转发]：克隆号不活跃 {sender_name}")
                return False
            
            cfg = config_manager.telegram_config
            
            try:
                # 在发送前尽量确保客户端处于连接状态（部分 Telethon 版本在断连时会抛出错误）
                try:
                    is_connected = False
                    if hasattr(client, 'is_connected'):
                        # is_connected 可能是方法或属性
                        attr = getattr(client, 'is_connected')
                        is_connected = attr() if callable(attr) else bool(attr)
                    else:
                        is_connected = True
                except Exception:
                    is_connected = True

                if not is_connected:
                    logger.warning(f"⚠️ [转发]：克隆号未连接 {sender_name}")
                    return False

                if not cfg.my_groups:
                    logger.warning(f"⚠️ [转发]：未配置目标群，跳过转发 {sender_name}")
                    return False

                success = True
                for group in cfg.my_groups:
                    try:
                        # 回复同步：查找目标群对应的被回复消息
                        reply_to_id = None
                        try:
                            if message.reply_to_msg_id:
                                reply_to_id = db_manager.get_target_message_id(
                                    message.chat_id,
                                    message.reply_to_msg_id,
                                    group
                                )
                        except Exception:
                            reply_to_id = None

                        # @ 同步：替换为对应克隆号用户名
                        send_text = message.text
                        if send_text:
                            send_text = self._replace_mentions(send_text)

                        if not message.media:
                            sent = await client.send_message(
                                group,
                                send_text,
                                reply_to=reply_to_id
                            )
                        else:
                            sent = await client.send_file(
                                group,
                                message.media,
                                caption=send_text,
                                reply_to=reply_to_id,
                                supports_streaming=True
                            )

                        # 记录转发
                        db_manager.record_message_forward(sender_name, group)
                        try:
                            if sent:
                                db_manager.record_message_mapping(
                                    message.chat_id,
                                    message.id,
                                    group,
                                    sent.id,
                                    sender_name
                                )
                        except Exception:
                            pass
                        logger.info(f"✅ [转发成功]：{sender_name} -> {group}")
                    except Exception as e:
                        success = False
                        logger.error(f"❌ [转发失败]：{sender_name} -> {group} - {e}")
                return success

            except (errors.UserDeactivatedError, errors.UnauthorizedError) as e:
                if sender_name in self.account_manager.sender_clients:
                    del self.account_manager.sender_clients[sender_name]
                await self.send_alert(f"💀 死号剔除：`{sender_name}`")
                logger.error(f"❌ [死号]：{sender_name}")
                return False

            except (errors.WriteForbiddenError, errors.ChatWriteForbiddenError) as e:
                if sender_name in self.account_manager.sender_clients:
                    del self.account_manager.sender_clients[sender_name]
                await self.send_alert(f"🚫 权限丢失：`{sender_name}`")
                logger.error(f"❌ [权限丢失]：{sender_name}")
                return False

            except Exception as e:
                # 处理断连类错误，避免抛出导致监听线程崩溃
                msg = str(e)
                logger.error(f"❌ [转发失败]：{sender_name} - {e}")
                if 'Cannot send requests while disconnected' in msg or 'disconnected' in msg:
                    # 移除不可用客户端，通知并继续
                    if sender_name in self.account_manager.sender_clients:
                        try:
                            del self.account_manager.sender_clients[sender_name]
                        except Exception:
                            pass
                    await self.send_alert(f"⚠️ 克隆号掉线：`{sender_name}`，已从可用列表移除")
                return False
        
        except Exception as e:
            logger.error(f"❌ [转发异常]：{e}")
            return False
    
    def setup_message_handlers(self, on_message_callback: Callable):
        """设置消息处理器"""
        self.message_handler = on_message_callback

    def _replace_mentions(self, text: str) -> str:
        """将 @源用户 替换为对应克隆号的 @用户名"""
        if not text:
            return text

        # 匹配 @username（前一个字符不是字母/数字/下划线）
        pattern = r'(?<![A-Za-z0-9_])@([A-Za-z0-9_]{3,32})'

        def repl(match):
            username = match.group(1)
            sender_name = db_manager.get_sender_by_source_username(username)
            if not sender_name:
                return match.group(0)
            status = db_manager.get_account_status(sender_name)
            if not status or not status.get('username'):
                return match.group(0)
            clone_username = status.get('username', '').lstrip('@')
            if not clone_username:
                return match.group(0)
            return f"@{clone_username}"

        try:
            return re.sub(pattern, repl, text)
        except Exception:
            return text
    
    async def check_monitor_status(self):
        """检查监控号状态"""
        if not self.account_manager.monitor_client:
            return
        
        try:
            cfg = config_manager.telegram_config
            for group in cfg.source_groups:
                try:
                    entity = await self.account_manager.monitor_client.get_entity(group)
                    await self.account_manager.monitor_client(
                        functions.channels.GetParticipantRequest(
                            channel=entity, participant='me'
                        )
                    )
                except errors.UserNotParticipantError:
                    await self.send_alert(f"🚨 监控号已离开源群：{group}")
                    logger.warning(f"⚠️ [巡检]：监控号不在源群 {group}")
        except Exception as e:
            logger.error(f"❌ [巡检失败]：{e}")


# 全局 Telegram 服务实例 (需要在创建时传入 account_manager)
telegram_service = None


def init_telegram_service(account_manager):
    """初始化 Telegram 服务"""
    global telegram_service
    telegram_service = TelegramService(account_manager)
    return telegram_service
