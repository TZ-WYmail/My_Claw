# advanced_features 目标域映射（2026-06-13）

更新时间：2026-06-13  
目的：明确 `/api/advanced/*` 这组历史聚合路由，后续应如何映射到稳定业务域

## 1. 当前判断

`/api/advanced/*` 不是一个稳定业务域。  
它只是历史上把“增强能力”堆在一起的聚合入口。

现在内部 application 已经开始按领域拆开，但对外路由命名还停留在历史阶段。

所以这份文档只解决两件事：

1. 每类能力真正属于哪个业务域
2. 后续路由应该怎么迁，不在迁移时重新混装

## 2. 当前 `/api/advanced/*` 能力分组

当前路由实际包含五类能力：

1. tags
2. subtasks
3. pomodoro
4. calendar
5. task-detail / batch task maintenance

这五类能力之间并不构成一个自然统一域。

## 3. 目标域映射

### 3.1 tags

当前入口：

- `POST /api/advanced/tags`
- `GET /api/advanced/tags`
- `DELETE /api/advanced/tags/{tag_id}`
- `POST /api/advanced/tasks/{task_id}/tags`
- `DELETE /api/advanced/tasks/{task_id}/tags`

目标归属：

- `tag` 域

建议目标路径：

- `/api/tags`
- `/api/tags/{tag_id}`
- `/api/tasks/{task_id}/tags`

说明：

- tags 本质上是 task 的关联元数据，不应继续挂在 “advanced” 名下

### 3.2 subtasks

当前入口：

- `POST /api/advanced/subtasks`
- `GET /api/advanced/tasks/{task_id}/subtasks`
- `PUT /api/advanced/subtasks/{subtask_id}`
- `DELETE /api/advanced/subtasks/{subtask_id}`

目标归属：

- `subtask` 域，或 `task child resource`

建议目标路径：

- `/api/subtasks`
- `/api/subtasks/{subtask_id}`
- `/api/tasks/{task_id}/subtasks`

说明：

- subtasks 明显属于 task 的子资源，不应继续放在增强功能集合里

### 3.3 pomodoro

当前入口：

- `POST /api/advanced/pomodoro/start`
- `POST /api/advanced/pomodoro/complete`
- `POST /api/advanced/pomodoro/interrupt`
- `GET /api/advanced/pomodoro/status`
- `GET /api/advanced/pomodoro/stats`
- `GET /api/advanced/pomodoro/history`

目标归属：

- `pomodoro` 域

建议目标路径：

- `/api/pomodoro/start`
- `/api/pomodoro/complete`
- `/api/pomodoro/interrupt`
- `/api/pomodoro/status`
- `/api/pomodoro/stats`
- `/api/pomodoro/history`

说明：

- pomodoro 已是独立运行时能力，不需要再作为 advanced 子类出现

### 3.4 calendar

当前入口：

- `POST /api/advanced/calendar/events`
- `GET /api/advanced/calendar/events`
- `DELETE /api/advanced/calendar/events/{event_id}`
- `GET /api/advanced/calendar/view`

目标归属：

- `calendar` 域

建议目标路径：

- `/api/calendar/events`
- `/api/calendar/events/{event_id}`
- `/api/calendar/view`

说明：

- 当前仓库已经存在 `routers/calendar_sync.py`
- 所以后续需要避免把 “calendar data view” 和 “calendar sync integration” 再次混装

建议拆分：

- `calendar` 路由负责事件与视图
- `calendar/sync` 路由负责外部同步配置与同步动作

### 3.5 task detail / batch maintenance

当前入口：

- `POST /api/advanced/tasks/batch-update`
- `GET /api/advanced/tasks/{task_id}/detail`

目标归属：

- `task maintenance`
- `task detail view`

建议目标路径：

- `/api/tasks/batch-update`
- `/api/tasks/{task_id}/detail`

说明：

- 这两类能力都直接属于 task 域
- 放在 advanced 下面只会继续制造“task 主入口不完整”的假象

## 4. 推荐迁移顺序

### 阶段 A：内部边界先稳定

当前已完成：

- application 已拆成 tag/subtask/pomodoro/calendar/task-detail action owner

这一阶段不需要改外部 URL。

### 阶段 B：增加正式域路由

建议先新增正式路由，不立即删除 `/api/advanced/*`：

1. `tags`
2. `subtasks`
3. `pomodoro`
4. `calendar`
5. `tasks/detail` 与 `tasks/batch-update`

### 阶段 C：兼容期双路由

在一个观察期内同时保留：

- 新正式域路由
- 旧 `/api/advanced/*` 路由

要求：

- 旧路由只做转发
- 不允许新逻辑只接在旧路由上

### 阶段 D：删除历史命名

条件满足后删除：

- `/api/advanced/*`
- `routers/advanced_features.py`

## 5. 当前不建议做的事情

当前不建议直接进行：

1. 一次性改前端全部接口路径
2. 一次性删除 `/api/advanced/*`
3. 在没有正式域路由前先删除历史路由

原因：

- 当前风险主要不是内部实现，而是接口引用面未知

## 6. 下一步最合理的动作

建议下一步按下面顺序推进：

1. 新增正式域 router，但先不删 `/advanced/*`
2. 让旧 `advanced_features` router 只保留兼容转发
3. 清点前端/API 调用面
4. 最后再删历史命名

## 7. 完成标准

满足以下条件，说明 `advanced_features` 这条线真正完成：

1. 对外已有稳定业务域路由
2. `/api/advanced/*` 不再承载主路径
3. 旧路由只剩兼容职责
4. 最终可以删除 `advanced_features` 这个历史命名
