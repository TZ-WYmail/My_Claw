# Phase 3: 生态连接 - 详细实现文档

> 目标: 连接外部系统，成为数字中枢
> 预计工期: 8-10周
> 版本目标: v0.9.0
> 依赖: Phase 1-2完成

---

## 一、本阶段目标

### 1.1 核心交付物

| 类别 | 交付物 | 验收标准 |
|------|--------|----------|
| 集成 | 日历同步 | 支持Google/Outlook/iCloud双向同步 |
| 集成 | 生产力工具 | Notion/Obsidian/Zotero集成 |
| 集成 | 开发工具 | GitHub/GitLab/Issue同步 |
| 功能 | 全文检索 | 支持PDF/图片OCR/代码内容搜索 |
| 功能 | 自动化工作流 | 可视化流程编排，支持触发器和动作 |
| 功能 | Webhook系统 | 接收外部事件，触发内部流程 |
| 架构 | 插件系统基础 | 支持第三方扩展开发 |

### 1.2 用户价值

完成Phase 3后，用户可以：
- 任务与日历双向同步，一处管理时间
- 笔记与Notion/Obsidian双向同步
- GitHub Issues自动同步为本地任务
- 搜索PDF内容和图片中的文字
- 设置自动化流程（如下载后自动处理）

---

## 二、模块详细设计

### 2.1 日历同步系统

#### 2.1.1 支持的服务

| 服务 | 协议 | 功能 | 优先级 |
|------|------|------|--------|
| Google Calendar | CalDAV + API | 双向同步 | P0 |
| Outlook | Microsoft Graph | 双向同步 | P0 |
| 苹果日历 | CalDAV | 双向同步 | P1 |
| 飞书日历 | OpenAPI | 单向导入 | P1 |
| 钉钉日历 | OpenAPI | 单向导入 | P2 |

#### 2.1.2 数据库Schema

```sql
-- 外部账户表
CREATE TABLE external_accounts (
    account_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    provider TEXT NOT NULL, -- google/outlook/caldav/feishu
    account_name TEXT,
    
    -- OAuth凭证
    access_token TEXT,
    refresh_token TEXT,
    token_expires_at TEXT,
    
    -- 同步设置
    sync_enabled BOOLEAN DEFAULT 1,
    sync_direction TEXT DEFAULT 'bidirectional', -- import/export/bidirectional
    default_calendar_id TEXT,
    
    -- 状态
    last_sync_at TEXT,
    sync_status TEXT DEFAULT 'active', -- active/error/disabled
    error_message TEXT,
    
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

-- 同步映射表（本地任务 <-> 外部事件）
CREATE TABLE calendar_sync_mappings (
    mapping_id TEXT PRIMARY KEY,
    local_task_id TEXT,
    external_event_id TEXT,
    external_calendar_id TEXT,
    account_id TEXT,
    last_synced_at TEXT,
    external_etag TEXT, -- 用于增量同步
    
    FOREIGN KEY (local_task_id) REFERENCES tasks(task_id) ON DELETE CASCADE,
    FOREIGN KEY (account_id) REFERENCES external_accounts(account_id) ON DELETE CASCADE
);

-- 同步日志
CREATE TABLE sync_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id TEXT,
    sync_type TEXT, -- import/export/full
    status TEXT, -- success/partial/failed
    items_synced INTEGER DEFAULT 0,
    items_failed INTEGER DEFAULT 0,
    error_details TEXT,
    started_at TEXT,
    completed_at TEXT
);
```

#### 2.1.3 同步策略

```
同步触发时机:
1. 定时同步 (每15分钟)
2. 实时推送 (Webhook - Google/Outlook支持)
3. 手动触发
4. 本地变更后立即推送

冲突解决策略:
1. 时间戳优先 (last-write-wins)
2. 用户配置优先级
3. 手动合并界面

增量同步流程:
1. 获取上次同步时间
2. 查询外部变更 (使用syncToken/ctime)
3. 查询本地变更
4. 应用变更
5. 记录同步时间
```

#### 2.1.4 API设计

```python
# 账户管理
POST   /api/integrations/calendar/accounts
GET    /api/integrations/calendar/accounts
DELETE /api/integrations/calendar/accounts/{account_id}

# OAuth回调
GET    /api/integrations/calendar/callback/{provider}

# 手动同步
POST   /api/integrations/calendar/sync/{account_id}
GET    /api/integrations/calendar/sync-status/{account_id}

# 日历列表
GET    /api/integrations/calendar/{account_id}/calendars
PUT    /api/integrations/calendar/{account_id}/settings
```

#### 2.1.5 Google Calendar集成示例

```python
# services/integrations/calendar/google.py

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request

class GoogleCalendarProvider:
    SCOPES = ['https://www.googleapis.com/auth/calendar']
    
    def __init__(self, account: ExternalAccount):
        self.account = account
        self.creds = self._get_credentials()
        self.service = build('calendar', 'v3', credentials=self.creds)
    
    def _get_credentials(self) -> Credentials:
        creds = Credentials(
            token=self.account.access_token,
            refresh_token=self.account.refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=GOOGLE_CLIENT_ID,
            client_secret=GOOGLE_CLIENT_SECRET,
            scopes=self.SCOPES
        )
        
        # 检查并刷新token
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            await self._update_tokens(creds.token, creds.expiry)
        
        return creds
    
    async def sync_from_external(self, since: datetime) -> List[SyncItem]:
        """从Google同步到本地"""
        events_result = self.service.events().list(
            calendarId=self.account.default_calendar_id or 'primary',
            updatedMin=since.isoformat(),
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        
        sync_items = []
        for event in events:
            sync_items.append(SyncItem(
                external_id=event['id'],
                title=event.get('summary', ''),
                description=event.get('description', ''),
                start=self._parse_datetime(event['start']),
                end=self._parse_datetime(event['end']),
                external_etag=event['etag'],
                updated_at=self._parse_datetime(event['updated'])
            ))
        
        return sync_items
    
    async def sync_to_external(self, task: Task) -> str:
        """将本地任务同步到Google"""
        event = {
            'summary': task.name,
            'description': task.description,
            'start': {
                'dateTime': task.due_time,
                'timeZone': 'Asia/Shanghai',
            },
            'end': {
                'dateTime': task.end_time or task.due_time + timedelta(hours=1),
                'timeZone': 'Asia/Shanghai',
            },
        }
        
        if task.external_event_id:
            # 更新现有事件
            event = self.service.events().update(
                calendarId=self.account.default_calendar_id or 'primary',
                eventId=task.external_event_id,
                body=event
            ).execute()
        else:
            # 创建新事件
            event = self.service.events().insert(
                calendarId=self.account.default_calendar_id or 'primary',
                body=event
            ).execute()
        
        return event['id']
```

---

### 2.2 第三方工具集成

#### 2.2.1 Notion集成

```python
# services/integrations/notion/client.py

from notion_client import Client

class NotionIntegration:
    def __init__(self, token: str):
        self.client = Client(auth=token)
    
    async def sync_database_to_tasks(
        self, 
        database_id: str,
        task_mapping: Dict[str, str]  # Notion字段 -> Task字段
    ) -> List[Task]:
        """将Notion数据库同步为本地任务"""
        
        results = self.client.databases.query(
            database_id=database_id,
            filter={
                "property": "Status",
                "select": {
                    "does_not_equal": "Done"
                }
            }
        )
        
        tasks = []
        for page in results["results"]:
            task = await self._convert_page_to_task(page, task_mapping)
            tasks.append(task)
        
        return tasks
    
    async def push_task_to_notion(self, task: Task, database_id: str):
        """将本地任务推送到Notion"""
        properties = {
            "Name": {"title": [{"text": {"content": task.name}}]},
            "Status": {"select": {"name": "Not started" if task.status == "pending" else "In progress"}},
            "Due Date": {"date": {"start": task.due_time}},
        }
        
        if task.external_notion_page_id:
            # 更新
            self.client.pages.update(
                page_id=task.external_notion_page_id,
                properties=properties
            )
        else:
            # 创建
            page = self.client.pages.create(
                parent={"database_id": database_id},
                properties=properties
            )
            task.external_notion_page_id = page["id"]
```

#### 2.2.2 GitHub集成

```python
# services/integrations/github/client.py

from github import Github

class GitHubIntegration:
    def __init__(self, token: str):
        self.github = Github(token)
    
    async def sync_issues_to_tasks(
        self,
        repos: List[str],  # ["owner/repo", ...]
        labels: Optional[List[str]] = None
    ) -> List[Task]:
        """将GitHub Issues同步为本地任务"""
        
        tasks = []
        for repo_name in repos:
            repo = self.github.get_repo(repo_name)
            
            # 构建查询
            query = "state:open"
            if labels:
                for label in labels:
                    query += f" label:{label}"
            
            issues = repo.get_issues(state='open', labels=labels)
            
            for issue in issues:
                task = await self._convert_issue_to_task(issue)
                tasks.append(task)
        
        return tasks
    
    async def create_issue_from_task(self, task: Task, repo: str) -> str:
        """从本地任务创建GitHub Issue"""
        repo_obj = self.github.get_repo(repo)
        
        issue = repo_obj.create_issue(
            title=task.name,
            body=task.description,
            labels=["from-local-command-center"]
        )
        
        return issue.number
    
    async def setup_webhook_listener(self, repo: str, webhook_url: str):
        """设置Webhook接收Issue变更"""
        repo_obj = self.github.get_repo(repo)
        
        config = {
            "url": webhook_url,
            "content_type": "json"
        }
        
        events = ["issues"]
        
        repo_obj.create_hook(
            name="web",
            config=config,
            events=events,
            active=True
        )
```

#### 2.2.3 集成配置界面

```yaml
# config/integrations.yaml
integrations:
  notion:
    enabled: true
    token: ${NOTION_TOKEN}
    databases:
      - id: "abc123"
        name: "项目任务"
        sync_direction: "bidirectional"
        field_mapping:
          "Name": "name"
          "Due Date": "due_time"
          "Priority": "priority"
          "Status": "status"
  
  github:
    enabled: true
    token: ${GITHUB_TOKEN}
    repos:
      - "myorg/project-a"
      - "myorg/project-b"
    sync:
      issues: true
      pull_requests: true
      labels: ["bug", "feature"]
```

---

### 2.3 全文检索系统

#### 2.3.1 技术选型

| 方案 | 优点 | 缺点 | 选择 |
|------|------|------|------|
| SQLite FTS5 | 无需额外服务 | 功能有限 | 基础搜索 |
| Whoosh (Python) | 纯Python | 性能一般 | 不推荐 |
| Elasticsearch | 功能强大 | 资源占用高 | 未来扩展 |
| Meilisearch | 轻量、快速 | 需额外服务 | **推荐** |

**选择: Meilisearch**
- 轻量级，Docker部署简单
- 支持中文分词
- 实时索引
- 容错搜索

#### 2.3.2 索引设计

```python
# services/search/indexer.py

from meilisearch import Client

class SearchIndexer:
    def __init__(self):
        self.client = Client('http://localhost:7700', 'masterKey')
    
    async def setup_indices(self):
        """初始化索引"""
        # 任务索引
        self.client.create_index('tasks', {'primaryKey': 'id'})
        self.client.index('tasks').update_settings({
            'searchableAttributes': ['name', 'description'],
            'filterableAttributes': ['status', 'priority', 'tags', 'due_date'],
            'sortableAttributes': ['due_date', 'created_at']
        })
        
        # 文件索引
        self.client.create_index('files', {'primaryKey': 'path'})
        self.client.index('files').update_settings({
            'searchableAttributes': ['filename', 'content', 'ocr_text'],
            'filterableAttributes': ['category', 'file_type', 'size'],
        })
        
        # 笔记索引
        self.client.create_index('notes', {'primaryKey': 'id'})
        self.client.index('notes').update_settings({
            'searchableAttributes': ['title', 'content'],
        })
    
    async def index_task(self, task: Task):
        """索引任务"""
        document = {
            'id': task.task_id,
            'name': task.name,
            'description': task.description,
            'status': task.status,
            'priority': task.priority,
            'tags': task.tags,
            'due_date': task.due_time,
            'created_at': task.created_at
        }
        self.client.index('tasks').add_documents([document])
    
    async def index_file(self, file_info: FileInfo, content: str = "", ocr_text: str = ""):
        """索引文件"""
        document = {
            'path': file_info.path,
            'filename': file_info.filename,
            'category': file_info.category,
            'content': content[:10000],  # 限制大小
            'ocr_text': ocr_text,
            'file_type': file_info.extension,
            'size': file_info.size
        }
        self.client.index('files').add_documents([document])
```

#### 2.3.3 内容提取

```python
# services/search/extractors.py

import fitz  # PyMuPDF
from PIL import Image
import pytesseract

def extract_pdf_content(filepath: str) -> str:
    """提取PDF文本内容"""
    doc = fitz.open(filepath)
    text = ""
    for page in doc:
        text += page.get_text()
    doc.close()
    return text

def extract_image_text(filepath: str, lang: str = 'chi_sim+eng') -> str:
    """OCR提取图片文字"""
    image = Image.open(filepath)
    text = pytesseract.image_to_string(image, lang=lang)
    return text

def extract_code_content(filepath: str) -> str:
    """提取代码文件内容"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except:
        return ""

# 文件类型映射
EXTRACTORS = {
    '.pdf': extract_pdf_content,
    '.txt': extract_code_content,
    '.py': extract_code_content,
    '.js': extract_code_content,
    '.md': extract_code_content,
    '.png': extract_image_text,
    '.jpg': extract_image_text,
    '.jpeg': extract_image_text,
}
```

#### 2.3.4 搜索API

```python
GET /api/search/unified
Query: {
    "q": "搜索关键词",
    "types": ["task", "file", "note"],  # 搜索类型
    "filters": {
        "task_status": "pending",
        "file_category": "paper"
    },
    "sort": "relevance",  # relevance/date
    "limit": 20,
    "offset": 0
}
Response: {
    "hits": [
        {
            "type": "task",
            "id": "task_xxx",
            "title": "任务名称",
            "highlight": "...关键词...",
            "url": "/tasks/task_xxx"
        },
        {
            "type": "file",
            "path": "/downloads/paper/xxx.pdf",
            "title": "文件名",
            "highlight": "...关键词...",
            "url": "/files/view?path=xxx"
        }
    ],
    "total": 42,
    "facets": {
        "by_type": {"task": 10, "file": 20, "note": 12}
    }
}
```

---

### 2.4 自动化工作流引擎

#### 2.4.1 架构设计

```
触发器 (Trigger)
    ├── 定时触发 (Cron)
    ├── 事件触发 (Event)
    │       ├── 任务创建/完成
    │       ├── 文件下载完成
    │       └── Webhook接收
    └── 手动触发

    ↓

条件判断 (Condition)
    ├── IF-ELSE
    ├── 循环
    └── 并行分支

    ↓

动作 (Action)
    ├── 本地动作
    │       ├── 创建任务
    │       ├── 发送通知
    │       └── 执行沙盒
    ├── 集成动作
    │       ├── 发送邮件
    │       ├── 调用API
    │       └── 推送消息
    └── 文件动作
            ├── 移动/复制文件
            ├── 解压/压缩
            └── 格式转换
```

#### 2.4.2 数据库Schema

```sql
-- 工作流定义
CREATE TABLE workflows (
    workflow_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    
    -- 触发器配置 (JSON)
    trigger_type TEXT, -- cron/event/webhook/manual
    trigger_config TEXT, -- JSON
    
    -- 流程定义 (JSON)
    flow_definition TEXT NOT NULL, -- 节点和连接
    
    -- 状态
    enabled BOOLEAN DEFAULT 1,
    last_run_at TEXT,
    last_run_status TEXT,
    last_run_error TEXT,
    
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

-- 工作流执行记录
CREATE TABLE workflow_executions (
    execution_id TEXT PRIMARY KEY,
    workflow_id TEXT,
    status TEXT, -- running/completed/failed
    trigger_data TEXT, -- 触发时的数据
    context TEXT, -- 执行上下文
    started_at TEXT,
    completed_at TEXT,
    error_message TEXT,
    
    FOREIGN KEY (workflow_id) REFERENCES workflows(workflow_id)
);

-- 执行步骤日志
CREATE TABLE workflow_step_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    execution_id TEXT,
    step_id TEXT,
    step_type TEXT,
    input_data TEXT,
    output_data TEXT,
    status TEXT,
    started_at TEXT,
    completed_at TEXT,
    error_message TEXT
);
```

#### 2.4.3 流程定义格式

```json
{
  "nodes": [
    {
      "id": "trigger-1",
      "type": "trigger",
      "subtype": "event",
      "config": {
        "event": "download.completed"
      }
    },
    {
      "id": "condition-1",
      "type": "condition",
      "config": {
        "expression": "{{file.category}} == 'paper'"
      }
    },
    {
      "id": "action-1",
      "type": "action",
      "subtype": "sandbox",
      "config": {
        "tool": "python",
        "script": "extract_summary.py",
        "input": "{{file.path}}"
      }
    },
    {
      "id": "action-2",
      "type": "action",
      "subtype": "notification",
      "config": {
        "type": "desktop",
        "message": "论文摘要已生成: {{output.summary}}"
      }
    }
  ],
  "edges": [
    {"from": "trigger-1", "to": "condition-1"},
    {"from": "condition-1", "to": "action-1", "label": "true"},
    {"from": "action-1", "to": "action-2"}
  ]
}
```

#### 2.4.4 执行引擎

```python
# services/automation/engine.py

class WorkflowEngine:
    def __init__(self):
        self.executors = {
            'trigger': TriggerExecutor(),
            'condition': ConditionExecutor(),
            'action': ActionExecutor(),
        }
    
    async def execute(self, workflow: Workflow, trigger_data: dict = None):
        """执行工作流"""
        execution = await self.create_execution(workflow, trigger_data)
        
        try:
            context = ExecutionContext(
                execution_id=execution.execution_id,
                variables=trigger_data or {}
            )
            
            # 解析流程图
            flow = FlowParser(workflow.flow_definition)
            
            # 从触发器开始执行
            start_node = flow.get_start_node()
            await self.execute_node(start_node, context, flow)
            
            execution.status = 'completed'
        except Exception as e:
            execution.status = 'failed'
            execution.error_message = str(e)
            raise
        finally:
            execution.completed_at = datetime.now()
            await self.save_execution(execution)
    
    async def execute_node(self, node, context: ExecutionContext, flow: FlowParser):
        """执行单个节点"""
        executor = self.executors[node.type]
        
        # 执行节点
        result = await executor.execute(node, context)
        
        # 记录日志
        await self.log_step(node, context, result)
        
        # 更新上下文
        context.variables[f"node_{node.id}_output"] = result
        
        # 找到下一个节点
        next_nodes = flow.get_next_nodes(node, result)
        for next_node in next_nodes:
            await self.execute_node(next_node, context, flow)

class ActionExecutor:
    async def execute(self, node, context):
        subtype = node.subtype
        config = self.render_config(node.config, context)
        
        if subtype == 'sandbox':
            return await self.run_sandbox(config)
        elif subtype == 'notification':
            return await self.send_notification(config)
        elif subtype == 'task':
            return await self.create_task(config)
        # ... 更多动作
    
    def render_config(self, config: dict, context: ExecutionContext) -> dict:
        """渲染模板变量"""
        template = Template(json.dumps(config))
        rendered = template.render(**context.variables)
        return json.loads(rendered)
```

---

### 2.5 Webhook系统

#### 2.5.1 接收Webhook

```python
# routers/webhook.py

from fastapi import APIRouter, Request, Header

router = APIRouter(prefix="/webhook")

@router.post("/{integration}/{event}")
async def receive_webhook(
    integration: str,  # github/notion/custom
    event: str,
    request: Request,
    x_hub_signature: Optional[str] = Header(None)
):
    """接收外部Webhook"""
    
    payload = await request.json()
    
    # 验证签名
    if not verify_webhook_signature(integration, payload, x_hub_signature):
        raise HTTPException(401, "Invalid signature")
    
    # 转换为标准事件格式
    standard_event = WebhookAdapter.adapt(integration, event, payload)
    
    # 存储原始事件
    await store_webhook_event(integration, event, payload)
    
    # 触发工作流
    await trigger_workflows(standard_event)
    
    return {"status": "received"}

# 适配器
class GitHubWebhookAdapter:
    @staticmethod
    def adapt(event: str, payload: dict) -> StandardEvent:
        if event == "issues":
            action = payload.get("action")
            issue = payload.get("issue", {})
            
            return StandardEvent(
                source="github",
                event_type=f"issue.{action}",
                data={
                    "id": str(issue.get("id")),
                    "title": issue.get("title"),
                    "body": issue.get("body"),
                    "url": issue.get("html_url"),
                    "state": issue.get("state"),
                    "labels": [l["name"] for l in issue.get("labels", [])]
                }
            )
```

#### 2.5.2 发送Webhook

```python
# 用户可以配置外部Webhook
POST /api/webhooks/outgoing
Body: {
    "name": "任务完成通知",
    "url": "https://example.com/webhook",
    "events": ["task.completed", "habit.checked"],
    "secret": "webhook_secret_for_signature",
    "active": true
}
```

---

## 三、实现时间表

| 周次 | 任务 | 输出 |
|------|------|------|
| W1 | 日历集成架构<br>Google Calendar集成 | OAuth流程<br>双向同步基础 |
| W2 | Outlook/CalDAV<br>同步冲突解决 | 多服务商支持 |
| W3 | Notion集成<br>GitHub集成 | 数据库同步<br>Issue同步 |
| W4 | 全文检索架构<br>Meilisearch部署 | 搜索引擎<br>索引系统 |
| W5 | 内容提取<br>OCR集成 | PDF/图片索引 |
| W6 | 工作流引擎<br>基础节点 | 引擎框架<br>可视化编辑器 |
| W7 | Webhook系统<br>高级工作流 | 接收/发送Webhook |
| W8 | 插件系统基础<br>SDK | 插件架构<br>示例插件 |
| W9 | 集成测试<br>性能优化 | 测试报告 |
| W10 | Bug修复<br>文档<br>v0.9.0发布 | 发布版本 |

---

*本文档将持续更新*
