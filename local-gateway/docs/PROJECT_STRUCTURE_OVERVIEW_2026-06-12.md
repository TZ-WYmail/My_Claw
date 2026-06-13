# LocalCommandCenter 项目结构梳理

更新时间：2026-06-13  
代码基线：`origin/main` 已同步到本地，当前主分支 `main`

## 1. 项目定位

这个仓库的核心仍然是 `local-gateway/`，但它现在已经明确演进成一个“本地工作台平台”，而不是早期的轻量工具网关。

当前主线可以分成 5 组：

1. task / notes / habits / pomodoro / calendar / notification
2. AI chat / AI planning
3. search / download / sandbox / security
4. mail workspace
5. sync / encryption / workflow / webhook / mobile

技术形态：

- 后端：FastAPI + aiosqlite
- 前端：React 19 + Vite
- 数据：SQLite + 本地 JSON 配置/状态文件
- AI：OpenAI 兼容接口
- 执行隔离：Docker 沙盒

## 2. 仓库顶层结构

```text
My_Claw/
├── AGENTS.md
├── README.md
├── docs/
└── local-gateway/
```

真正的应用代码都在 `local-gateway/`。

## 3. `local-gateway/` 总览

```text
local-gateway/
├── main.py
├── config.py
├── environment.yml
├── requirements*.txt
├── application/
├── docs/
├── frontend/
├── models/
├── routers/
├── scripts/
├── services/
├── static/
└── test/
```

当前规模概览：

- `routers/`: 32 个 Python 文件
- `services/`: 40 个顶层 Python 文件
- `services/mail/`: 13 个子模块
- `frontend/src/pages/`: 11 个页面
- `frontend/src/components/`: 25 个组件文件
- `test/test_*.py`: 44 个测试文件

## 4. 运行入口

### 4.1 `main.py`

`main.py` 是总装配入口，职责非常集中：

- 创建 FastAPI app
- 注册 CORS
- 注册全部 router
- 挂载 `/static`
- 提供 `/`、`/health`、`/api-info`、`/api/system/time`
- 在 lifespan 中初始化：
  - `ensure_dirs()`
  - `bootstrap_service.init_db()`
  - `mail_service.init_mail_db()`
  - `mail_service.start_mail_polling_scheduler()`
  - `sync_engine.initialize()`
  - 通知调度器
  - reminder 恢复

这里最重要的变化是：

- 数据库初始化 owner 已经不是 `task_service`
- 搜索路由已拆成 `search` / `file_search` / `fulltext_search`
- `advanced_features` 已经只是兼容路由聚合

### 4.2 `config.py`

`config.py` 是系统环境边界，不只是常量表。

它集中持有：

- 服务配置：`HOST`、`PORT`、`DEBUG`
- 路径配置：`BASE_DIR`、`DOWNLOADS_DIR`、`DB_PATH`
- Docker / 下载 / CORS / Job TTL
- AI 配置持久化

## 5. 目录级结构

### 5.1 `application/`

这是当前代码结构里最重要的新层。

当前主要文件：

- `task_actions.py`
- `planning_actions.py`
- `dashboard_actions.py`
- `mobile_actions.py`
- `sync_actions.py`
- `tag_actions.py`
- `subtask_actions.py`
- `pomodoro_actions.py`
- `calendar_actions.py`
- `task_detail_actions.py`
- `mail_actions.py`
- `ai_tools.py`
- `advanced_actions.py`

当前职责：

- 用例编排
- 参数归一
- 跨入口复用
- 成功后补查聚合数据

`advanced_actions.py` 现在已经只是 compatibility aggregator，不再是主业务 owner。

### 5.2 `models/`

核心文件：

- `schemas.py`
- `sync_models.py`

`schemas.py` 仍然是对外接口模型中心，覆盖：

- task / batch task
- search / downloader / sandbox
- dashboard / logs
- AI chat / AI planning
- tag / subtask / pomodoro
- notes / habits / calendar
- mail / sync / encryption 的外围结构

### 5.3 `routers/`

router 现在已经可以分成 3 类：

#### 正式主路径

- `task_manager.py`
- `search.py`
- `fulltext_search.py`
- `dashboard.py`
- `tags.py`
- `subtasks.py`
- `pomodoro.py`
- `calendar.py`
- `task_detail.py`
- `chat.py`
- `ai_planning.py`
- `notes.py`
- `habits.py`
- `mobile.py`
- `sync.py`
- `voice.py`
- `webhooks.py`
- `workflows.py`
- `mail.py`
- `mail_api.py`
- `mail_portal.py`
- `shortcuts.py`
- `notification.py`
- `calendar_sync.py`
- `encryption.py`

#### 兼容路径

- `advanced_features.py`
- `file_search.py`

#### 基础工具/平台

- `safe_downloader.py`
- `sandbox_executor.py`
- `job_status.py`

当前最关键的 router 边界变化：

1. `routers/search.py`
   - 只负责 `POST /api/search`

2. `routers/file_search.py`
   - 只保留 `POST /api/search/legacy`

3. `routers/fulltext_search.py`
   - 负责全文索引相关正式入口

4. `routers/advanced_features.py`
   - 不再维护一套平行 handler
   - 现在通过 `include_router(...)` 复用正式域 router

### 5.4 `services/`

这是当前仓库最核心的实现层。

#### task 领域

- `bootstrap_service.py`
- `task_db_schema.py`
- `task_command_service.py`
- `task_query_service.py`
- `task_detail_service.py`
- `task_planning_service.py`
- `task_service.py`

当前边界：

- `bootstrap_service`
  - 数据库/bootstrap owner
- `task_command_service`
  - task 写侧
- `task_query_service`
  - task 列表/过滤/统计读侧
- `task_detail_service`
  - task 跨域详情聚合
- `task_planning_service`
  - 时间归一、analyze、daily plan
- `task_service`
  - compatibility facade，只为历史导入路径保留

#### dashboard / runtime / mobile

- `dashboard_query_service.py`
- `runtime_state_service.py`
- `runtime_log_service.py`
- `mobile_query_service.py`

这些模块已经把原先散落在 `task_service` 或 router 里的跨域查询/状态逻辑拆了出来。

#### task 周边领域

- `tag_service.py`
- `subtask_service.py`
- `pomodoro_service.py`
- `note_service.py`
- `habit_service.py`
- `streak_service.py`
- `calendar_sync_service.py`
- `notification_service.py`

#### AI

- `ai_service.py`
- `ai_planning_service.py`
- `ai_planning_preview_service.py`
- `ai_planning_variant_service.py`
- `ai_planning_replan_service.py`

#### 搜索 / 下载 / 沙盒 / 安全

- `unified_search_service.py`
- `fulltext_search_service.py`
- `search_service.py`（旧文件搜索能力仍在）
- `download_service.py`
- `sandbox_service.py`
- `security_service.py`
- `time_service.py`

当前边界：

- `unified_search_service`
  - 只做统一搜索聚合
- `fulltext_search_service`
  - 全文索引 owner

#### 平台能力

- `sync_service.py`
- `e2e_encryption.py`
- `shortcut_service.py`
- `voice_service.py`
- `webhook_service.py`
- `workflow_service.py`
- `utils.py`

#### 邮件系统

- `mail_service.py`
- `services/mail/*`

其中：

- `mail_service.py`
  - 仍是 facade
- `services/mail/facade.py`
  - 对外导出面
- `services/mail/schema.py`
  - schema / migration
- `services/mail/accounts.py`
  - 账户 / 文件夹
- `services/mail/threads.py`
  - 线程 / 消息 / 仪表盘
- `services/mail/drafts.py`
  - 草稿
- `services/mail/sync.py`
  - 同步
- `services/mail/automation.py`
  - 自动处理
- `services/mail/parsing.py`
  - 解析与 AI mail 辅助

### 5.5 `frontend/`

前端是 React + Vite。

关键目录：

- `frontend/src/pages/`
- `frontend/src/components/`
- `frontend/src/services/api.js`

前端现在仍需要重点关注是否还命中：

- `/api/advanced/*`
- `/api/search/legacy`

这是后续继续删除兼容路径前必须核对的点。

### 5.6 `static/`

这里是前端构建产物，由 FastAPI 直接托管。

### 5.7 `test/`

测试已经分成两类：

#### 业务测试

- task / planning / mobile / sync / mail / dashboard / habits 等

#### 架构护栏测试

- `test_architecture_guards.py`
- `test_search_routers.py`
- `test_domain_routers.py`

这些测试现在很重要，因为它们在锁：

- 内部主链不再导入 `task_service`
- search / legacy / fulltext 的 owner 分层
- `advanced_features` 只做 compatibility alias

## 6. 当前最重要的结构性判断

### 6.1 `task_service.py` 不再是主实现

现在它只是 compatibility facade。

如果要理解 task 领域，不要先读它，应该先读：

1. `bootstrap_service.py`
2. `task_command_service.py`
3. `task_query_service.py`
4. `task_detail_service.py`
5. `task_planning_service.py`

### 6.2 搜索已经分成 3 条路径

```text
/api/search            -> routers/search.py
/api/search/legacy     -> routers/file_search.py
/api/search/fulltext   -> routers/fulltext_search.py
```

### 6.3 `advanced_features` 已经不是“聚合实现”

它只是兼容 alias。

正式 owner 已经是：

- `tags.py`
- `subtasks.py`
- `pomodoro.py`
- `calendar.py`
- `task_detail.py`

### 6.4 application 层已经形成

这是理解当前项目最关键的结构变化之一。

router 已经不再是唯一的业务编排点，很多内部调用都先经过 application 层。

## 7. 当前最值得关注的设计问题

从当前结构看，主要问题已经从“完全混在一起”变成“兼容层仍偏厚、少数核心服务仍偏大”。

最值得继续关注的点：

1. `task_service.py` 仍然公开面偏宽
2. `task_service.init_db()` 仍是兼容入口，尚未显式废弃
3. `/api/search/legacy` 仍保留
4. `/api/advanced/*` 仍保留
5. `ai_service.py`、`ai_planning_service.py` 仍偏厚
6. `mail_service.py` 仍保留 facade 存在感
7. 旧 README / 旧阅读文档很容易误导新人

## 8. 如果你只想抓住当前骨架

建议优先看这 15 个文件：

1. `main.py`
2. `services/bootstrap_service.py`
3. `application/task_actions.py`
4. `services/task_command_service.py`
5. `services/task_query_service.py`
6. `services/task_detail_service.py`
7. `services/task_planning_service.py`
8. `services/task_service.py`
9. `routers/search.py`
10. `routers/file_search.py`
11. `routers/fulltext_search.py`
12. `routers/advanced_features.py`
13. `application/ai_tools.py`
14. `services/ai_service.py`
15. `test/test_architecture_guards.py`

读完这批文件，你就能先掌握当前真实结构，再决定深入哪个子系统。
