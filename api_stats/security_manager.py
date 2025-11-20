"""

API安全防护模块
检测、记录和阻止恶意请求
"""

import sqlite3
import re
from datetime import datetime
from typing import Tuple
from contextlib import contextmanager
import threading


class SecurityManager:
    """API安全管理器"""
    
    def __init__(self, db_path: str = "api_stats.db"):
        self.db_path = db_path
        self._lock = threading.Lock()
        
        # 恶意请求特征检测
        self.malicious_patterns = [
            r'\.\./',  # 目录遍历
            r'\.\.\\',  # Windows目录遍历
            r'<script',  # XSS
            r'javascript:',  # XSS
            r'onerror=',  # XSS
            r'onclick=',  # XSS
            r'union\s+select',  # SQL注入
            r'drop\s+table',  # SQL注入
            r'delete\s+from',  # SQL注入
            r'insert\s+into',  # SQL注入
            r'update\s+',  # SQL注入
            r'exec\s*\(',  # 命令执行
            r'system\s*\(',  # 命令执行
            r'eval\s*\(',  # 代码执行
            r'__import__',  # Python导入
            r'os\.system',  # 系统命令
            r'subprocess',  # 子进程
            r'shell=true',  # Shell命令
            r'cmd\.exe',  # Windows命令
            r'/bin/bash',  # Linux命令
        ]
        
        # 可疑路径列表
        self.suspicious_paths = [
            # WordPress
            '/wp-admin', '/wp-content', '/wp-includes', '/wp-json',
            '/wp-config', '/wp-settings', '/wp-load',
            'xmlrpc.php', 'wp-cron.php',
            # 通用管理路径
            '/admin', '/administrator', '/phpmyadmin',
            # 配置文件
            '/.env', '/.git', '/.gitignore', 
            'config.php', 'web.config', 'web.xml', 'settings.py',
            # 备份和日志
            '/backup', '/backups', '/tmp', '/var/www',
            'debug.log', '.log', 'error.log', 'access.log',
            # 其他常见路径
            '/shell', '/console',
            '/api/admin', '/api/config', '/api/debug',
            # 数据库相关
            '/database', '/db', '/sql', '/mysql', '/phpmyadmin',
            # 源代码相关
            '/.svn', '/.hg', '/CVS', '/.bzr',
        ]
        
        self._init_database()
    
    @contextmanager
    def _get_connection(self):
        """获取数据库连接的上下文管理器"""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def _init_database(self):
        """初始化数据库表"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 创建恶意请求日志表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS malicious_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    client_ip TEXT NOT NULL,
                    method TEXT NOT NULL,
                    path TEXT NOT NULL,
                    query_string TEXT,
                    user_agent TEXT,
                    threat_type TEXT NOT NULL,
                    threat_details TEXT,
                    full_url TEXT,
                    request_body TEXT,
                    action_taken TEXT DEFAULT 'blocked'
                )
            ''')
            
            # 创建IP黑名单表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ip_blacklist (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ip_address TEXT UNIQUE NOT NULL,
                    reason TEXT,
                    threat_count INTEGER DEFAULT 1,
                    first_seen TEXT NOT NULL,
                    last_seen TEXT NOT NULL,
                    blocked BOOLEAN DEFAULT 1
                )
            ''')
            
            # 创建索引
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_malicious_ip 
                ON malicious_requests(client_ip)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_malicious_timestamp 
                ON malicious_requests(timestamp)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_blacklist_ip 
                ON ip_blacklist(ip_address)
            ''')
            
            conn.commit()
    
    def detect_malicious_request(self, path: str, query_string: str = "", 
                                request_body: str = "") -> Tuple[bool, str, str]:
        """
        检测恶意请求
        返回: (is_malicious, threat_type, threat_details)
        """
        path_lower = path.lower()
        
        # 检查可疑路径（精确匹配路径段）
        for suspicious_path in self.suspicious_paths:
            suspicious_lower = suspicious_path.lower()
            
            # 检查是否精确匹配路径段
            # 例如: /wp-admin 应该匹配 /wp-admin 或 /wp-admin/xxx
            # 但不应该匹配 /mywp-admin 或 /stats/requests (即使包含test)
            
            if suspicious_lower.startswith('/'):
                # 对于以/开头的路径，检查是否作为路径段出现
                # 1. 完全匹配整个路径
                if path_lower == suspicious_lower:
                    return True, "suspicious_path", f"检测到可疑路径: {suspicious_path}"
                # 2. 作为路径开始（后面跟/或结束）
                if path_lower.startswith(suspicious_lower + '/') or path_lower.startswith(suspicious_lower + '?'):
                    return True, "suspicious_path", f"检测到可疑路径: {suspicious_path}"
                # 3. 作为路径段出现（前面有/，后面有/或结束）
                if '/' + suspicious_lower.lstrip('/') + '/' in path_lower + '/':
                    return True, "suspicious_path", f"检测到可疑路径: {suspicious_path}"
            else:
                # 对于不以/开头的路径（如文件扩展名），直接检查包含
                if suspicious_lower in path_lower:
                    return True, "suspicious_path", f"检测到可疑路径: {suspicious_path}"
        
        # 检查恶意模式
        full_request = f"{path}?{query_string} {request_body}".lower()
        
        for pattern in self.malicious_patterns:
            if re.search(pattern, full_request, re.IGNORECASE):
                return True, "malicious_pattern", f"检测到恶意模式: {pattern}"
        
        return False, "", ""
    
    def log_malicious_request(self, client_ip: str, method: str, path: str, 
                             query_string: str, user_agent: str, threat_type: str, 
                             threat_details: str, full_url: str = "", 
                             request_body: str = "") -> bool:
        """记录恶意请求到数据库"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                timestamp = datetime.now().isoformat()
                
                # 记录恶意请求
                cursor.execute('''
                    INSERT INTO malicious_requests 
                    (timestamp, client_ip, method, path, query_string, user_agent, 
                     threat_type, threat_details, full_url, request_body)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (timestamp, client_ip, method, path, query_string, user_agent, 
                      threat_type, threat_details, full_url, request_body))
                
                # 更新或创建IP黑名单记录
                cursor.execute('SELECT threat_count FROM ip_blacklist WHERE ip_address = ?', 
                             (client_ip,))
                result = cursor.fetchone()
                
                if result:
                    threat_count = result[0] + 1
                    cursor.execute('''
                        UPDATE ip_blacklist 
                        SET threat_count = ?, last_seen = ?
                        WHERE ip_address = ?
                    ''', (threat_count, timestamp, client_ip))
                else:
                    cursor.execute('''
                        INSERT INTO ip_blacklist (ip_address, reason, first_seen, last_seen)
                        VALUES (?, ?, ?, ?)
                    ''', (client_ip, threat_type, timestamp, timestamp))
                
                conn.commit()
                return True
        except Exception as e:
            print(f"❌ 记录恶意请求失败: {e}")
            return False
    
    def is_ip_blacklisted(self, client_ip: str) -> bool:
        """检查IP是否在黑名单中"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'SELECT blocked FROM ip_blacklist WHERE ip_address = ? AND blocked = 1', 
                    (client_ip,)
                )
                result = cursor.fetchone()
                return result is not None
        except Exception as e:
            print(f"⚠️ 检查IP黑名单失败: {e}")
            return False
    
    def get_malicious_requests(self, limit: int = 100) -> list:
        """获取恶意请求日志"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM malicious_requests 
                    ORDER BY timestamp DESC 
                    LIMIT ?
                ''', (limit,))
                
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            print(f"❌ 获取恶意请求日志失败: {e}")
            return []
    
    def get_blacklist(self) -> list:
        """获取IP黑名单"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM ip_blacklist 
                    WHERE blocked = 1
                    ORDER BY threat_count DESC
                ''')
                
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            print(f"❌ 获取IP黑名单失败: {e}")
            return []
    
    def unblock_ip(self, ip_address: str) -> bool:
        """解除IP黑名单"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE ip_blacklist 
                    SET blocked = 0
                    WHERE ip_address = ?
                ''', (ip_address,))
                
                conn.commit()
                return True
        except Exception as e:
            print(f"❌ 解除IP黑名单失败: {e}")
            return False


# 全局实例
_security_manager = None


def get_security_manager() -> SecurityManager:
    """获取全局安全管理器实例"""
    global _security_manager
    if _security_manager is None:
        _security_manager = SecurityManager()
    return _security_manager
