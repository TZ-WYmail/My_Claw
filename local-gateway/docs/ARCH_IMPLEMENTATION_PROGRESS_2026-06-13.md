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

### 1.10 task planning 与 preview state 治理

已完成：

- 新建 `services/task_planning_service.py`
- 新建 `services/ai_planning_preview_service.py`
- 新建 `services/ai_planning_variant_service.py`
- 新建 `services/ai_planning_replan_service.py`
- 新建 `services/runtime_log_service.py`
- 新建 `services/dashboard_query_service.py`
- 将 task planning 相关辅助职责从 `task_command_service` 中拆出：
  - 时间归一
  - weekday 计算
  - 批量 analyze
  - 每日计划生成
  - 可读时间摘要
- 将 AI planning preview/replan 相关预览生命周期职责从 `ai_planning_service` 中继续拆出：
  - preview id 生成
  - task normalize
  - variant capacity 定义
  - preview 持久化与确认读取
  - variant task schedule 映射
  - 冲突链提取
  - replan context 构建
- 将 AI planning variant 计划构建职责从 `ai_planning_service` 中继续拆出：
  - variant scheduling strategy
  - 日容量分配
  - deep work / admin block 排程
  - overload / infeasible / unslotted 风险汇总
- 将 AI planning replan 职责从 `ai_planning_service` 中继续拆出：
  - LLM 冲突链重排请求
  - JSON 解析与结果补默认值
  - fallback 重排建议
  - suggestion accept/apply
- 将 runtime 杂项记录写路径从 `task_service` 中继续拆出：
  - download history 写入/更新
  - operation log 写入
- `application/task_actions.py` 的批量 preview/create 分析主链改为直接走 `task_planning_service`
- 将 dashboard/history 查询从 `task_query_service` 中继续拆出：
  - dashboard stats
  - download history 查询
  - operation logs 查询
- `application/dashboard_actions.py` 主链改为直接走 `dashboard_query_service`
- 在 `services/runtime_state_service.py` 中新增 planning preview 存储能力
- `services/ai_planning_service.py` 的 preview/confirm 主链改为使用 runtime state 持久化 preview
- `services/ai_planning_service.py` 的 preview/confirm/replan 主链已开始委托 `ai_planning_preview_service`
- `services/ai_planning_service.py` 的 variant plan 生成已开始委托 `ai_planning_variant_service`
- `services/ai_planning_service.py` 的 replan 主链已开始委托 `ai_planning_replan_service`

当前结果：

- `task_command_service` 已明显向纯 command 侧收缩
- task planning 已形成独立服务边界
- planning preview 不再依赖进程内 `_planning_previews` 作为主状态源
- confirm 成功后会清理已消费的 preview state
- preview 生命周期与重排上下文已形成独立服务边界
- variant plan 构建已形成独立服务边界
- replan 编排与建议应用已形成独立服务边界
- `task_service` 在生产代码中的跨域写侧职责进一步收缩
- `task_query_service` 在主调用链中的跨域 dashboard/history 查询职责进一步收缩
- `ai_planning_service` 继续保留高层公开入口编排

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
- `services/task_planning_service.py`
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
- `test/test_task_planning_service.py`
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
- `services/runtime_state_service.py`
- `services/task_planning_service.py`
- `services/ai_planning_preview_service.py`
- `services/ai_planning_variant_service.py`
- `services/ai_planning_replan_service.py`
- `services/runtime_log_service.py`
- `services/dashboard_query_service.py`

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
- `test/test_task_planning_service.py`
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
- phase-6 task planning / preview state 回归一组：`68` 个用例通过，`4` 个按测试设计跳过

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

### 5.5 planning preview 已从内存态转为 runtime state

现在 `ai_planning_service` 的 preview/confirm 主链不再依赖进程内字典：

- preview 会持久化到 runtime state
- confirm 会读取持久态 preview
- 成功确认后会删除已消费 preview

这解决了单进程内存状态的脆弱性，但还没有进一步做容量治理、后台清理策略和更细的状态建模。

### 5.6 preview 生命周期已形成独立 owner

现在 preview/confirm/replan 的状态编排不再散落在 `ai_planning_service` 内部：

- `ai_planning_preview_service` 持有 preview 生命周期辅助逻辑
- `ai_planning_service` 主要保留高层 planning 编排与 LLM 冲突重排
- 预览持久化、确认读取、冲突链提取开始有单一职责边界

这一步的价值不是“文件变多”，而是避免 preview 逻辑和规划策略继续绑定在同一个巨石 service 里。

### 5.7 variant 计划构建已形成独立 owner

现在 variant plan 的计算与排程细节不再直接堆在 `ai_planning_service` 内：

- `ai_planning_variant_service` 持有 variant strategy 与 daily plan 构建
- `ai_planning_preview_service` 持有 preview 生命周期
- `ai_planning_service` 主要保留高层 orchestration 与 LLM 冲突重排

这让后续继续拆分规则引擎、容量策略、日历约束时，不必再同时修改一个巨石模块。

### 5.8 replan 编排已形成独立 owner

现在 replan 的建议生成与应用不再直接堆在 `ai_planning_service` 内：

- `ai_planning_replan_service` 持有 LLM 重排、fallback、accept/apply
- `ai_planning_preview_service` 持有 preview 生命周期
- `ai_planning_variant_service` 持有 variant plan 构建

这让 `ai_planning_service` 更接近 facade/orchestrator，而不是继续膨胀成单文件规则中心。

### 5.9 task facade 的跨域职责继续退场

现在生产代码里，`task_service` 不再承担下载记录与操作日志写入：

- `runtime_log_service` 持有 download history / operation log 写侧
- `download_service` / `shortcut_service` 已改走新服务
- `application.task_actions` 的 planning 分析主链已直接走 `task_planning_service`

当前生产代码里保留对 `task_service` 的直接依赖，基本只剩数据库初始化入口。

### 5.10 dashboard/history 查询已形成独立 owner

现在 dashboard、download history、operation logs 查询不再由 `task_query_service` 直接承载主调用链：

- `dashboard_query_service` 持有 dashboard/history 查询实现
- `application.dashboard_actions` 已切换到新服务
- `task_query_service` 仅保留兼容转发，便于渐进退场

这一步让 task query 边界更接近“任务领域读侧”，而不是继续混装仪表盘与运行历史查询。

## 6. 仍然存在的主要问题

### 6.1 `mobile` 的主坏味道已收口，但移动端聚合查询仍偏临时

已经解决：

- router 内直接写 SQL
- router 内直接操作离线同步队列
- router 依赖其他 router 私有函数

仍待优化：

- `services/mobile_service.py` 仍是移动端聚合查询容器，不是稳定领域服务
- 后续应继续把 task / habit / pomodoro 查询口做成更清晰的领域查询接口

### 6.2 状态所有权开始收口，但还没有真正治理完成

虽然主调用链开始收口，但以下状态仍未明确统一归属：

- SQLite 持久状态
- JSON / JSONL 文件状态
- 内存缓存
- replan 这类短生命周期状态的更细粒度治理
- 同步队列状态
- push token / device runtime 状态

已经改善：

- planning preview 已从进程内状态迁到 runtime state

### 6.3 service 层仍然偏“巨石化”

尤其是：

- `services/ai_planning_service.py`
- `services/task_service.py`
- `services/mail_service.py`
- `services/voice_service.py`

其中：

- `task_service` 已不再是主实现，但兼容层仍偏厚
- `task_command_service` 已进一步收缩，但仍保留一部分 compatibility helper 转发
- `services/task_planning_service.py` 已拆出，但后续还可以继续细化 planning domain
- `services/ai_planning_service.py` 已收出 preview lifecycle、variant builder、replan apply，但仍承担公开 planning 聚合入口
- `task_query_service` 仍保留一层 compatibility wrapper，尚未完全退成纯 task 读侧

问题不再是“有没有 application 层”，而是 service 内部仍承担过多职责。

### 6.4 前后端命名与业务域仍未完全对齐

例如：

- `advanced_features` 仍是兼容性命名，不是稳定业务域命名
- 一些 router 还是按“功能堆叠”组织，而不是按领域组织
- `task_service` 作为 facade 仍继续暴露较大的兼容面，后续需要明确退场边界

## 7. 建议的下一步实施顺序

建议按以下顺序继续：

1. 明确 `task_service` 初始化职责是否下沉到独立 bootstrap/db service
2. 继续压缩 `task_command_service` 的 compatibility helper 面积
3. 评估 `task_query_service` compatibility wrapper 的删除时机
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
