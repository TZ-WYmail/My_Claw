# 兼容层与边界清单（2026-06-13）

更新时间：2026-06-13  
目的：给当前仍保留的 facade / compatibility wrapper / 历史命名入口建立清单、分类和后续退场顺序

## 1. 当前判断原则

本清单只回答四件事：

1. 这个入口现在是不是主路径
2. 它为什么还要保留
3. 它的主要风险是什么
4. 后续应该按什么顺序收缩

不在这里讨论具体代码实现。

## 2. 兼容层分类

### 2.1 facade 类

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

- `routers/advanced_features.py`
- `/api/advanced/*`
- `services/unified_search_service.py` 里的全文索引兼容接口
- `POST /api/search/legacy`（位于 `routers/file_search.py`）

特点：

- 主要问题不是逻辑重复，而是命名继续暴露旧结构判断
- 容易让后续开发围绕历史命名继续堆功能

### 2.4 子系统 facade 类

- `services/mail_service.py` -> `services/mail/facade.py`

特点：

- 对邮件子系统外部调用方仍有价值
- 但阅读和演进时必须明确 `mail_service.py` 不是邮件主实现

## 3. 清单与分类

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

当前问题：

- 文件名容易掩盖真实主实现位于 `services/mail/*`
- facade 仍有较强存在感

建议动作：

1. 保留对外 facade
2. 在文档和新代码中明确 mail 主实现边界
3. 避免继续往 `mail_service.py` 堆新逻辑

### 3.4 `routers/advanced_features.py` / `/api/advanced/*`

分类：`可进入观察期`

当前作用：

- 承接标签、子任务、番茄钟、日历、任务详情等增强功能

当前问题：

- 这是典型历史聚合命名，不是稳定业务域
- 容易继续把不相关功能塞到同一路由下

建议动作：

1. 先冻结继续新增“advanced” 类型能力
2. 继续以正式域路由承接新增主路径
3. 再决定是拆路由还是仅改命名层

### 3.5 `services/unified_search_service.py` 中的全文索引兼容接口

分类：`可进入观察期`

当前作用：

- 兼容旧全文搜索调用方式

当前问题：

- 新旧搜索接口共存，容易继续扩大兼容面

建议动作：

1. 明确正式全文索引入口由 `routers/fulltext_search.py` 承接
2. 标记 `unified_search_service` 中这组函数为历史兼容接口
3. 待调用面收口后再删除

### 3.6 `POST /api/search/legacy`（位于 `routers/file_search.py`）

分类：`可计划淘汰`

当前作用：

- 保持旧文件搜索 API 可用

当前问题：

- 路由层继续暴露 legacy 语义
- `routers/file_search.py` 这个模块名仍带历史色彩
- 但 unified search 正式 owner 已转到 `routers/search.py`

建议动作：

1. 统计是否仍有调用
2. 若仅剩测试依赖，先迁测试
3. 然后删除 legacy 路由

## 4. 推荐退场顺序

按风险和收益，建议顺序如下：

1. `POST /api/search/legacy`
2. `services/unified_search_service.py` 里的全文索引 compat 函数
3. `routers/advanced_features.py` 的历史命名与边界重整
4. `task_service.init_db()` compat 入口
5. `services/task_service.py` 更大范围的 facade 瘦身

## 5. 当前不建议立刻动的部分

以下对象现在不建议直接删除：

- `services/task_service.py`
- `services/mail_service.py`
- `task_service.init_db()`

原因：

- 仍承担历史导入路径稳定性
- 直接删除的收益小于回归成本

## 6. 已完成退场项

以下兼容点已完成退场，不再属于当前主风险面：

- `services/mobile_service.py`
- `task_query_service.get_task_detail()`

## 7. 下一阶段建议

建议把后续动作拆成两组并行目标：

### 7.1 低风险清理组

- 清点 legacy file search 调用面
- 清点 `unified_search_service` 中全文索引兼容函数的调用面
- 评估 `task_service.init_db()` 的仓库外保留必要性

### 7.2 边界重命名组

- 为 `advanced_features` 建立目标域映射文档
- 评估 `routers/file_search.py` 的模块命名是否需要最终调整
- 评估新的 router/package 命名方案
- 明确是否需要前后端一起改路径

## 7. 完成标准

满足以下条件，说明这份清单被真正用起来了：

1. 新代码不再继续增加对 facade/wrapper 的主链依赖
2. 每个 compat 入口都有保留理由
3. 每个 compat 入口都有预计退场顺序
4. `advanced_features` 不再被当作长期稳定业务域
