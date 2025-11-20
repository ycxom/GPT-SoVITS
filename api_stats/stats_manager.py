"""
API统计管理模块
使用SQLite存储API请求统计数据
"""

import sqlite3
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from contextlib import contextmanager
import threading
import json


class StatsManager:
    """API统计管理器"""
    
    def __init__(self, db_path: str = "api_stats.db"):
        self.db_path = db_path
        self.start_time = time.time()
        self._lock = threading.Lock()
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
            
            # 请求记录表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    api_key TEXT,
                    model_name TEXT,
                    text_length INTEGER,
                    processing_time REAL,
                    tts_time REAL,
                    success INTEGER,
                    error_message TEXT,
                    client_ip TEXT,
                    text_lang TEXT,
                    media_type TEXT,
                    text_preview TEXT,
                    text_full TEXT,
                    ref_audio_path TEXT,
                    prompt_text TEXT
                )
            """)
            
            # 检查并添加新字段（用于数据库迁移）
            cursor.execute("PRAGMA table_info(requests)")
            columns = [column[1] for column in cursor.fetchall()]
            
            if 'text_preview' not in columns:
                cursor.execute("ALTER TABLE requests ADD COLUMN text_preview TEXT")
            if 'text_full' not in columns:
                cursor.execute("ALTER TABLE requests ADD COLUMN text_full TEXT")
            if 'tts_time' not in columns:
                cursor.execute("ALTER TABLE requests ADD COLUMN tts_time REAL")
            if 'ref_audio_path' not in columns:
                cursor.execute("ALTER TABLE requests ADD COLUMN ref_audio_path TEXT")
            if 'prompt_text' not in columns:
                cursor.execute("ALTER TABLE requests ADD COLUMN prompt_text TEXT")
            
            # 系统事件日志表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS system_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    event_type TEXT NOT NULL,
                    event_name TEXT NOT NULL,
                    details TEXT,
                    status TEXT,
                    duration REAL
                )
            """)
            
            # 创建索引以提高查询性能
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp 
                ON requests(timestamp)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_api_key 
                ON requests(api_key)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_model_name 
                ON requests(model_name)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_event_timestamp 
                ON system_events(timestamp)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_event_type 
                ON system_events(event_type)
            """)
            
            conn.commit()
    
    def record_request(
        self,
        api_key: str,
        model_name: str,
        text_length: int,
        processing_time: float,
        success: bool,
        error_message: Optional[str] = None,
        client_ip: Optional[str] = None,
        text_lang: Optional[str] = None,
        media_type: Optional[str] = None,
        text_preview: Optional[str] = None,
        text_full: Optional[str] = None,
        tts_time: Optional[float] = None,
        ref_audio_path: Optional[str] = None,
        prompt_text: Optional[str] = None
    ):
        """记录一次API请求"""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO requests 
                    (timestamp, api_key, model_name, text_length, processing_time, tts_time,
                     success, error_message, client_ip, text_lang, media_type,
                     text_preview, text_full, ref_audio_path, prompt_text)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    time.time(),
                    api_key,
                    model_name,
                    text_length,
                    processing_time,
                    tts_time,
                    1 if success else 0,
                    error_message,
                    client_ip,
                    text_lang,
                    media_type,
                    text_preview,
                    text_full,
                    ref_audio_path,
                    prompt_text
                ))
                conn.commit()
    
    def get_total_requests(self) -> int:
        """获取总请求数"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as count FROM requests")
            return cursor.fetchone()["count"]
    
    def get_success_rate(self) -> float:
        """获取成功率"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(success) as success_count
                FROM requests
            """)
            row = cursor.fetchone()
            total = row["total"]
            if total == 0:
                return 0.0
            return (row["success_count"] / total) * 100
    
    def get_average_processing_time(self) -> float:
        """获取平均处理时间（秒）"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT AVG(processing_time) as avg_time 
                FROM requests 
                WHERE success = 1
            """)
            result = cursor.fetchone()["avg_time"]
            return result if result else 0.0
    
    def get_requests_per_minute(self, minutes: int = 1) -> float:
        """获取最近N分钟的请求数"""
        cutoff_time = time.time() - (minutes * 60)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) as count 
                FROM requests 
                WHERE timestamp > ?
            """, (cutoff_time,))
            count = cursor.fetchone()["count"]
            return count / minutes
    
    def get_uptime(self) -> float:
        """获取运行时长（秒）"""
        return time.time() - self.start_time
    
    def get_uptime_formatted(self) -> str:
        """获取格式化的运行时长"""
        uptime = self.get_uptime()
        days = int(uptime // 86400)
        hours = int((uptime % 86400) // 3600)
        minutes = int((uptime % 3600) // 60)
        seconds = int(uptime % 60)
        
        parts = []
        if days > 0:
            parts.append(f"{days}天")
        if hours > 0:
            parts.append(f"{hours}小时")
        if minutes > 0:
            parts.append(f"{minutes}分钟")
        parts.append(f"{seconds}秒")
        
        return " ".join(parts)
    
    def get_model_stats(self) -> List[Dict]:
        """获取各模型的统计信息"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    model_name,
                    COUNT(*) as total_requests,
                    SUM(success) as success_count,
                    AVG(CASE WHEN success = 1 THEN processing_time END) as avg_time
                FROM requests
                GROUP BY model_name
                ORDER BY total_requests DESC
            """)
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    "model_name": row["model_name"],
                    "total_requests": row["total_requests"],
                    "success_count": row["success_count"],
                    "success_rate": (row["success_count"] / row["total_requests"] * 100) if row["total_requests"] > 0 else 0,
                    "avg_processing_time": row["avg_time"] if row["avg_time"] else 0
                })
            
            return results
    
    def get_api_key_stats(self) -> List[Dict]:
        """获取各API Key的统计信息"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    api_key,
                    COUNT(*) as total_requests,
                    SUM(success) as success_count,
                    AVG(CASE WHEN success = 1 THEN processing_time END) as avg_time
                FROM requests
                GROUP BY api_key
                ORDER BY total_requests DESC
            """)
            
            results = []
            for row in cursor.fetchall():
                api_key = row["api_key"] or "anonymous"
                # 脱敏处理
                if api_key != "anonymous" and len(api_key) > 8:
                    api_key_display = api_key[:8] + "..."
                else:
                    api_key_display = api_key
                
                results.append({
                    "api_key": api_key_display,
                    "total_requests": row["total_requests"],
                    "success_count": row["success_count"],
                    "success_rate": (row["success_count"] / row["total_requests"] * 100) if row["total_requests"] > 0 else 0,
                    "avg_processing_time": row["avg_time"] if row["avg_time"] else 0
                })
            
            return results
    
    def get_hourly_stats(self, hours: int = 24) -> List[Dict]:
        """获取最近N小时的每小时统计"""
        cutoff_time = time.time() - (hours * 3600)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    strftime('%Y-%m-%d %H:00:00', datetime(timestamp, 'unixepoch', 'localtime')) as hour,
                    COUNT(*) as total_requests,
                    SUM(success) as success_count,
                    AVG(CASE WHEN success = 1 THEN processing_time END) as avg_time
                FROM requests
                WHERE timestamp > ?
                GROUP BY hour
                ORDER BY hour DESC
            """, (cutoff_time,))
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    "hour": row["hour"],
                    "total_requests": row["total_requests"],
                    "success_count": row["success_count"],
                    "success_rate": (row["success_count"] / row["total_requests"] * 100) if row["total_requests"] > 0 else 0,
                    "avg_processing_time": row["avg_time"] if row["avg_time"] else 0
                })
            
            return results
    
    def get_recent_errors(self, limit: int = 10) -> List[Dict]:
        """获取最近的错误记录"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    timestamp,
                    api_key,
                    model_name,
                    error_message,
                    client_ip
                FROM requests
                WHERE success = 0
                ORDER BY timestamp DESC
                LIMIT ?
            """, (limit,))
            
            results = []
            for row in cursor.fetchall():
                api_key = row["api_key"] or "anonymous"
                if api_key != "anonymous" and len(api_key) > 8:
                    api_key_display = api_key[:8] + "..."
                else:
                    api_key_display = api_key
                
                results.append({
                    "timestamp": datetime.fromtimestamp(row["timestamp"]).strftime("%Y-%m-%d %H:%M:%S"),
                    "api_key": api_key_display,
                    "model_name": row["model_name"],
                    "error_message": row["error_message"],
                    "client_ip": row["client_ip"]
                })
            
            return results
    
    def get_ip_stats(self) -> List[Dict]:
        """获取IP统计信息"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    client_ip,
                    COUNT(*) as total_requests,
                    SUM(success) as success_count,
                    AVG(CASE WHEN success = 1 THEN processing_time END) as avg_time,
                    MAX(timestamp) as last_request_time
                FROM requests
                WHERE client_ip IS NOT NULL AND client_ip != ''
                GROUP BY client_ip
                ORDER BY total_requests DESC
                LIMIT 50
            """)
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    "client_ip": row["client_ip"],
                    "total_requests": row["total_requests"],
                    "success_count": row["success_count"],
                    "success_rate": (row["success_count"] / row["total_requests"] * 100) if row["total_requests"] > 0 else 0,
                    "avg_processing_time": row["avg_time"] if row["avg_time"] else 0,
                    "last_request_time": datetime.fromtimestamp(row["last_request_time"]).strftime("%Y-%m-%d %H:%M:%S")
                })
            
            return results
    
    def get_recent_requests(self, limit: int = 20) -> List[Dict]:
        """获取最近的请求记录（包含请求内容）"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    id,
                    timestamp,
                    api_key,
                    model_name,
                    text_length,
                    processing_time,
                    success,
                    error_message,
                    client_ip,
                    text_lang,
                    media_type,
                    text_preview,
                    ref_audio_path,
                    prompt_text
                FROM requests
                ORDER BY timestamp DESC
                LIMIT ?
            """, (limit,))
            
            results = []
            for row in cursor.fetchall():
                api_key = row["api_key"] or "anonymous"
                if api_key != "anonymous" and len(api_key) > 8:
                    api_key_display = api_key[:8] + "..."
                else:
                    api_key_display = api_key
                
                results.append({
                    "id": row["id"],
                    "timestamp": datetime.fromtimestamp(row["timestamp"]).strftime("%Y-%m-%d %H:%M:%S"),
                    "api_key": api_key_display,
                    "model_name": row["model_name"],
                    "text_length": row["text_length"],
                    "processing_time": round(row["processing_time"], 3) if row["processing_time"] else 0,
                    "success": bool(row["success"]),
                    "error_message": row["error_message"],
                    "client_ip": row["client_ip"],
                    "text_lang": row["text_lang"],
                    "media_type": row["media_type"],
                    "text_preview": row["text_preview"],
                    "ref_audio_path": row["ref_audio_path"],
                    "prompt_text": row["prompt_text"]
                })
            
            return results
    
    def get_request_detail(self, request_id: int) -> Optional[Dict]:
        """获取指定请求的详细信息"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    id,
                    timestamp,
                    api_key,
                    model_name,
                    text_length,
                    processing_time,
                    tts_time,
                    success,
                    error_message,
                    client_ip,
                    text_lang,
                    media_type,
                    text_preview,
                    text_full,
                    ref_audio_path,
                    prompt_text
                FROM requests
                WHERE id = ?
            """, (request_id,))
            
            row = cursor.fetchone()
            if not row:
                return None
            
            api_key = row["api_key"] or "anonymous"
            if api_key != "anonymous" and len(api_key) > 8:
                api_key_display = api_key[:8] + "..."
            else:
                api_key_display = api_key
            
            return {
                "id": row["id"],
                "timestamp": datetime.fromtimestamp(row["timestamp"]).strftime("%Y-%m-%d %H:%M:%S"),
                "api_key": api_key_display,
                "model_name": row["model_name"],
                "text_length": row["text_length"],
                "processing_time": round(row["processing_time"], 3) if row["processing_time"] else 0,
                "tts_time": round(row["tts_time"], 3) if row["tts_time"] else None,
                "success": bool(row["success"]),
                "error_message": row["error_message"],
                "client_ip": row["client_ip"],
                "text_lang": row["text_lang"],
                "media_type": row["media_type"],
                "text_preview": row["text_preview"],
                "text_full": row["text_full"],
                "ref_audio_path": row["ref_audio_path"],
                "prompt_text": row["prompt_text"]
            }
    
    def get_ip_request_trend(self, client_ip: str, hours: int = 24) -> List[Dict]:
        """获取指定IP的请求趋势"""
        cutoff_time = time.time() - (hours * 3600)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    strftime('%Y-%m-%d %H:00:00', datetime(timestamp, 'unixepoch', 'localtime')) as hour,
                    COUNT(*) as total_requests,
                    SUM(success) as success_count
                FROM requests
                WHERE client_ip = ? AND timestamp > ?
                GROUP BY hour
                ORDER BY hour DESC
            """, (client_ip, cutoff_time))
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    "hour": row["hour"],
                    "total_requests": row["total_requests"],
                    "success_count": row["success_count"],
                    "success_rate": (row["success_count"] / row["total_requests"] * 100) if row["total_requests"] > 0 else 0
                })
            
            return results
    
    def get_dashboard_stats(self) -> Dict:
        """获取仪表板统计数据"""
        return {
            "total_requests": self.get_total_requests(),
            "success_rate": round(self.get_success_rate(), 2),
            "avg_processing_time": round(self.get_average_processing_time(), 3),
            "requests_per_minute": round(self.get_requests_per_minute(1), 2),
            "uptime": self.get_uptime_formatted(),
            "uptime_seconds": int(self.get_uptime()),
            "model_stats": self.get_model_stats(),
            "api_key_stats": self.get_api_key_stats(),
            "hourly_stats": self.get_hourly_stats(24),
            "recent_errors": self.get_recent_errors(10),
            "ip_stats": self.get_ip_stats(),
            "recent_requests": self.get_recent_requests(20),
            "system_events": self.get_system_events(30)
        }
    
    def log_system_event(
        self,
        event_type: str,
        event_name: str,
        details: Optional[str] = None,
        status: str = "success",
        duration: Optional[float] = None
    ):
        """记录系统事件
        
        Args:
            event_type: 事件类型 (model_load, model_switch, server_start, server_stop, error等)
            event_name: 事件名称 (如: GPT模型加载, SoVITS模型加载等)
            details: 详细信息
            status: 状态 (success, failed, warning)
            duration: 持续时间（秒）
        """
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO system_events 
                    (timestamp, event_type, event_name, details, status, duration)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    time.time(),
                    event_type,
                    event_name,
                    details,
                    status,
                    duration
                ))
                conn.commit()
    
    def get_system_events(self, limit: int = 50, event_type: Optional[str] = None) -> List[Dict]:
        """获取系统事件日志"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            if event_type:
                cursor.execute("""
                    SELECT 
                        id,
                        timestamp,
                        event_type,
                        event_name,
                        details,
                        status,
                        duration
                    FROM system_events
                    WHERE event_type = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (event_type, limit))
            else:
                cursor.execute("""
                    SELECT 
                        id,
                        timestamp,
                        event_type,
                        event_name,
                        details,
                        status,
                        duration
                    FROM system_events
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (limit,))
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    "id": row["id"],
                    "timestamp": datetime.fromtimestamp(row["timestamp"]).strftime("%Y-%m-%d %H:%M:%S"),
                    "event_type": row["event_type"],
                    "event_name": row["event_name"],
                    "details": row["details"],
                    "status": row["status"],
                    "duration": round(row["duration"], 3) if row["duration"] else None
                })
            
            return results
    
    def get_model_load_history(self, limit: int = 20) -> List[Dict]:
        """获取模型加载历史"""
        return self.get_system_events(limit=limit, event_type="model_load")
    
    def cleanup_old_records(self, days: int = 30):
        """清理旧记录"""
        cutoff_time = time.time() - (days * 86400)
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # 清理请求记录
                cursor.execute("""
                    DELETE FROM requests 
                    WHERE timestamp < ?
                """, (cutoff_time,))
                deleted_requests = cursor.rowcount
                
                # 清理系统事件
                cursor.execute("""
                    DELETE FROM system_events 
                    WHERE timestamp < ?
                """, (cutoff_time,))
                deleted_events = cursor.rowcount
                
                conn.commit()
                return {
                    "requests": deleted_requests,
                    "events": deleted_events,
                    "total": deleted_requests + deleted_events
                }


# 全局统计管理器实例
_stats_manager = None


def get_stats_manager(db_path: str = "api_stats.db") -> StatsManager:
    """获取全局统计管理器实例"""
    global _stats_manager
    if _stats_manager is None:
        _stats_manager = StatsManager(db_path)
    return _stats_manager
