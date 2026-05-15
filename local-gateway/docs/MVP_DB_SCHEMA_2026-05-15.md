# LocalCommandCenter MVP 数据库设计

> 文档版本: 1.0
> 更新日期: 2026-05-15
> 依据文档: `MVP_PRD_2026-05-15.md`、`MVP_API_CONTRACT_2026-05-15.md`

---

## 一、目标

本文件用于定义 MVP 版本所需的最小数据模型，支持以下主链路：

**今天工作台 -> 任务 -> 日历 -> 笔记 -> AI 辅助**

目标是：

1. 保证主链路字段完整
2. 避免为未来能力过度设计
3. 为任务、日历、笔记、AI 联动提供稳定数据基础

---

## 二、设计原则

1. 只为 MVP 主路径建模
2. 字段命名统一、可读
3. 保留必要扩展位，但不引入复杂多态结构
4. 优先支持单用户本地使用场景

---

## 三、核心实体

MVP 只定义以下核心实体：

1. `projects`
2. `tasks`
3. `subtasks`
4. `notes`
5. `note_templates`
6. `task_note_links`
7. `habits`
8. `habit_checkins`
9. `ai_conversations`
10. `ai_messages`
11. `ai_suggested_actions`

---

## 四、表结构设计

## 4.1 `projects`

### 用途

为任务提供轻量归属维度。

### 字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `project_id` | TEXT | 是 | 主键 |
| `name` | TEXT | 是 | 项目名称 |
| `description` | TEXT | 否 | 描述 |
| `status` | TEXT | 是 | `active` / `archived` |
| `created_at` | TEXT | 是 | ISO 时间 |
| `updated_at` | TEXT | 是 | ISO 时间 |

---

## 4.2 `tasks`

### 用途

承载 MVP 任务主数据。

### 字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `task_id` | TEXT | 是 | 主键 |
| `task_name` | TEXT | 是 | 任务标题 |
| `status` | TEXT | 是 | `todo` / `in_progress` / `done` / `overdue` |
| `priority` | INTEGER | 是 | `0-3` |
| `project_id` | TEXT | 否 | 关联项目 |
| `start_time` | TEXT | 否 | 开始时间 |
| `end_time` | TEXT | 否 | 结束时间 |
| `due_time` | TEXT | 否 | 截止时间 |
| `estimated_minutes` | INTEGER | 否 | 预估时长 |
| `actual_minutes` | INTEGER | 否 | 实际时长 |
| `context` | TEXT | 否 | 执行上下文 |
| `energy_level` | TEXT | 否 | `low` / `medium` / `high` |
| `location` | TEXT | 否 | 可选地点 |
| `postpone_count` | INTEGER | 是 | 默认 0 |
| `review_note` | TEXT | 否 | 完成/延期复盘说明 |
| `created_at` | TEXT | 是 | 创建时间 |
| `updated_at` | TEXT | 是 | 更新时间 |
| `completed_at` | TEXT | 否 | 完成时间 |

### 索引建议

- `idx_tasks_status`
- `idx_tasks_due_time`
- `idx_tasks_start_time`
- `idx_tasks_project_id`

---

## 4.3 `subtasks`

### 用途

支持轻量任务拆分。

### 字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `subtask_id` | TEXT | 是 | 主键 |
| `task_id` | TEXT | 是 | 关联任务 |
| `name` | TEXT | 是 | 子任务名称 |
| `status` | TEXT | 是 | `todo` / `done` |
| `sort_order` | INTEGER | 是 | 顺序 |
| `created_at` | TEXT | 是 | 创建时间 |
| `updated_at` | TEXT | 是 | 更新时间 |

---

## 4.4 `notes`

### 用途

承载结构化工作记录。

### 字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `note_id` | TEXT | 是 | 主键 |
| `title` | TEXT | 是 | 标题 |
| `content` | TEXT | 是 | Markdown 内容 |
| `summary` | TEXT | 否 | 可选摘要 |
| `source_type` | TEXT | 否 | `manual` / `ai_generated` / `task_generated` |
| `created_at` | TEXT | 是 | 创建时间 |
| `updated_at` | TEXT | 是 | 更新时间 |
| `archived` | INTEGER | 是 | 0/1 |

---

## 4.5 `note_templates`

### 用途

提供 MVP 模板能力。

### 字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `template_id` | TEXT | 是 | 主键 |
| `name` | TEXT | 是 | 模板名称 |
| `content` | TEXT | 是 | 模板内容 |
| `category` | TEXT | 否 | 模板分类 |
| `created_at` | TEXT | 是 | 创建时间 |

---

## 4.6 `task_note_links`

### 用途

建立任务与笔记的双向关联。

### 字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `link_id` | TEXT | 是 | 主键 |
| `task_id` | TEXT | 是 | 任务 ID |
| `note_id` | TEXT | 是 | 笔记 ID |
| `link_type` | TEXT | 是 | `primary` / `reference` |
| `created_at` | TEXT | 是 | 创建时间 |

### 约束建议

- 唯一约束：`(task_id, note_id)`

---

## 4.7 `habits`

### 用途

支持 MVP 级轻量习惯卡片。

### 字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `habit_id` | TEXT | 是 | 主键 |
| `name` | TEXT | 是 | 名称 |
| `frequency` | TEXT | 是 | `daily` / `weekly` |
| `target_count` | INTEGER | 是 | 目标次数 |
| `color` | TEXT | 否 | 展示色 |
| `active` | INTEGER | 是 | 0/1 |
| `created_at` | TEXT | 是 | 创建时间 |
| `updated_at` | TEXT | 是 | 更新时间 |

---

## 4.8 `habit_checkins`

### 用途

记录习惯打卡。

### 字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `checkin_id` | TEXT | 是 | 主键 |
| `habit_id` | TEXT | 是 | 习惯 ID |
| `checkin_date` | TEXT | 是 | 日期 |
| `count` | INTEGER | 是 | 次数 |
| `created_at` | TEXT | 是 | 创建时间 |

---

## 4.9 `ai_conversations`

### 用途

保留 AI 会话元信息。

### 字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `conversation_id` | TEXT | 是 | 主键 |
| `title` | TEXT | 否 | 会话标题 |
| `context_type` | TEXT | 否 | `today` / `task` / `note` |
| `created_at` | TEXT | 是 | 创建时间 |
| `updated_at` | TEXT | 是 | 更新时间 |

---

## 4.10 `ai_messages`

### 用途

记录 AI 对话消息。

### 字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `message_id` | TEXT | 是 | 主键 |
| `conversation_id` | TEXT | 是 | 会话 ID |
| `role` | TEXT | 是 | `user` / `assistant` / `system` |
| `content` | TEXT | 是 | 消息内容 |
| `created_at` | TEXT | 是 | 创建时间 |

---

## 4.11 `ai_suggested_actions`

### 用途

记录 AI 提出的可确认动作。

### 字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `action_id` | TEXT | 是 | 主键 |
| `conversation_id` | TEXT | 是 | 会话 ID |
| `action_type` | TEXT | 是 | `reschedule_task` / `create_subtasks` / `create_note` |
| `target_id` | TEXT | 否 | 关联任务/笔记 ID |
| `payload_json` | TEXT | 是 | 动作载荷 |
| `confirmed` | INTEGER | 是 | 0/1 |
| `applied` | INTEGER | 是 | 0/1 |
| `created_at` | TEXT | 是 | 创建时间 |
| `applied_at` | TEXT | 否 | 应用时间 |

---

## 五、关系说明

### 5.1 任务与项目

- 一个项目可有多个任务
- 一个任务最多属于一个项目

### 5.2 任务与子任务

- 一个任务可有多个子任务

### 5.3 任务与笔记

- 一个任务可关联多个笔记
- 一个笔记可关联一个主任务，也可不关联

### 5.4 习惯与打卡

- 一个习惯有多条打卡记录

### 5.5 AI 会话与动作

- 一个会话有多条消息
- 一个会话可生成多个建议动作

---

## 六、MVP 不建模内容

以下内容明确不进入本版数据库主模型：

1. 团队协作成员
2. 权限角色体系
3. 多设备同步版本冲突
4. 工作流编排 DSL
5. 下载深度元数据
6. 沙盒执行产物体系
7. 高级搜索索引结构

---

## 七、迁移建议

### 7.1 迁移策略

建议采用：

1. 新增字段优先
2. 尽量不破坏现有主表
3. 对旧数据提供默认值

### 7.2 最小迁移项

1. `tasks` 增加：
   - `project_id`
   - `estimated_minutes`
   - `actual_minutes`
   - `context`
   - `energy_level`
   - `location`
   - `postpone_count`
   - `review_note`

2. 新增：
   - `projects`
   - `subtasks`
   - `note_templates`
   - `task_note_links`
   - `ai_conversations`
   - `ai_messages`
   - `ai_suggested_actions`

---

## 八、首页聚合查询建议

为了支持今天工作台，建议准备以下查询：

1. 今日重点任务查询
2. 今日时间块查询
3. 逾期任务查询
4. 最近更新笔记查询
5. 今日习惯汇总查询

这些查询可由服务层聚合，不强制新建物化表。

---

## 九、总结

MVP 数据库设计的重点是支持主链路，而不是为未来的所有能力预埋复杂模型。

只要能稳定支撑：

1. 任务
2. 时间安排
3. 笔记记录
4. AI 建议与确认

这套模型就是足够的。
