"""
日志管理模块
"""
import logging
import os
import json
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime
from typing import List, Dict
from collections import deque
from threading import RLock


class RotatingMemoryHandler(logging.Handler):
    """内存日志处理器 - 保存最近的日志在内存中"""
    
    def __init__(self, max_logs: int = 1000):
        super().__init__()
        self.logs = deque(maxlen=max_logs)
        self.lock = RLock()
    
    def emit(self, record):
        try:
            log_entry = {
                'timestamp': datetime.fromtimestamp(record.created).isoformat(),
                'level': record.levelname,
                'message': self.format(record),
                'module': record.module
            }
            with self.lock:
                self.logs.append(log_entry)
        except Exception:
            self.handleError(record)
    
    def get_logs(self, level: str = None, limit: int = 100) -> List[Dict]:
        """获取日志"""
        with self.lock:
            logs = list(self.logs)
        
        if level:
            logs = [log for log in logs if log['level'] == level]
        
        return logs[-limit:]


class LoggerManager:
    """日志管理器"""
    
    def __init__(self, log_folder: str = 'logs'):
        self.log_folder = log_folder
        if not os.path.exists(log_folder):
            os.makedirs(log_folder)
        
        # 主系统日志
        self.logger = logging.getLogger('MainSystem')
        self.logger.setLevel(logging.INFO)
        
        # 内存处理器
        self.memory_handler = RotatingMemoryHandler(max_logs=2000)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        self.memory_handler.setFormatter(formatter)
        
        # 文件处理器
        log_file = os.path.join(log_folder, 'bot_activity.log')
        file_handler = TimedRotatingFileHandler(
            log_file, when='midnight', interval=1, 
            backupCount=7, encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        
        # 控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        
        # 添加处理器
        self.logger.addHandler(self.memory_handler)
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
        
        # 设置 telethon 日志级别
        logging.getLogger('telethon').setLevel(logging.WARNING)
    
    def info(self, message: str):
        """记录信息日志"""
        self.logger.info(message)
    
    def warning(self, message: str):
        """记录警告日志"""
        self.logger.warning(message)
    
    def error(self, message: str):
        """记录错误日志"""
        self.logger.error(message)
    
    def debug(self, message: str):
        """记录调试日志"""
        self.logger.debug(message)
    
    def get_logs(self, level: str = None, limit: int = 100) -> List[Dict]:
        """获取日志"""
        return self.memory_handler.get_logs(level=level, limit=limit)
    
    def get_logs_by_date(self, date_str: str = None) -> List[str]:
        """按日期获取日志文件"""
        try:
            log_files = []
            for f in os.listdir(self.log_folder):
                if f.startswith('bot_activity.log'):
                    log_files.append(f)
            log_files.sort(reverse=True)
            return log_files[:10]  # 返回最近 10 个日志文件
        except Exception as e:
            print(f"❌ 获取日志文件失败: {e}")
            return []
    
    def read_log_file(self, filename: str) -> str:
        """读取日志文件内容"""
        try:
            log_path = os.path.join(self.log_folder, filename)
            if os.path.exists(log_path):
                with open(log_path, 'r', encoding='utf-8') as f:
                    return f.read()
            return "日志文件不存在"
        except Exception as e:
            return f"❌ 读取日志失败: {e}"
    
    def clear_old_logs(self, days: int = 7):
        """清理旧日志"""
        import time
        try:
            now = time.time()
            for f in os.listdir(self.log_folder):
                log_path = os.path.join(self.log_folder, f)
                if os.path.isfile(log_path):
                    if os.stat(log_path).st_mtime < now - days * 86400:
                        os.remove(log_path)
        except Exception as e:
            self.error(f"❌ 清理旧日志失败: {e}")


# 全局日志管理器实例
logger_manager = LoggerManager()
logger = logger_manager
