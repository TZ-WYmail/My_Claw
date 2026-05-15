# LocalCommandCenter MVP API 契约

> 文档版本: 1.0
> 更新日期: 2026-05-15
> 依据文档: `MVP_PRD_2026-05-15.md`

---

## 一、目标

本文件用于定义 MVP 版本前后端联调所需的 API 契约，重点覆盖主链路：

**今天工作台 -> 任务 -> 日历 -> 笔记 -> AI 辅助**

目标是：

1. 明确 MVP 必要接口
2. 统一字段命名
3. 避免前端基于猜测拼装数据结构
4. 为后续接口重构提供边界

---

## 二、契约原则

1. 优先提供面向页面的稳定结构
2. 避免一个接口既服务旧逻辑又服务新逻辑
3. 所有时间字段统一使用 ISO 8601
4. 所有列表接口返回统一分页结构或明确声明不分页
5. 所有错误返回统一格式

---

## 三、通用响应格式

### 3.1 成功响应

```json
{
  "status": "success",
  "message": "optional",
  "data": {}
}
```

### 3.2 错误响应

```json
{
  "status": "error",
  "message": "human readable message",
  "code": "optional_error_code"
}
```

### 3.3 分页响应

```json
{
  "status": "success",
  "data": {
    "items": [],
    "page": 1,
    "page_size": 20,
    "total": 0
  }
}
```

---

## 四、首页工作台接口

### 4.1 `GET /api/mvp/today`

#### 用途

为“今天工作台”提供聚合数据。

#### 响应

```json
{
  "status": "success",
  "data": {
    "today_focus_tasks": [
      {
        "task_id": "t_001",
        "task_name": "完成周报",
        "priority": 1,
        "status": "in_progress",
        "start_time": "2026-05-15T09:00:00+08:00",
        "end_time": "2026-05-15T10:30:00+08:00",
        "due_time": "2026-05-15T18:00:00+08:00",
        "project": "团队运营"
      }
    ],
    "today_schedule": {
      "total_slots": 5,
      "scheduled_count": 3,
      "free_blocks": [
        {
          "start_time": "2026-05-15T14:00:00+08:00",
          "end_time": "2026-05-15T15:00:00+08:00"
        }
      ]
    },
    "overdue_tasks": [
      {
        "task_id": "t_009",
        "task_name": "补充文档",
        "due_time": "2026-05-13T18:00:00+08:00",
        "overdue_days": 2
      }
    ],
    "recent_notes": [
      {
        "note_id": "n_001",
        "title": "周会记录",
        "updated_at": "2026-05-15T08:30:00+08:00",
        "linked_task_id": "t_001"
      }
    ],
    "habit_summary": {
      "enabled": true,
      "today_checked_count": 1,
      "today_total_count": 3,
      "current_streak": 5
    }
  }
}
```

---

## 五、任务接口

### 5.1 `GET /api/mvp/tasks/today`

#### 用途

获取今日任务视图。

#### 查询参数

- `date`：可选，默认今天

#### 响应

```json
{
  "status": "success",
  "data": {
    "items": [
      {
        "task_id": "t_001",
        "task_name": "完成周报",
        "priority": 1,
        "status": "in_progress",
        "start_time": "2026-05-15T09:00:00+08:00",
        "end_time": "2026-05-15T10:30:00+08:00",
        "due_time": "2026-05-15T18:00:00+08:00",
        "project": "团队运营",
        "subtasks": [
          { "subtask_id": "s_001", "name": "整理数据", "status": "done" },
          { "subtask_id": "s_002", "name": "撰写总结", "status": "todo" }
        ],
        "linked_note_id": "n_001",
        "overdue": false
      }
    ]
  }
}
```

### 5.2 `GET /api/mvp/tasks/week`

#### 用途

获取本周任务视图。

#### 查询参数

- `week_start`：可选，周一日期

#### 响应

```json
{
  "status": "success",
  "data": {
    "items": [],
    "week_start": "2026-05-11",
    "week_end": "2026-05-17"
  }
}
```

### 5.3 `POST /api/mvp/tasks`

#### 用途

创建任务。

#### 请求体

```json
{
  "task_name": "完成周报",
  "priority": 1,
  "start_time": "2026-05-15T09:00:00+08:00",
  "end_time": "2026-05-15T10:30:00+08:00",
  "due_time": "2026-05-15T18:00:00+08:00",
  "project": "团队运营",
  "subtasks": [
    { "name": "整理数据" },
    { "name": "撰写总结" }
  ]
}
```

### 5.4 `PUT /api/mvp/tasks/{task_id}`

#### 用途

更新任务。

### 5.5 `POST /api/mvp/tasks/{task_id}/complete`

#### 用途

完成任务。

### 5.6 `DELETE /api/mvp/tasks/{task_id}`

#### 用途

删除任务。

### 5.7 `POST /api/mvp/tasks/{task_id}/link-note`

#### 用途

关联笔记。

#### 请求体

```json
{
  "note_id": "n_001"
}
```

---

## 六、日历接口

### 6.1 `GET /api/mvp/calendar/week`

#### 用途

获取周视图数据。

#### 响应

```json
{
  "status": "success",
  "data": {
    "days": [
      {
        "date": "2026-05-15",
        "items": [
          {
            "task_id": "t_001",
            "task_name": "完成周报",
            "start_time": "2026-05-15T09:00:00+08:00",
            "end_time": "2026-05-15T10:30:00+08:00",
            "priority": 1,
            "conflicted": false
          }
        ]
      }
    ]
  }
}
```

### 6.2 `GET /api/mvp/calendar/month`

#### 用途

获取月视图概览。

### 6.3 `POST /api/mvp/calendar/reschedule`

#### 用途

调整任务时间。

#### 请求体

```json
{
  "task_id": "t_001",
  "start_time": "2026-05-15T10:00:00+08:00",
  "end_time": "2026-05-15T11:00:00+08:00"
}
```

#### 响应

```json
{
  "status": "success",
  "message": "任务时间已更新",
  "data": {
    "task_id": "t_001",
    "conflicted": false
  }
}
```

---

## 七、笔记接口

### 7.1 `GET /api/mvp/notes/recent`

#### 用途

获取最近笔记。

### 7.2 `GET /api/mvp/notes`

#### 用途

获取笔记列表。

#### 查询参数

- `keyword`
- `page`
- `page_size`
- `linked_task_id`

### 7.3 `GET /api/mvp/notes/{note_id}`

#### 用途

获取单条笔记详情。

### 7.4 `POST /api/mvp/notes`

#### 用途

创建笔记。

#### 请求体

```json
{
  "title": "周会记录",
  "content": "# 周会记录",
  "tags": ["会议", "周报"],
  "linked_task_id": "t_001"
}
```

### 7.5 `PUT /api/mvp/notes/{note_id}`

#### 用途

更新笔记。

### 7.6 `DELETE /api/mvp/notes/{note_id}`

#### 用途

删除笔记。

### 7.7 `GET /api/mvp/note-templates`

#### 用途

获取笔记模板。

#### 响应

```json
{
  "status": "success",
  "data": {
    "items": [
      { "template_id": "meeting", "name": "会议纪要" },
      { "template_id": "project_log", "name": "项目日志" },
      { "template_id": "study_note", "name": "学习笔记" }
    ]
  }
}
```

---

## 八、AI 助手接口

### 8.1 `POST /api/mvp/ai/plan-today`

#### 用途

根据今日任务生成建议安排。

#### 请求体

```json
{
  "date": "2026-05-15"
}
```

#### 响应

```json
{
  "status": "success",
  "data": {
    "summary": "今天优先完成周报和项目复盘。",
    "suggested_actions": [
      {
        "type": "reschedule_task",
        "task_id": "t_001",
        "start_time": "2026-05-15T09:00:00+08:00",
        "end_time": "2026-05-15T10:30:00+08:00",
        "reason": "该任务优先级高且已接近截止时间"
      }
    ],
    "requires_confirmation": true
  }
}
```

### 8.2 `POST /api/mvp/ai/breakdown-task`

#### 用途

拆解任务为轻量子任务。

### 8.3 `POST /api/mvp/ai/summarize-note`

#### 用途

整理零散记录为结构化笔记。

### 8.4 `POST /api/mvp/ai/day-review`

#### 用途

生成简短日终回顾。

### 8.5 `POST /api/mvp/ai/apply`

#### 用途

在用户确认后应用 AI 建议。

#### 请求体

```json
{
  "action_id": "a_001",
  "confirmed": true
}
```

---

## 九、设置接口

### 9.1 `GET /api/mvp/settings`

#### 用途

获取 MVP 设置页所需的最小配置。

### 9.2 `PUT /api/mvp/settings/theme`

#### 用途

更新主题。

### 9.3 `PUT /api/mvp/settings/ai`

#### 用途

更新 AI 基础连接配置。

### 9.4 `POST /api/mvp/settings/ai/test`

#### 用途

测试 AI 连接。

---

## 十、字段约定

### 时间字段

- `start_time`
- `end_time`
- `due_time`
- `created_at`
- `updated_at`

统一使用 ISO 8601。

### 状态字段

任务状态统一为：

- `todo`
- `in_progress`
- `done`
- `overdue`

### 优先级字段

- `0`：紧急
- `1`：高
- `2`：中
- `3`：低

---

## 十一、兼容策略

MVP 契约不要求立即替换仓库内所有旧接口，但要求：

1. 前端 MVP 页面只依赖这里定义的新契约或稳定适配层
2. 旧接口不得继续直接暴露给新页面
3. 若短期内复用旧接口，必须在服务端或前端建立显式 adapter

---

## 十二、总结

MVP API 契约的重点是稳定服务主链路，而不是维护所有历史能力的兼容面。

只要能稳定支持：

1. 首页聚合
2. 任务管理
3. 日历排程
4. 笔记记录
5. AI 轻量辅助

这个 MVP 契约就是合格的。
