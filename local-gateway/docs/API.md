# LocalCommandCenter API 文档

## 基础信息

- **基础URL**: `http://localhost:8900`
- **API前缀**: `/api`
- **Swagger UI**: `http://localhost:8900/docs`

---

## 任务管理

### 基础任务操作

#### POST /api/task
任务管理基础操作

**请求体**:
```json
{
  "action": "add_task|delete_task|complete_task|get_weekly_plan",
  "task_name": "任务名称",
  "task_id": "任务ID",
  "due_time": "2026-04-26T10:00:00+08:00",
  "recurrence": "once|daily|weekly|monthly",
  "priority": 2,
  "description": "任务描述",
  "estimated_minutes": 60,
  "tags": ["标签1", "标签2"]
}
```

#### POST /api/task/batch
批量任务编排

**请求体**:
```json
{
  "action": "preview|create",
  "tasks": [
    {
      "task_name": "任务名",
      "due_time": "2026-04-26",
      "recurrence": "once",
      "priority": 2
    }
  ]
}
```

### 高级任务功能

#### GET /api/tasks/all
获取所有任务（支持筛选）

**查询参数**:
- `status`: active|pending|completed|deleted
- `keyword`: 搜索关键词
- `tag`: 标签筛选
- `priority`: 0-3 (0=紧急, 3=低)
- `page`: 页码
- `page_size`: 每页数量

---

## 标签管理

#### GET /api/advanced/tags
获取所有标签

#### POST /api/advanced/tags
创建标签

**请求体**:
```json
{
  "name": "标签名",
  "color": "#3498db"
}
```

#### POST /api/advanced/tasks/{task_id}/tags
为任务添加标签

**请求体**: `["标签1", "标签2"]`

---

## 子任务管理

#### GET /api/advanced/tasks/{task_id}/subtasks
获取任务的所有子任务

#### POST /api/advanced/subtasks
创建子任务

**请求体**:
```json
{
  "task_id": "任务ID",
  "name": "子任务名称"
}
```

---

## 番茄钟

#### GET /api/advanced/pomodoro/status
获取当前番茄钟状态

#### POST /api/advanced/pomodoro/start
开始番茄钟

**请求体**:
```json
{
  "task_id": "关联任务ID(可选)",
  "duration_minutes": 25
}
```

#### POST /api/advanced/pomodoro/complete
完成番茄钟

#### POST /api/advanced/pomodoro/interrupt
中断番茄钟

**请求体**:
```json
{
  "session_id": "会话ID",
  "reason": "中断原因"
}
```

#### GET /api/advanced/pomodoro/stats
获取番茄钟统计

#### GET /api/advanced/pomodoro/history
获取历史记录

**查询参数**:
- `page`: 页码
- `page_size`: 每页数量

---

## 日历

#### GET /api/advanced/calendar/view
获取月历视图

**查询参数**:
- `year`: 年份
- `month`: 月份 (1-12)

#### GET /api/advanced/calendar/events
获取日历事件

**查询参数**:
- `start_date`: 开始日期 (YYYY-MM-DD)
- `end_date`: 结束日期 (YYYY-MM-DD)

#### POST /api/advanced/calendar/events
创建日历事件

**请求体**:
```json
{
  "title": "事件标题",
  "description": "描述",
  "start_time": "2026-04-26T10:00:00+08:00",
  "end_time": "2026-04-26T11:00:00+08:00",
  "event_type": "personal|work|meeting|deadline",
  "color": "#3498db"
}
```

---

## 笔记

#### GET /api/notes
获取笔记列表

**查询参数**:
- `keyword`: 搜索关键词
- `tag`: 标签筛选
- `page`: 页码

#### POST /api/notes
创建笔记

**请求体**:
```json
{
  "title": "笔记标题",
  "content": "笔记内容 (Markdown)",
  "content_type": "markdown",
  "tags": ["标签1"],
  "task_id": "关联任务ID"
}
```

#### GET /api/notes/{note_id}
获取单个笔记

#### PUT /api/notes/{note_id}
更新笔记

#### DELETE /api/notes/{note_id}
删除笔记

---

## 习惯

#### GET /api/habits
获取所有习惯

#### POST /api/habits
创建习惯

**请求体**:
```json
{
  "name": "习惯名称",
  "description": "描述",
  "frequency": "daily|weekly|monthly",
  "target_count": 1,
  "reminder_time": "09:00",
  "color": "#27ae60"
}
```

#### GET /api/habits/{habit_id}
获取习惯详情

#### POST /api/habits/{habit_id}/checkin
习惯打卡

**请求体**:
```json
{
  "count": 1,
  "note": "打卡备注"
}
```

#### GET /api/habits/{habit_id}/stats
获取习惯统计

---

## AI 规划

#### POST /api/ai/decompose
AI 任务拆解

**请求体**:
```json
{
  "task_name": "复杂任务名称",
  "description": "任务描述"
}
```

#### POST /api/ai/plan
AI 生成计划

**请求体**:
```json
{
  "tasks": [{"task_name": "", "due_time": ""}],
  "constraints": {}
}
```

#### POST /api/ai/estimate
AI 时间估算

**请求体**:
```json
{
  "task_name": "任务名",
  "description": "描述",
  "category": "类别"
}
```

#### GET /api/ai/suggestions
智能建议

#### GET /api/ai/insights
效率洞察

---

## 下载管理

#### POST /api/download
安全下载

**请求体**:
```json
{
  "url": "https://example.com/file.pdf",
  "category": "paper|video|code|misc",
  "filename": "可选的文件名"
}
```

#### GET /api/download/queue
获取下载队列状态

#### POST /api/download/queue
添加下载到队列

**查询参数**:
- `url`: 下载地址
- `category`: 分类
- `filename`: 文件名
- `priority`: 1-10 (越小优先级越高)

#### POST /api/download/pause/{job_id}
暂停下载

#### POST /api/download/resume/{job_id}
恢复下载

#### POST /api/download/cancel/{job_id}
取消下载

---

## 快捷键

#### GET /api/shortcuts
获取所有快捷键

#### POST /api/shortcuts
注册快捷键

**请求体**:
```json
{
  "key_combo": "ctrl+k",
  "shortcut_id": "search",
  "name": "搜索",
  "action": "open_search",
  "description": "打开搜索"
}
```

#### POST /api/shortcuts/trigger
触发快捷键

**请求体**:
```json
{
  "key_combo": "ctrl+k",
  "context": {}
}
```

---

## 语音

#### POST /api/voice/upload
上传语音文件

**Form Data**:
- `file`: 音频文件
- `transcribe`: 是否转文字 (true/false)

#### POST /api/voice/task
语音创建任务

**请求体**:
```json
{
  "transcription": "语音转文字内容"
}
```

---

## 沙盒执行

#### POST /api/sandbox
Docker 沙盒执行

**请求体**:
```json
{
  "tool_name": "python|node|ffmpeg|pandoc",
  "execution_command": "python script.py",
  "setup_commands": ["pip install xxx"],
  "dynamic_files": {
    "script.py": "print('hello')"
  },
  "input_files": ["/path/to/input"]
}
```

---

## AI 对话

#### POST /api/chat
AI 对话

**请求体**:
```json
{
  "message": "用户消息",
  "conversation_id": "default"
}
```

#### GET /api/chat/config
获取 AI 配置

#### POST /api/chat/config
更新 AI 配置

---

## 仪表盘

#### GET /api/dashboard
仪表盘统计

#### GET /api/download/history
下载历史

#### GET /api/logs
操作日志

#### GET /api/job/status
异步任务状态

**请求体**:
```json
{
  "job_id": "任务ID"
}
```

---

## 文件搜索

#### POST /api/search
搜索本地文件

**请求体**:
```json
{
  "keyword": "关键词",
  "category": "paper|video|code|misc|all"
}
```

---

## 环境变量

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `AI_API_BASE` | `https://open.bigmodel.cn/api/coding/paas/v4` | AI API 地址 |
| `AI_API_KEY` | - | AI API Key |
| `AI_MODEL` | `glm-4-flash` | AI 模型 |
| `GATEWAY_HOST` | `0.0.0.0` | 监听地址 |
| `GATEWAY_PORT` | `8900` | 监听端口 |
| `DOWNLOADS_DIR` | `./downloads` | 下载目录 |
| `SANDBOX_TIMEOUT` | `300` | 沙盒超时(秒) |
