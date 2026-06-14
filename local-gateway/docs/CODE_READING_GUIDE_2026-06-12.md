# LocalCommandCenter 代码阅读指南

更新时间：2026-06-14
目标：按当前真实架构读完 `local-gateway/`，避免把兼容层误判成主实现

## 1. 先建立一个正确前提

现在这套代码已经不是“从 `task_service.py` 往外长出来的单体任务系统”。

当前阅读时必须先接受这 6 个事实：

1. `bootstrap_service` 才是数据库初始化 owner
2. `task_service` 已经退成 compatibility facade，不再是仓库内部主链
3. task 领域已经拆成：
   - `task_command_service`
   - `task_query_service`
   - `task_detail_service`
   - `task_planning_service`
4. `/api/search` 与 `/api/search/fulltext` 已分属不同 router owner，历史 `/api/search/legacy` 已删除
5. 历史 `/api/advanced/*` 已删除，正式域 router 已成为唯一 HTTP owner
6. application 层已经成形，router 不再是唯一业务编排点

如果还按旧思路把 `task_service.py` 当主入口，后面会越读越乱；历史 `routers/advanced_features.py` 与 `routers/file_search.py` 已不再存在。

## 2. 读完后你至少要能回答的问题

读完之后，你至少要能回答这 12 个问题：

1. 应用启动时谁在初始化数据库和子系统？
2. task 写侧、读侧、详情聚合、规划分别在哪？
3. `task_service` 现在还保留它的原因是什么？
4. AI 对话工具调用是怎么落到 application/service 的？
5. AI planning 的 preview / confirm / replan 分别由谁组织？
6. mobile dashboard 的聚合 owner 是谁？
7. `advanced_features` 退场后，原有职责现在落到哪些正式域路由？
8. `/api/search` 与 `/api/search/fulltext` 的边界分别是什么？为什么历史 `/api/search/legacy` 可以删除？
9. 邮件子系统的 facade 和子包实现如何分层？
10. 哪些测试是在锁架构边界，而不是只锁业务行为？
11. 现在哪几个模块仍然明显偏厚？
12. 如果下一轮继续删兼容层，顺序应该是什么？

## 3. 推荐阅读顺序

### 第一轮：20-30 分钟，先建立地图

只读这些文件，不深挖实现：

1. `main.py`
2. `config.py`
3. `models/schemas.py`
4. `docs/ARCH_IMPLEMENTATION_PROGRESS_2026-06-13.md`
5. `docs/ARCH_COMPAT_BOUNDARY_CATALOG_2026-06-13.md`
6. `frontend/package.json`

这一轮的目标不是记住细节，而是确认：

- 应用生命周期怎么启动
- router 总装配长什么样
- 当前“正式 owner”和“兼容入口”分别是谁
- 前后端、数据库、AI、邮件、同步都在系统里

### 第二轮：后端主骨架

按这个顺序读：

1. `main.py`
2. `services/bootstrap_service.py`
3. `services/task_db_schema.py`
4. `models/schemas.py`
5. `application/task_actions.py`
6. `routers/task_manager.py`

这一轮你要搞清楚：

- 应用启动时初始化链是什么
- schema owner 已不在 `task_service`
- task router 现在先过 application，再进分拆后的 task service

读完后，你应该能画出：

```text
main.py
-> bootstrap_service
-> routers/*
-> application/*
-> split services
```

## 4. 第三轮：task 领域主链

这是当前最重要的一轮。

按这个顺序读：

1. `services/task_command_service.py`
2. `services/task_query_service.py`
3. `services/task_detail_service.py`
4. `services/task_planning_service.py`
5. `services/task_service.py`

阅读重点：

### 4.1 写侧

看 `task_command_service.py`：

- `add_task`
- `update_task`
- `complete_task`
- `delete_task`
- `batch_*`

这就是 task 主写侧 owner。

### 4.2 读侧

看 `task_query_service.py`：

- `get_task_by_id`
- `get_all_tasks`
- `get_pending_tasks`
- `get_weekly_plan`

这就是 task 领域列表/过滤/统计读侧。

### 4.3 详情聚合

看 `task_detail_service.py`：

- task
- notes
- subtasks
- pomodoro
- weekly neighbors

它已经不是普通 query，而是跨域 detail read model。

### 4.4 规划

看 `task_planning_service.py`：

- 时间归一
- analyze
- daily plan
- 辅助时间函数

### 4.5 compat facade

最后才看 `task_service.py`。

你要带着这个问题读：

- 哪些函数只是转发？
- 它为什么还留着？
- 哪些外部旧导入可能还需要它？
- 为什么 `init_db()` 在仓库内已经只剩废弃告警测试意义？
- 为什么它已经不再承担 split service 的 `DB_PATH` 同步职责？
- 为什么一些历史 planning helper 已经不再由它导出？
- 为什么它现在只该出现在单独的 compat 测试里？

不要再把它当作仓库内部主实现。

## 5. 第四轮：task 周边领域

按这个顺序读：

1. `services/tag_service.py`
2. `services/subtask_service.py`
3. `services/pomodoro_service.py`
4. `services/note_service.py`
5. `services/habit_service.py`
6. `services/calendar_sync_service.py`
7. `services/notification_service.py`
8. `services/dashboard_query_service.py`
9. `services/mobile_query_service.py`
10. `services/runtime_state_service.py`
11. `services/runtime_log_service.py`

这一轮的目标：

- 看哪些是领域能力
- 看哪些是聚合查询
- 看哪些是 runtime 基础设施

特别注意两点：

1. `dashboard_query_service` 已从 task query 中独立出来
2. `mobile_query_service` 只做移动端快照聚合，不再直接写 task/habit SQL

## 6. 第五轮：router 边界

先按正式路径读，再看兼容路径。

### 正式路径

1. `routers/task_manager.py`
2. `routers/search.py`
3. `routers/fulltext_search.py`
4. `routers/tags.py`
5. `routers/subtasks.py`
6. `routers/pomodoro.py`
7. `routers/calendar.py`
8. `routers/task_detail.py`
9. `routers/dashboard.py`
10. `routers/mobile.py`
11. `routers/sync.py`
12. `routers/chat.py`
13. `routers/ai_planning.py`

### 兼容路径

当前已无 router 级兼容路径。

历史 `routers/advanced_features.py`、`routers/file_search.py`、`POST /api/search/legacy` 与 `/api/advanced/*` 已删除。

阅读重点：

- 正式路由只承担什么
- compatibility alias 现在还承担什么
- 哪些路由是“主入口”
- 哪些路由只是“旧路径还活着”

当前你应该形成这样的判断：

```text
/api/search            -> search router
/api/search/fulltext   -> fulltext_search router

/api/tags ...          -> formal domain routers
```

## 7. 第六轮：application 层

现在 application 层已经值得单独读。

建议顺序：

1. `application/task_actions.py`
2. `application/planning_actions.py`
3. `application/dashboard_actions.py`
4. `application/mobile_actions.py`
5. `application/sync_actions.py`
6. `application/tag_actions.py`
7. `application/subtask_actions.py`
8. `application/pomodoro_actions.py`
9. `application/calendar_actions.py`
10. `application/task_detail_actions.py`
11. `application/ai_tools.py`
12. `application/mail_actions.py`
13. `application/advanced_actions.py`

这一轮重点看：

- router 和 AI tool dispatch 现在如何共享内部用例
- 哪些地方 application 层在做编排、参数归一、结果补查
- `advanced_actions.py` 现在为什么只是 compatibility aggregator
- 为什么它在仓库内已经只剩 compat 测试覆盖面
- 为什么它也应该只出现在专门的 compat 测试里？

## 8. 第七轮：搜索、下载、沙盒、安全

按这个顺序读：

1. `application/ai_tools.py`
2. `services/unified_search_service.py`
3. `services/fulltext_search_service.py`
4. `services/download_service.py`
5. `services/sandbox_service.py`
6. `services/security_service.py`
7. `services/time_service.py`

重点：

- unified search 现在只负责统一搜索聚合
- fulltext owner 已独立，不再经过 unified search compat wrapper
- 下载、沙盒、安全三者共同构成高风险执行边界

## 9. 第八轮：AI 系统

AI 现在要分成两条线读。

### 对话智能体线

1. `routers/chat.py`
2. `services/ai_service.py`
3. `application/ai_tools.py`

重点：

- tool schema
- tool dispatch
- 流式对话
- code interpreter / shell 边界
- conversation 持久化

### planning 线

1. `routers/ai_planning.py`
2. `application/planning_actions.py`
3. `services/ai_planning_service.py`
4. `services/ai_planning_preview_service.py`
5. `services/ai_planning_variant_service.py`
6. `services/ai_planning_replan_service.py`

重点：

- preview / confirm / replan 生命周期
- runtime state 如何持久化 preview
- variant plan owner 和 replan owner 已怎么拆开

## 10. 第九轮：邮件子系统

邮件已经是一个完整子系统，要单独读。

建议顺序：

1. `routers/mail.py`
2. `routers/mail_api.py`
3. `routers/mail_portal.py`
4. `services/mail_service.py`
5. `services/mail/facade.py`
6. `services/mail/runtime_env.py`
7. `services/mail/schema.py`
8. `services/mail/accounts.py`
9. `services/mail/threads.py`
10. `services/mail/drafts.py`
11. `services/mail/sync.py`
12. `services/mail/automation.py`
13. `services/mail/parsing.py`
14. `services/mail/runtime.py`
15. `services/mail/utils.py`

核心问题：

- `mail_service.py` 为什么还保留
- `services/mail/facade.py` 对外暴露什么
- `services/mail/runtime_env.py` 为什么存在，以及它如何承接测试注入
- 真正的子系统实现分散在哪些文件

## 11. 第十轮：前端

按这个顺序读：

1. `frontend/src/main.jsx`
2. `frontend/src/App.jsx`
3. `frontend/src/pages/*.jsx`
4. `frontend/src/components/*.jsx`
5. `frontend/src/services/api.js`

前端阅读重点不是视觉，而是：

- 哪些页面还在消费 legacy 路径
- 哪些页面已经可以切到正式域路径
- 搜索、advanced、task、mail 几条后端链怎么被前端命中

## 12. 最后一轮：测试

优先读这些：

1. `test/test_task_application.py`
2. `test/test_planning_application.py`
3. `test/test_mobile_application.py`
4. `test/test_sync_application.py`
5. `test/test_domain_routers.py`
6. `test/test_search_routers.py`
7. `test/test_architecture_guards.py`
8. `test/test_task_command_service.py`
9. `test/test_task_query_service.py`
10. `test/test_task_planning_service.py`
11. `test/test_runtime_state_service.py`
12. `test/test_ai_planning_flow.py`
13. `test/test_mail_automation.py`

阅读重点：

- 哪些测试在锁业务行为
- 哪些测试在锁 owner 边界
- 哪些测试是在防架构倒退

当前最有价值的架构护栏测试：

- `test/test_architecture_guards.py`
- `test/test_search_routers.py`
- `test/test_domain_routers.py`

## 13. 现在最值得重点关注的设计问题

读代码时重点盯住这几类问题：

1. `task_service.py` 仍然公开面偏宽，但已经不是内部主链
2. `services/ai_service.py` 和 `services/ai_planning_service.py` 仍然偏厚
3. `mail_service.py` 仍然保留 facade 存在感
4. AI 兼容工具别名 `local_file_search` 仍保留，但正式名已切到 `local_unified_search`
5. mail runtime 注入虽然已从 compat 桥迁走，但 facade 测试覆盖点仍需要继续治理
6. `task_service` 已不再承担路径同步桥，但转发面仍偏宽
7. `task_service` 和 `advanced_actions` 的测试使用面已经被收口到单独 compat 测试
8. 部分旧文档和 README 还停留在重构前的判断

## 14. 一个最省时间的阅读策略

如果你要在最短时间读通当前系统，建议直接按下面这个列表走：

1. `main.py`
2. `services/bootstrap_service.py`
3. `application/task_actions.py`
4. `services/task_command_service.py`
5. `services/task_query_service.py`
6. `services/task_detail_service.py`
7. `services/task_planning_service.py`
8. `services/task_service.py`
9. `routers/search.py`
10. `routers/fulltext_search.py`
11. `routers/tags.py`
12. `application/ai_tools.py`
13. `services/fulltext_search_service.py`
14. `services/ai_service.py`
15. `services/ai_planning_service.py`
16. `services/mail_service.py`
17. `services/mail/facade.py`
18. `services/mail/runtime_env.py`
19. `test/test_architecture_guards.py`

走完这 19 个文件，你会先得到现在的真实骨架，再决定去深挖哪个子系统。
