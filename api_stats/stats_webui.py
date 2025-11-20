"""
API统计WebUI模块
提供统计数据的Web界面展示
"""

from fastapi import FastAPI, Request, Cookie, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from .stats_manager import get_stats_manager
import os
import yaml
import hashlib


def load_config():
    """加载配置文件"""
    try:
        with open("api_config.yaml", "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except:
        return {}


def check_auth(auth_token: str = None) -> bool:
    """检查授权"""
    config = load_config()
    
    # 检查是否启用授权
    require_auth = config.get("statistics", {}).get("require_dashboard_auth", True)
    if not require_auth:
        return True
    
    # 获取配置的授权码
    auth_code = config.get("statistics", {}).get("dashboard_auth_code", "GPT-SoVits")
    
    # 生成授权码的 hash
    expected_token = hashlib.sha256(auth_code.encode()).hexdigest()
    
    return auth_token == expected_token


def register_stats_routes(app: FastAPI):
    """注册统计相关的路由"""
    
    # 获取当前模块所在目录
    current_dir = os.path.dirname(os.path.abspath(__file__))
    static_dir = os.path.join(current_dir, "static")
    templates_dir = os.path.join(current_dir, "templates")
    
    # 挂载静态文件目录
    if os.path.exists(static_dir):
        app.mount("/stats/static", StaticFiles(directory=static_dir), name="stats_static")
    
    # ==================== 页面路由 ====================
    
    @app.get("/", response_class=HTMLResponse)
    async def home_page():
        """主页"""
        index_html = os.path.join(templates_dir, "index.html")
        if os.path.exists(index_html):
            with open(index_html, 'r', encoding='utf-8') as f:
                return HTMLResponse(content=f.read())
        
        return HTMLResponse(content="""
            <html>
                <body>
                    <h1>GPT-SoVITS API</h1>
                    <p>主页模板文件不存在</p>
                    <a href="/stats">统计面板</a>
                </body>
            </html>
        """)
    
    @app.get("/stats/login", response_class=HTMLResponse)
    async def stats_login_page(request: Request):
        """统计面板登录页面"""
        # 检查是否有错误参数
        error = request.query_params.get("error")
        
        login_html = os.path.join(templates_dir, "login.html")
        if os.path.exists(login_html):
            with open(login_html, 'r', encoding='utf-8') as f:
                content = f.read()
                # 如果有错误，添加错误标记
                if error:
                    content = content.replace('<!-- ERROR_PLACEHOLDER -->', 
                        '<div class="error-message">❌ 授权码错误，请重试</div>')
                return HTMLResponse(content=content)
        
        # 如果模板不存在，返回简单的登录页面
        error_html = '<p style="color: red;">授权码错误</p>' if error else ''
        return HTMLResponse(content=f"""
            <html>
                <body>
                    <h1>统计面板登录</h1>
                    {error_html}
                    <form method="post" action="/stats/auth">
                        <input type="password" name="auth_code" placeholder="请输入授权码" required>
                        <button type="submit">登录</button>
                    </form>
                </body>
            </html>
        """)
    
    @app.post("/stats/auth")
    async def stats_auth(request: Request, response: Response):
        """处理授权验证"""
        form_data = await request.form()
        auth_code = form_data.get("auth_code", "")
        
        # 生成 token
        token = hashlib.sha256(auth_code.encode()).hexdigest()
        
        # 验证授权码
        if check_auth(token):
            # 设置 cookie（有效期7天）
            resp = RedirectResponse(url="/stats", status_code=302)
            resp.set_cookie(
                key="stats_auth",
                value=token,
                max_age=7 * 24 * 60 * 60,
                httponly=True
            )
            return resp
        else:
            # 返回登录页面并显示错误
            return RedirectResponse(url="/stats/login?error=1", status_code=302)
    
    @app.get("/stats", response_class=HTMLResponse)
    async def stats_dashboard(request: Request, stats_auth: str = Cookie(None)):
        """统计仪表板页面"""
        # 检查授权
        if not check_auth(stats_auth):
            return RedirectResponse(url="/stats/login")
        
        dashboard_html = os.path.join(templates_dir, "dashboard.html")
        if os.path.exists(dashboard_html):
            with open(dashboard_html, 'r', encoding='utf-8') as f:
                return HTMLResponse(content=f.read())
        
        return HTMLResponse(content="""
            <html>
                <body>
                    <h1>错误</h1>
                    <p>模板文件不存在: dashboard.html</p>
                    <p>请确保 api_stats/templates/dashboard.html 文件存在</p>
                </body>
            </html>
        """, status_code=500)
    
    @app.get("/stats/requests", response_class=HTMLResponse)
    async def requests_list_page(request: Request, stats_auth: str = Cookie(None)):
        """请求列表页面"""
        # 检查授权
        if not check_auth(stats_auth):
            return RedirectResponse(url="/stats/login")
        
        requests_html = os.path.join(templates_dir, "requests.html")
        if os.path.exists(requests_html):
            with open(requests_html, 'r', encoding='utf-8') as f:
                return HTMLResponse(content=f.read())
        
        return HTMLResponse(content="""
            <html>
                <body>
                    <h1>错误</h1>
                    <p>模板文件不存在: requests.html</p>
                    <p>请确保 api_stats/templates/requests.html 文件存在</p>
                </body>
            </html>
        """, status_code=500)
    
    @app.get("/stats/security", response_class=HTMLResponse)
    async def security_page(request: Request, stats_auth: str = Cookie(None)):
        """安全日志页面"""
        # 检查授权
        if not check_auth(stats_auth):
            return RedirectResponse(url="/stats/login")
        
        security_html = os.path.join(templates_dir, "security.html")
        if os.path.exists(security_html):
            with open(security_html, 'r', encoding='utf-8') as f:
                return HTMLResponse(content=f.read())
        
        return HTMLResponse(content="""
            <html>
                <body>
                    <h1>错误</h1>
                    <p>模板文件不存在: security.html</p>
                    <p>请确保 api_stats/templates/security.html 文件存在</p>
                </body>
            </html>
        """, status_code=500)
    
    # ==================== API 路由 ====================
    
    @app.get("/stats/api")
    async def stats_api(stats_auth: str = Cookie(None)):
        """获取统计数据的API接口"""
        # 检查授权
        if not check_auth(stats_auth):
            return JSONResponse(
                status_code=401,
                content={"error": "Unauthorized"}
            )
        
        try:
            stats_manager = get_stats_manager()
            stats = stats_manager.get_dashboard_stats()
            return JSONResponse(content=stats)
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={"error": str(e)}
            )
    
    @app.get("/stats/recent")
    async def get_recent_requests(limit: int = 50, stats_auth: str = Cookie(None)):
        """获取最近的请求记录"""
        # 检查授权
        if not check_auth(stats_auth):
            return JSONResponse(
                status_code=401,
                content={"error": "Unauthorized"}
            )
        
        try:
            stats_manager = get_stats_manager()
            requests = stats_manager.get_recent_requests(limit)
            return JSONResponse(content={
                "requests": requests,
                "count": len(requests)
            })
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={"error": str(e)}
            )
    
    @app.get("/stats/request/{request_id}")
    async def get_request_detail(request_id: int, stats_auth: str = Cookie(None)):
        """获取指定请求的详细信息"""
        # 检查授权
        if not check_auth(stats_auth):
            return JSONResponse(
                status_code=401,
                content={"error": "Unauthorized"}
            )
        
        try:
            stats_manager = get_stats_manager()
            detail = stats_manager.get_request_detail(request_id)
            if detail is None:
                return JSONResponse(
                    status_code=404,
                    content={"error": "Request not found"}
                )
            return JSONResponse(content=detail)
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={"error": str(e)}
            )
    
    @app.get("/stats/ip/{client_ip}")
    async def get_ip_details(client_ip: str):
        """获取指定IP的详细统计"""
        try:
            stats_manager = get_stats_manager()
            trend = stats_manager.get_ip_request_trend(client_ip, hours=24)
            return JSONResponse(content={
                "client_ip": client_ip,
                "trend": trend
            })
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={"error": str(e)}
            )
    
    @app.get("/stats/events")
    async def get_system_events(limit: int = 50, event_type: str = None):
        """获取系统事件日志"""
        try:
            stats_manager = get_stats_manager()
            events = stats_manager.get_system_events(limit=limit, event_type=event_type)
            return JSONResponse(content={
                "events": events,
                "count": len(events)
            })
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={"error": str(e)}
            )
    
    @app.post("/stats/event")
    async def log_system_event(
        event_type: str,
        event_name: str,
        details: str = None,
        status: str = "success",
        duration: float = None
    ):
        """记录系统事件"""
        try:
            stats_manager = get_stats_manager()
            stats_manager.log_system_event(
                event_type=event_type,
                event_name=event_name,
                details=details,
                status=status,
                duration=duration
            )
            return JSONResponse(content={"message": "Event logged successfully"})
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={"error": str(e)}
            )
    
    @app.get("/stats/cleanup")
    async def cleanup_old_records(days: int = 30):
        """清理旧记录"""
        try:
            stats_manager = get_stats_manager()
            deleted = stats_manager.cleanup_old_records(days)
            return JSONResponse(content={
                "message": f"成功清理 {deleted} 条记录",
                "deleted_count": deleted
            })
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={"error": str(e)}
            )
    
    # ==================== 安全相关API ====================
    
    @app.get("/security/malicious_requests")
    async def get_malicious_requests_api(limit: int = 100, stats_auth: str = Cookie(None)):
        """获取恶意请求日志（使用cookie认证）"""
        # 检查授权
        if not check_auth(stats_auth):
            return JSONResponse(
                status_code=401,
                content={"error": "Unauthorized"}
            )
        
        try:
            stats_manager = get_stats_manager()
            records = stats_manager.get_malicious_requests(limit)
            return JSONResponse(content={
                "total": len(records),
                "records": records
            })
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={"error": str(e)}
            )
    
    @app.get("/security/blacklist")
    async def get_blacklist_api(stats_auth: str = Cookie(None)):
        """获取IP黑名单（使用cookie认证）"""
        # 检查授权
        if not check_auth(stats_auth):
            return JSONResponse(
                status_code=401,
                content={"error": "Unauthorized"}
            )
        
        try:
            stats_manager = get_stats_manager()
            records = stats_manager.get_blacklist()
            return JSONResponse(content={
                "total": len(records),
                "records": records
            })
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={"error": str(e)}
            )
    
    @app.post("/security/unblock_ip")
    async def unblock_ip_api(ip_address: str = "", stats_auth: str = Cookie(None)):
        """解除IP黑名单（使用cookie认证）"""
        # 检查授权
        if not check_auth(stats_auth):
            return JSONResponse(
                status_code=401,
                content={"error": "Unauthorized"}
            )
        
        if not ip_address:
            return JSONResponse(
                status_code=400,
                content={"message": "ip_address is required"}
            )
        
        try:
            stats_manager = get_stats_manager()
            if stats_manager.unblock_ip(ip_address):
                return JSONResponse(content={
                    "message": f"IP {ip_address} has been unblocked"
                })
            else:
                return JSONResponse(
                    status_code=500,
                    content={"message": "Failed to unblock IP"}
                )
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={"error": str(e)}
            )
    
    @app.get("/security/stats")
    async def get_security_stats_api(stats_auth: str = Cookie(None)):
        """获取安全统计信息（使用cookie认证）"""
        # 检查授权
        if not check_auth(stats_auth):
            return JSONResponse(
                status_code=401,
                content={"error": "Unauthorized"}
            )
        
        try:
            stats_manager = get_stats_manager()
            stats = stats_manager.get_security_stats()
            return JSONResponse(content=stats)
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={"error": str(e)}
            )
