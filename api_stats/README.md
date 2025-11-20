# API统计功能使用说明

## 功能概述

为 `api_server.py` 添加了完整的统计功能，包括：

- ✅ API请求总量统计
- ✅ 平均处理时间统计
- ✅ 每分钟请求数统计
- ✅ 运行时长统计
- ✅ 模型使用统计
- ✅ API Key使用统计
- ✅ IP地址请求统计（Top 50）
- ✅ 最近请求记录（含请求内容）
- ✅ 每小时请求趋势
- ✅ 错误记录追踪
- ✅ 成功率统计
- ✅ **图表可视化**（扇形图、折线图）
- ✅ **请求列表管理**（排序、筛选、翻页、导出）

## 图表可视化

仪表板现在包含4个交互式图表：

### 📊 请求状态分布（扇形图）
- 直观展示成功和失败请求的比例
- 环形图设计，绿色表示成功，红色表示失败
- 鼠标悬停显示具体数量和百分比

### 📈 24小时请求趋势（折线图）
- 显示过去24小时的请求量变化
- 蓝色线：总请求数
- 绿色线：成功请求数
- 可以快速识别流量高峰和异常时段

### 🤖 模型使用分布（扇形图）
- 展示不同模型的使用比例
- 多彩配色方案，易于区分
- 帮助了解哪些模型最受欢迎

### ⚡ 处理时间趋势（折线图）
- 显示平均处理时间的变化趋势
- 橙色曲线表示处理时间
- 帮助识别性能瓶颈和优化效果

## 架构设计

采用模块化设计，前后端分离，不影响原有 `api_server.py` 的代码结构：

```
api_server.py          # 主API服务（集成统计功能）
api_stats/             # 统计模块文件夹
├── __init__.py        # 模块初始化
├── stats_manager.py   # 统计管理模块（SQLite存储）
├── stats_webui.py     # 统计WebUI后端路由
├── templates/         # HTML 模板文件
│   ├── dashboard.html # 仪表板页面
│   └── requests.html  # 请求列表页面
├── static/            # 静态资源文件
│   ├── dashboard.css  # 仪表板样式
│   ├── dashboard.js   # 仪表板脚本
│   ├── requests.css   # 请求列表样式
│   └── requests.js    # 请求列表脚本
├── test_stats.py      # 测试脚本
└── README.md          # 本文档
api_stats.db           # SQLite数据库（自动创建在项目根目录）
```

### 前后端分离优势

- ✅ HTML/CSS/JS 独立文件，易于维护和修改
- ✅ 可以使用专业的前端开发工具
- ✅ 浏览器可以缓存静态文件，提升性能
- ✅ 修改样式和交互无需改动 Python 代码
- ✅ 支持热更新，修改后刷新浏览器即可生效

详见：[前端文件结构说明](FRONTEND_STRUCTURE.md)

## 快速开始

### 1. 启动API服务

```bash
python api_server.py -a 0.0.0.0 -p 9880
```

### 2. 访问统计仪表板

在浏览器中打开：

```
http://localhost:9880/stats          # 统计仪表板（带图表）
http://localhost:9880/stats/requests # 请求列表（Excel式管理）
```

### 3. 登录授权

首次访问需要输入授权码：
- **默认授权码**：`GPT-SoVits`
- 可在 `api_config.yaml` 中修改
- 详见：[授权验证指南](AUTH_GUIDE.md)

### 3. 查看效果

打开浏览器访问统计页面，你会看到：
- 📊 4个交互式图表（扇形图和折线图）
- 📋 完整的数据表格
- 🎨 现代化的界面设计
- 📱 响应式布局，支持移动设备

### 4. 自定义样式

如果你想修改页面样式：
1. 编辑 `api_stats/static/dashboard.css` 或 `requests.css`
2. 刷新浏览器（Ctrl+F5）即可看到效果

详见：[前端文件结构说明](FRONTEND_STRUCTURE.md)

### 5. 运行测试

```bash
python api_stats/test_stats.py
```

## 统计仪表板功能

### 核心指标卡片

- **总请求数**: 显示所有API请求的总数
- **成功率**: 显示请求成功的百分比
- **平均处理时间**: 显示成功请求的平均处理时间（秒）
- **每分钟请求数**: 显示最近1分钟的平均请求数
- **运行时长**: 显示API服务的运行时间

### 详细统计表格

1. **模型使用统计**
   - 各模型的请求次数
   - 成功次数和成功率
   - 平均处理时间

2. **API Key使用统计**
   - 各API Key的请求次数（脱敏显示）
   - 成功次数和成功率
   - 平均处理时间

3. **24小时请求趋势**
   - 按小时统计的请求数据
   - 成功率和平均处理时间

4. **IP地址请求统计**
   - Top 50 活跃IP地址
   - 各IP的请求次数、成功率
   - 平均处理时间和最后请求时间

5. **最近请求记录**
   - 最新20条请求详情
   - 包含IP、API Key、模型、文本长度、语言、格式等
   - 实时状态和错误信息
   - **点击"查看详情"按钮可查看完整请求内容** ⭐
     - **完整的文本内容**（不限长度）
     - 参考音频路径
     - 提示文本
     - 完整的请求参数
     - 字符数统计

6. **最近错误记录**
   - 最近10条错误记录
   - 包含时间、API Key、模型、错误信息等

### 自动刷新

- 页面每30秒自动刷新数据
- 可点击右下角"🔄 刷新数据"按钮手动刷新

## API接口

### 获取统计数据

```http
GET /stats/api
```

返回JSON格式的统计数据：

```json
{
  "total_requests": 1234,
  "success_rate": 98.5,
  "avg_processing_time": 2.345,
  "requests_per_minute": 5.2,
  "uptime": "2天 3小时 45分钟 12秒",
  "uptime_seconds": 186312,
  "model_stats": [...],
  "api_key_stats": [...],
  "hourly_stats": [...],
  "ip_stats": [...],
  "recent_requests": [...],
  "recent_errors": [...]
}
```

### 获取指定IP的详细统计

```http
GET /stats/ip/{client_ip}
```

返回指定IP的24小时请求趋势。

### 获取最近请求记录

```http
GET /stats/recent?limit=50
```

获取最近N条请求记录（默认50条）。

### 获取请求详情

```http
GET /stats/request/{request_id}
```

获取指定请求的完整详细信息，包括文本内容、参考音频等。

### 清理旧记录

```http
GET /stats/cleanup?days=30
```

清理30天前的统计记录（默认30天）。

## 数据库结构

### requests 表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| timestamp | REAL | 请求时间戳 |
| api_key | TEXT | API密钥 |
| model_name | TEXT | 模型名称 |
| text_length | INTEGER | 文本长度 |
| processing_time | REAL | 处理时间（秒） |
| success | INTEGER | 是否成功（1/0） |
| error_message | TEXT | 错误信息 |
| client_ip | TEXT | 客户端IP |
| text_lang | TEXT | 文本语言 |
| media_type | TEXT | 媒体类型 |
| text_preview | TEXT | 文本内容预览（前100字符，用于列表显示） |
| text_full | TEXT | 完整文本内容 |
| ref_audio_path | TEXT | 参考音频路径 |
| prompt_text | TEXT | 提示文本 |

### 索引

- `idx_timestamp`: 时间戳索引（提高时间范围查询性能）
- `idx_api_key`: API Key索引（提高用户统计查询性能）
- `idx_model_name`: 模型名称索引（提高模型统计查询性能）

## 性能优化

1. **线程安全**: 使用线程锁保证并发写入安全
2. **连接池**: 使用上下文管理器管理数据库连接
3. **索引优化**: 为常用查询字段创建索引
4. **批量查询**: 统计数据使用SQL聚合函数，减少Python层计算

## 数据维护

### 定期清理

建议定期清理旧数据以保持数据库性能：

```python
# 清理30天前的数据
from api_stats import get_stats_manager

stats_manager = get_stats_manager()
deleted_count = stats_manager.cleanup_old_records(days=30)
print(f"清理了 {deleted_count} 条记录")
```

或通过API接口：

```bash
curl "http://localhost:9880/stats/cleanup?days=30"
```

### 数据备份

SQLite数据库文件位于项目根目录 `api_stats.db`，可以直接复制备份：

```bash
# Windows
copy api_stats.db api_stats_backup_%date:~0,4%%date:~5,2%%date:~8,2%.db

# Linux/Mac
cp api_stats.db api_stats_backup_$(date +%Y%m%d).db
```

恢复数据库：

```bash
# Windows
copy api_stats_backup_20241120.db api_stats.db

# Linux/Mac
cp api_stats_backup_20241120.db api_stats.db
```

## 集成说明

统计功能已完全集成到 `api_server.py` 中，无需额外配置：

1. **自动记录**: 每次API请求自动记录统计信息
2. **零侵入**: 不影响原有业务逻辑
3. **异常安全**: 统计失败不影响API正常响应

在 `api_server.py` 中的集成代码：

```python
# 导入统计模块
from api_stats import get_stats_manager, register_stats_routes

# 注册统计WebUI路由
APP = FastAPI()
register_stats_routes(APP)

# 在请求处理中记录统计
stats_manager = get_stats_manager()
stats_manager.record_request(
    api_key=user_info['key'],
    model_name=model_name,
    text_length=len(req.get("text", "")),
    processing_time=processing_time,
    success=True,
    # ... 其他参数
)
```

## 扩展功能

### 自定义统计周期

可以修改 `stats_manager.py` 中的查询方法来自定义统计周期：

```python
from api_stats import get_stats_manager

stats_manager = get_stats_manager()

# 获取最近7天的统计
stats_manager.get_hourly_stats(hours=24*7)

# 获取最近5分钟的请求数
stats_manager.get_requests_per_minute(minutes=5)
```

### 导出统计报告

可以通过API接口获取数据后导出为Excel或CSV：

```python
import requests
import pandas as pd

# 获取统计数据
response = requests.get('http://localhost:9880/stats/api')
data = response.json()

# 导出模型统计
df = pd.DataFrame(data['model_stats'])
df.to_excel('model_stats.xlsx', index=False)

# 导出API Key统计
df = pd.DataFrame(data['api_key_stats'])
df.to_csv('apikey_stats.csv', index=False)
```

### 自定义数据库路径

默认数据库文件在项目根目录，可以自定义路径：

```python
from api_stats import get_stats_manager

# 使用自定义路径
stats_manager = get_stats_manager(db_path="/path/to/custom_stats.db")
```

## 故障排查

### 数据库锁定

如果遇到数据库锁定问题，检查是否有其他进程在访问数据库：

```bash
# Windows
dir api_stats.db*

# Linux/Mac
ls -lh api_stats.db*
```

如果看到 `.db-journal` 或 `.db-wal` 文件，说明有未完成的事务。

### 统计数据不更新

1. 检查 `api_stats` 模块是否正确导入
2. 检查数据库文件权限
3. 查看API服务日志是否有错误信息
4. 确认 `api_server.py` 中已正确集成统计代码

### 性能问题

如果统计查询较慢：

1. 定期清理旧数据（建议保留30-90天）
2. 检查索引是否正常创建：
   ```python
   import sqlite3
   conn = sqlite3.connect('api_stats.db')
   cursor = conn.cursor()
   cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
   print(cursor.fetchall())
   ```
3. 考虑使用更高性能的数据库（如PostgreSQL）

### WebUI无法访问

1. 确认API服务已启动
2. 检查端口是否被占用
3. 确认防火墙设置
4. 查看浏览器控制台是否有错误

## 技术栈

- **后端**: FastAPI + SQLite
- **前端**: 原生HTML + CSS + JavaScript
- **数据库**: SQLite3
- **并发**: Python threading

## 更新日志

### v1.0.0 (2024-11-20)

- ✅ 初始版本发布
- ✅ 基础统计功能
- ✅ WebUI仪表板
- ✅ SQLite数据存储
- ✅ 模块化设计

## 许可证

与主项目保持一致

## 贡献

欢迎提交Issue和Pull Request！
