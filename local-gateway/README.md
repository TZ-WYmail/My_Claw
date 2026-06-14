# LocalCommandCenter 本地网关

本目录是当前仓库的核心应用。

它现在已经不是早期的“5 个 Tool Schema 网关”，而是一个本地工作台系统，包含：

- task / notes / habits / pomodoro / calendar / notification
- AI chat / AI planning
- search / download / sandbox / security
- mail workspace
- sync / encryption / workflow / webhook / mobile

## 技术栈

- 后端：FastAPI + aiosqlite
- 前端：React 19 + Vite
- 数据：SQLite + 本地 JSON 状态文件
- AI：OpenAI 兼容接口
- 沙盒：Docker

## 快速启动

```bash
cd local-gateway

# 首次推荐
conda env create -f environment.yml || conda env update -f environment.yml --prune

conda activate claude

# 仅沙盒功能依赖 Docker
docker info

python main.py
```

默认地址：

- Web UI: `http://localhost:8900`
- Swagger: `http://localhost:8900/docs`

## 当前关键架构事实

这几条判断是阅读和修改代码前必须先知道的：

1. `bootstrap_service` 是数据库初始化 owner
2. `task_service` 已经退成 compatibility facade
3. task 领域已拆成：
   - `task_command_service`
   - `task_query_service`
   - `task_detail_service`
   - `task_planning_service`
4. `/api/search`
   - 正式统一搜索：`routers/search.py`
   - 全文索引：`routers/fulltext_search.py`
5. 历史 `POST /api/search/legacy` 与 `routers/file_search.py` 已删除
6. 历史 `/api/advanced/*` 与 `routers/advanced_features.py` 已删除
7. application 层已经成形，router 不再是唯一业务编排点

## 主要目录

```text
local-gateway/
├── main.py
├── config.py
├── application/
├── models/
├── routers/
├── services/
├── frontend/
├── static/
├── test/
└── docs/
```

### `application/`

当前内部用例编排层，典型文件：

- `task_actions.py`
- `planning_actions.py`
- `dashboard_actions.py`
- `mobile_actions.py`
- `sync_actions.py`
- `ai_tools.py`

### `routers/`

正式主路径：

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
- `mobile.py`
- `sync.py`
- `mail.py`

历史兼容 router：

- 无。历史 `advanced_features.py` 与 `file_search.py` 均已删除。

### `services/`

当前主干：

- `bootstrap_service.py`
- `task_command_service.py`
- `task_query_service.py`
- `task_detail_service.py`
- `task_planning_service.py`
- `dashboard_query_service.py`
- `mobile_query_service.py`
- `runtime_state_service.py`
- `runtime_log_service.py`
- `ai_service.py`
- `ai_planning_service.py`
- `mail/facade.py`（内部正式 facade）
- `mail_service.py`（compat facade）

## API 主入口

### task

- `POST /api/task`
- `PUT /api/task/{task_id}`
- `POST /api/task/batch`

### search

- `POST /api/search`
- `GET /api/search/fulltext`
- `POST /api/search/index`
- `GET /api/search/index/stats`
- `POST /api/search/index/rebuild`

### AI

- `POST /api/chat`
- `POST /api/chat/stream`
- `POST /api/ai/decompose`
- `POST /api/ai/plan`
- `POST /api/ai/plan/preview`
- `POST /api/ai/plan/confirm`
- `POST /api/ai/plan/replan`
- `POST /api/ai/plan/replan/accept`
- `POST /api/ai/estimate`
- `GET /api/ai/suggestions`
- `GET /api/ai/insights`

### 正式域增强能力

- `/api/tags`
- `/api/subtasks`
- `/api/pomodoro/*`
- `/api/calendar/*`
- `/api/tasks/{task_id}/detail`
- `/api/tasks/batch-update`
- `/api/mail/*`

### 历史兼容增强路径

- 历史 `/api/advanced/*` 已删除，对应正式域入口已稳定。

## 测试

常用回归命令：

```bash
conda run -n claude python -m pytest test/test_task_application.py test/test_planning_application.py test/test_mobile_application.py test/test_mobile_query_service.py test/test_sync_application.py test/test_mail_automation.py test/test_phase3.py test/test_execution_guards.py test/test_unified_search.py test/test_task_query_service.py test/test_ai_planning_flow.py test/test_runtime_state_service.py test/test_task_planning_service.py test/test_task_command_service.py test/test_services.py test/test_security.py test/test_dashboard_application.py test/test_habit_service.py test/test_advanced_application.py test/test_backend_remediation.py test/test_domain_routers.py test/test_search_routers.py test/test_architecture_guards.py test/test_ai_tool_application.py -q
```

当前重要测试类型：

- application 层测试
- domain router 薄路由测试
- search router owner 测试
- architecture guard 测试

## 阅读入口

建议先读：

1. `docs/PROJECT_STRUCTURE_OVERVIEW_2026-06-12.md`
2. `docs/CODE_READING_GUIDE_2026-06-12.md`
3. `docs/ARCH_IMPLEMENTATION_PROGRESS_2026-06-13.md`
4. `docs/ARCH_COMPAT_BOUNDARY_CATALOG_2026-06-13.md`

## 当前主要兼容面

还保留但已经不是主实现的对象：

- `services/task_service.py`
- `task_service.init_db()`（已显式废弃，暂留兼容）
- `services/mail_service.py`（内部主链已迁离，仓库内新代码应优先依赖 `services.mail.facade`）
- AI 兼容工具别名 `local_file_search`（正式名已切到 `local_unified_search`）

如果你继续做架构收口，优先不要往这些对象继续堆新逻辑。
