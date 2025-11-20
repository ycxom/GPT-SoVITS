"""
安全防护WebUI模块
提供安全日志和黑名单管理的Web界面
使用api_stats.db存储数据
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse
from .stats_manager import get_stats_manager
import yaml


def load_config():
    """加载配置文件"""
    try:
        with open("api_config.yaml", "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except:
        return {}


def authenticate_admin(api_key: str) -> bool:
    """验证管理员权限"""
    config = load_config()
    admin_keys = list(config.get('api_keys', {}).keys())
    return admin_keys and api_key == admin_keys[0]


def register_security_routes(app: FastAPI):
    """注册安全相关的路由"""
    
    # ==================== 安全管理API ====================
    
    @app.get("/security/malicious_requests")
    async def get_malicious_requests(api_key: str = "", limit: int = 100):
        """获取恶意请求日志（需要管理员API Key）"""
        if not authenticate_admin(api_key):
            return JSONResponse(status_code=403, content={"message": "Unauthorized"})
        
        stats_manager = get_stats_manager()
        records = stats_manager.get_malicious_requests(limit)
        
        return JSONResponse(status_code=200, content={
            "total": len(records),
            "records": records
        })
    
    @app.get("/security/blacklist")
    async def get_blacklist(api_key: str = ""):
        """获取IP黑名单（需要管理员API Key）"""
        if not authenticate_admin(api_key):
            return JSONResponse(status_code=403, content={"message": "Unauthorized"})
        
        stats_manager = get_stats_manager()
        records = stats_manager.get_blacklist()
        
        return JSONResponse(status_code=200, content={
            "total": len(records),
            "records": records
        })
    
    @app.post("/security/unblock_ip")
    async def unblock_ip(api_key: str = "", ip_address: str = ""):
        """解除IP黑名单（需要管理员API Key）"""
        if not authenticate_admin(api_key):
            return JSONResponse(status_code=403, content={"message": "Unauthorized"})
        
        if not ip_address:
            return JSONResponse(status_code=400, content={"message": "ip_address is required"})
        
        stats_manager = get_stats_manager()
        if stats_manager.unblock_ip(ip_address):
            return JSONResponse(status_code=200, content={"message": f"IP {ip_address} has been unblocked"})
        else:
            return JSONResponse(status_code=500, content={"message": "Failed to unblock IP"})
    
    @app.get("/security/stats")
    async def get_security_stats(api_key: str = ""):
        """获取安全统计信息（需要管理员API Key）"""
        if not authenticate_admin(api_key):
            return JSONResponse(status_code=403, content={"message": "Unauthorized"})
        
        stats_manager = get_stats_manager()
        stats = stats_manager.get_security_stats()
        
        return JSONResponse(status_code=200, content=stats)
    
    @app.get("/security/dashboard", response_class=HTMLResponse)
    async def security_dashboard(api_key: str = ""):
        """安全防护仪表板"""
        if not authenticate_admin(api_key):
            return HTMLResponse(content="""
                <html>
                    <body>
                        <h1>未授权</h1>
                        <p>需要管理员权限</p>
                    </body>
                </html>
            """, status_code=403)
        
        stats_manager = get_stats_manager()
        stats = stats_manager.get_security_stats()
        malicious_count = stats.get('total_malicious_requests', 0)
        blacklist_count = stats.get('blacklist_count', 0)
        
        return HTMLResponse(content=f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <title>安全防护仪表板</title>
                <link rel="stylesheet" href="/stats/static/security.css">
            </head>
            <body>
                <div class="security-container">
                    <div class="security-header">
                        <h1>🔒 安全防护仪表板</h1>
                        <p>实时监控恶意请求和IP黑名单</p>
                    </div>
                    
                    <div class="stats-grid">
                        <div class="stat-card danger">
                            <h3>恶意请求</h3>
                            <div class="number">{malicious_count}</div>
                        </div>
                        <div class="stat-card warning">
                            <h3>黑名单IP</h3>
                            <div class="number">{blacklist_count}</div>
                        </div>
                    </div>
                    
                    <div class="section">
                        <h2>最近的恶意请求</h2>
                        <div id="malicious-list">加载中...</div>
                    </div>
                    
                    <div class="section">
                        <h2>IP黑名单</h2>
                        <div id="blacklist">加载中...</div>
                    </div>
                </div>
                
                <script src="/stats/static/security.js"></script>
                <script>
                    const apiKey = '{api_key}';
                </script>
            </body>
            </html>
        """)
