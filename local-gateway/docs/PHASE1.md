# Phase 1: 基础夯实 - 详细实现文档

> 目标: 完善核心功能，提升基础体验，修复技术债务
> 预计工期: 6-8周
> 版本目标: v0.5.0

---

## 一、本阶段目标

### 1.1 核心交付物

| 类别 | 交付物 | 验收标准 |
|------|--------|----------|
| 功能 | 任务高级属性系统 | 支持优先级、标签、子任务、描述 |
| 功能 | 番茄工作法 | 完整的计时、统计、关联任务 |
| 功能 | 下载管理增强 | 批量下载、队列、断点续传 |
| 功能 | 日历基础视图 | 日/周/月视图，拖拽调整 |
| 功能 | 全局快捷键 | 快速创建/搜索/导航 |
| 质量 | 测试覆盖率 | 单元测试>80%，集成测试覆盖核心流程 |
| 文档 | API文档 | OpenAPI完整注释 |

### 1.2 用户价值

完成Phase 1后，用户可以：
- 更细致地管理任务（优先级、标签分类）
- 使用番茄钟提升专注力
- 批量下载资料并追踪进度
- 在日历视图中直观管理时间
- 通过快捷键快速操作

---

## 二、模块详细设计

### 2.1 任务高级属性系统

#### 2.1.1 数据库Schema变更

```sql
-- 新增: 标签表
CREATE TABLE IF NOT EXISTS tags (
    tag_id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    color TEXT DEFAULT '#3498db',
    created_at TEXT DEFAULT (datetime('now'))
);

-- 新增: 任务-标签关联表
CREATE TABLE IF NOT EXISTS task_tags (
    task_id TEXT NOT NULL,
    tag_id TEXT NOT NULL,
    PRIMARY KEY (task_id, tag_id),
    FOREIGN KEY (task_id) REFERENCES tasks(task_id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES tags(tag_id) ON DELETE CASCADE
);

-- 新增: 子任务表
CREATE TABLE IF NOT EXISTS subtasks (
    subtask_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    title TEXT NOT NULL,
    status TEXT DEFAULT 'pending', -- pending/completed
    sort_order INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (task_id) REFERENCES tasks(task_id) ON DELETE CASCADE
);

-- 修改: tasks表新增字段
ALTER TABLE tasks ADD COLUMN priority INTEGER DEFAULT 2; -- 1=高, 2=中, 3=低
ALTER TABLE tasks ADD COLUMN description TEXT DEFAULT '';
ALTER TABLE tasks ADD COLUMN estimated_minutes INTEGER DEFAULT 0;
ALTER TABLE tasks ADD COLUMN project_id TEXT; -- 预留，用于后续项目功能
```

#### 2.1.2 API设计

```python
# 新增端点

# 标签管理
POST   /api/tags              # 创建标签
GET    /api/tags              # 获取所有标签
PUT    /api/tags/{tag_id}     # 更新标签
DELETE /api/tags/{tag_id}     # 删除标签

# 子任务管理
POST   /api/tasks/{task_id}/subtasks      # 添加子任务
PUT    /api/tasks/{task_id}/subtasks/{subtask_id}  # 更新子任务
DELETE /api/tasks/{task_id}/subtasks/{subtask_id}  # 删除子任务
PATCH  /api/tasks/{task_id}/subtasks/{subtask_id}/toggle  # 切换完成状态

# 任务增强
GET    /api/tasks             # 获取任务列表（支持筛选）
# 查询参数: status, priority, tag, search, sort_by, order
```

#### 2.1.3 关键实现点

**任务筛选服务** (`services/task_filter_service.py`):
```python
class TaskFilter:
    def __init__(self):
        self.conditions = []
        self.params = []
    
    def by_status(self, status: Optional[str]):
        if status:
            self.conditions.append("status = ?")
            self.params.append(status)
        return self
    
    def by_priority(self, priority: Optional[int]):
        if priority:
            self.conditions.append("priority = ?")
            self.params.append(priority)
        return self
    
    def by_tags(self, tags: List[str]):
        if tags:
            placeholders = ','.join('?' * len(tags))
            self.conditions.append(f"""
                task_id IN (
                    SELECT task_id FROM task_tags 
                    WHERE tag_id IN ({placeholders})
                )
            """)
            self.params.extend(tags)
        return self
    
    def search(self, keyword: str):
        if keyword:
            self.conditions.append("(task_name LIKE ? OR description LIKE ?)")
            self.params.extend([f"%{keyword}%", f"%{keyword}%"])
        return self
    
    def build(self) -> Tuple[str, List]:
        where = " AND ".join(self.conditions) if self.conditions else "1=1"
        return where, self.params
```

---

### 2.2 番茄工作法

#### 2.2.1 数据库Schema

```sql
-- 番茄钟记录表
CREATE TABLE IF NOT EXISTS pomodoro_sessions (
    session_id TEXT PRIMARY KEY,
    task_id TEXT, -- 可为空，表示自由番茄
    start_time TEXT NOT NULL,
    end_time TEXT,
    duration_minutes INTEGER DEFAULT 25,
    status TEXT DEFAULT 'running', -- running/completed/interrupted
    interrupt_reason TEXT,
    FOREIGN KEY (task_id) REFERENCES tasks(task_id) ON DELETE SET NULL
);

-- 任务番茄统计（冗余表，用于快速查询）
CREATE TABLE IF NOT EXISTS task_pomodoro_stats (
    task_id TEXT PRIMARY KEY,
    total_pomodoros INTEGER DEFAULT 0,
    total_focus_minutes INTEGER DEFAULT 0,
    last_pomodoro_at TEXT,
    FOREIGN KEY (task_id) REFERENCES tasks(task_id) ON DELETE CASCADE
);
```

#### 2.2.2 状态机设计

```
空闲(Idle) --[开始]--> 专注中(Focusing)
专注中 --[25分钟到]--> 休息中(Break)
专注中 --[中断]--> 已中断(Interrupted) --[恢复]--> 专注中
休息中 --[5分钟到]--> 空闲
休息中 --[跳过]--> 空闲
```

#### 2.2.3 API设计

```python
# 番茄钟管理
POST   /api/pomodoro/start              # 开始番茄钟
       Body: { task_id?: str, duration?: int }
POST   /api/pomodoro/{session_id}/stop  # 停止/完成
POST   /api/pomodoro/{session_id}/interrupt  # 中断
GET    /api/pomodoro/status             # 获取当前状态
GET    /api/pomodoro/stats              # 获取统计
       Query: period=today/week/month
GET    /api/pomodoro/history            # 历史记录
```

#### 2.2.4 前端组件

**番茄钟组件** (`static/components/pomodoro.js`):
```javascript
class PomodoroTimer {
    constructor() {
        this.state = 'idle'; // idle/focusing/break/interrupted
        this.timeLeft = 25 * 60; // 秒
        this.taskId = null;
        this.timer = null;
    }
    
    start(taskId = null, duration = 25) {
        this.taskId = taskId;
        this.timeLeft = duration * 60;
        this.state = 'focusing';
        this.timer = setInterval(() => this.tick(), 1000);
        this.notifyServer('start');
    }
    
    tick() {
        this.timeLeft--;
        this.updateDisplay();
        if (this.timeLeft <= 0) {
            this.complete();
        }
    }
    
    complete() {
        clearInterval(this.timer);
        this.notifyServer('complete');
        this.showNotification('番茄钟完成！休息一下吧');
        this.startBreak();
    }
    
    // ... 其他方法
}
```

---

### 2.3 下载管理增强

#### 2.3.1 下载队列系统

**架构设计**:
```
用户请求下载
    ↓
加入下载队列 (Redis/内存队列)
    ↓
下载工作池 (Worker Pool, 最大并发3)
    ↓
下载中 ←→ 暂停/恢复/取消
    ↓
完成 → 安全扫描 → 归档 → 通知
```

#### 2.3.2 数据库Schema

```sql
-- 下载队列表（增强现有download_history）
ALTER TABLE download_history ADD COLUMN queue_position INTEGER;
ALTER TABLE download_history ADD COLUMN retry_count INTEGER DEFAULT 0;
ALTER TABLE download_history ADD COLUMN max_retries INTEGER DEFAULT 3;
ALTER TABLE download_history ADD COLUMN error_message TEXT;
ALTER TABLE download_history ADD COLUMN downloaded_bytes INTEGER DEFAULT 0;
ALTER TABLE download_history ADD COLUMN total_bytes INTEGER;
ALTER TABLE download_history ADD COLUMN resumable BOOLEAN DEFAULT 0;
```

#### 2.3.3 断点续传实现

```python
# services/download_service.py

class ResumableDownloader:
    def __init__(self):
        self.chunk_size = 8192
        self.temp_dir = Path("./data/temp_downloads")
    
    async def download(
        self, 
        url: str, 
        target_path: Path,
        resume: bool = True
    ) -> DownloadResult:
        temp_path = self.temp_dir / f"{target_path.name}.tmp"
        
        # 获取已下载大小
        downloaded = temp_path.stat().st_size if temp_path.exists() and resume else 0
        
        headers = {}
        if downloaded > 0:
            headers["Range"] = f"bytes={downloaded}-"
        
        async with httpx.AsyncClient() as client:
            async with client.stream("GET", url, headers=headers) as response:
                total = int(response.headers.get("content-length", 0)) + downloaded
                
                mode = "ab" if downloaded > 0 else "wb"
                async with aiofiles.open(temp_path, mode) as f:
                    async for chunk in response.aiter_bytes(self.chunk_size):
                        await f.write(chunk)
                        downloaded += len(chunk)
                        self.update_progress(downloaded, total)
        
        # 下载完成，移动文件
        temp_path.rename(target_path)
        return DownloadResult(success=True, path=target_path)
```

#### 2.3.4 批量下载API

```python
POST /api/download/batch
Body: {
    "items": [
        {"url": "...", "category": "paper", "filename": "..."},
        {"url": "...", "category": "video"}
    ],
    "options": {
        "queue": true,  -- 是否加入队列
        "autostart": true  -- 是否立即开始
    }
}
Response: {
    "batch_id": "batch_xxx",
    "total": 5,
    "queued": 5,
    "jobs": [{"job_id": "...", "status": "queued"}]
}

GET /api/download/queue
Response: {
    "active": [...],  -- 下载中
    "pending": [...], -- 等待中
    "completed": [...], -- 已完成
    "failed": [...]   -- 失败
}

POST /api/download/{job_id}/pause
POST /api/download/{job_id}/resume
POST /api/download/{job_id}/cancel
```

---

### 2.4 日历基础视图

#### 2.4.1 数据模型

复用现有 `tasks` 表，增加日历视图查询支持。

#### 2.4.2 API设计

```python
GET /api/calendar/events
Query: {
    "view": "day/week/month",  -- 视图类型
    "date": "2026-04-26",      -- 锚定日期
    "project_id": "...",       -- 可选筛选
    "tag": "..."               -- 可选筛选
}
Response: {
    "period": {"start": "...", "end": "..."},
    "events": [
        {
            "id": "task_xxx",
            "title": "任务名称",
            "start": "2026-04-26T09:00:00",
            "end": "2026-04-26T10:00:00",
            "type": "task",
            "status": "pending",
            "priority": 1,
            "color": "#3498db"  -- 根据优先级/标签返回
        }
    ]
}

# 拖拽调整时间
PUT /api/calendar/events/{task_id}
Body: {
    "start": "2026-04-26T14:00:00",
    "end": "2026-04-26T15:30:00"
}
```

#### 2.4.3 前端实现

采用现有原生JS实现，不引入重型库：

```javascript
// static/components/calendar.js
class Calendar {
    constructor(container) {
        this.container = container;
        this.view = 'week'; // day/week/month
        this.currentDate = new Date();
        this.events = [];
    }
    
    async render() {
        const data = await this.fetchEvents();
        this.events = data.events;
        
        if (this.view === 'week') {
            this.renderWeekView();
        } else if (this.view === 'month') {
            this.renderMonthView();
        }
    }
    
    renderWeekView() {
        // 7列时间网格
        // 支持拖拽调整
        // 支持点击创建
    }
}
```

---

### 2.5 全局快捷键

#### 2.5.1 快捷键映射

| 快捷键 | 功能 | 场景 |
|--------|------|------|
| `Ctrl/Cmd + K` | 全局搜索 | 任何页面 |
| `Ctrl/Cmd + N` | 新建任务 | 任何页面 |
| `Ctrl/Cmd + Shift + N` | 快速笔记 | 任何页面 |
| `Ctrl/Cmd + P` | 启动番茄钟 | 任何页面 |
| `Ctrl/Cmd + D` | 下载对话框 | 任何页面 |
| `Ctrl/Cmd + 1/2/3/4` | 切换标签页 | Dashboard/任务/下载/日历 |
| `Ctrl/Cmd + [` / `]` | 上/下一周（日历） | 日历视图 |
| `Esc` | 关闭弹窗/取消 | 任何页面 |
| `?` | 显示快捷键帮助 | 任何页面 |

#### 2.5.2 实现方式

```javascript
// static/core/shortcuts.js
class ShortcutManager {
    constructor() {
        this.shortcuts = new Map();
        this.setupListener();
    }
    
    register(key, callback, options = {}) {
        this.shortcuts.set(key, {
            callback,
            preventDefault: options.preventDefault ?? true,
            requireInput: options.requireInput ?? false
        });
    }
    
    setupListener() {
        document.addEventListener('keydown', (e) => {
            const key = this.normalizeKey(e);
            const shortcut = this.shortcuts.get(key);
            
            if (!shortcut) return;
            
            // 如果在输入框中，不触发（除非明确设置）
            if (this.isInputActive() && !shortcut.requireInput) {
                return;
            }
            
            if (shortcut.preventDefault) {
                e.preventDefault();
            }
            
            shortcut.callback(e);
        });
    }
    
    normalizeKey(e) {
        const parts = [];
        if (e.ctrlKey || e.metaKey) parts.push('Cmd');
        if (e.shiftKey) parts.push('Shift');
        if (e.altKey) parts.push('Alt');
        parts.push(e.key);
        return parts.join('+');
    }
}

// 使用
const shortcuts = new ShortcutManager();
shortcuts.register('Cmd+K', () => app.openGlobalSearch());
shortcuts.register('Cmd+N', () => app.openTaskModal());
shortcuts.register('Cmd+P', () => pomodoro.start());
```

---

## 三、技术债务处理

### 3.1 测试体系建立

#### 3.1.1 测试结构

```
test/
├── unit/                      # 单元测试
│   ├── services/
│   │   ├── test_task_service.py
│   │   ├── test_pomodoro_service.py
│   │   └── test_download_service.py
│   └── utils/
│       └── test_validators.py
├── integration/               # 集成测试
│   ├── test_task_api.py
│   ├── test_pomodoro_api.py
│   └── test_download_api.py
├── e2e/                       # 端到端测试
│   └── test_user_flows.py
└── fixtures/                  # 测试数据
    └── sample_data.sql
```

#### 3.1.2 测试基类

```python
# test/base.py
import pytest
import asyncio
from httpx import AsyncClient
from main import app

class BaseAPITest:
    @pytest.fixture(scope="class")
    async def client(self):
        async with AsyncClient(app=app, base_url="http://test") as client:
            yield client
    
    @pytest.fixture(autouse=True)
    async def setup_db(self):
        # 每个测试前清理数据
        await init_db()
        yield
        # 清理

class BaseServiceTest:
    @pytest.fixture(autouse=True)
    async def setup(self):
        await init_db()
        yield
```

### 3.2 错误处理统一

```python
# services/exceptions.py
class ServiceError(Exception):
    """服务层异常基类"""
    def __init__(self, message: str, code: str = None, details: dict = None):
        self.message = message
        self.code = code or "INTERNAL_ERROR"
        self.details = details or {}
        super().__init__(message)

class TaskNotFoundError(ServiceError):
    def __init__(self, task_id: str):
        super().__init__(
            message=f"任务 {task_id} 不存在",
            code="TASK_NOT_FOUND",
            details={"task_id": task_id}
        )

class ValidationError(ServiceError):
    pass

# routers/exception_handlers.py
@app.exception_handler(ServiceError)
async def service_error_handler(request, exc: ServiceError):
    return JSONResponse(
        status_code=400,
        content={
            "status": "error",
            "code": exc.code,
            "message": exc.message,
            "details": exc.details
        }
    )
```

---

## 四、实现时间表

### 4.1 任务分解

| 周次 | 任务 | 输出 | 负责人 |
|------|------|------|--------|
| W1 | 数据库迁移脚本<br>标签系统后端 | migration v1.1<br>Tag CRUD API | Backend |
| W2 | 子任务系统<br>任务筛选API | 子任务完整功能<br>高级搜索 | Backend |
| W3 | 番茄钟后端<br>下载队列重构 | Pomodoro API<br>下载队列系统 | Backend |
| W4 | 日历API<br>断点续传 | Calendar API<br>Resumable download | Backend |
| W5 | 前端-标签/子任务UI<br>快捷键系统 | 任务增强界面<br>Shortcuts | Frontend |
| W6 | 前端-番茄钟组件<br>下载队列UI | Pomodoro UI<br>Download queue UI | Frontend |
| W7 | 前端-日历视图<br>集成测试 | Calendar component<br>测试报告 | Frontend/QA |
| W8 | Bug修复<br>文档完善<br>v0.5.0发布 | Release notes<br>用户手册 | All |

### 4.2 依赖关系

```
数据库迁移
    ↓
标签系统 ──┬──→ 任务筛选UI
           └──→ 日历视图
    ↓
子任务系统
    ↓
番茄钟后端 ──→ 番茄钟UI
    ↓
下载队列重构 ──→ 下载队列UI
```

---

## 五、风险评估

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| 数据库迁移问题 | 中 | 高 | 完整备份，提供回滚脚本 |
| 断点续传复杂度高 | 中 | 中 | 先实现基础版本，后续优化 |
| 前端状态管理混乱 | 中 | 中 | 引入轻量级状态管理(Pinia) |
| 测试时间不足 | 高 | 中 | 核心功能优先测试，边开发边写测试 |

---

## 六、附录

### 6.1 接口变更日志

#### v0.5.0 新增接口

| Method | Path | Description |
|--------|------|-------------|
| POST | /api/tags | 创建标签 |
| GET | /api/tags | 获取标签列表 |
| POST | /api/tasks/{id}/subtasks | 添加子任务 |
| POST | /api/pomodoro/start | 开始番茄钟 |
| GET | /api/calendar/events | 获取日历事件 |
| POST | /api/download/batch | 批量下载 |

### 6.2 数据库版本

- **v1.0** - 初始版本 (tasks, download_history, operation_logs)
- **v1.1** - Phase 1 (tags, subtasks, pomodoro_sessions, task enhancements)

### 6.3 参考文档

- [数据库设计](./schema/v1.1.sql)
- [API文档](./api/v0.5.0.md)
- [测试用例](./test/phase1.md)

---

*本文档将在开发过程中持续更新*
