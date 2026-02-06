"""
配置管理模块 - 集中管理所有配置项
"""
import json
import os
from typing import Dict, Any
from dataclasses import dataclass, asdict


@dataclass
class TelegramConfig:
    """Telegram 配置"""
    monitor_account_id: int = 6
    monitor_api_hash: str = 'eb06d4ab352772397adad09530d31d5d'
    shared_api_id: int = 6
    shared_api_hash: str = 'eb06d4ab352772397adad09530d31d5d'
    alert_group: str = '@aopame3'
    source_groups: list = None
    my_groups: list = None
    
    def __post_init__(self):
        if self.source_groups is None:
            self.source_groups = ['@asfaaasfa1']
        if self.my_groups is None:
            self.my_groups = ['@hgfher2']


@dataclass
class ProxyConfig:
    """代理配置"""
    use_proxy: bool = False
    proxy_type: str = 'SOCKS5'
    proxy_host: str = '127.0.0.1'
    proxy_port: int = 7897
    proxy_username: str = ''
    proxy_password: str = ''
    
    def to_dict(self):
        return asdict(self)


@dataclass
class FilterConfig:
    """过滤配置"""
    keywords: list = None
    max_file_size_mb: int = 10
    
    def __post_init__(self):
        if self.keywords is None:
            self.keywords = ['广告', '加粉', '联系方式', '私聊', 'http', 't.me', 'vx', '私信']


@dataclass
class SystemConfig:
    """系统配置"""
    max_concurrent_tasks: int = 3
    msg_queue_size: int = 500
    auto_check_interval: int = 30
    check_status_interval: int = 30
    login_timeout_sec: int = 30


class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_file: str = 'config.json'):
        self.config_file = config_file
        self.telegram_config = TelegramConfig()
        self.proxy_config = ProxyConfig()
        self.filter_config = FilterConfig()
        self.system_config = SystemConfig()
        
        # 加载现有配置
        if os.path.exists(config_file):
            self.load_config()
        else:
            self.save_config()
    
    def load_config(self):
        """从文件加载配置"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # 加载 Telegram 配置
            if 'telegram' in data:
                for key, value in data['telegram'].items():
                    if hasattr(self.telegram_config, key):
                        setattr(self.telegram_config, key, value)
                # 向后兼容：旧配置使用 my_group 字段
                if 'my_group' in data['telegram'] and not getattr(self.telegram_config, 'my_groups', None):
                    self.telegram_config.my_groups = [data['telegram']['my_group']]
                # 容错：若 my_groups 被写成字符串，转换为列表
                if isinstance(self.telegram_config.my_groups, str):
                    self.telegram_config.my_groups = [self.telegram_config.my_groups]
            
            # 加载代理配置
            if 'proxy' in data:
                for key, value in data['proxy'].items():
                    if hasattr(self.proxy_config, key):
                        setattr(self.proxy_config, key, value)
            
            # 加载过滤配置
            if 'filter' in data:
                for key, value in data['filter'].items():
                    if hasattr(self.filter_config, key):
                        setattr(self.filter_config, key, value)
            
            # 加载系统配置
            if 'system' in data:
                for key, value in data['system'].items():
                    if hasattr(self.system_config, key):
                        setattr(self.system_config, key, value)
        except Exception as e:
            print(f"❌ 加载配置失败: {e}")
    
    def save_config(self):
        """保存配置到文件"""
        try:
            config_data = {
                'telegram': asdict(self.telegram_config),
                'proxy': asdict(self.proxy_config),
                'filter': asdict(self.filter_config),
                'system': asdict(self.system_config)
            }
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"❌ 保存配置失败: {e}")
    
    def update_telegram_config(self, **kwargs):
        """更新 Telegram 配置"""
        for key, value in kwargs.items():
            if hasattr(self.telegram_config, key):
                setattr(self.telegram_config, key, value)
        self.save_config()
    
    def update_proxy_config(self, **kwargs):
        """更新代理配置"""
        for key, value in kwargs.items():
            if hasattr(self.proxy_config, key):
                setattr(self.proxy_config, key, value)
        self.save_config()
    
    def update_filter_config(self, **kwargs):
        """更新过滤配置"""
        for key, value in kwargs.items():
            if hasattr(self.filter_config, key):
                setattr(self.filter_config, key, value)
        self.save_config()
    
    def update_system_config(self, **kwargs):
        """更新系统配置"""
        for key, value in kwargs.items():
            if hasattr(self.system_config, key):
                setattr(self.system_config, key, value)
        self.save_config()
    
    def get_all_config(self) -> Dict[str, Any]:
        """获取所有配置"""
        return {
            'telegram': asdict(self.telegram_config),
            'proxy': asdict(self.proxy_config),
            'filter': asdict(self.filter_config),
            'system': asdict(self.system_config)
        }


# 全局配置管理器实例
config_manager = ConfigManager()
