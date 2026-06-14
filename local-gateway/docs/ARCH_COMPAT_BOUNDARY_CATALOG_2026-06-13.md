# 兼容层与边界清单（2026-06-14）

更新时间：2026-06-14
目的：给当前仍保留的 facade / compatibility wrapper / 历史命名入口建立清单、分类和后续收缩顺序

## 1. 当前判断原则

本清单只回答四件事：

1. 这个入口现在是不是主路径
2. 它为什么还要保留
3. 它的主要风险是什么
4. 后续应该按什么顺序收缩

不在这里讨论具体代码实现。

## 2. 当前仍活跃的兼容层分类

### 2.1 facade 类

- `application/advanced_actions.py`
- `services/task_service.py`
- `services/mail_service.py`

特点：

- 对外仍暴露较大公开面
- 内部真实实现已经拆到多个 service
- 主要价值是稳住旧调用面与测试注入方式

### 2.2 wrapper 类

- `task_service.init_db()`

特点：

- 本身不再拥有主实现
- 只保留转发与兼容职责
- 可以作为优先退场对象

### 2.3 命名兼容类

- `local_file_search`（AI tool 兼容别名；正式名已切到 `local_unified_search`）

特点：

- 主要问题不是逻辑重复，而是命名继续暴露旧结构判断
- 容易让后续开发围绕历史语义继续堆功能

## 3. 活跃兼容清单

### 3.1 `services/task_service.py`

分类：`必须短期保留`

当前作用：

- 保持历史任务导入路径与旧函数签名可用
- 为仓库外部旧调用保留兼容转发面
- 继续提供统一的兼容 facade，而不再承载仓库内部主链

当前问题：

- facade 面仍然偏宽
- 容易被误当 task 领域主实现
- 仍承担 split service 的 `DB_PATH` 同步责任

建议动作：

1. 保留 facade，但继续禁止新增仓库内部主链依赖它
2. 观察外部旧调用面是否仍需要 `task_service.init_db()` 与宽 facade 面
3. 条件成熟后，再评估公开废弃策略与进一步瘦身

### 3.2 `task_service.init_db()`

分类：`必须短期保留`

当前作用：

- 兼容历史初始化入口
- 真实 owner 已是 `bootstrap_service`
- 当前调用会显式发出 `DeprecationWarning`

当前问题：

- 容易让人误判“task 领域拥有系统初始化”

建议动作：

1. 生产启动保持只走 `bootstrap_service`
2. 继续观察是否仍有仓库外部历史调用依赖它
3. 条件成熟后再评估显式废弃或删除

### 3.3 `services/mail_service.py`

分类：`必须短期保留`

当前作用：

- 对邮件子系统提供统一公开面
- 为旧模块引用保留稳定导入路径
- 当前仓库内部主链已改为直接依赖 `services.mail.facade`

当前问题：

- 文件名容易掩盖真实主实现位于 `services/mail/*`
- facade 仍有较强存在感

建议动作：

1. 保留对外 facade
2. 在仓库内部继续禁止新增主链直接依赖 `services.mail_service`
3. 用 architecture guard 固化该边界
4. 在文档和新代码中明确 mail 主实现边界
5. 避免继续往 `mail_service.py` 堆新逻辑

### 3.4 `services/mail/compat.py`

分类：`已退场`

当前作用：

- 已由 `services/mail/runtime_env.py` 替代
- 旧的 runtime 反向桥接不再保留

当前问题：

- 通过 `services.mail_service` 反向找运行时对象会把内部实现重新绑回兼容 facade
- 容易让 mail 子模块把测试注入和生产 runtime 混成一层

建议动作：

1. 不再恢复 `services/mail/compat.py`
2. 统一改用 `services.mail.runtime_env`
3. 保持 tests 通过 `services.mail_service` 注入 runtime 覆盖点

### 3.5 `local_file_search` 工具别名

分类：`可进入观察期`

当前作用：

- 维持历史 AI tool 调用名称稳定
- 让旧调用方仍能命中统一搜索执行链

当前问题：

- 旧名称仍然强调“file search”，和当前统一搜索语义不一致
- 容易与已删除的 `POST /api/search/legacy` 混淆
- 正式工具名已经改为 `local_unified_search`，旧名只剩兼容意义

建议动作：

1. 新调用统一使用 `local_unified_search`
2. 旧 `local_file_search` 继续保留为兼容别名并发出废弃告警
3. 用 architecture guard 禁止仓库内部主链重新回流到旧名字
4. 观察是否还存在仓库外旧调用，再决定最终删除窗口

### 3.6 `application/advanced_actions.py`

分类：`可进入观察期`

当前作用：

- 为历史 `advanced` 概念保留稳定导入面
- 继续聚合 tags / subtasks / pomodoro / calendar / task detail 相关 action
- 当前仓库内部主链已直接依赖各领域 application action owner

当前问题：

- `advanced` 命名已经不再对应任何正式 HTTP 路由
- 容易让后续开发误判它仍是增强能力的正式 application 入口
- 会弱化按领域组织 action owner 的边界感

建议动作：

1. 保留兼容聚合壳，但不要再往里挂新主逻辑
2. 在仓库内部禁止新增主链直接依赖 `application.advanced_actions`
3. 继续让测试仅承担兼容覆盖，而不是把它当正式 owner

## 4. 推荐收缩顺序

按风险和收益，建议顺序如下：

1. 继续观察 `task_service.init_db()` 的废弃告警是否足够暴露到外部调用方
2. `services/task_service.py` 更大范围的 facade 瘦身
3. `application/advanced_actions.py` 的仓库外保留必要性评估
4. `local_file_search` 兼容别名最终退场

## 5. 当前不建议立刻动的部分

以下对象现在不建议直接删除：

- `services/task_service.py`
- `services/mail_service.py`
- `task_service.init_db()`
- `application/advanced_actions.py`
- `local_file_search` 兼容别名

原因：

- 仍承担历史导入路径稳定性
- 直接删除的收益小于回归成本

## 6. 已完成退场项

以下兼容点已完成退场，不再属于当前主风险面：

- `services/mobile_service.py`
- `task_query_service.get_task_detail()`
- `services/unified_search_service.py` 中的全文索引 compat 函数
- `POST /api/search/legacy`
- `routers/file_search.py`
- `/api/advanced/*`
- `routers/advanced_features.py`

## 7. 下一阶段建议

建议把后续动作拆成两组并行目标：

### 7.1 低风险清理组

- 评估 `task_service.init_db()` 的仓库外保留必要性
- 清点 `mail_service.py` 对外导出面里哪些仍被历史调用依赖
- 评估 `application/advanced_actions.py` 是否还存在仓库外稳定调用面
- 评估 `services.mail.facade` 是否可以继续下沉为更细粒度导入

### 7.2 命名治理组

- 观察 `local_file_search` 兼容别名是否仍有外部使用
- 评估是否需要为 `task_service` / `mail_service` 补更明确的 deprecation 提示

## 8. 完成标准

满足以下条件，说明这份清单被真正用起来了：

1. 新代码不再继续增加对 facade/wrapper 的主链依赖
2. 每个 compat 入口都有保留理由
3. 每个 compat 入口都有预计收缩顺序
4. 历史 HTTP 路由兼容层不再回流
