# Phase 3 API 文档

## 日历同步

### GET /api/calendar/sync/status
获取日历同步状态

### GET /api/calendar/sync/google/auth
获取 Google 授权 URL

### POST /api/calendar/sync/google/callback
Google OAuth 回调

**请求体**:
```json
{
  "code": "授权码",
  "redirect_uri": "回调URL",
  "client_id": "Google Client ID",
  "client_secret": "Google Client Secret"
}
```

### POST /api/calendar/sync/google/sync
从 Google Calendar 同步事件

### GET /api/calendar/sync/outlook/auth
获取 Outlook 授权 URL

### POST /api/calendar/sync/outlook/callback
Outlook OAuth 回调

### POST /api/calendar/sync/outlook/sync
从 Outlook Calendar 同步事件

### POST /api/calendar/sync/{provider}/toggle
启用/禁用同步

### POST /api/calendar/sync/{provider}/disconnect
断开日历连接

---

## 全文检索

### GET /api/search/fulltext
全文搜索

**查询参数**:
- `q`: 搜索关键词
- `category`: 分类筛选
- `top_k`: 返回数量 (默认20)

### POST /api/search/index
构建/更新搜索索引

### GET /api/search/index/stats
获取索引统计

### POST /api/search/index/rebuild
重建搜索索引

---

## Webhook

### GET /api/webhooks
获取所有 Webhook

### POST /api/webhooks
注册 Webhook

**请求体**:
```json
{
  "url": "https://example.com/webhook",
  "events": ["task.completed", "habit.checkin"],
  "secret": "签名密钥",
  "description": "描述"
}
```

### DELETE /api/webhooks/{webhook_id}
删除 Webhook

### POST /api/webhooks/{webhook_id}/toggle
启用/禁用 Webhook

### POST /api/webhooks/broadcast
广播事件

---

## 工作流

### GET /api/workflows
获取所有工作流

### POST /api/workflows
创建工作流

**请求体**:
```json
{
  "name": "自动归档",
  "description": "完成任务后创建笔记",
  "trigger": {
    "type": "task_completed",
    "conditions": {}
  },
  "actions": [
    {
      "type": "create_note",
      "config": {
        "title": "任务完成: {{task_name}}",
        "content": "任务已完成"
      }
    }
  ]
}
```

### POST /api/workflows/{workflow_id}/execute
手动执行工作流

### GET /api/workflows/types/triggers
获取触发器类型列表

### GET /api/workflows/types/actions
获取动作类型列表
