# AI Task Planning Implementation Plan — 2026-05-15

> 依据文档:
> - `AI_TASK_PLANNING_USE_CASES_2026-05-15.md`
> - `MVP_API_CONTRACT_2026-05-15.md`
> - `MVP_DB_SCHEMA_2026-05-15.md`

---

## 一、目标

本实施方案用于把“AI 安排任务”的问题分析落成可执行开发计划。

目标不是继续增加聊天能力，而是把 AI 安排任务从“可展示建议”升级为“能处理真实任务约束的可执行规划器”。

本次实施以现实任务处理中最常见的痛点为驱动：

1. 时间歧义
2. 任务过载
3. 跨多天推进
4. 日历冲突
5. 插入式重排
6. 估时不稳定
7. 计划缺少解释

---

## 二、当前能力与缺口

### 当前已有能力

- AI 拆解任务
- AI 估算任务时间
- AI 生成任务计划
- 批量任务预览 / 创建
- 获取今日建议

### 当前核心缺口

1. `generate_task_plan()` 仍偏通用 LLM 输出，没有稳定约束建模
2. 任务排程没有真实读取用户日历占用
3. 没有“最早开始 / 每日容量 / 缓冲时间 / 不可行判断”
4. 没有“插入突发任务后重排”能力
5. 缺少“计划解释层”
6. 预览和创建之间的计划结构不够稳定

---

## 三、设计原则

### 原则 1：先结构化，再让 AI 生成

AI 不应该直接输出最终落库任务。

正确顺序应为：

1. 输入解析
2. 约束建模
3. 排程计算
4. AI 解释与优化
5. 用户确认
6. 创建任务

### 原则 2：把 AI 放在“辅助决策层”

AI 负责：
- 拆解
- 估时
- 识别风险
- 解释理由

规则引擎负责：
- 容量计算
- 冲突检测
- 时间块落位
- 不可行判断

### 原则 3：默认先预览，不直接落库

所有批量安排场景一律先 preview。

---

## 四、实施分期

## Phase A1：输入理解与约束标准化

### 目标

先把用户输入从自然语言任务列表变成稳定结构，减少后续规划漂移。

### 任务

#### 1. 日期/时间标准化层

- 把以下输入统一转成结构化字段：
  - `due_time`
  - `earliest_start`
  - `time_preference`
  - `work_domain`
- 对歧义输入打标：
  - `ambiguous_date`
  - `missing_duration`
  - `missing_dependency`

#### 2. 输入分类

- 识别：
  - 目标型任务
  - 动作型任务
  - 提醒型事项
  - 可选型事项
  - 周期任务

#### 3. 约束模型

- 定义：
  - 每日可用工时
  - 最早开始时间
  - 最晚结束时间
  - 日历占用
  - 缓冲时间
  - 任务域（工作/个人/学习）

### 输出

- 新的 AI planning input schema
- preview 阶段统一标准化结果

### 验收

- 用户输入任务后，系统可明确显示：
  - 已识别信息
  - 缺失信息
  - 歧义信息

---

## Phase A2：规则排程引擎

### 目标

把排程能力从“LLM 自由生成”改成“约束驱动的排程”。

### 任务

#### 1. 每日容量计算

- 基于用户可用时间和日历占用计算当日剩余容量
- 支持工作日/周末不同容量

#### 2. 多天分摊

- 大任务按剩余工时分散到多个工作日
- 自动生成最晚开始日

#### 3. 冲突检测

- 与已有任务冲突
- 与日历事件冲突
- 与用户不可用时间冲突

#### 4. 过载与不可行判断

- 当日容量超过上限时标记 `overload`
- 截止日前无法完成时标记 `infeasible`

#### 5. 插入式重排

- 新增突发任务时，重排后续任务
- 返回受影响任务列表

### 输出

- 稳定的 preview 结构：
  - `daily_plan`
  - `daily_timeline`
  - `conflicts`
  - `overload_days`
  - `infeasible_tasks`
  - `reschedule_candidates`

### 验收

- 相同输入多次 preview，结果结构稳定
- 不再依赖 LLM 自己幻想时间块

---

## Phase A3：AI 解释与多方案生成

### 目标

让 AI 负责“为什么这样排”和“还有什么替代方案”。

### 任务

#### 1. 计划解释

- 基于规则引擎结果，AI 输出：
  - 优先级原因
  - 冲突原因
  - 延后原因
  - 风险提示

#### 2. 多方案生成

- 稳妥方案
- 平衡方案
- 激进方案

#### 3. 下一步建议

- 当前应先做哪项
- 哪项可延期
- 哪项需要拆解

### 输出

- 解释型响应模板
- 多方案比较卡片

### 验收

- 用户可以理解“为什么排成这样”
- 不是只有一个黑箱结论

---

## Phase A4：前端交互升级

### 目标

让 AI 安排任务从聊天文本结果变成真正可操作的规划界面。

### 任务

#### 1. 预览结果界面

- 已识别信息区
- 缺失信息区
- 每日时间线区
- 冲突提示区
- 方案切换区

#### 2. 快捷操作

- 一键创建
- 一键推迟低优先级任务
- 一键拆解大任务
- 一键压缩计划

#### 3. 确认流

- preview
- 修改约束
- 再 preview
- confirm create

### 输出

- AI 安排任务专用预览界面
- 不再依赖纯文本聊天呈现

### 验收

- 用户能在不手工读大段文本的情况下完成计划确认

---

## Phase A5：学习与反馈闭环

### 目标

让 AI 安排任务随着用户使用变得更像“这个用户自己的规划器”。

### 任务

#### 1. 记录计划与实际偏差

- 计划时长
- 实际完成时长
- 是否延期
- 延期次数

#### 2. 用户模式学习

- 高效时段
- 容易拖延的任务类型
- 经常低估/高估的任务类型

#### 3. 反馈驱动估时修正

- 下次估时优先参考个人历史

### 输出

- 个人估时修正系数
- 计划偏差报告

### 验收

- 同类任务后续估时更贴近用户实际

---

## 五、后端改造清单

### 5.1 新增/增强服务

#### `services/ai_planning_service.py`

建议新增函数：

- `normalize_task_inputs()`
- `build_planning_constraints()`
- `calculate_daily_capacity()`
- `schedule_tasks_with_constraints()`
- `generate_plan_explanation()`
- `generate_plan_variants()`
- `replan_with_interrupt()`

#### `services/task_service.py`

增强：

- 查询某日期范围已有任务
- 查询按时段分组的任务
- 查询延期历史（如后续落库）

#### `services/calendar_sync_service.py`

增强：

- 返回规划时段内的占用块
- 提供标准化空闲时间接口

### 5.2 数据模型建议

建议为 `tasks` 增加后续字段：

- `earliest_start`
- `work_domain`
- `energy_type`
- `optional`
- `postpone_count`
- `planning_source`

建议新增 planning 相关表：

- `planning_sessions`
- `planning_variants`
- `planning_feedback`

---

## 六、前端改造清单

### 页面

- `AI Chat` 页面：保留对话，但增加结构化计划面板
- `Today` 页面：增加 AI 推荐入口
- `Calendar` 页面：支持接收 AI 预览计划

### 组件

- `PlanningPreviewPanel`
- `ConstraintEditor`
- `ConflictList`
- `VariantSelector`
- `CreateConfirmationBar`

---

## 七、API 改造建议

建议不要只保留现有 `/api/ai/plan` 的松散输入输出。

### 新接口建议

#### `POST /api/ai/plan/preview`

输入：
- tasks
- constraints
- calendar_range
- mode

输出：
- normalized_tasks
- daily_plan
- daily_timeline
- conflicts
- overload_days
- infeasible_tasks
- variants
- explanation

#### `POST /api/ai/plan/confirm`

输入：
- preview_id
- selected_variant
- user_adjustments

输出：
- created_tasks
- skipped_tasks
- warnings

#### `POST /api/ai/plan/replan`

输入：
- new_task / unfinished_tasks / date_range

输出：
- affected_tasks
- new_plan
- postpone_candidates

---

## 八、测试计划

### 单元测试

- 日期歧义识别
- 多天分摊
- 每日容量控制
- 冲突检测
- 不可行判断

### 集成测试

- preview -> confirm
- 突发任务插入 -> 重排
- 日历占用 -> 排程避让
- 大任务拆解 -> 多天推进

### 回归测试

- 不影响现有 batch task preview/create
- 不影响任务创建与周视图

---

## 九、优先级建议

### 第一批必须做

1. 输入标准化
2. 每日容量计算
3. 多天分摊
4. 冲突检测
5. preview 结果结构稳定化

### 第二批高价值

6. 多方案生成
7. 插入式重排
8. 解释层
9. 前端结构化预览界面

### 第三批增强

10. 个性化学习
11. 反馈闭环
12. 偏差修正

---

## 十、建议执行顺序

### Sprint 1

- 完成输入标准化
- 完成每日容量/冲突/多天分摊
- 改造 preview 输出结构

### Sprint 2

- 完成解释层
- 完成多方案生成
- 完成 replan 模式

### Sprint 3

- 完成前端结构化计划预览
- 完成确认流
- 完成快捷操作

### Sprint 4

- 完成学习与反馈
- 完成偏差修正
- 完成系统级测试

---

## 十一、完成标准

满足以下条件，才算 AI 安排任务功能进入“真实可用”状态：

1. 能识别并显示歧义输入
2. 能考虑日历占用与每日容量
3. 能把大任务分摊到多天
4. 能在冲突和不可行时给出替代方案
5. 能先 preview 再 create
6. 能解释安排依据
7. 能支持插入式重排

---

## 十二、结论

AI 安排任务的正确方向不是“让模型更会说”，而是：

1. 用规则层把现实约束建模清楚
2. 用 AI 层解释、补全、优化
3. 用前端把规划结果结构化呈现

只有这样，这个功能才会从“演示型智能”变成“能每天用的工作规划器”。
