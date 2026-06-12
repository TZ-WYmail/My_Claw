# 架构重整实施进度（2026-06-13）

更新时间：2026-06-13  
目标：记录当前已经完成的 application/use-case 层落地情况，便于验收与继续推进

## 1. 本轮已完成内容

### 1.1 AI 内部工具调用链收口

已完成：

- 新建 `application/ai_tools.py`
- 新建 `application/task_actions.py`
- `services/ai_service.py` 不再通过 HTTP 回打自身 `/api/...`

当前主链：

```text
AI runtime
-> application.ai_tools
-> application.task_actions / service
```

已收口工具：

- `local_task_manager`
- `batch_task_manager`
- `local_safe_downloader`
- `local_file_search`
- `local_sandbox_executor`
- `local_job_status`

### 1.2 task 主链收口

已完成：

- `routers/task_manager.py`
  - `POST /task`
  - `POST /task/batch`
  - `PUT /task/{task_id}`
- 统一改为走 `application.task_actions`

当前主链：

```text
HTTP task router
-> application.task_actions
-> task_service
```

### 1.3 AI planning 主链收口

已完成：

- 新建 `application/planning_actions.py`
- `routers/ai_planning.py` 改为只做请求接入与响应返回

已收口动作：

- `decompose`
- `plan`
- `plan/preview`
- `plan/confirm`
- `plan/replan`
- `plan/replan/accept`
- `estimate`
- `suggestions`
- `insights`

当前主链：

```text
HTTP ai_planning router
-> application.planning_actions
-> ai_planning_service
```

### 1.4 dashboard 查询主链收口

已完成：

- 新建 `application/dashboard_actions.py`
- `routers/dashboard.py` 改为调用 application 层

已收口查询：

- `GET /dashboard`
- `GET /download/history`
- `GET /logs`
- `GET /tasks/all`
- `GET /streak`

### 1.5 advanced_features 主链收口

已完成：

- 新建 `application/advanced_actions.py`
- `routers/advanced_features.py` 改为通过 application 层组织行为

已收口能力：

- 标签
- 子任务
- 番茄钟
- 日历事件/视图
- 批量任务更新
- 任务聚合详情

### 1.6 mail 主链收口

此前已完成：

- 新建 `application/mail_actions.py`
- `routers/mail_api.py`
- `routers/mail_portal.py`

### 1.7 mobile / sync / runtime state 主链收口

已完成：

- 新建 `application/mobile_actions.py`
- 新建 `application/sync_actions.py`
- 新建 `services/runtime_state_service.py`
- 新建 `services/mobile_service.py`
- 新建 `models/sync_models.py`
- `routers/mobile.py` 改为通过 application 层处理
- `routers/sync.py` 改为通过 application 层处理

已收口能力：

- mobile dashboard 聚合
- mobile quick action
- mobile voice task
- push token 注册/注销/测试
- mobile 离线队列批量写入与按设备查询
- sync 状态 / push / pull / full sync
- sync device 注册 / 心跳 / 列表
- sync offline queue 写入 / 查询 / 批量标记同步

额外完成：

- 去掉 `mobile -> routers.sync` 的反向依赖
- 将共享 sync 请求模型抽到 `models/sync_models.py`
- 为语音移动端入口补上 `services.voice_service.process_voice`

### 1.8 task 查询侧拆分

已完成：

- 新建 `services/task_query_service.py`
- 将 task 读路径从 `task_service` 中开始拆出
- `application/task_actions.py` 的查询动作改走 query service
- `application/dashboard_actions.py` 改走 query service
- `application/advanced_actions.py` 中的 task detail 改走 query service
- `services/ai_planning_service.py` 的历史任务/周计划/完成任务分析改走 query service
- `services/unified_search_service.py` 的 task 搜索改走 query service

当前结果：

- `task_service` 仍保留兼容入口
- 但主查询路径已经开始转向独立读服务
- command 与 query 的职责边界开始成形

### 1.9 task 命令侧拆分与兼容层收缩

已完成：

- 新建 `services/task_command_service.py`
- 将 task 写路径与时间规划辅助逻辑从 `task_service` 中拆出
- `services/task_service.py` 改为 task 领域兼容 facade
- facade 会同步 `DB_PATH` 到 command/query service，兼容既有测试与临时库注入方式

已切换到 command service 的主路径：

- `application/task_actions.py`
- `application/advanced_actions.py`
- `application/mobile_actions.py`
- `services/ai_planning_service.py`
- `services/voice_service.py`
- `services/webhook_service.py`
- `services/workflow_service.py`
- `services/mail/automation.py`

当前结果：

- `task_service` 不再承载 task 主业务实现
- task command / query 已形成两块独立实现
- 旧调用面仍可继续工作，但主入口已显式依赖 `task_command_service` / `task_query_service`

## 2. 本轮新增文件

- `application/task_actions.py`
- `application/planning_actions.py`
- `application/dashboard_actions.py`
- `application/advanced_actions.py`
- `application/mobile_actions.py`
- `application/sync_actions.py`
- `services/runtime_state_service.py`
- `services/mobile_service.py`
- `services/task_command_service.py`
- `services/task_query_service.py`
- `models/sync_models.py`
- `test/test_task_application.py`
- `test/test_planning_application.py`
- `test/test_dashboard_application.py`
- `test/test_advanced_application.py`
- `test/test_mobile_application.py`
- `test/test_sync_application.py`
- `test/test_runtime_state_service.py`
- `test/test_task_command_service.py`
- `test/test_task_query_service.py`

## 3. 本轮修改文件

- `application/ai_tools.py`
- `routers/task_manager.py`
- `routers/ai_planning.py`
- `routers/dashboard.py`
- `routers/advanced_features.py`
- `routers/mobile.py`
- `routers/sync.py`
- `application/task_actions.py`
- `application/advanced_actions.py`
- `application/mobile_actions.py`
- `services/voice_service.py`
- `services/unified_search_service.py`
- `services/ai_planning_service.py`
- `services/webhook_service.py`
- `services/workflow_service.py`
- `services/mail/automation.py`
- `services/task_service.py`

## 4. 回归验证结果

已通过：

- `test/test_ai_tool_application.py`
- `test/test_task_application.py`
- `test/test_planning_application.py`
- `test/test_dashboard_application.py`
- `test/test_advanced_application.py`
- `test/test_ai_planning_flow.py`
- `test/test_unified_search.py`
- `test/test_mail_application.py`
- `test/test_mail_accounts.py`
- `test/test_mail_runtime.py`
- `test/test_mail_sync.py`
- `test/test_mail_threads.py`
- `test/test_mail_drafts.py`
- `test/test_mail_automation.py`
- `test/test_task_command_service.py`
- `test/test_mobile_application.py`
- `test/test_sync_application.py`
- `test/test_runtime_state_service.py`
- `test/test_phase4.py`
- `test/test_habit_service.py`
- `test/test_pomodoro_service.py`

汇总：

- application 层新增/相关单测一组：`18` 个用例通过
- 既有相关回归一组：`44` 个用例通过
- mobile/sync/runtime 新增与相关回归一组：`34` 个用例通过，`4` 个按测试设计跳过
- task query 拆分与相关回归一组：`25` 个用例通过
- task command 拆分与主链回归一组：`34` 个用例通过
- workflow / webhook / automation 相关回归一组：`22` 个用例通过，`4` 个按测试设计跳过

未直接执行成功的测试：

- `test/test_api.py`
- `test/test_advanced_features.py`

原因：

- 这两组用例依赖本地已有服务监听 `http://localhost:8900`
- 当前执行环境未启动后端服务，因此失败原因为 `Connection refused`
- 这不是本轮代码逻辑失败

## 5. 现在已经改善的设计问题

### 5.1 入口层职责更清晰

router 不再继续承担“组织多个 service 的业务动作”。

### 5.2 application 层开始形成真实边界

当前 application 层已经不是空壳，开始承接：

- 行为编排
- 参数归一
- 成功后补查聚合数据
- 跨入口复用

### 5.3 AI 内部回打自身 HTTP 的关键路径已切断

这是本项目之前最不稳的一条主路径之一。

### 5.4 `task_service` 从业务实现转成兼容层

现在的 `task_service` 更接近 compatibility facade：

- 旧函数签名仍可用
- 真实命令实现下沉到 `task_command_service`
- 真实查询实现下沉到 `task_query_service`

这让后续继续删兼容层、改调用面时不会再同时承担“迁移调用方”和“维护两份逻辑”两种风险。

## 6. 仍然存在的主要问题

### 6.1 `mobile` 的主坏味道已收口，但移动端聚合查询仍偏临时

已经解决：

- router 内直接写 SQL
- router 内直接操作离线同步队列
- router 依赖其他 router 私有函数

仍待优化：

- `services/mobile_service.py` 仍是移动端聚合查询容器，不是稳定领域服务
- 后续应继续把 task / habit / pomodoro 查询口做成更清晰的领域查询接口

### 6.2 状态所有权还没有真正治理

虽然主调用链开始收口，但以下状态仍未明确统一归属：

- SQLite 持久状态
- JSON / JSONL 文件状态
- 内存缓存
- preview/replan 这类短生命周期状态
- 同步队列状态
- push token / device runtime 状态

### 6.3 service 层仍然偏“巨石化”

尤其是：

- `services/ai_planning_service.py`
- `services/task_service.py`
- `services/mail_service.py`
- `services/voice_service.py`

其中：

- `task_service` 已不再是主实现，但兼容层仍偏厚
- `task_command_service` 已独立，但内部还同时承担 CRUD、批量编排、时间解析、计划分析
- `services/ai_planning_service.py` 依然承担过多规划策略与临时状态管理

问题不再是“有没有 application 层”，而是 service 内部仍承担过多职责。

### 6.4 前后端命名与业务域仍未完全对齐

例如：

- `advanced_features` 仍是兼容性命名，不是稳定业务域命名
- 一些 router 还是按“功能堆叠”组织，而不是按领域组织
- `task_service` 作为 facade 仍继续暴露较大的兼容面，后续需要明确退场边界

## 7. 建议的下一步实施顺序

建议按以下顺序继续：

1. 继续拆 `task_command_service` 内部的 planning/normalization 辅助职责
2. 开始治理 planning preview/replan 的临时状态存放方式
3. 明确 `task_service` 兼容 facade 的退场范围与剩余调用方
4. 把 `mobile_service` 临时聚合查询继续下沉到稳定领域查询接口
5. 再处理 `advanced_features` 等兼容命名与页面/路由边界对齐

## 8. 当前判断

到今天为止，项目已经从：

```text
router / AI / portal 各自直接撞 service
```

开始转向：

```text
entrypoint
-> application/use-case
-> service
```

这说明 phase-2 已经不是纸面 planning，而是进入了可持续推进的真实实现阶段。
