# 任务时间范围 + 邮件提醒 + 多对话管理 + 激励机制 设计文档

日期: 2026-05-10

## 概述

对 LocalCommandCenter 进行四项改进：
1. 任务增加时间范围（start_time / end_time），支持周视图时间轴渲染
2. 邮件提醒系统（晨报、开始前提醒、截止前提醒）
3. AI 对话多会话管理（新建/切换/删除对话）
4. 任务完成激励机制（streak、逾期压力、即时反馈）

---

## 模块 1：任务时间范围

### 数据库变更

`tasks` 表新增两列（可空，兼容旧数据）：

```sql
ALTER TABLE tasks ADD COLUMN start_time TEXT;
ALTER TABLE tasks ADD COLUMN end_time TEXT;
```

- 旧数据：`start_time`/`end_time` 为 NULL 时，前端回退显示 `due_time`
- 新数据：`start_time` + `end_time` 表示执行时间段，`due_time` 表示截止时间（语义不变）

### Schema 变更

**models/schemas.py**：
- `TaskManagerRequest` 增加 `start_time: Optional[str]`、`end_time: Optional[str]`
- `TaskInfo` 增加 `start_time: Optional[str]`、`end_time: Optional[str]`
- `BatchTaskItem` 同样增加
- `TaskManagerResponse` 增加 `warnings: Optional[list[str]]`

**services/ai_service.py TOOLS_SCHEMA**：
- `local_task_manager` 的 parameters 增加 `start_time`/`end_time`
- `batch_task_manager` 的 tasks items 增加 `start_time`/`end_time`

### 冲突检测

`task_service.py` 新增 `_check_conflicts(start_time, end_time, exclude_task_id=None)` 方法：

- 查询同一日期内时间段重叠的已有任务
- 计算当日已有总工时，超 8h 标记过载
- 在 `add_task` 和 `batch_add_tasks` 中自动调用
- 返回 `warnings` 列表：`["09:00-11:00 与已有任务「项目会议」时间冲突", "今日已有 7h 任务，接近上限"]`

### 未完成任务感知

- `local_task_manager` 新增 action：`get_pending_tasks`，查询所有 status=pending 且 due_time < now 的任务
- `batch_task_manager(preview)` 返回数据增加 `existing_tasks`（相关日期的已有任务列表）
- system prompt 增加规则：创建任务前先用 get_pending_tasks / get_weekly_plan 了解已有安排

### 前端周视图改造

当前周视图（`Tasks.jsx` WeekView）只是一个表格。改造为时间轴视图：

- 7 列日历（周一~周日）+ 24 行时间轴（0:00-23:00）
- 任务块按 `start_time` 定位在对应行，高度按 start_time→end_time 计算
- 无 start_time 的任务放在底部「未安排时间」区域
- 任务块显示：任务名 + 时间范围，颜色按优先级区分（紧急=红、高=橙、中=蓝、低=灰）

### 任务表单改造

`TaskForm` 组件增加：
- 「开始时间」datetime-local 输入
- 「结束时间」datetime-local 输入
- 保留「截止时间」不变

---

## 模块 2：邮件提醒系统

### 架构

全部在 FastAPI 进程内，使用已有的 APScheduler：

```
APScheduler (后台线程)
  ├── cron: 每天 8:00 → 查今日任务+未完成 → 发晨报邮件
  ├── 动态 job: 任务 start_time 前 15min → 发开始提醒
  └── 动态 job: 任务 due_time 前 30min → 发截止提醒
```

### 邮件配置

存在 `data/ai_config.json`，前端 Settings 页可配置：

| 字段 | 说明 | 示例 |
|------|------|------|
| `smtp_host` | SMTP 服务器 | smtp.qq.com |
| `smtp_port` | 端口 | 465 |
| `smtp_user` | 发件邮箱 | xxx@qq.com |
| `smtp_password` | 授权码 | xxxxxxxx |
| `notify_email` | 收件邮箱 | user@example.com |
| `reminder_minutes_before` | 提前多少分钟提醒 | 15 |

- 配置变更时，重新注册所有 scheduler job
- 首次配置后发一封测试邮件验证连通性

### 新增文件

- `services/notification_service.py`：邮件发送 + APScheduler 调度逻辑
- `routers/notification.py`：配置 CRUD + 测试发送端点

### 新增 API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/notification/config` | GET | 获取通知配置（密码脱敏） |
| `/api/notification/config` | POST | 保存通知配置 |
| `/api/notification/test` | POST | 发送测试邮件 |

### 提醒模板

**晨报（每日 8:00）**：
```
📊 你的数据
  连续完成: 🔥 5 天
  本周完成率: 78%

⚠️ 逾期任务（2项）
  - 数据分析（逾期 3 天）
  - 文档整理（逾期 1 天）

📋 今日任务（3项）
  09:00-10:30  项目会议  [高优先级]
  14:00-16:00  写报告    [中优先级]
```

**开始前提醒**：`「项目会议」将在 15 分钟后开始 (09:00-10:30)`

**截止前提醒**：`「写报告」将在 30 分钟后截止 (截止时间: 16:00)`

### 调度逻辑

- `add_task`：注册 start_time 前 N 分钟的提醒 job + due_time 前 30 分钟的提醒 job
- `complete_task`：取消该任务的提醒 job
- `delete_task`：取消该任务的提醒 job
- 服务重启时：从数据库重新加载所有 pending 任务，重新注册 job
- 配置变更时：清除所有现有 job，重新注册

---

## 模块 3：多对话管理

### 现状

后端已支持 `conversation_id`，前端硬编码 `'default'`。对话历史存 `data/conversations/{id}.jsonl`。后端有 `list_conversations` 和 `get_chat_history`，但前端未使用多对话。

### 后端改动

**新增 API**：

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/chat/conversations` | POST | 新建对话，返回 conversation_id |
| `/api/chat/conversations/{id}` | DELETE | 删除对话（内存+磁盘） |

**修改 API**：

| 端点 | 变更 |
|------|------|
| `GET /api/chat/conversations` | 返回数据增加 `title`（第一条用户消息前 30 字）、`message_count` |
| `POST /api/chat/clear` | 改为同时删除磁盘文件（`{id}.jsonl` + `{id}_history.jsonl`） |

**对话元数据**：

新增 `data/conversations/{id}_meta.json`：
```json
{"title": "今日任务规划", "created_at": "2026-05-10T08:00:00", "updated_at": "2026-05-10T09:30:00"}
```

- 新对话的第一条用户消息自动成为标题（前 30 字）
- 每次发消息时更新 `updated_at`

### 前端改动

AiChat 页面布局从单栏改为 **左栏对话列表 + 右栏聊天区**：

```
┌──────────┬──────────────────────────┐
│ + 新对话  │  AI 对话  deepseek-v4    │
│──────────│──────────────────────────│
│ 今日任务  │  [消息区域]              │
│ 规划     │                          │
│ 代码调试  │                          │
│          │                          │
│          │──────────────────────────│
│          │  [输入框]        [发送]   │
└──────────┴──────────────────────────┘
```

- 左栏宽度 240px，对话列表按 `updated_at` 倒序
- 每项显示：标题 + 最后更新时间
- 顶部「+ 新对话」按钮，点击生成 UUID 作为新 conversation_id
- 点击对话项切换，加载对应历史消息
- 当前对话高亮，hover 显示删除按钮
- 左栏在窄屏可折叠（汉堡菜单）

### 清除对话语义

- 「删除对话」= 删除整个对话（内存+磁盘+元数据）
- 「新建对话」= 新 conversation_id，全新上下文
- 「切换对话」= 加载旧对话历史，恢复上下文继续聊

---

## 模块 4：任务积极性激励

### 第一层：即时反馈

- 完成任务时前端弹出简短提示：「已完成 3/5 项今日任务」
- 全部完成时：「今日任务全部完成！」
- 完成动画：任务卡片划线+淡出
- Dashboard 顶部增加每日完成率进度条

### 第二层：延迟压力

- 未完成任务按逾期天数分级着色：
  - 逾期 1 天：黄色边框
  - 逾期 2-3 天：橙色边框 + 「!」标记
  - 逾期 7 天+：红色边框 + 「严重逾期」标签
- Dashboard 增加「逾期任务」红色卡片
- 晨报邮件中逾期任务排在最前面

### 第三层：连续成就（Streak）

- **连续完成天数**：当天所有任务都完成（或无任务），streak+1；有未完成，streak 归零
- Dashboard 显示当前 streak：「已连续 5 天完成所有任务 🔥」
- 里程碑通知：streak 达到 7/14/30 天时邮件祝贺
- 周报邮件：本周完成率、与上周对比、streak 状态

### 数据支撑

- `tasks` 表新增 `completed_at TEXT` 列
- 新增 `data/streak.json`：
  ```json
  {"current_streak": 5, "longest_streak": 12, "last_check_date": "2026-05-10"}
  ```
- 每日首次打开 Dashboard 或晨报触发时，计算当天是否「全部完成」来更新 streak

### 不做

- 不做积分/金币/等级体系
- 不做社交排名
- 不做惩罚机制

---

## 实现优先级

1. **模块 1（时间范围）** — 其他模块依赖它，必须先做
2. **模块 2（邮件提醒）** — 依赖模块 1 的 start_time/end_time
3. **模块 4（激励机制）** — 依赖模块 1 的 completed_at 和模块 2 的邮件
4. **模块 3（多对话）** — 独立模块，可并行或最后做
