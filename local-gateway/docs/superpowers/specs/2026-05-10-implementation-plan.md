# 实施计划：任务时间范围 + 三时报 + 多对话 + 激励机制

日期: 2026-05-10
版本: v2（拆分解耦版）

---

## 依赖关系总览

```
A1(DB迁移) ──→ A2(后端task字段) ──→ A3(AI工具schema) ──→ A4(冲突检测)
                                        │                      │
                                        ↓                      ↓
                                   B1(周视图时间轴)        B2(未完成感知)
                                   B3(任务表单)           B3(任务表单)

A2(后端task字段) ──→ C1(通知服务) ──→ C2(三时报调度) ──→ C3(动态提醒)
                                            │
                                            ↓
                                      D1(streak引擎) ──→ D2(Dashboard激励) ──→ D3(逾期压力)
                                            │
                                            ↓
                                      C2(三时报调度) ← 消费 D1/D3 的数据

E1(对话元数据) ──→ E2(对话API) ──→ E3(AiChat前端)   [独立链路，无外部依赖]
```

---

## A 链：任务时间范围（核心基础链，必须最先完成）

### A1: 数据库迁移

**文件**: `services/task_service.py` 的 `init_db()` 和 `_schema`
**改动**:
- `_schema` 的 `CREATE TABLE tasks` 增加 `start_time TEXT`、`end_time TEXT`、`completed_at TEXT` 三列，均为可空
- `init_db()` 末尾增加迁移逻辑：检测旧表是否缺少这三列，缺少则 `ALTER TABLE ADD COLUMN`
- 迁移逻辑须幂等（重复执行不报错）

**产出**: 运行 `init_db()` 后 tasks 表有三个新列，旧数据不受影响

**验证**: 启动服务后，`sqlite3 data/tasks.db ".schema tasks"` 能看到三列

---

### A2: 后端 task 字段贯通

**文件**: `services/task_service.py`、`models/schemas.py`
**改动**:

*task_service.py*:
- `add_task()` 签名增加 `start_time=None, end_time=None`，INSERT 语句包含这两列
- `complete_task()` 增加 `SET completed_at = datetime('now')`
- `batch_complete_tasks()` 同上
- `get_weekly_plan()` 的 SELECT 增加 `start_time, end_time, completed_at`
- `get_all_tasks()` 同上
- `batch_add_tasks()` 每条任务支持 `start_time`/`end_time`
- 所有返回 TaskInfo 结构的地方均包含三个新字段

*models/schemas.py*:
- `TaskManagerRequest` 增加 `start_time: Optional[str]`、`end_time: Optional[str]`
- `TaskInfo` 增加 `start_time: Optional[str]`、`end_time: Optional[str]`、`completed_at: Optional[str]`
- `BatchTaskItem` 增加 `start_time`/`end_time`
- `TaskManagerResponse` 增加 `warnings: Optional[list[str]] = None`
- `TaskAction` 枚举增加 `get_pending_tasks`

**依赖**: A1
**验证**: `POST /api/task` 传 `start_time`/`end_time` 能正常创建任务并返回

---

### A3: AI 工具 Schema 更新

**文件**: `services/ai_service.py`
**改动**:

- `TOOLS_SCHEMA` 中 `local_task_manager` 的 parameters.properties 增加 `start_time`/`end_time`，description 说明为 ISO 8601 格式的执行时间段
- `batch_task_manager` 的 tasks.items.properties 增加 `start_time`/`end_time`
- `local_task_manager` 的 action.enum 增加 `get_pending_tasks`
- `SYSTEM_PROMPT_BASE` 增加规则段落：创建任务前先用 `get_pending_tasks` / `get_weekly_plan` 查询已有安排，避免时间冲突
- `_execute_tool()` 中 `local_task_manager` 的端点调用已支持透传新字段，无需改动

**依赖**: A2
**验证**: AI 对话中让 AI 创建带时间范围的任务，观察 tool_call 参数是否包含 start_time/end_time

---

### A4: 冲突检测

**文件**: `services/task_service.py`
**改动**:

- 新增 `_check_conflicts(start_time, end_time, exclude_task_id=None) -> list[str]` 方法
  - 查询同一日期（start_time 的日期部分）内时间段重叠的 pending 任务
  - 重叠判定：`existing.start_time < new.end_time AND existing.end_time > new.start_time`
  - 计算当日 pending 任务的总工时（有 end_time-start_time 的按实际差值，无的按 estimated_minutes 或默认 1h），超 8h 标记过载
  - 返回 warnings 列表
- `add_task()` 调用 `_check_conflicts()`，将结果放入返回 dict 的 `warnings` 字段
- `batch_add_tasks()` 每条任务调用 `_check_conflicts()`，结果放在各自的 result 中
- `analyze_tasks()` 的冲突检测改为调用 `_check_conflicts()`，替换原有简单计数逻辑

**依赖**: A2
**验证**: 创建两个时间段重叠的任务，第二个返回 warnings 包含冲突信息

---

### A5: 未完成任务感知

**文件**: `services/task_service.py`、`routers/task_manager.py`
**改动**:

- `task_service.py` 新增 `get_pending_tasks() -> dict`
  - 查询 `status = 'pending'` 的所有任务，按 due_time 升序
  - 额外标记 `overdue`：due_time < now
- `routers/task_manager.py` 的 `handle_task()` 处理 `action=get_pending_tasks`
- `batch_add_tasks()` 的 `analyze_tasks(preview)` 返回值增加 `existing_tasks`：相关日期（新任务的 due_time 日期）的已有 pending 任务列表

**依赖**: A2
**验证**: `POST /api/task {"action": "get_pending_tasks"}` 返回未完成任务列表

---

### A6: 前端周视图时间轴

**文件**: `frontend/src/pages/Tasks.jsx`
**改动**:

- WeekView 组件完全重写：
  - 顶部保持周导航（上一周/本周/下一周）
  - 主体区为 7 列 x 24 行的时间轴网格
  - 左侧时间刻度列（0:00-23:00，可只显示偶数小时以节省空间）
  - 每列为一日，列头显示日期+星期
  - 任务块：绝对定位，top = (start_hour / 24) * 100%，height = (duration_hours / 24) * 100%
  - 颜色：priority 0=红, 1=橙, 2=蓝, 3=灰
  - 块内显示：任务名（截断）、时间范围
  - 无 start_time 的任务不渲染在时间轴，放在网格下方的「未安排时间」列表区
  - 当前时间线：一条水平红线标记当前时刻
  - 点击任务块弹出详情（可完成/删除）
- AllTasksView 列表中的「截止时间」列增加 start_time-end_time 的展示

**依赖**: A2（后端返回 start_time/end_time）
**验证**: 创建带时间范围的任务后，周视图能看到时间轴上的色块

---

### A7: 前端任务表单改造

**文件**: `frontend/src/pages/Tasks.jsx` 中的 TaskForm 组件
**改动**:

- 表单 grid 布局从 2 列调整为 2 列，增加：
  - 「开始时间」datetime-local 输入
  - 「结束时间」datetime-local 输入
- 保留「截止时间」字段不变
- 提交时将三个时间字段均传给后端
- 用户填了「开始时间」但未填「截止时间」时，截止时间默认=结束时间（前端自动补全，非强制）

**依赖**: A2
**验证**: 通过新表单创建任务，后端存储和返回均包含 start_time/end_time

---

## B 链：通知系统（依赖 A 链的 A2）

### B1: 通知配置与邮件发送

**新文件**: `services/notification_service.py`
**改动**:

- `NotificationConfig` 类：管理 SMTP 配置，持久化到 `data/notification_config.json`
  - 字段：smtp_host, smtp_port, smtp_user, smtp_password, notify_email, reminder_minutes_before(默认15), reminder_due_minutes(默认30)
  - 提供 `to_dict()`（密码脱敏）、`save()`、`_load()`
  - 全局单例 `notification_config`
- `send_email(subject, body_html)` 异步函数：
  - 使用 `aiosmtplib` 或标准 `smtplib`（在线程池中执行）发送 HTML 邮件
  - 邮件模板为简单 HTML（纯文字也 OK，用 `<pre>` 包裹）
  - 错误处理：连接失败、认证失败均 log 并返回失败
- `send_test_email()` 函数：发送一封测试邮件

**依赖**: 无外部依赖，但配置路径约定与 `config.py` 的 BASE_DIR 一致
**验证**: 调用 `send_email()` 成功收到邮件

---

### B2: 通知配置 API 与前端

**新文件**: `routers/notification.py`
**改动**:

- `GET /api/notification/config` — 返回配置（密码脱敏）
- `POST /api/notification/config` — 保存配置，同时重新注册所有 scheduler job
- `POST /api/notification/test` — 发送测试邮件
- `main.py` 中注册 router

**前端**: `frontend/src/pages/Settings.jsx`
**改动**:

- 在现有设置页面增加「通知配置」区块：
  - SMTP 服务器、端口、发件邮箱、授权码、收件邮箱
  - 提前提醒分钟数（开始前）、截止提醒分钟数
  - 「测试邮件」按钮
  - 「保存配置」按钮

**依赖**: B1
**验证**: 前端 Settings 页面能保存配置并收到测试邮件

---

### B3: 三时报调度引擎

**文件**: `services/notification_service.py`（扩展）
**改动**:

- 使用项目已有的 `apscheduler`（APScheduler），在 FastAPI lifespan 中启动 `AsyncIOScheduler`
- 三种定时报告：

**晨报（每天 08:00）**：
  - 查询今日所有 pending 任务（按 start_time 排序）
  - 查询未完成的逾期任务
  - 查询当前 streak（来自 streak.json）
  - 组装邮件发送

**午报（每天 13:00）**：
  - 查询上午应完成但未完成的任务（start_time 在 00:00-13:00 之间，status 仍为 pending）
  - 查询下午待执行的任务（start_time 在 13:00-18:00 之间）
  - 逾期任务简要提醒
  - 鼓励语：如「上午完成了 X 项，继续加油！」或「上午的任务还没完成，下午抓紧哦」

**晚报（每天 21:00）**：
  - 查询今日已完成任务数 vs 总任务数（完成率）
  - 查询仍未完成的今日任务（标记为逾期）
  - 更新 streak 状态
  - 明日预览：明天的任务列表
  - 鼓励/总结：完成率高则鼓励，低则温和提醒

- 每种报告的邮件主题分别为：`🌤 晨报 - 今日任务`、`☀️ 午报 - 下午安排`、`🌙 晚报 - 今日总结`
- 调度器注册在 `lifespan` 的 startup 阶段，shutdown 阶段关闭
- 仅在 `notification_config.notify_email` 非空时注册 cron job

**依赖**: B1, A2（需要 start_time/end_time/completed_at 字段）
**验证**: 到达设定时间后收到对应邮件

---

### B4: 动态任务提醒

**文件**: `services/notification_service.py`（扩展）
**改动**:

- `schedule_task_reminders(task)` 函数：
  - 根据 task.start_time 注册一个 APScheduler `run_date` job：提前 N 分钟发「开始提醒」邮件
  - 根据 task.due_time 注册一个 `run_date` job：提前 M 分钟发「截止提醒」邮件
  - job_id 格式：`reminder_start_{task_id}`、`reminder_due_{task_id}`
- `cancel_task_reminders(task_id)` 函数：
  - 移除上述两个 job
- 调用时机：
  - `task_service.add_task()` 末尾调用 `schedule_task_reminders(task)`
  - `task_service.complete_task()` 末尾调用 `cancel_task_reminders(task_id)`
  - `task_service.delete_task()` 末尾调用 `cancel_task_reminders(task_id)`
- 服务重启恢复：`lifespan` startup 时查询所有 pending 任务，逐个调用 `schedule_task_reminders()`

**依赖**: B1, B3, A2
**验证**: 创建一个 5 分钟后开始的任务，到达提醒时间后收到邮件

---

## C 链：激励机制（依赖 A2 和 B3）

### C1: Streak 引擎

**新文件**: `services/streak_service.py`
**改动**:

- `data/streak.json` 持久化：`{"current_streak": 0, "longest_streak": 0, "last_check_date": "", "history": []}`
  - history 为最近 30 天的每日记录：`[{"date": "2026-05-10", "total": 3, "completed": 3, "all_done": true}]`
- `check_and_update_streak() -> dict`：
  - 查询昨天的任务完成情况：昨天有任务且全部完成 → streak+1；昨天有任务且未全完成 → streak 归零；昨天无任务 → streak 不变
  - 更新 current_streak、longest_streak、last_check_date
  - 幂等：如果 last_check_date 已是今天，跳过
- `get_streak_info() -> dict`：返回当前 streak、最长 streak、近 7 天完成率、近 30 天历史
- `get_weekly_stats() -> dict`：本周每天完成率、总完成率、与上周对比
- 里程碑检测：`check_milestones() -> list[str]`，返回如 `["streak_7"]` 表示刚达 7 天连续

**依赖**: A2（需要 completed_at 字段）
**验证**: 手动调用 `check_and_update_streak()` 后 streak.json 正确更新

---

### C2: Dashboard 激励展示

**文件**: `frontend/src/pages/Dashboard.jsx`
**改动**:

- 顶部增加「每日进度」卡片：
  - 进度条：今日已完成 / 今日总任务
  - 文字：「已完成 3/5 项今日任务」
  - 全部完成时进度条变绿 + 文字变为「今日任务全部完成！」
- 增加「连续天数」卡片：
  - 显示当前 streak 数字，大字体
  - 文字：「已连续 N 天完成所有任务 🔥」
  - 无 streak 时：「开始你的连续完成之旅」
- 增加「逾期任务」卡片（红色警告风格）：
  - 显示逾期任务数量，点击跳转任务页
  - 逾期天数分级：1天=黄色、2-3天=橙色、7天+=红色

**新文件**: `services/streak_router.py` 或在 `routers/dashboard.py` 中增加
**改动**:

- `GET /api/streak` — 返回 streak 信息（调用 streak_service）
- 在 `get_dashboard_stats()` 中增加 streak 数据和今日完成进度

**依赖**: C1, A2
**验证**: Dashboard 显示进度条和 streak 数据

---

### C3: 逾期压力渲染

**文件**: `frontend/src/pages/Tasks.jsx`
**改动**:

- AllTasksView 的任务行样式增加逾期着色逻辑：
  - 计算 due_time 与当前时间的天数差
  - 逾期 1 天：左侧 3px 黄色边框
  - 逾期 2-3 天：左侧 3px 橙色边框 + 任务名前显示「!」图标
  - 逾期 7 天+：左侧 3px 红色边框 + 红色「严重逾期」badge
- 完成任务时的动画：
  - 点击完成按钮后，任务行添加 CSS class：文字划线 + opacity 渐变到 0.3（保留行，不消失，避免列表跳动）
- 完成后的 toast 提示增加进度感：
  - 查询今日完成数/总数
  - 提示文案：「已完成！今日进度 3/5」
  - 全部完成时：「太棒了！今日任务全部完成 🎉」

**依赖**: A2
**验证**: 逾期任务有视觉区分，完成任务有动画和进度提示

---

### C4: 邮件中的激励内容

**文件**: `services/notification_service.py`（B3 的三时报模板中集成）
**改动**:

晨报模板增加：
```
📊 你的数据
  连续完成: 🔥 {streak} 天
  本周完成率: {weekly_rate}%
```

晚报模板增加：
```
📊 今日总结
  完成率: {today_completed}/{today_total} ({rate}%)
  连续天数: 🔥 {streak} 天
  明日任务: {tomorrow_count} 项

{milestone_message}  ← 里程碑时出现
```

- 里程碑邮件：`check_milestones()` 返回非空时，额外发送一封祝贺邮件
  - 7 天：「坚持了一周，好习惯正在养成！」
  - 14 天：「两周连续完成，你比 90% 的人更自律！」
  - 30 天：「一个月！这是真正的习惯力量！」

**依赖**: C1, B3
**验证**: 三时报邮件中包含 streak 和激励内容

---

## D 链：多对话管理（独立链路，可与 A/B/C 并行）

### D1: 对话元数据管理

**文件**: `services/ai_service.py`（扩展）
**改动**:

- 新增 `_save_conversation_meta(conversation_id, title=None)` 函数：
  - 写入 `data/conversations/{id}_meta.json`
  - 内容：`{"title": str, "created_at": ISO, "updated_at": ISO, "message_count": int}`
  - title 为空时从 JSONL 第一条 user 消息取前 30 字
- 新增 `_load_conversation_meta(conversation_id) -> dict`
- 新增 `_list_all_conversations() -> list[dict]`：
  - 扫描 `data/conversations/*_meta.json`
  - 返回列表按 updated_at 倒序，每项包含 id、title、updated_at、message_count
- 修改 `_save_conversation_message()`：保存后更新 meta 的 updated_at 和 message_count
- 修改 `clear_conversation()`：
  - 同时删除 `{id}.jsonl`、`{id}_history.jsonl`、`{id}_meta.json`
  - 清除内存中的 `_conversations[id]` 和 `_conversation_timestamps[id]`

**依赖**: 无
**验证**: 发送消息后 meta.json 自动创建和更新

---

### D2: 对话管理 API

**文件**: `routers/chat.py`（扩展）
**改动**:

- `GET /api/chat/conversations` — 改用 `_list_all_conversations()`，返回 title/message_count
- `POST /api/chat/conversations` — 新建对话：生成 UUID，创建空 meta，返回 `{"conversation_id": "..."}`
- `DELETE /api/chat/conversations/{id}` — 调用 `clear_conversation(id)` 删除全部数据
- `POST /api/chat/clear` — 保持原有行为（清除指定 conversation），同时删磁盘

**依赖**: D1
**验证**: 通过 API 新建、列表、删除对话均正常

---

### D3: AiChat 前端改造

**文件**: `frontend/src/pages/AiChat.jsx`
**改动**:

- 组件状态增加：`conversations: list`、`activeConversationId: string`
- 页面布局改为左右两栏：
  - 左栏（240px，可折叠）：
    - 顶部「+ 新对话」按钮
    - 对话列表：每项显示标题（30字截断）+ 更新时间（相对时间如「2分钟前」）
    - 当前对话高亮（背景色区分）
    - hover 时右侧显示删除图标
    - 窄屏时左栏折叠，顶部显示汉堡按钮
  - 右栏（现有聊天区不变）：
    - header 增加当前对话标题显示
    - 配置面板保留
- 新对话流程：
  - 点击「+ 新对话」→ 调用 `POST /api/chat/conversations` → 获取新 ID → 切换到空白聊天
- 切换对话流程：
  - 点击列表项 → 设置 activeConversationId → 调用 `GET /api/chat/history/{id}` 加载消息
- 删除对话流程：
  - 点击删除图标 → confirm → `DELETE /api/chat/conversations/{id}` → 刷新列表
  - 如果删除的是当前对话，自动切换到列表第一项或空白
- 发送消息时使用 `activeConversationId` 而非硬编码 `'default'`

**依赖**: D2
**验证**: 能新建对话、切换对话、删除对话，各对话上下文独立

---

## 实施分组（可并行）

### 第一波（无依赖，可全并行）
- **A1** 数据库迁移
- **D1** 对话元数据管理
- **B1** 通知配置与邮件发送

### 第二波（依赖第一波，可并行）
- **A2** 后端 task 字段贯通（依赖 A1）
- **D2** 对话管理 API（依赖 D1）
- **B2** 通知配置 API 与前端（依赖 B1）

### 第三波（依赖第二波，可并行）
- **A3** AI 工具 Schema（依赖 A2）
- **A4** 冲突检测（依赖 A2）
- **A5** 未完成任务感知（依赖 A2）
- **A6** 前端周视图时间轴（依赖 A2）
- **A7** 前端任务表单（依赖 A2）
- **D3** AiChat 前端改造（依赖 D2）
- **C1** Streak 引擎（依赖 A2）

### 第四波（依赖第三波，可并行）
- **B3** 三时报调度引擎（依赖 B1, A2, C1）
- **B4** 动态任务提醒（依赖 B3）
- **C2** Dashboard 激励展示（依赖 C1）
- **C3** 逾期压力渲染（依赖 A2）

### 第五波
- **C4** 邮件中的激励内容（依赖 C1, B3）

---

## 三时报邮件模板详细设计

### 晨报（08:00）— 全局规划视角

主题：`🌤 晨报 - {date} 今日任务`

```
🌤 早上好！

📊 你的数据
  连续完成: 🔥 {streak} 天
  本周完成率: {weekly_rate}%

⚠️ 逾期任务（{overdue_count}项）
  - {task_name}（逾期 {days}天）
  ...

📋 今日任务（{today_count}项）
  {start_time}-{end_time}  {task_name}  [{priority_label}]
  {start_time}-{end_time}  {task_name}  [{priority_label}]
  ...
  [未安排时间] {task_name}（截止 {due_time}）

祝高效的一天！
```

### 午报（13:00）— 进度检查视角

主题：`☀️ 午报 - 下午安排`

```
☀️ 下午好！

📈 上午进度
  已完成: {morning_done}/{morning_total} 项
  {encouragement}  ← 完成多则鼓励，完成少则温和提醒

⚠️ 上午未完成（{morning_pending}项）
  - {task_name}（原定 {start_time}-{end_time}）
  ...

📋 下午待执行（{afternoon_count}项）
  {start_time}-{end_time}  {task_name}  [{priority_label}]
  ...

💡 提示：逾期任务已标红，请优先处理。
```

- encouragement 文案逻辑：
  - 完成率 >= 80%：「上午效率很高，继续保持！」
  - 完成率 50-79%：「上午完成了一半以上，下午继续加油！」
  - 完成率 < 50%：「上午的任务还有不少没完成，下午抓紧哦！」
  - 无上午任务：「今天上午没有安排任务，下午有 X 项待执行。」

### 晚报（21:00）— 总结反思视角

主题：`🌙 晚报 - 今日总结`

```
🌙 晚上好！

📊 今日总结
  完成率: {completed}/{total} ({rate}%)
  连续天数: 🔥 {streak} 天
  最长纪录: {longest_streak} 天

✅ 已完成（{completed_count}项）
  ✓ {task_name}（{start_time}-{end_time}）
  ...

❌ 未完成（{pending_count}项）→ 已转为逾期
  ✗ {task_name}（截止 {due_time}）
  ...

📅 明日预览（{tomorrow_count}项）
  {start_time}-{end_time}  {task_name}  [{priority_label}]
  ...

{closing_message}
```

- closing_message 逻辑：
  - 完成率 100%：「完美的一天！明天继续！🔥」
  - 完成率 >= 70%：「今天大部分任务都完成了，很棒！未完成的明天优先处理。💪」
  - 完成率 < 70%：「今天的完成率不太理想，明天重新规划一下？目标小一点，完成率高一点。」
  - 无任务：「今天没有安排任务，明天试试规划一下？」

---

## 文件变更清单

| 文件 | 改动类型 | 涉及子任务 |
|------|---------|-----------|
| `services/task_service.py` | 修改 | A1, A2, A4, A5 |
| `models/schemas.py` | 修改 | A2 |
| `services/ai_service.py` | 修改 | A3, D1 |
| `routers/task_manager.py` | 修改 | A5 |
| `routers/chat.py` | 修改 | D2 |
| `main.py` | 修改 | B2(注册router), B3(调度器) |
| `config.py` | 修改 | 无（通知配置独立文件） |
| `services/notification_service.py` | 新建 | B1, B3, B4, C4 |
| `routers/notification.py` | 新建 | B2 |
| `services/streak_service.py` | 新建 | C1 |
| `frontend/src/pages/Tasks.jsx` | 修改 | A6, A7, C3 |
| `frontend/src/pages/AiChat.jsx` | 修改 | D3 |
| `frontend/src/pages/Dashboard.jsx` | 修改 | C2 |
| `frontend/src/pages/Settings.jsx` | 修改 | B2 |
