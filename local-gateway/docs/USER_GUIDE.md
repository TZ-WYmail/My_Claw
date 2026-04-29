# LocalCommandCenter 使用说明

> 版本: v3.0 | 更新: 2026-04-29

## 一、产品简介

**LocalCommandCenter** 是一个 FastAPI 本地网关，接收 GLM 智能体的 Tool Call 请求并操作本地系统。它同时提供完整的 Web 管理界面、AI 自然语言对话、移动端 API 和 PWA 离线支持。

**核心能力**：
- 任务规划与番茄钟 — 支持优先级、标签、子任务、周期提醒
- 安全下载与归档 — URL 校验 + 大文件异步下载 + 分类归档
- 本地文件检索 — 模糊搜索 + 全文索引
- Docker 沙盒执行 — 隔离运行 Python/Node/FFmpeg/Pandoc
- AI 对话 — 自然语言操控全部功能（OpenAI/GLM 兼容）
- 多端同步 — 设备注册、增量同步、离线队列、端到端加密
- PWA — 可安装到桌面/手机，支持离线缓存和后台同步

---

## 二、安装与启动

### 2.1 环境要求

| 组件 | 最低版本 | 用途 |
|------|---------|------|
| Python | 3.11+ | 运行网关 |
| Conda | 任意 | 环境管理 |
| Docker | 20.x+ | 沙盒功能（可选） |
| ngrok | 3.x | 外网访问（可选） |

### 2.2 安装步骤

```bash
# 1. 激活 Conda 环境
conda activate claude

# 2. 安装 Python 依赖
cd local-gateway
pip install -r requirements.txt

# 3. 确保 Docker 运行中（仅沙盒功能需要）
docker info

# 4. 启动网关
python main.py
```

启动成功后会看到：
```
🚀 LocalCommandCenter v3.0.0 启动中...
✅ 数据库初始化完成: tasks.db
✅ 同步引擎初始化完成
📡 服务监听: http://0.0.0.0:8900
```

### 2.3 外网访问（供 GLM 智能体调用）

```bash
ngrok http 8900
```

将 ngrok 生成的 HTTPS URL 配置到 GLM 智能体中心即可。

### 2.4 环境变量

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `GATEWAY_HOST` | `0.0.0.0` | 监听地址 |
| `GATEWAY_PORT` | `8900` | 监听端口 |
| `GATEWAY_DEBUG` | `false` | 调试模式（热重载 + 详细日志） |
| `DOWNLOADS_DIR` | `./downloads` | 下载归档根目录 |
| `SANDBOX_TIMEOUT` | `300` | 沙盒超时（秒） |
| `SANDBOX_MEMORY_LIMIT` | `512m` | 沙盒内存限制 |
| `CORS_ORIGINS` | `*` | CORS 允许来源（生产环境应限制） |
| `CORS_ALLOW_CREDENTIALS` | `true` | CORS 允许凭证 |
| `AI_API_BASE` | `https://open.bigmodel.cn/api/coding/paas/v4` | AI API 地址 |
| `AI_API_KEY` | （空） | AI API 密钥 |
| `AI_MODEL` | `glm-4-flash` | AI 模型名称 |

---

## 三、Web 管理界面

浏览器打开 `http://localhost:8900` 进入管理界面。

### 3.1 功能页面

| 页面 | 功能 |
|------|------|
| 仪表盘 | 任务/下载/磁盘统计 + 最近活动 |
| 任务管理 | 周日历视图 + 全部任务列表（标签/优先级过滤） |
| 下载中心 | 新建下载 + 下载历史 + 带宽限速 |
| 文件检索 | 模糊搜索 + 全文搜索已归档文件 |
| 沙盒执行 | Docker 隔离执行代码 |
| 操作日志 | 所有操作可追溯 |
| AI 助手 | 右下角悬浮窗，自然语言操控全部功能 |

### 3.2 快捷键

| 快捷键 | 功能 |
|--------|------|
| `Ctrl+K` | 全局搜索 |
| `Ctrl+N` | 新建任务 |
| `Ctrl+J` | 打开 AI 助手 |

### 3.3 PWA 安装

1. Chrome/Edge 打开 `http://localhost:8900`
2. 地址栏右侧出现安装图标，点击"安装 LocalCommandCenter"
3. 安装后可从桌面/启动器直接打开，支持离线访问

---

## 四、AI 对话功能

### 4.1 配置

```bash
export AI_API_KEY="your-api-key"
export AI_MODEL="glm-4-flash"
python main.py
```

也可通过 API 在线修改配置：

```bash
# 查看 AI 配置
curl http://localhost:8900/api/chat/config

# 修改模型
curl -X POST http://localhost:8900/api/chat/config \
  -H "Content-Type: application/json" \
  -d '{"model": "glm-4-plus"}'
```

### 4.2 使用

```bash
# 发送消息
curl -X POST http://localhost:8900/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "提醒我明天下午3点开会"}'
```

AI 通过 function calling 自动调用 5 个核心工具：

| 工具 | 能力 |
|------|------|
| `local_task_manager` | 添加/删除/完成/查询周计划 |
| `local_safe_downloader` | URL → 安全下载 → 归档 |
| `local_file_search` | 关键词搜索本地文件 |
| `local_sandbox_executor` | Docker 代码运行 |
| `local_job_status` | 异步任务状态查询 |

---

## 五、API 参考

### 5.1 核心工具 API（GLM Tool Call）

#### 任务管理 `/api/task`

```bash
# 添加任务
curl -X POST http://localhost:8900/api/task \
  -H "Content-Type: application/json" \
  -d '{
    "action": "add_task",
    "task_name": "提交报告",
    "due_time": "2026-04-30T15:00:00+08:00",
    "recurrence": "once",
    "priority": 1
  }'

# 查看周计划
curl -X POST http://localhost:8900/api/task \
  -d '{"action": "get_weekly_plan"}'

# 完成任务
curl -X POST http://localhost:8900/api/task \
  -d '{"action": "complete_task", "task_id": "task_xxx"}'

# 删除任务
curl -X POST http://localhost:8900/api/task \
  -d '{"action": "delete_task", "task_id": "task_xxx"}'
```

#### 安全下载 `/api/download`

```bash
curl -X POST http://localhost:8900/api/download \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com/paper.pdf",
    "category": "paper",
    "filename": "paper.pdf"
  }'
```

支持的分类: `paper` / `video` / `code` / `misc`

#### 文件检索 `/api/search`

```bash
curl -X POST http://localhost:8900/api/search \
  -H "Content-Type: application/json" \
  -d '{"keyword": "论文", "category": "all"}'
```

#### 沙盒执行 `/api/sandbox`

```bash
curl -X POST http://localhost:8900/api/sandbox \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "python",
    "execution_command": "python /workspace/main.py",
    "dynamic_files": {
      "main.py": "print('Hello from sandbox!')"
    }
  }'
```

#### 异步任务状态 `/api/job/status`

```bash
curl -X POST http://localhost:8900/api/job/status \
  -H "Content-Type: application/json" \
  -d '{"job_id": "job_xxx"}'
```

### 5.2 任务增强 API `/api/task`

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/task` | POST | 核心操作（add/get/complete/delete） |
| `/api/task/batch` | POST | 批量创建任务 |
| `/api/tasks/all` | GET | 全部任务列表（支持标签/优先级/关键词过滤） |
| `/api/tasks/batch-update` | POST | 批量更新任务状态 |
| `/api/tags` | GET/POST | 标签管理 |
| `/api/tags/{tag_id}` | DELETE | 删除标签 |
| `/api/tasks/{task_id}/tags` | POST/DELETE | 任务标签关联 |
| `/api/tasks/{task_id}/subtasks` | GET | 获取子任务 |
| `/api/subtasks` | POST | 创建子任务 |
| `/api/subtasks/{subtask_id}` | PUT/DELETE | 更新/删除子任务 |

#### 标签和优先级过滤

```bash
# 按标签过滤
curl "http://localhost:8900/api/tasks/all?tag=工作"

# 按优先级过滤（0=紧急 1=高 2=中 3=低）
curl "http://localhost:8900/api/tasks/all?priority=1"

# 关键词搜索
curl "http://localhost:8900/api/tasks/all?keyword=报告"
```

### 5.3 番茄钟 API `/api/task`

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/pomodoro/start` | POST | 开始番茄钟 |
| `/api/pomodoro/complete` | POST | 完成番茄钟 |
| `/api/pomodoro/interrupt` | POST | 中断番茄钟 |
| `/api/pomodoro/status` | GET | 当前番茄钟状态 |
| `/api/pomodoro/stats` | GET | 番茄钟统计（今日/本周/7天趋势） |
| `/api/pomodoro/history` | GET | 番茄钟历史 |

```bash
# 开始 25 分钟番茄钟
curl -X POST http://localhost:8900/api/pomodoro/start \
  -d '{"task_id": "task_xxx", "duration_minutes": 25}'

# 查看统计
curl http://localhost:8900/api/pomodoro/stats
```

### 5.4 日历 API `/api/calendar`

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/calendar/view` | GET | 月度日历视图（任务+事件+番茄钟） |
| `/api/calendar/events` | GET/POST | 日历事件查询/创建 |
| `/api/calendar/events/{id}` | DELETE | 删除事件 |

```bash
# 获取月度视图
curl "http://localhost:8900/api/calendar/view?year=2026&month=4"

# 创建日历事件
curl -X POST http://localhost:8900/api/calendar/events \
  -d '{"title": "项目评审", "start_time": "2026-04-30T14:00:00", "end_time": "2026-04-30T15:00:00"}'
```

### 5.5 笔记 API `/api/notes`

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/notes` | GET/POST | 笔记列表/创建 |
| `/api/notes/{id}` | GET/PUT/DELETE | 笔记详情/更新/删除 |

```bash
# 创建 Markdown 笔记
curl -X POST http://localhost:8900/api/notes \
  -d '{"title": "会议纪要", "content": "# 要点\n- 进度正常", "tags": ["工作", "会议"]}'

# 按关键词搜索
curl "http://localhost:8900/api/notes?keyword=会议"
```

### 5.6 习惯追踪 API `/api/habits`

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/habits` | GET/POST | 习惯列表/创建 |
| `/api/habits/{id}` | GET/DELETE | 习惯详情/删除 |
| `/api/habits/{id}/checkin` | POST | 习惯打卡 |
| `/api/habits/{id}/stats` | GET | 习惯统计 |

```bash
# 创建习惯
curl -X POST http://localhost:8900/api/habits \
  -d '{"name": "阅读30分钟", "frequency": "daily"}'

# 打卡
curl -X POST http://localhost:8900/api/habits/habit_xxx/checkin
```

### 5.7 数据同步 API `/api/sync`

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/sync/status` | GET | 同步状态 |
| `/api/sync/push` | POST | 推送变更 |
| `/api/sync/pull` | POST | 拉取变更 |
| `/api/sync/full` | POST | 完整同步 |
| `/api/sync/device/register` | POST | 注册设备 |
| `/api/sync/devices` | GET | 已注册设备列表 |
| `/api/sync/device/{id}/heartbeat` | POST | 设备心跳 |
| `/api/sync/offline/queue` | GET/POST | 离线操作队列 |
| `/api/sync/offline/sync` | POST | 执行离线同步 |

```bash
# 查看同步状态
curl http://localhost:8900/api/sync/status

# 注册设备
curl -X POST http://localhost:8900/api/sync/device/register \
  -d '{"device_id": "my_phone", "device_name": "iPhone", "device_type": "mobile"}'

# 增量拉取
curl -X POST "http://localhost:8900/api/sync/pull?since=2026-04-29T00:00:00"
```

### 5.8 移动端 API `/api/mobile`

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/mobile/dashboard` | GET | 移动端首页聚合数据 |
| `/api/mobile/quick-action` | POST | 快捷操作（完成/番茄钟/打卡） |
| `/api/mobile/voice-task` | POST | 语音创建任务 |
| `/api/mobile/push/register` | POST | 注册推送令牌 |
| `/api/mobile/push/unregister` | POST | 注销推送令牌 |
| `/api/mobile/push/test` | POST | 测试推送 |
| `/api/mobile/offline/queue-batch` | POST | 批量离线操作 |
| `/api/mobile/offline/pending` | GET | 待同步操作 |
| `/api/mobile/sync/delta` | GET | 增量同步（减少流量） |
| `/api/mobile/settings` | GET/POST | 移动端设置 |

```bash
# 移动端首页
curl http://localhost:8900/api/mobile/dashboard

# 快捷操作
curl -X POST http://localhost:8900/api/mobile/quick-action \
  -d '{"action_type": "complete_task", "target_id": "task_xxx"}'

# 增量同步
curl "http://localhost:8900/api/mobile/sync/delta?since=2026-04-29T00:00:00&tables=tasks,habits"
```

### 5.9 端到端加密 API `/api/encryption`

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/encryption/key-info` | GET | 当前密钥信息 |
| `/api/encryption/rotate-key` | POST | 密钥轮换 |
| `/api/encryption/encrypt` | POST | 加密文本 |
| `/api/encryption/decrypt` | POST | 解密文本 |
| `/api/encryption/encrypt-object` | POST | 加密对象敏感字段 |
| `/api/encryption/decrypt-object` | POST | 解密对象 |
| `/api/encryption/encrypt-payload` | POST | 加密同步数据包 |
| `/api/encryption/decrypt-payload` | POST | 解密同步数据包 |

```bash
# 查看密钥信息
curl http://localhost:8900/api/encryption/key-info

# 加密文本
curl -X POST http://localhost:8900/api/encryption/encrypt \
  -d '{"plaintext": "机密内容"}'

# 加密对象（自动加密 title/description 等敏感字段）
curl -X POST http://localhost:8900/api/encryption/encrypt-object \
  -d '{"data": {"title": "秘密任务", "priority": 1}}'

# 密钥轮换
curl -X POST http://localhost:8900/api/encryption/rotate-key
```

> 注意: 密钥轮换后，旧密钥加密的数据将无法解密。生产环境应先解密再加密。

### 5.10 其他 API

| 模块 | 前缀 | 核心端点 |
|------|------|---------|
| 下载管理 | `/api/download` | 下载/暂停/恢复/取消/带宽限速 |
| 文件搜索 | `/api/search` | 模糊搜索 + 全文搜索 `/api/search/fulltext` |
| 沙盒执行 | `/api/sandbox` | Docker 代码执行 |
| 仪表盘 | `/api/dashboard` | 统计/日志/历史 |
| AI 规划 | `/api/ai` | 建议/洞察/时间估算/任务分解 |
| 快捷键 | `/api/shortcuts` | 自定义快捷键管理 |
| 日历同步 | `/api/calendar/sync` | Google/Outlook 日历同步 |
| 语音 | `/api/voice` | 录音/转写/备忘录 |
| 全文搜索 | `/api/search` | 索引构建/重建/搜索 |
| Webhook | `/api/webhooks` | Webhook 注册/触发/管理 |
| 工作流 | `/api/workflows` | 自动化工作流定义/执行 |
| 聊天 | `/api/chat` | AI 对话 + 配置 |

---

## 六、项目结构

```
local-gateway/
├── main.py                      # FastAPI 入口，路由注册，生命周期管理
├── config.py                    # 全局配置 + AIConfig 持久化
├── requirements.txt             # Python 依赖
├── models/
│   └── schemas.py               # Pydantic 模型（5 个 Tool Schema + 扩展模型）
├── routers/                     # HTTP 端点（薄层，委托到 services/）
│   ├── task_manager.py          # 任务管理（核心5工具之一）
│   ├── safe_downloader.py       # 安全下载（核心5工具之一）
│   ├── file_search.py           # 文件检索（核心5工具之一）
│   ├── sandbox_executor.py      # 沙盒执行（核心5工具之一）
│   ├── job_status.py            # 异步任务（核心5工具之一）
│   ├── chat.py                  # AI 对话 + Function Calling
│   ├── dashboard.py             # 仪表盘统计
│   ├── encryption.py            # 端到端加密 API
│   ├── sync.py                  # 数据同步 + 设备管理 + 离线队列
│   ├── mobile.py                # 移动端优化 API
│   ├── notes.py                 # 笔记管理
│   ├── habits.py                # 习惯追踪
│   ├── calendar_sync.py         # 日历同步
│   ├── shortcuts.py             # 快捷键管理
│   ├── ai_planning.py           # AI 智能规划
│   ├── voice.py                 # 语音输入
│   ├── fulltext_search.py       # 全文搜索
│   ├── webhooks.py              # Webhook 管理
│   └── workflows.py             # 自动化工作流
├── services/                    # 业务逻辑
│   ├── task_service.py          # SQLite CRUD + 标签/子任务/番茄钟/日历/笔记/习惯
│   ├── download_service.py      # 异步下载 + 安全扫描 + 带宽控制
│   ├── search_service.py        # 本地文件模糊检索
│   ├── sandbox_service.py       # Docker SDK 沙盒调度
│   ├── ai_service.py            # OpenAI/GLM API + Function Calling 循环
│   ├── sync_service.py          # 同步协议 + 变更追踪 + 冲突解决
│   ├── e2e_encryption.py        # PBKDF2+Fernet 端到端加密
│   ├── security_service.py      # XSS/SSRF/注入防护
│   ├── ai_planning_service.py   # AI 任务规划
│   ├── calendar_sync_service.py # 日历同步服务
│   ├── fulltext_search_service.py # 全文索引引擎
│   ├── shortcut_service.py      # 快捷键服务
│   ├── voice_service.py         # 语音处理
│   ├── webhook_service.py       # Webhook 服务
│   └── workflow_service.py      # 工作流引擎
├── static/                      # Web 前端
│   ├── index.html               # 主页面
│   ├── style.css                # 暗色主题样式
│   ├── app.js                   # 前端交互逻辑
│   ├── manifest.json            # PWA 配置
│   ├── sw.js                    # Service Worker（离线缓存 + 后台同步）
│   └── icons/                   # PWA 图标（8种尺寸）
├── data/                        # 运行时数据（自动创建）
│   ├── tasks.db                 # SQLite 数据库
│   ├── ai_config.json           # AI 配置持久化
│   ├── sync_state.json          # 同步状态
│   ├── .device_id               # 设备标识
│   ├── .e2e_key                 # 加密密钥
│   └── .e2e_salt                # 加密盐值
├── test/                        # 测试
│   ├── test_api.py              # API 端点测试
│   ├── test_security.py         # 安全测试
│   ├── test_services.py         # 服务层测试
│   ├── test_phase2.py           # Phase 2 测试
│   ├── test_phase3.py           # Phase 3 测试
│   └── test_phase4.py           # Phase 4 测试
└── downloads/                   # 下载归档（自动创建）
    ├── paper/
    ├── video/
    ├── code/
    └── misc/
```

---

## 七、数据库表

系统使用 SQLite (`data/tasks.db`)，包含以下主要表：

| 表名 | 用途 | 核心字段 |
|------|------|---------|
| `tasks` | 任务管理 | task_id, task_name, due_time, recurrence, priority, status |
| `tags` | 标签 | tag_id, name, color |
| `task_tags` | 任务-标签关联 | task_id, tag_id |
| `subtasks` | 子任务 | subtask_id, task_id, name, status, sort_order |
| `pomodoro_sessions` | 番茄钟 | session_id, task_id, duration_minutes, status |
| `calendar_events` | 日历事件 | event_id, title, start_time, end_time, event_type |
| `notes` | 笔记 | note_id, title, content, content_type, tags |
| `habits` | 习惯 | habit_id, name, frequency, target_count |
| `habit_checkins` | 习惯打卡 | checkin_id, habit_id, checkin_date, count |
| `download_history` | 下载记录 | id, url, filename, category, status |
| `operation_logs` | 操作日志 | id, operation, endpoint, result |
| `sync_changes` | 同步变更日志 | change_id, table_name, record_id, operation |
| `sync_devices` | 同步设备 | device_id, device_name, device_type, last_seen |
| `sync_offline_queue` | 离线操作队列 | id, operation, table_name, data, synced |
| `push_tokens` | 推送令牌 | device_id, token, platform |

---

## 八、同步与加密

### 8.1 同步协议

采用版本向量 + 时间戳的同步协议：

1. **变更追踪**: 所有数据变更自动记录到 `sync_changes` 表
2. **增量同步**: 通过 `since` 参数只获取变更的数据
3. **冲突解决**: 支持 4 种策略
   - `last_write_wins` — 最后写入优先（默认）
   - `first_write_wins` — 首次写入优先
   - `merge` — 自动合并（非空字段覆盖）
   - `manual` — 需人工解决
4. **离线队列**: 离线操作存入 SQLite，联网后自动同步

### 8.2 端到端加密

- 算法: PBKDF2-SHA256 (100,000 iterations) + Fernet 对称加密
- 自动加密 `title`/`name`/`description`/`content`/`note` 等敏感字段
- 密钥文件存储在 `data/.e2e_key` 和 `data/.e2e_salt`
- 支持密钥轮换（`/api/encryption/rotate-key`）

---

## 九、安全注意事项

1. **CORS**: 生产环境应限制 `CORS_ORIGINS` 为 GLM 智能体中心的域名
2. **认证**: 建议添加 API Key 验证，防止未授权访问
3. **Docker 镜像**: 沙盒首次使用需拉取镜像 (`docker pull python:3.11-slim`)
4. **目录权限**: 确保网关进程对 `downloads/` 和 `data/` 目录有读写权限
5. **加密密钥**: `data/.e2e_key` 和 `data/.e2e_salt` 应妥善保管，切勿提交到版本控制
6. **SQL 注入防护**: 所有数据库操作使用参数化查询，更新操作有列名白名单校验
7. **沙盒安全**: Docker 隔离 + 超时限制 + 内存限制 + 可执行文件检测

---

## 十、测试

```bash
# 运行全部测试（需服务器运行在 localhost:8900）
conda run -n claude python -m pytest test/ -v

# 仅运行服务层测试（不需要服务器）
conda run -n claude python -m pytest test/test_services.py test/test_security.py -v

# 运行特定测试
conda run -n claude python -m pytest test/test_services.py::TestPomodoro -v
```

---

## 十一、开发阶段

| 阶段 | 内容 | 状态 |
|------|------|------|
| Phase 1 | 核心网关（任务/下载/搜索/沙盒/AI对话 + Web UI） | 已完成 |
| Phase 2 | 功能增强（标签/子任务/番茄钟/日历/笔记/习惯/语音/快捷键/AI规划） | 已完成 |
| Phase 3 | 安全加固（XSS/SSRF防护 + 安全下载增强 + 60个测试） | 已完成 |
| Phase 4 | 多端统一（同步协议/移动端API/PWA/E2E加密/离线队列） | 已完成 |
| Phase 5 | 专业深化（知识图谱/数据分析/插件系统/团队协作） | 规划中 |
