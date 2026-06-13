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

### 1.11 bootstrap 与 mobile query owner 收口

已完成：

- 新建 `services/bootstrap_service.py`
- 新建 `services/mobile_query_service.py`
- `main.py` 启动初始化主链改为直接调用 `bootstrap_service.init_db()`
- `task_service.init_db()` 收缩为兼容入口，转发到 `bootstrap_service`
- `application/mobile_actions.py` 的 mobile dashboard 主链改为直接依赖 `mobile_query_service`
- `services/mobile_service.py` 收缩为兼容 wrapper，保留旧调用面

当前结果：

- 数据库/bootstrap 初始化不再继续挂在 `task_service` 这个 task facade 名下
- mobile dashboard 聚合查询已有更明确 owner，router/application 主链不再依赖临时聚合容器
- `task_service` 与 `mobile_service` 都进一步退向 compatibility facade

### 1.12 task schema owner 与 compat 继续收缩

已完成：

- 新建 `services/task_db_schema.py`
- `bootstrap_service` 不再从 `task_service` 导入 schema
- `task_service` 删除内嵌 task schema 定义，继续向纯 facade 收缩
- `task_query_service` 删除 dashboard/download/logs 兼容转发，仅保留 task 领域读侧
- `task_command_service` 删除未被主链使用的 planning helper shim

当前结果：

- bootstrap 初始化已不再反向依赖 task facade
- task schema 的 owner 已从 compatibility facade 中剥离
- `task_query_service` 更接近纯 task-domain query service
- `task_command_service` 的兼容面进一步变薄

### 1.13 mobile dashboard 聚合继续下沉到领域查询

已完成：

- `task_query_service` 新增通用任务区间查询与计数接口
- `habit_service` 新增“习惯 + 今日打卡状态”读接口
- `mobile_query_service` 不再直接写 task/habit SQL，改为编排领域查询
- 新增 `test/test_mobile_query_service.py` 锁定 mobile dashboard 聚合行为

当前结果：

- mobile dashboard 仍保留一个移动端聚合 owner
- 但聚合 owner 已不再直接碰 tasks/habits 表
- task / habit 的读侧职责更清晰，mobile 只负责组合视图数据

### 1.14 task detail 聚合拆出独立 owner

已完成：

- 新建 `services/task_detail_service.py`
- `application/advanced_actions.py` 的 task detail 主链改为直接依赖 `task_detail_service`
- `task_query_service.get_task_detail()` 收缩为兼容转发
- `task_service.get_task_detail()` 继续保留 facade 转发

当前结果：

- task detail 这类跨 task/note/subtask/pomodoro 的聚合不再继续堆在 `task_query_service`
- `task_query_service` 更接近任务领域读侧
- `advanced_actions` 主链不再依赖继续膨胀的 task query 容器

### 1.15 advanced application 继续按领域拆分

已完成：

- 新建 `application/tag_actions.py`
- 新建 `application/subtask_actions.py`
- 新建 `application/pomodoro_actions.py`
- 新建 `application/calendar_actions.py`
- 新建 `application/task_detail_actions.py`
- `routers/advanced_features.py` 主链改为直接依赖各领域 action owner
- `application/advanced_actions.py` 收缩为兼容聚合壳

当前结果：

- `advanced_features` 路由内部已不再继续把所有增强能力都压到单一 application 模块
- tag / subtask / pomodoro / calendar / task-detail 已有独立 application 落点
- 后续即使还暂时保留 `/advanced/*` 命名，也不会继续把实现边界绑死在 `advanced_actions.py`

### 1.16 正式域 router 已补齐

已完成：

- 新建 `routers/tags.py`
- 新建 `routers/subtasks.py`
- 新建 `routers/pomodoro.py`
- 新建 `routers/calendar.py`
- 新建 `routers/task_detail.py`
- `main.py` 已注册正式域 router
- 新增 `test/test_domain_routers.py` 锁定新路由对 application owner 的调用面

当前结果：

- `/api/advanced/*` 不再是 tags/subtasks/pomodoro/calendar/task-detail 的唯一 HTTP 入口
- 正式域路由已经存在，后续可以把 `advanced_features` 继续退成纯兼容转发
- 路由层迁移不再依赖一次性改前端或一次性删除旧路径

### 1.17 advanced_features 已明确标注为兼容路由

已完成：

- `routers/advanced_features.py` 文件头已明确声明其为历史兼容入口
- 文档与代码对“正式域路由 vs 兼容路由”的角色已经对齐

当前结果：

- 新逻辑继续挂在 `/api/advanced/*` 上的风险进一步降低
- 后续收缩这组旧路径时，不会再和“它是不是主入口”混淆

### 1.18 task facade 的测试依赖面继续收缩

已完成：

- 一批 task 相关测试 fixture 改为直接依赖 `bootstrap_service`
- 一批 task 写侧测试改为直接依赖 `task_command_service`
- 一批 task detail 测试改为直接依赖 `task_detail_service`
- `task_service` 在测试中的角色继续向“兼容入口”而不是“默认 owner”收缩

当前结果：

- `task_service.init_db()` 不再是所有 task 相关测试的默认初始化入口
- `task_service.DB_PATH` 的 patch 面积进一步缩小
- 后续继续压缩 `task_service` facade 时，测试阻力会更低

### 1.19 mobile / task detail compat 继续退场

已完成：

- 删除 `services/mobile_service.py`
- 删除 `task_query_service.get_task_detail()` compat 转发
- `task_service.get_task_detail()` 改为直接转发到 `task_detail_service`
- `task detail` 相关测试改为直接依赖 `task_detail_service`

当前结果：

- mobile dashboard 的旧 wrapper 已不再保留
- `task_query_service` 更接近纯 task-domain read service
- task detail 的 owner 已只剩 `task_detail_service` 与 `task_service` facade 兼容入口

### 1.20 测试初始化与 facade 依赖继续收缩

已完成：

- `test/test_runtime_state_service.py` 改为直接通过 `bootstrap_service.init_db()` 初始化
- `test/test_ai_planning_flow.py` 改为直接通过 `bootstrap_service.init_db()` 初始化
- `test/test_unified_search.py` 改为直接依赖 `bootstrap_service` 与 `task_command_service`
- `test/test_phase_mvp_updates.py` 改为直接依赖 `task_command_service` / `task_query_service`
- `test/test_mobile_query_service.py` 的 fixture 和测试变量改为显式使用 `task_command_service`
- `test/test_services.py` 中 task 创建/查询测试改为直接依赖 `task_command_service` / `task_query_service`

当前结果：

- `task_service.init_db()` 在测试中的默认入口角色继续减弱
- `task_service` 在测试里的 owner 误导性进一步下降
- `bootstrap_service` 作为系统初始化 owner 的语义更稳定
- 后续继续瘦身 `task_service` facade 时，测试迁移成本会更低

### 1.21 `task_service` 已退出仓库内部主链依赖

已完成：

- 清理仓库内部剩余对 `task_service` 的直接调用与测试主路径依赖
- `services/task_service.py` 调整为更明确的 compatibility facade 说明
- facade 的 `DB_PATH` 同步逻辑补齐到 `task_planning_service`

当前结果：

- 当前仓库内部的 application / services / routers / 主测试链已不再直接依赖 `task_service`
- `task_service` 的保留价值已进一步收敛到外部历史导入路径与兼容转发
- 后续如果继续退场，主要问题已从“拆业务实现”转为“处理历史调用面”

### 1.22 搜索与全文索引路由 owner 已分离

已完成：

- `main.py` 注册 `routers/fulltext_search.py` 作为正式全文索引路由 owner
- `routers/file_search.py` 不再承载 `/api/search/fulltext` 与索引管理端点
- `routers/file_search.py` 只保留统一搜索主入口与 `/api/search/legacy` 兼容入口
- 新增 `test/test_search_routers.py` 锁定 unified search / legacy search / fulltext search 的路由归属

当前结果：

- 全文索引接口不再继续挂在历史命名的 `file_search` 路由模块里
- `/api/search/legacy` 的兼容边界更清晰
- 搜索路由层的正式 owner 与兼容 owner 已开始分离

### 1.23 unified search 正式 owner 已从 `file_search` 命名中分离

已完成：

- 新建 `routers/search.py` 承接 `POST /api/search`
- `routers/file_search.py` 收缩为只保留 `POST /api/search/legacy`
- `main.py` 改为分别注册 `search` / `file_search` / `fulltext_search`
- `api_info` 中的搜索入口说明改为 `search` 与 `search_legacy`

当前结果：

- `file_search` 不再继续承载统一搜索主入口
- 搜索主路径、legacy 文件搜索、全文索引三者已形成更清晰的 owner 分层
- 后续如果删除 legacy 文件搜索入口，不需要再改 unified search 主入口模块

### 1.24 unified search 中的全文索引 compat 函数已删除

已完成：

- 删除 `services/unified_search_service.py` 中对全文索引服务的兼容包装函数
- 全文索引主链统一收口到 `services/fulltext_search_service.py`
- 路由层继续直接依赖 `routers/fulltext_search.py` -> `services/fulltext_search_service.py`

当前结果：

- `unified_search_service` 回到统一搜索聚合 owner 的单一职责
- 全文索引的正式 owner 不再经过一层无内部调用的 compat 包装
- 搜索子系统内的正式路径和兼容路径边界更清晰

### 1.25 `advanced_features` 已收缩为正式域 router 的兼容别名聚合

已完成：

- `routers/advanced_features.py` 不再重复维护 tags/subtasks/pomodoro/calendar/task-detail 的端点函数
- 兼容路由改为直接 `include_router(...)` 复用正式域 router
- `/api/advanced/*` 继续可用，但实现 owner 已完全回到正式域 router

当前结果：

- `advanced_features` 不再继续持有一份平行的路由实现
- 正式域 router 与 advanced 兼容路径之间不再存在重复的 handler 维护面
- 后续删除 `/api/advanced/*` 时，主要工作会变成路径兼容治理，而不是清理重复实现

### 1.26 架构护栏测试已补上

已完成：

- 新增 `test/test_architecture_guards.py`
- 锁定仓库内部代码不再直接导入 `services.task_service`
- 锁定 `advanced_features` 只作为正式域 router 的兼容别名聚合
- 锁定 unified search / legacy search / fulltext search 的路由 owner 分层

当前结果：

- 这几轮架构收口不再只依赖文档约束
- 后续如果有人把主链重新挂回 `task_service`、把 legacy/search/advanced 边界重新混回去，测试会直接失败

### 1.27 阅读与结构文档已同步到当前架构

已完成：

- 重写 `docs/CODE_READING_GUIDE_2026-06-12.md`
- 重写 `docs/PROJECT_STRUCTURE_OVERVIEW_2026-06-12.md`
- 将阅读顺序、结构说明、owner 判断、compat 边界同步到 2026-06-13 当前代码状态

当前结果：

- 旧文档不再继续把 `task_service`、`file_search`、`advanced_features` 描述成主实现入口
- 新读者可以直接按当前 application / split services / formal routers / compat routers 的结构理解代码
- 文档层与代码层的架构判断已经基本对齐

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
- `services/bootstrap_service.py`
- `services/mobile_query_service.py`
- `services/task_db_schema.py`
- `services/task_detail_service.py`
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
- `test/test_mobile_query_service.py`
- `application/tag_actions.py`
- `application/subtask_actions.py`
- `application/pomodoro_actions.py`
- `application/calendar_actions.py`
- `application/task_detail_actions.py`
- `routers/tags.py`
- `routers/subtasks.py`
- `routers/pomodoro.py`
- `routers/calendar.py`
- `routers/task_detail.py`
- `test/test_domain_routers.py`

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
- `services/bootstrap_service.py`
- `services/mobile_query_service.py`
- `services/task_db_schema.py`
- `services/habit_service.py`
- `services/task_detail_service.py`
- `main.py`
- `application/advanced_actions.py`
- `routers/advanced_features.py`
- `main.py`

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

### 5.11 bootstrap 初始化已形成独立 owner

现在数据库初始化与基础子系统建表不再由 `task_service` 主持：

- `bootstrap_service` 持有 schema 初始化与子模块建表编排
- `main.py` 已切到新 owner
- `task_service.init_db()` 仅保留兼容转发

这一步的意义在于把“系统启动基础设施”从“任务领域 facade”里拿出来，避免继续扩大 task 领域的表面职责。

### 5.12 mobile dashboard 查询 owner 更清晰

现在 mobile dashboard 聚合查询不再由 `mobile_service` 这个泛名入口承载主调用链：

- `mobile_query_service` 持有移动端 dashboard 聚合查询
- `application.mobile_actions` 已改为直接依赖查询 owner
- `mobile_service` 仅保留兼容转发

这一步让 mobile 侧后续继续拆 task/habit/pomodoro 聚合时，有了明确的读侧落点。

### 5.13 task schema owner 已脱离 facade

现在 task 表与运行期基础表的 DDL 不再内嵌在 `task_service`：

- `task_db_schema.py` 持有 schema 定义
- `bootstrap_service` 直接依赖 schema owner
- `task_service` 不再作为 bootstrap 的隐式依赖

这一步解决的不是“文件大小”本身，而是避免基础设施初始化继续耦合到兼容 facade。

### 5.14 task query compat wrapper 已明显变薄

现在 `task_query_service` 已不再兼容承载 dashboard/history/log 查询：

- 仪表盘与运行历史查询完全回到 `dashboard_query_service`
- `task_query_service` 仅保留 task 读侧查询与 task detail 聚合

这让 query 边界从“任务加一堆旁路查询”继续收敛到“任务领域读模型”。

### 5.15 mobile 聚合已从直接查表转为领域查询编排

现在 `mobile_query_service` 虽然仍是聚合 owner，但它已经不再直接承载 task/habit SQL：

- task 列表与计数来自 `task_query_service`
- habit 今日打卡视图来自 `habit_service`
- mobile query service 只保留 dashboard snapshot 的组合职责

这一步的价值在于后续继续拆 mobile 侧读模型时，不需要先从“移动端私有 SQL”回退到领域能力。

### 5.16 task detail 聚合已形成独立 owner

现在 task detail 不再被视为普通 task query 的一部分：

- `task_detail_service` 持有跨 task/note/subtask/pomodoro 的聚合视图
- `advanced_actions` 已切到新 owner
- `task_query_service` 仅保留兼容转发，便于平滑退场

这一步的意义在于把“任务列表/过滤查询”和“任务详情聚合视图”拆成不同的读模型边界。

### 5.17 advanced application 已从单文件聚合转为领域 action 组合

现在 `advanced_features` 的 application 层虽然还保留历史兼容入口文件，但主实现已开始分域：

- tags -> `application/tag_actions.py`
- subtasks -> `application/subtask_actions.py`
- pomodoro -> `application/pomodoro_actions.py`
- calendar -> `application/calendar_actions.py`
- task detail -> `application/task_detail_actions.py`

这一步的价值在于后续要改 `/advanced/*` 命名时，可以先改路由边界，而不用再先从一个混装 application 文件里拆实现。

### 5.18 advanced 历史路由已不再是唯一正式入口

现在 tags/subtasks/pomodoro/calendar/task-detail 已有正式域 router：

- `/api/tags`
- `/api/subtasks`
- `/api/pomodoro/*`
- `/api/calendar/*`
- `/api/tasks/{task_id}/detail`
- `/api/tasks/batch-update`

这意味着：

- `advanced_features` 已开始退成兼容命名层
- 后续删除 `/api/advanced/*` 时，不需要再和“补正式入口”绑成一次大改

### 5.19 advanced 兼容路由的角色已在代码中固定

现在 `routers/advanced_features.py` 不再只是架构文档里的“历史入口”，而是代码层面已明确标注为兼容路由。

这一步虽然不是大改实现，但它很重要，因为后续所有开发者都能从代码本身看到：

- `/api/advanced/*` 不是推荐主入口
- 正式域路径已经存在
- 旧路由的职责是兼容，而不是继续承接新增功能

### 5.20 task facade 的保留理由已更集中在兼容层

现在 `task_service` 的主要保留价值进一步收敛到：

- 历史导入路径
- 少量尚未迁完的测试 glue
- 兼容入口转发

这意味着后续如果还要继续瘦身 `task_service`，目标已经不再是“先拆业务逻辑”，而是继续迁掉剩余测试与旧调用面。

### 5.21 两个最薄 compat 点已实际删除

现在下面这两个兼容点已不再保留：

- `services/mobile_service.py`
- `task_query_service.get_task_detail()`

这说明兼容层收缩已经不再停留在“标记与规划”阶段，而是开始进入真实删除阶段。

## 6. 仍然存在的主要问题

### 6.1 `mobile` 的主坏味道已继续收口，但移动端聚合模型仍偏粗

已经解决：

- router 内直接写 SQL
- router 内直接操作离线同步队列
- router 依赖其他 router 私有函数

仍待优化：

- `mobile_query_service` 已改为编排领域查询，但 snapshot 仍是单一粗粒度模型
- 后续应继续评估是否需要拆成 today focus / habit summary / sync summary 等更稳定的移动端读模型

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
- `task_command_service` 已进一步收缩，但仍保留完整 task facade 兼容入口背后的转发压力
- `services/task_planning_service.py` 已拆出，但后续还可以继续细化 planning domain
- `services/ai_planning_service.py` 已收出 preview lifecycle、variant builder、replan apply，但仍承担公开 planning 聚合入口
- `task_query_service` 已基本回到 task 读侧，但 `task_service` 仍保留较宽 facade 面
- `advanced_actions` 对外命名仍然偏历史兼容入口，未按更稳定业务域拆包

问题不再是“有没有 application 层”，而是 service 内部仍承担过多职责。

### 6.4 前后端命名与业务域仍未完全对齐

例如：

- `advanced_features` 仍是兼容性命名，不是稳定业务域命名
- 一些 router 还是按“功能堆叠”组织，而不是按领域组织
- `task_service` 作为 facade 仍继续暴露较大的兼容面，后续需要明确退场边界

已经改善：

- `advanced_actions.py` 已不再是增强功能的单一实现 owner
- `routers/advanced_features.py` 下面的内部 application 落点已经开始按领域分拆
- 正式域 router 已存在，剩余问题主要是兼容路径与调用面迁移，不再是缺正式入口

## 7. 建议的下一步实施顺序

建议按以下顺序继续：

1. 让 `advanced_features` router 逐步收缩为纯兼容转发，避免新逻辑继续挂在旧路径上
2. 继续压缩 `task_service` 仍保留的宽兼容入口，识别可以直接改主调用链的旧依赖
3. 评估 `ai_planning_service` 的公开入口中还能继续下沉的 orchestration 片段
4. 清点剩余 facade/compat wrapper 的保留理由与退场顺序
5. 评估 mobile dashboard snapshot 是否需要拆成更稳定的移动端读模型

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
