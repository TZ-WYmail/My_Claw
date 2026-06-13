# 阶段 6：task planning 与 runtime state 重整计划（2026-06-13）

更新时间：2026-06-13  
定位：这是 phase-2 / phase-3 之后的继续实施文档，聚焦 task command 内部分层与 planning 临时状态治理  
目标：把 task 领域的“写操作能力”和“规划分析能力”继续拆开，并把 AI planning preview/replan 的短生命周期状态从进程内内存迁到可控存储

## 1. 本阶段目标

本阶段聚焦解决两个核心问题：

1. `services/task_command_service.py` 仍同时承担写操作与规划分析职责
2. `services/ai_planning_service.py` 仍使用进程内 `_planning_previews` 保存 preview 状态

本阶段完成后，系统应达到以下状态：

- task 写路径和 task planning 路径形成更清晰的服务边界
- AI planning preview/confirm 链路不再依赖进程内内存字典
- 现有 application/router/API 行为保持兼容

## 2. 范围

本阶段包含：

- task command 内部进一步拆分
- planning preview state 持久化/可管理化
- 相关测试补齐
- 进度文档同步

本阶段不包含：

- 前端页面改造
- 任务模型字段的大规模重设计
- WebSocket / 实时协同
- mail / workflow / webhook 的进一步架构拆分

## 3. 当前问题拆解

### 3.1 `task_command_service` 职责过载

当前该模块同时承担：

- 单任务写操作
- 批量写操作
- 时间格式归一
- 任务分析
- 每日计划生成
- 文本化时间摘要

这会导致：

- 模块过厚
- 单测目标不清晰
- planning 逻辑和写 DB 逻辑耦合
- 后续如果要做更复杂规划，很难隔离风险

### 3.2 planning preview 状态仍在内存中

当前 `services/ai_planning_service.py` 使用 `_planning_previews: dict[str, dict]`

这会导致：

- 服务重启丢失 preview
- 多 worker / 多进程不一致
- 无法控制生命周期
- 无法审计 preview 来源与时间
- confirm/replan 难以做可恢复处理

## 4. 设计原则

本阶段遵守以下原则：

1. 不破坏现有 API 响应结构
2. 优先拆职责，不先做大规模重命名
3. 新状态统一进入 runtime state service 或明确持久表
4. 保留兼容入口，先迁主链，再缩兼容层
5. 测试先覆盖新边界，再做内部实现替换

## 5. 任务清单

### 5.1 task 规划服务拆分

要做的事情：

- 新建 `services/task_planning_service.py`
- 从 `task_command_service` 中迁出：
  - 时间格式归一
  - 日期转 weekday
  - 批量 analyze
  - 日计划生成
  - 人类可读时间格式化
- 保持 `task_command_service` 对外兼容导出

完成标准：

- `task_command_service` 主要聚焦写路径
- `task_planning_service` 聚焦 planning/normalization
- 现有上层调用不回归

### 5.2 planning preview runtime state 持久化

要做的事情：

- 在 runtime state 存储中新增 planning preview state 读写能力
- 定义 preview state 最低字段：
  - `preview_id`
  - `payload`
  - `selected_variant`
  - `created_at`
  - `expire_at`
  - `source`
- `preview_task_plan()` 改为写入 preview state
- `confirm_task_plan()` 改为从持久状态读取

完成标准：

- `_planning_previews` 不再作为主状态源
- preview 缺失/过期有明确错误返回
- 现有测试通过

### 5.3 兼容层继续收缩

要做的事情：

- `task_service` 保持 facade，但不再承载新增 planning 逻辑
- 新的 planning helper 一律从 `task_planning_service` 获取
- AI planning 主链直接依赖 planning/runtime service

完成标准：

- 新代码不再继续增加对 `task_service` 的内部依赖
- task facade 退场路径更清晰

## 6. 风险与注意点

### 6.1 测试中的 `DB_PATH` 注入

现有测试大量通过 patch/monkeypatch `task_service.DB_PATH` 驱动临时数据库。

因此本阶段必须确保：

- 新增 service 的 `DB_PATH` 能被同步或显式 patch
- 不能破坏既有 `init_db()` 兼容行为

### 6.2 preview payload 体积

planning preview 包含：

- `variant_plans`
- `daily_plan`
- `calendar_events`
- `conflicts`

这是大对象。

因此实现时要注意：

- 先保证正确性
- 序列化格式保持简单
- 后续如有性能问题，再引入裁剪或分层存储

### 6.3 兼容 API 结构

前端、router、测试当前依赖已有字段名：

- `preview_id`
- `selected_variant`
- `variant_plans`
- `daily_timeline`

本阶段不得擅自改响应结构。

## 7. 推荐实施顺序

按以下顺序推进：

1. 先抽 `task_planning_service`
2. 再把 `ai_planning_service` 切到新 planning service
3. 再增加 preview state 持久化
4. 再补测试
5. 最后更新进度文档

## 8. 完成标准

本阶段完成时，需要满足：

1. `task_planning_service.py` 已落地
2. `task_command_service.py` 不再承载主要 planning 实现
3. `ai_planning_service.py` 不再把 preview 状态保存在进程内 dict
4. 新增 runtime/planning state 测试通过
5. 既有 task/planning/mobile/mail/workflow 相关回归通过
