"""
API统计模块
提供API请求统计、数据存储和WebUI展示功能
"""

from .stats_manager import StatsManager, get_stats_manager
from .stats_webui import register_stats_routes
from .security_manager import SecurityManager, get_security_manager

__all__ = [
    'StatsManager',
    'get_stats_manager',
    'register_stats_routes',
    'SecurityManager',
    'get_security_manager'
]

__version__ = '1.0.0'
