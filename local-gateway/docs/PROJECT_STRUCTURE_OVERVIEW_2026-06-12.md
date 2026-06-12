# LocalCommandCenter 项目结构梳理

更新时间：2026-06-12  
代码基线：`origin/main` 已拉取到本地，当前分支 `main`，最新快进到 `ff66eab`

## 1. 项目定位

这个仓库的核心是 `local-gateway/`，它已经不是最初那个只提供 5 个工具接口的轻量网关，而是一个逐步扩展出来的本地工作台系统，当前大致包含 4 条主线：

1. `任务/笔记/习惯/日历/通知` 这条个人效率主线
2. `AI 对话 + AI 规划` 这条智能交互主线
3. `邮件收发/线程/草稿/自动处理` 这条邮件工作台主线
4. `同步/加密/Webhook/工作流/快捷键/移动端` 这条平台能力主线

它的真实形态是：

- 后端：FastAPI + aiosqlite
- 前端：React 19 + Vite，构建产物输出到后端 `static/`
- 数据：单机 SQLite + 若干本地 JSON 状态文件
- AI：OpenAI 兼容接口，支持 function calling、流式对话、代码执行、shell 执行
- 执行隔离：Docker 沙盒

## 2. 仓库顶层结构

仓库根目录当前主要内容：

```text
My_Claw/
├── AGENTS.md
├── CLAUDE.md
├── README.md
├── docs/                  # 根级文档区，当前工作树里有大量未提交删除
└── local-gateway/         # 真正的应用代码
```

注意两点：

1. 根目录 `README.md` 和 `local-gateway/README.md` 都明显落后于真实代码。
2. 当前工作树里 `docs/` 与 `local-gateway/docs/` 有大量本地删除，属于用户现有改动，不能据此反推代码结构。

## 3. `local-gateway/` 总览

`local-gateway/` 是完整应用，包含：

```text
local-gateway/
├── main.py
├── config.py
├── environment.yml
├── requirements.txt
├── requirements-dev.txt
├── models/
├── routers/
├── services/
├── frontend/
├── static/
├── scripts/
├── test/
└── docs/
```

目录规模概览：

- `routers/`: 26 个文件
- `services/`: 40 个文件（含 `services/mail/` 子包）
- `frontend/src/pages/`: 11 个页面
- `frontend/src/components/`: 25 个组件文件
- `test/`: 31 个测试文件

## 4. 后端主入口

### 4.1 `main.py`

`main.py` 是总装配文件，职责很明确：

- 创建 FastAPI 应用
- 注册 CORS
- 注册所有 router
- 挂载 `/static`
- 提供 `/`、`/health`、`/api-info`、`/api/system/time`
- 在 `lifespan` 中初始化：
  - 基础目录
  - 主数据库
  - 邮件数据库/邮件轮询
  - 同步引擎
  - 通知调度器
  - 已有任务提醒恢复

启动顺序很关键，因为它定义了整个系统的运行依赖链。

### 4.2 `config.py`

`config.py` 不是简单常量表，而是整个系统的环境边界：

- 服务基础配置：`HOST`、`PORT`、`DEBUG`
- 路径配置：`BASE_DIR`、`DOWNLOADS_DIR`、`DB_PATH`
- 下载、安全、Docker、CORS、Job TTL
- `AIConfig` 持久化对象

尤其要注意：

1. AI 配置会落到 `data/ai_config.json`
2. CORS 默认值已经偏安全，不再是完全开放
3. 许多服务都间接依赖这里的路径和运行时配置

## 5. 数据模型层

### `models/schemas.py`

这是后端的统一接口模型中心，文件很大（667 行），已经超出“5 个工具 schema”的早期定位。

它现在覆盖：

- 任务管理
- 批量任务编排
- 下载/队列/带宽
- 统一搜索/全文搜索
- 沙盒执行/异步任务状态
- 仪表盘/日志/全部任务
- AI 对话/AI 配置
- 标签/子任务/番茄钟
- 日历
- 笔记
- 习惯
- 同步/加密/邮件相关请求体的部分外围结构

阅读这个文件的意义不是背字段，而是先确认“系统对外暴露了哪些稳定能力”。

## 6. Router 层结构

Router 基本遵守“薄路由”模式：参数校验、错误转换、调用 service。

### 6.1 核心基础路由

- `routers/task_manager.py`
  - `/api/task`
  - `/api/task/{task_id}`
  - `/api/task/batch`
  - 仍然保留早期 tool-call 风格接口

- `routers/safe_downloader.py`
  - `/api/download`
  - 下载队列、暂停、恢复、取消、带宽控制

- `routers/file_search.py`
  - `/api/search`
  - 已从旧“文件搜索”演进为统一搜索入口
  - 同时兼容 legacy 文件搜索与全文索引接口

- `routers/sandbox_executor.py`
  - `/api/sandbox`

- `routers/job_status.py`
  - `/api/job/status`

### 6.2 AI 与计划相关

- `routers/chat.py`
  - `/api/chat`
  - `/api/chat/stream`
  - `/api/chat/config`
  - `/api/chat/models`
  - `/api/chat/history/*`
  - `/api/chat/conversations/*`

- `routers/ai_planning.py`
  - 任务拆解、排期预览、确认、重排、估时、建议、洞察

### 6.3 效率系统相关

- `routers/dashboard.py`
- `routers/advanced_features.py`
- `routers/notes.py`
- `routers/habits.py`
- `routers/calendar_sync.py`
- `routers/notification.py`
- `routers/shortcuts.py`

其中 `advanced_features.py` 是一个明显的“聚合路由”，塞了标签、子任务、番茄钟、日历视图、任务详情等增强能力。

### 6.4 平台能力相关

- `routers/sync.py`
- `routers/encryption.py`
- `routers/webhooks.py`
- `routers/workflows.py`
- `routers/mobile.py`
- `routers/voice.py`

### 6.5 邮件系统相关

- `routers/mail.py`
  - 只是聚合层，挂载：
    - `routers/mail_api.py`
    - `routers/mail_portal.py`

- `routers/mail_api.py`
  - 账户
  - 文件夹
  - 线程
  - 草稿
  - 同步
  - 轮询
  - 邮件仪表盘

- `routers/mail_portal.py`
  - 面向“邮件中的处理入口页”
  - 通过 token + thread_id 访问
  - 包含保存草稿、创建任务、归档、快捷动作、发送草稿等

- `routers/mail_portal_render.py`
  - HTML 渲染辅助，不是 API

## 7. Service 层结构

Service 层是这个仓库最重要的部分，业务逻辑几乎都压在这里。

### 7.1 主业务服务

- `services/task_service.py`（1391 行）
  - 项目里最核心的单体服务之一
  - 负责：
    - 主数据库初始化
    - 任务 CRUD
    - 时间冲突检测
    - 批量创建与批量更新
    - 周计划/待办查询
    - 下载记录
    - 操作日志
    - 仪表盘统计
    - 任务详情拼装
  - 它实际上是“任务中心 + 部分运营中心”

- `services/ai_service.py`（1355 行）
  - 第二个核心大文件
  - 负责：
    - system prompt
    - tools schema
    - 多轮 function calling
    - conversation 持久化
    - 流式输出
    - code interpreter
    - shell 执行桥接
  - 这是 AI 子系统的总调度中心

- `services/sync_service.py`
  - 同步协议、变更追踪、冲突解决、同步引擎

### 7.2 单一能力服务

- `download_service.py`：安全下载、队列、限速
- `sandbox_service.py`：Docker 容器执行与产物回拷
- `search_service.py`：旧文件搜索
- `unified_search_service.py`：统一搜索新入口
- `fulltext_search_service.py`：全文索引与内容检索
- `notification_service.py`：提醒与日报
- `security_service.py`：文件名、URL、命令白名单、安全 subprocess
- `time_service.py`：系统时间抽象

### 7.3 任务增强能力

- `tag_service.py`
- `subtask_service.py`
- `pomodoro_service.py`
- `note_service.py`
- `habit_service.py`
- `streak_service.py`
- `calendar_sync_service.py`

这些服务都围绕 `task_service.py` 扩展，但数据仍大多落在同一个 SQLite 中。

### 7.4 AI 规划能力

- `ai_planning_service.py`
  - 另一个重要的大文件
  - 负责：
    - 任务拆解
    - 任务排期 preview/confirm
    - 多 variant 计划
    - 日程负载分析
    - replan / acceptance
    - 估时 / 建议 / 模式分析

它和 `ai_service.py` 的关系是：

- `ai_service.py` 负责“对话式智能代理”
- `ai_planning_service.py` 负责“任务规划算法与 LLM 辅助排期”

### 7.5 邮件子系统

邮件子系统是当前仓库里最成体系的一个子包。

文件结构：

```text
services/mail/
├── accounts.py
├── automation.py
├── compat.py
├── drafts.py
├── facade.py
├── messages.py
├── parsing.py
├── runtime.py
├── schema.py
├── sync.py
├── threads.py
└── utils.py
```

职责分工：

- `schema.py`
  - 邮件表结构与迁移

- `accounts.py`
  - 邮件账户、文件夹、连接测试

- `threads.py`（797 行）
  - 线程、消息、附件、草稿、仪表盘、状态刷新
  - 这是邮件业务中心

- `drafts.py`
  - 草稿创建、更新、发送

- `messages.py`
  - 邮件入库

- `parsing.py`
  - MIME 解析、地址提取、命令提取、AI 回信内容生成桥

- `sync.py`
  - 单账户同步、同步状态、重分析

- `runtime.py`
  - 轮询调度运行时

- `automation.py`（440 行）
  - 自动回信策略、自动建任务、agent run 记录

- `utils.py`
  - token、portal link、message-id、地址与主题工具函数

- `facade.py`
  - 明确导出邮件子系统公共 API

而 `services/mail_service.py` 只是兼容与聚合层，方便旧引用继续通过 `mail_service.*` 使用邮件能力。

## 8. 前端结构

前端是单独的 React + Vite 应用，不再是 README 中描述的“纯静态 HTML/CSS/JS”。

### 8.1 构建关系

- 源码：`frontend/`
- Vite 构建输出：`../static`
- 后端运行时通过 `/static` 和 `/` 提供前端

`static/index.html` 当前已经引用打包产物 `assets/index-*.js/css`，说明线上实际使用的是 React 构建结果。

### 8.2 前端入口

- `frontend/src/main.jsx`
  - `createRoot` 挂载

- `frontend/src/App.jsx`（189 行）
  - 应用外壳
  - hash 路由
  - 顶栏、边栏、页面切换
  - 快捷键

### 8.3 页面层

11 个主要页面：

- `Dashboard.jsx`（742 行）
- `Tasks.jsx`（1740 行）
- `Notes.jsx`
- `Habits.jsx`
- `Calendar.jsx`
- `AiChat.jsx`（1185 行）
- `Workflows.jsx`
- `Sync.jsx`
- `Download.jsx`（实际已演变为邮件工作台）
- `Sandbox.jsx`
- `Settings.jsx`

这里有一个很重要的现实：

`Download.jsx` 的名字已经失真。这个页面现在主要是 Mail Desk / Correspondence Desk，不再是单纯下载中心。

### 8.4 组件层

主要分两块：

- `components/chat/*`
  - AI chat 视图、规划卡片、档案页、markdown 渲染等

- `components/maildesk/*`
  - 邮件工作台 UI
  - 线程侧栏、展开阅读、控制网格、草稿弹窗、任务弹窗

此外还有：

- `Sidebar.jsx`
- `TopBar.jsx`

### 8.5 Hook 与 Context

Hooks 是当前前端的重要组织方式：

- `useApi.js`
- `useMailDeskState.js`
- `useMailDeskData.js`
- `useMailDeskComposer.js`
- `useMailDeskLifecycle.js`
- `useMailDeskPollingActions.js`
- `useMailDeskAccountActions.js`
- `useMailDeskThreadActions.js`
- `useMailDeskDerivedState.js`

其中邮件工作台已经明显做过一轮拆分：页面只负责组装，状态与行为下沉到 hook。

Context 包括：

- `ThemeContext`
- `AppContext`
- `ToastContext`

## 9. 测试结构

测试主要分三类：

### 9.1 后端 pytest

`test/` 下 31 个测试文件，覆盖：

- API 层
- 服务层
- 安全校验
- AI 规划
- 统一搜索
- 笔记/习惯/番茄钟
- 邮件账户/线程/草稿/同步/解析/运行时

邮件相关测试已经形成独立簇：

- `test_mail_accounts.py`
- `test_mail_automation.py`
- `test_mail_drafts.py`
- `test_mail_facade.py`
- `test_mail_parsing.py`
- `test_mail_runtime.py`
- `test_mail_sync.py`
- `test_mail_threads.py`
- `test_mail_utils.py`

### 9.2 前端 vitest

当前测试主要集中在邮件工作台相关组件与 hook：

- `components/maildesk/__tests__/*`
- `hooks/__tests__/*`

### 9.3 旧测试报告

`test/TEST_REPORT.md` 仍然保留较早阶段的测试说明，能反映项目演进过程，但不能代表当前完整测试覆盖。

## 10. 关键数据流

### 10.1 后端主路径

```text
HTTP Request
-> Router
-> Service
-> SQLite / JSON / Docker / HTTP API
-> Router Response
```

### 10.2 AI 对话主路径

```text
前端 AiChat
-> /api/chat 或 /api/chat/stream
-> services.ai_service.chat/chat_stream
-> 外部 LLM
-> tool call dispatch
-> 本地 service / shell / code interpreter
-> 汇总回复
```

### 10.3 邮件主路径

```text
前端 Mail Desk
-> /api/mail/*
-> routers.mail_api
-> services.mail_service / services.mail.*
-> SQLite + IMAP/SMTP + 自动化策略
-> 线程/草稿/仪表盘返回
```

### 10.4 前端交付路径

```text
frontend/src/*
-> vite build
-> static/assets/*
-> FastAPI StaticFiles
-> 浏览器
```

## 11. 当前代码特征与阅读结论

这个项目不是严格模块化的“小而美”结构，而是典型的“功能不断叠加后的单仓应用”：

- 优点
  - 路由层相对清晰
  - service 分层基本成立
  - 邮件子系统拆分得比较完整
  - 前端已经开始用 hook 拆分复杂页面

- 风险
  - `task_service.py`、`ai_service.py`、`Tasks.jsx`、`AiChat.jsx` 等大文件过重
  - README 明显落后
  - 文件命名与实际业务可能不再一致，如 `Download.jsx`
  - 兼容层较多，阅读时必须区分“当前主路径”和“历史兼容路径”

## 12. 建议的阅读抓手

如果只看最关键的骨架，优先抓这几组文件：

1. `main.py`
2. `config.py`
3. `models/schemas.py`
4. `routers/task_manager.py`、`routers/chat.py`、`routers/mail.py`、`routers/file_search.py`
5. `services/task_service.py`
6. `services/ai_service.py`
7. `services/mail/facade.py` + `services/mail/threads.py` + `services/mail/automation.py`
8. `frontend/src/App.jsx`
9. `frontend/src/pages/Tasks.jsx`
10. `frontend/src/pages/AiChat.jsx`
11. `frontend/src/pages/Download.jsx`

这几组文件读通，整个项目的 70% 主路径就基本清楚了。
