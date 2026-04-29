# LocalCommandCenter 本地网关

> 🧠 本地指挥中心网关 — 接收 GLM 智能体的 Tool Call 请求并操作本地系统

## 功能概览

| 模块 | 说明 |
|------|------|
| 📋 **任务管理** | 添加/删除/完成/查询周计划，支持优先级/标签/子任务/周期提醒 |
| 🍅 **番茄钟** | 25分钟工作节奏，统计与历史记录 |
| 📥 **安全下载** | URL 安全校验 + 大文件异步下载 + 自动分类归档（paper/video/code/misc）|
| 🔍 **文件检索** | 模糊搜索 + 全文索引本地已归档文件 |
| 🔧 **沙盒执行** | Docker 容器隔离执行 Python/Node/FFmpeg/Pandoc，支持动态写入脚本 |
| 🤖 **AI 对话** | 自然语言操控全部功能（OpenAI/GLM 兼容） |
| 📓 **笔记** | Markdown 笔记，支持标签和关联任务 |
| ✅ **习惯追踪** | 每日/每周/每月习惯打卡，连续天数统计 |
| 📅 **日历** | 月度视图 + Google/Outlook 日历同步 |
| 🔄 **数据同步** | 多设备增量同步 + 离线队列 + 冲突解决 |
| 🔐 **端到端加密** | PBKDF2+Fernet 加密同步数据 |
| 📱 **PWA** | 可安装到桌面/手机，支持离线访问 |
| ⏳ **异步任务** | 大文件下载和长时间沙盒任务的异步状态查询 |
| 🖥️ **图形界面** | 内置 Web UI，暗色主题，响应式设计 |

> 详细使用说明: [USER_GUIDE.md](local-gateway/docs/USER_GUIDE.md)

## 快速启动

```bash
# 1. 激活环境
conda activate claude

# 2. 安装依赖（首次）
cd local-gateway
pip install -r requirements.txt

# 3. 确保 Docker 已启动（沙盒功能依赖）
docker info

# 4. 启动网关
python main.py
# 服务运行在 http://localhost:8900
# 浏览器打开 http://localhost:8900 进入图形界面

# 5. 内网穿透（让 GLM 云端可以访问你的本地服务）
ngrok http 8900
```

## 项目结构

```
local-gateway/
├── main.py                  # FastAPI 应用入口
├── config.py                # 全局配置
├── requirements.txt         # Python 依赖
├── models/
│   └── schemas.py           # Pydantic 请求/响应模型
├── routers/                 # HTTP 端点（20个模块）
│   ├── task_manager.py      # 任务管理（核心5工具之一）
│   ├── safe_downloader.py   # 安全下载（核心5工具之一）
│   ├── file_search.py       # 文件检索（核心5工具之一）
│   ├── sandbox_executor.py  # 沙盒执行（核心5工具之一）
│   ├── job_status.py        # 异步任务（核心5工具之一）
│   ├── chat.py              # AI 对话 + Function Calling
│   ├── dashboard.py         # 仪表盘统计
│   ├── encryption.py        # 端到端加密 API
│   ├── sync.py              # 数据同步 + 设备管理
│   ├── mobile.py            # 移动端优化 API
│   ├── notes.py             # 笔记管理
│   ├── habits.py            # 习惯追踪
│   ├── calendar_sync.py     # 日历同步
│   ├── shortcuts.py         # 快捷键管理
│   ├── ai_planning.py       # AI 智能规划
│   ├── voice.py             # 语音输入
│   ├── fulltext_search.py   # 全文搜索
│   ├── webhooks.py          # Webhook 管理
│   └── workflows.py         # 自动化工作流
├── services/                # 业务逻辑
│   ├── task_service.py      # SQLite CRUD + 标签/子任务/番茄钟/日历/笔记/习惯
│   ├── download_service.py  # 异步下载 + 安全扫描 + 带宽控制
│   ├── search_service.py    # 本地文件模糊检索
│   ├── sandbox_service.py   # Docker SDK 沙盒调度
│   ├── ai_service.py        # OpenAI/GLM API + Function Calling
│   ├── sync_service.py      # 同步协议 + 变更追踪 + 冲突解决
│   ├── e2e_encryption.py    # PBKDF2+Fentanyl 端到端加密
│   └── ...                  # 其他服务模块
├── static/                  # Web 前端 + PWA
│   ├── index.html           # 主页面
│   ├── style.css            # 暗色主题样式
│   ├── app.js               # 前端交互逻辑
│   ├── manifest.json        # PWA 配置
│   ├── sw.js                # Service Worker
│   └── icons/               # PWA 图标（8种尺寸）
├── data/                    # 运行时数据（自动创建）
├── test/                    # 测试（60+用例）
└── downloads/               # 下载归档目录（自动创建）
```

## API 端点

| GLM Tool Name | HTTP 端点 | 方法 | 描述 |
|---------------|-----------|------|------|
| `local_task_manager` | `/api/task` | POST | 任务管理 |
| `local_safe_downloader` | `/api/download` | POST | 安全下载 |
| `local_file_search` | `/api/search` | POST | 文件检索 |
| `local_job_status` | `/api/job/status` | POST | 异步任务状态 |
| `local_sandbox_executor` | `/api/sandbox` | POST | 沙盒执行 |

| 页面 | 端点 | 说明 |
|------|------|------|
| 🖥️ Web UI | `GET /` | 图形化管理界面 |
| 📖 API 文档 | `GET /docs` | Swagger UI |
| ❤️ 健康检查 | `GET /health` | 服务状态 |
| 🤖 **AI 对话** | `POST /api/chat` | 自然语言操控所有功能 |
| ℹ️ API 信息 | `GET /api-info` | 端点列表 |

## 图形界面

浏览器打开 `http://localhost:8900` 即可使用 Web 管理界面：

- **📊 仪表盘** — 一眼看到任务/下载/磁盘统计 + 最近活动
- **📋 任务管理** — 周日历视图（带时间纵轴 07:00-23:00）+ 全部任务列表
- **📥 下载中心** — 新建下载 + 下载历史记录（带分类筛选）
- **🔍 文件检索** — 搜索已归档文件
- **🔧 沙盒执行** — Docker 隔离执行代码
- **📜 操作日志** — 所有操作可追溯
- **🤖 AI 助手** — 右下角悬浮窗，自然语言操控全部功能（Ctrl+J 打开）

## AI 对话功能

通过自然语言对话操控所有本地功能。配置方法：

```bash
# 设置 AI API（支持 OpenAI/GLM 兼容格式）
export AI_API_KEY="your-api-key"
export AI_MODEL="glm-4-flash"  # 可选
export AI_API_BASE="https://open.bigmodel.cn/api/coding/paas/v4"  # 可选
python main.py
```

AI 可通过 function calling 自动调用 5 个工具：
- 任务管理（添加/删除/完成/查询周计划）
- 安全下载（URL → 归档）
- 文件检索（关键词搜索）
- 沙盒执行（Docker 代码运行）
- 异步任务查询

## 快捷键

| 快捷键 | 功能 |
|--------|------|
| `Ctrl+K` | 全局搜索 |
| `Ctrl+N` | 新建任务 |
| `Ctrl+J` | 打开 AI 助手 |

## 环境变量

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `GATEWAY_HOST` | `0.0.0.0` | 监听地址 |
| `GATEWAY_PORT` | `8900` | 监听端口 |
| `GATEWAY_DEBUG` | `false` | 调试模式 |
| `DOWNLOADS_DIR` | `./downloads` | 下载归档目录 |
| `SANDBOX_TIMEOUT` | `300` | 沙盒超时（秒） |
| `SANDBOX_MEMORY_LIMIT` | `512m` | 沙盒内存限制 |
| `CORS_ORIGINS` | `*` | 允许的 CORS 来源 |
| `AI_API_BASE` | `https://open.bigmodel.cn/api/coding/paas/v4` | AI API 地址 |
| `AI_API_KEY` | （空） | AI API Key |
| `AI_MODEL` | `glm-4-flash` | AI 模型名称 |

## 安全注意事项

1. **CORS**：生产环境应限制 `CORS_ORIGINS` 为 GLM 智能体中心的域名
2. **认证**：建议添加 API Key 验证，防止未授权访问
3. **Docker 镜像**：沙盒首次使用需拉取镜像，如 `docker pull python:3.11-slim`
4. **目录权限**：确保网关进程对 `downloads/` 目录有读写权限
5. **内网穿透**：ngrok 免费版有连接限制，生产环境建议使用固定域名方案
