# advanced_features 退场记录与域映射（2026-06-14）

更新时间：2026-06-14
目的：记录历史 `/api/advanced/*` 路径退场后的正式域映射，给外部调用迁移提供一个固定对照表

## 1. 当前状态

截至 2026-06-14：

- `/api/advanced/*` 已删除
- `routers/advanced_features.py` 已删除
- 前端主页面与常规测试已经全部迁到正式域路径
- 这份文档改为历史迁移对照表，而不是继续讨论是否保留 advanced 路由

## 2. 历史路径到正式路径映射

### 2.1 tags

- `POST /api/advanced/tags` -> `POST /api/tags`
- `GET /api/advanced/tags` -> `GET /api/tags`
- `DELETE /api/advanced/tags/{tag_id}` -> `DELETE /api/tags/{tag_id}`
- `POST /api/advanced/tasks/{task_id}/tags` -> `POST /api/tasks/{task_id}/tags`
- `DELETE /api/advanced/tasks/{task_id}/tags` -> `DELETE /api/tasks/{task_id}/tags`

### 2.2 subtasks

- `POST /api/advanced/subtasks` -> `POST /api/subtasks`
- `GET /api/advanced/tasks/{task_id}/subtasks` -> `GET /api/tasks/{task_id}/subtasks`
- `PUT /api/advanced/subtasks/{subtask_id}` -> `PUT /api/subtasks/{subtask_id}`
- `DELETE /api/advanced/subtasks/{subtask_id}` -> `DELETE /api/subtasks/{subtask_id}`

### 2.3 pomodoro

- `POST /api/advanced/pomodoro/start` -> `POST /api/pomodoro/start`
- `POST /api/advanced/pomodoro/complete` -> `POST /api/pomodoro/complete`
- `POST /api/advanced/pomodoro/interrupt` -> `POST /api/pomodoro/interrupt`
- `GET /api/advanced/pomodoro/status` -> `GET /api/pomodoro/status`
- `GET /api/advanced/pomodoro/stats` -> `GET /api/pomodoro/stats`
- `GET /api/advanced/pomodoro/history` -> `GET /api/pomodoro/history`

### 2.4 calendar

- `POST /api/advanced/calendar/events` -> `POST /api/calendar/events`
- `GET /api/advanced/calendar/events` -> `GET /api/calendar/events`
- `DELETE /api/advanced/calendar/events/{event_id}` -> `DELETE /api/calendar/events/{event_id}`
- `GET /api/advanced/calendar/view` -> `GET /api/calendar/view`

### 2.5 task detail / batch maintenance

- `POST /api/advanced/tasks/batch-update` -> `POST /api/tasks/batch-update`
- `GET /api/advanced/tasks/{task_id}/detail` -> `GET /api/tasks/{task_id}/detail`

## 3. 为什么现在可以删除

这次退场成立的前提有四个：

1. tags / subtasks / pomodoro / calendar / task-detail 的正式域路由已经稳定存在
2. 前端主页面不再调用 `/api/advanced/*`
3. 常规离线回归不再依赖 `/api/advanced/*`
4. advanced 路径在仓库内部只剩一个专门的兼容联调测试在证明“旧路径还活着”

在这个状态下，继续保留 advanced 路由只会让历史命名继续暴露为假主入口。

## 4. 退场后的边界判断

删除 `advanced_features` 之后，当前正式 HTTP owner 已明确收口到：

- `routers/tags.py`
- `routers/subtasks.py`
- `routers/pomodoro.py`
- `routers/calendar.py`
- `routers/task_detail.py`

后续如果还有调用方提到 `/api/advanced/*`，应该直接视为外部迁移问题，而不是再回补兼容路由。

## 5. 仍需关注的后续问题

advanced 退场之后，剩余兼容重点已经转到：

- `services/task_service.py`
- `task_service.init_db()`
- `services/mail_service.py`
- AI 工具命名 `local_file_search`

也就是说，后续治理重点已经从“历史 HTTP 路由”转向“历史 facade 与命名”。
