# LocalCommandCenter 全面优化设计

**策略**：核心优先（3 批完成）
- 第一批：task_service 拆分 + 搜索统一 + 日历统一（架构根基）
- 第二批：AI 对话增强 + 工作流增强（功能增强）
- 第三批：下载性能 + 同步加密 + UI 组件化（深度优化）

---

## 第 1 节：Task Service 领域拆分

### 现状

`task_service.py` 1913 行，10+ 职责，所有数据库表在一个 `_schema` 中定义。

### 拆分方案

| 新服务 | 职责 | 原始代码来源 |
|--------|------|-------------|
| `task_service.py` | 任务 CRUD、批量编排、每日规划、周计划 | 保留核心，去掉标签/子任务/番茄钟 |
| `tag_service.py` | 标签 CRUD、任务-标签关联、批量获取标签 | `create_tag` 到 `remove_task_tags` |
| `subtask_service.py` | 子任务 CRUD、排序 | `create_subtask` 到 `delete_subtask` |
| `pomodoro_service.py` | 番茄钟会话管理、统计、历史 | `start_pomodoro` 到 `get_pomodoro_history` |
| `note_service.py` | 笔记 CRUD、搜索 | `create_note` 到 `get_all_notes` |
| `habit_service.py` | 习惯 CRUD、打卡、连续天数、统计 | `create_habit` 到 `delete_habit` |

### 数据库 Schema 管理

- 每个 service 文件定义自己的 `_schema`（只包含相关表）
- `init_db()` 在 `task_service.py` 中保留为入口，调用各 service 的初始化函数
- 日历事件表迁移到 `calendar_service.py`（与日历模块统一）

### Router 层适配

- 每个领域服务对应已有独立 router
- Router 的 import 路径从 `services.task_service.xxx` 改为 `services.tag_service.xxx` 等
- 对外 API 端点不变，纯内部重构

### 依赖关系

- `task_service` → `tag_service`（任务添加时关联标签）
- `tag_service` → 无外部依赖
- `pomodoro_service` → `task_service`（查询关联任务名称）

---

## 第 2 节：搜索统一 + 日历统一

### 2.1 搜索统一

**现状**：`file_search` 基于文件名模糊匹配，`fulltext_search` 基于数据库内容，两者独立暴露不同端点。

**目标**：合并为统一搜索服务 `search_service.py`，一个端点搜所有。

**API**：
```
POST /api/search
{
  "keyword": "机器学习",
  "scope": "all",          // all | files | tasks | notes | habits
  "category": "all",       // 文件分类（仅 files scope 时有效）
  "page": 1,
  "page_size": 20
}
```

**返回结构**：
```json
{
  "status": "success",
  "results": {
    "files": [...],
    "tasks": [...],
    "notes": [...],
    "habits": [...]
  },
  "total": 42,
  "scope": "all"
}
```

**实现**：
- 新 `search_service.py` 内部调用各领域服务的查询方法
- 文件搜索保留 `asyncio.to_thread` 包装
- `scope=all` 时用 `asyncio.gather` 并行查询所有子域
- `fulltext_search_service.py` 中的全文索引逻辑合并进来，删除旧文件

### 2.2 日历统一

**现状**：`task_service.py` 中有 `calendar_events` 表 + CRUD，`calendar_service.py` 负责外部日历同步，两套体系。

**目标**：将内部日历事件管理迁入 `calendar_service.py`，统一管理。

- `calendar_service.py` 承担：
  1. 本地日历事件 CRUD（从 task_service 迁入）
  2. 日历视图查询（`get_calendar_view`，从 task_service 迁入）
  3. 外部日历同步（已有功能）
- `task_service.py` 不再持有 `calendar_events` 表
- 依赖方向：`calendar_service` → `task_service`（单向），不产生循环

---

## 第 3 节：AI 对话全面增强

### 3.1 上下文管理与恢复

**三层上下文架构**：

```
┌─────────────────────────────────────┐
│  Layer 1: System Context            │  ← 始终保留，不参与压缩
│  (SYSTEM_PROMPT + 工具定义 + 用户偏好) │
├─────────────────────────────────────┤
│  Layer 2: Compressed History        │  ← 旧消息自动压缩为摘要
│  (早期对话的摘要 + 关键决策记录)       │
├─────────────────────────────────────┤
│  Layer 3: Active Window             │  ← 最近 N 轮完整保留
│  (最近 10 轮完整消息 + 待处理 tool_call)│
└─────────────────────────────────────┘
```

**上下文压缩机制**：

当对话消息超过阈值（30 轮），触发自动压缩：
- 保留 Layer 1 不动
- Layer 2：将最早的 20 轮消息让 AI 生成结构化摘要，包含：
  - 已完成的操作及结果
  - 用户表达的关键偏好和约束
  - 未完成的意图和待办
  - 重要中间数据（task_id、文件路径等）
- Layer 3：最近 10 轮完整保留
- 压缩后的摘要以 `role: system, content: "[历史摘要] ..."` 形式插入

**上下文压缩实现**：将待压缩消息拼装为一次 AI API 调用：
```
System: 请将以下对话历史压缩为结构化摘要，保留：1)已完成的操作和结果 2)用户偏好和约束 3)未完成意图 4)重要中间数据(ID/路径等)
Messages: [待压缩的20轮消息]
```
压缩结果替代原始消息存入 DB，标记 `is_compressed=1`。压缩本身消耗一次 API 调用，但节省后续每次请求的 token 开销。

**对话恢复**：

持久化存储：
```sql
CREATE TABLE IF NOT EXISTS chat_conversations (
    conversation_id TEXT PRIMARY KEY,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
    message_count   INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL,
    role            TEXT NOT NULL,
    content         TEXT,
    tool_calls      TEXT,           -- JSON (仅 assistant)
    tool_call_id    TEXT,           -- (仅 tool)
    is_compressed   INTEGER DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (conversation_id) REFERENCES chat_conversations(conversation_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS chat_context_snapshots (
    snapshot_id     TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    messages_json   TEXT NOT NULL,  -- 完整 messages 数组序列化
    step_count      INTEGER,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (conversation_id) REFERENCES chat_conversations(conversation_id) ON DELETE CASCADE
);
```

- 每 5 轮 tool calling 后保存上下文快照
- 进程重启后从最新快照恢复，增量追加快照后新消息
- 跨设备通过同步引擎加密传输对话上下文

### 3.2 多 Agent 架构

```
┌──────────────────────────────────────────────┐
│              Orchestrator Agent               │
│  (路由用户意图 → 分配给合适的 Agent)            │
│  (汇总多 Agent 结果 → 流式返回给用户)           │
├──────────┬──────────┬──────────┬─────────────┤
│ Task     │ Download │ Sandbox  │ Research     │
│ Agent    │ Agent    │ Agent    │ Agent        │
│          │          │          │              │
│ 任务管理  │ 下载+搜索 │ 代码执行  │ 信息收集+分析 │
│ 日程编排  │ 文件归档  │ 沙盒运行  │ 代码解释器    │
│ 习惯打卡  │ 安全扫描  │ Shell    │ 网络搜索      │
└──────────┴──────────┴──────────┴─────────────┘
```

**各 Agent 职责**：

| Agent | 工具集 | System Prompt 风格 |
|-------|--------|-------------------|
| **Orchestrator** | 无直接工具，只路由 | 分析意图，分配任务，汇总结果 |
| **Task Agent** | `local_task_manager`, `batch_task_manager` | 专注任务规划和日程管理 |
| **Download Agent** | `local_safe_downloader`, `local_file_search` | 专注文件获取和检索 |
| **Sandbox Agent** | `local_sandbox_executor`, `code_interpreter`（执行型）, `shell_exec` | 专注代码执行和系统操作 |
| **Research Agent** | `code_interpreter`（分析型），未来可扩展搜索 API | 专注信息收集和分析 |

**code_interpreter 双归属规则**：Orchestrator 根据意图类型分配 — 用户明确要求"执行/运行代码"→ Sandbox Agent；用户要求"分析/计算/处理数据"→ Research Agent。同一轮对话中，同一 tool_call 只路由给一个 Agent。

**调度流程**：

Orchestrator 接收用户消息后，先调用一次 LLM 做意图分类（轻量级，不消耗 tool calling 额度），输出：
```json
{
  "intent_type": "simple | compound | parallel",
  "agents": ["task_agent"],
  "sub_tasks": [
    {"agent": "task_agent", "message": "添加3个任务"},
    {"agent": "download_agent", "message": "搜索论文文件"}
  ]
}
```

- 简单请求（单 agent）→ 直接路由到单一 Agent
- 复合请求（多 agent 串行）→ 按顺序分配给不同 Agent，前一步结果作为后一步上下文
- 并行请求（多 agent 并行）→ 多个 Agent 同时执行，结果汇总后由 Orchestrator 整合回复

Orchestrator 本身不持有工具，只做路由和汇总。每个 Agent 独立维护自己的 Agentic Loop 和工具集。

### 3.3 流式调用

**SSE 端点**：`POST /api/chat/stream`

**流式事件类型**：

| 事件 | 含义 |
|------|------|
| `thinking` | AI 正在思考 |
| `agent_dispatch` | 任务分配给某 Agent |
| `tool_call` | 调用工具（含步骤编号） |
| `tool_result` | 工具返回结果摘要 |
| `agent_result` | Agent 完成任务 |
| `confirmation_required` | 需要用户确认高风险操作 |
| `assistant_chunk` | AI 回复文本片段 |
| `done` | 流结束，附带统计 |

**实现**：
- FastAPI `StreamingResponse` + `asyncio.Queue`
- 每个 Agent 在独立 asyncio Task 中执行，结果通过 Queue 传递给 SSE 流
- 并行 Agent 结果交错推送，前端按 `agent` 字段区分
- 非流式 `/api/chat` 保留兼容，内部复用相同逻辑但收集完再返回

**流恢复机制**（confirmation_required 暂停后）：
- 服务端在内存中保存待处理的 `pending_tool_call` 和当前 `conversation_id`
- SSE 流发送 `confirmation_required` 事件后，不关闭连接，而是 `await confirmation_event.wait()`
- 用户调用 `POST /api/chat/confirm` → 服务端 `confirmation_event.set()` → SSE 流恢复
- 若超时未确认（默认 5 分钟），自动拒绝并发送 `assistant_chunk: "操作已超时取消"` + `done`
- 前端断线重连：携带 `Last-Event-ID`，服务端从断点重发未确认事件

### 3.4 安全检查点

**风险分级**：

| 级别 | 工具 | 行为 |
|------|------|------|
| 低风险 | `local_task_manager`、`batch_task_manager`、`local_file_search`、`local_job_status` | 自动执行 |
| 中风险 | `local_safe_downloader`、`local_sandbox_executor` | 连续执行 ≥5 次时暂停确认 |
| 高风险 | `code_interpreter`、`shell_exec` | 每次执行前必须用户确认 |

**确认流程**：
1. AI 返回高风险 tool_call → 不执行，返回 `confirmation_required` 事件
2. 前端展示操作描述 + 确认/拒绝按钮
3. 用户确认 → `POST /api/chat/confirm` → 服务端执行 → 继续流
4. 用户拒绝 → 拒绝信息加入对话历史 → AI 调整策略

**API**：
```
POST /api/chat/confirm
{
  "conversation_id": "xxx",
  "tool_call_id": "call_0_0",
  "approved": true
}
```

### 3.5 AIConfig 扩展

```python
class AIConfig:
    # 现有字段
    api_base / api_key / model / gateway_base_url

    # 新增字段
    auto_approve_level: str = "high_risk"   # all / high_risk / all_risk
    max_agent_parallel: int = 3             # 最大并行 Agent 数
    context_compress_threshold: int = 30    # 触发压缩的轮数
    snapshot_interval: int = 5              # 快照间隔（轮数）
    stream_enabled: bool = True             # 是否启用流式
```

---

## 第 4 节：下载性能优化

### 4.1 Event 驱动替代轮询

用 `asyncio.Event` 替代 `asyncio.sleep(1)` 轮询：

- `_download_available`：队列有新任务时 `set()`
- `_download_completed`：一个下载完成时 `set()`
- `_process_queue()` 用 `await _download_completed.wait()` 替代轮询

触发点：
- `add_to_queue()` → `_download_available.set()`
- `_download_with_retry()` finally → `_download_completed.set()`

### 4.2 令牌桶带宽控制

```python
class TokenBucket:
    def __init__(self, rate_kb: int, burst_kb: int = None):
        self.rate = rate_kb * 1024
        self.burst = (burst_kb or rate_kb) * 1024
        self.tokens = self.burst
        self.last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self, nbytes: int):
        async with self._lock:
            self._refill()
            if self.tokens >= nbytes:
                self.tokens -= nbytes
                return
            deficit = nbytes - self.tokens
            wait_seconds = deficit / self.rate
            self.tokens = 0
        await asyncio.sleep(wait_seconds)
        async with self._lock:
            self._refill()
            self.tokens -= min(nbytes, self.tokens)

    def _refill(self):
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.burst, self.tokens + elapsed * self.rate)
        self.last_refill = now
```

- 每个 chunk 写入前 `await bucket.acquire(len(chunk))`
- `rate_kb=0` 时跳过 acquire
- `set_bandwidth_limit()` 动态更新 `bucket.rate`

### 4.3 Job 状态持久化

```sql
CREATE TABLE IF NOT EXISTS download_jobs (
    job_id       TEXT PRIMARY KEY,
    url          TEXT NOT NULL,
    category     TEXT NOT NULL,
    filename     TEXT,
    save_path    TEXT,
    status       TEXT NOT NULL DEFAULT 'queued',
    progress     INTEGER DEFAULT 0,
    total_bytes  INTEGER DEFAULT 0,
    downloaded_bytes INTEGER DEFAULT 0,
    error        TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at   TEXT NOT NULL DEFAULT (datetime('now'))
);
```

- 队列状态变更时同步写 DB
- 进程重启后从 DB 加载 `status=queued/downloading` 的 Job，downloading 重置为 queued 重新入队
- 内存 dict `_jobs` 仍作热缓存

---

## 第 5 节：同步 + 加密全面增强

### 5.1 同步引擎增强

#### 向量时钟

每条记录附加版本向量：
```json
{
    "task_id": "task_20260422_...",
    "version_vector": {"device_A": 3, "device_B": 1},
    "updated_at": "2026-04-22T15:00:00"
}
```

版本比较规则：
- `V1 >= V2`（所有分量 >=）→ 无冲突，V1 是后续版本
- 不可比较（各有大小）→ 并发冲突

数据库变更：
```sql
ALTER TABLE tasks ADD COLUMN version_vector TEXT DEFAULT '{}';
ALTER TABLE notes ADD COLUMN version_vector TEXT DEFAULT '{}';
ALTER TABLE habits ADD COLUMN version_vector TEXT DEFAULT '{}';
ALTER TABLE tasks ADD COLUMN field_timestamps TEXT DEFAULT '{}';
```

`field_timestamps` 存储字段修改时间：`{"task_name": "2026-04-22T10:00:00", "due_time": "2026-04-22T14:00:00"}`

#### 冲突解决策略

| 策略 | 适用场景 | 逻辑 |
|------|---------|------|
| `last_write_wins` | 习惯打卡、操作日志 | 后写覆盖 |
| `field_level_merge` | 任务、笔记 | 逐字段比较，取各设备最新修改合并 |
| `manual_resolve` | 关键任务、重要笔记 | 生成冲突记录，等用户手动选择 |

`field_level_merge` 逻辑：比较各字段的 `field_timestamps`，取最新值；合并版本向量取各分量最大值。

#### Delta 同步协议升级

```
设备A → 服务器: POST /api/sync/push
{
    "device_id": "device_A",
    "changes": [
        {
            "table": "tasks",
            "operation": "update",
            "record_id": "task_xxx",
            "data": {"task_name": "新名称", "due_time": "..."},
            "version_vector": {"device_A": 4, "device_B": 1},
            "field_timestamps": {"task_name": "2026-04-22T10:00:00"}
        }
    ]
}

服务器 → 设备A: 200
{
    "accepted": [...],
    "conflicts": [
        {
            "record_id": "task_yyy",
            "local_data": {...},
            "remote_data": {...},
            "suggested_merge": {...}
        }
    ]
}
```

### 5.2 加密服务增强

#### 密钥层级

```
Master Key (用户密码 Argon2id 派生，不存储)
  └── Identity Key (长期 X25519，Master Key 加密存储)
        ├── Device Key (每设备独立 X25519)
        ├── Session Key (X3DH 协商，前向安全)
        └── Data Encryption Key (每条记录 AES-256-GCM)
```

**Layer 1 — Master Key**：Argon2id 派生（替代 PBKDF2），不存储，登录时临时计算。

**Layer 2 — Identity Key**：X25519 密钥对，Master Key 加密存储，用于设备间密钥协商和签名。

**Layer 3 — Device Key**：每设备独立 X25519 密钥对，注册时 Identity Key 签名授权，丢失时可撤销。

**Layer 4 — Session Key**：每次同步会话 X3DH 协商，提供前向安全，会话后销毁。

**Layer 5 — Data Encryption Key (DEK)**：每条敏感记录独立 AES-256-GCM 密钥，DEK 用 Session Key 加密传输。

#### X3DH 密钥协商

```
设备A 注册:
1. 生成 IK_A + SPK_A + OPK_A
2. 上传公钥 bundle: {IK_A_pub, SPK_A_pub, OPK_A_pub, signature}
3. IK_A 私钥用 Master Key 加密本地存储

设备B → 设备A 同步:
1. B 获取 A 的 Pre-Key Bundle
2. B 计算 X3DH 共享密钥:
   DH1 = DH(IK_B, IK_A)
   DH2 = DH(IK_B, SPK_A)
   DH3 = DH(EK_B, IK_A)      # EK_B 临时密钥
   DH4 = DH(EK_B, SPK_A)
   SK = KDF(DH1 || DH2 || DH3 || DH4)
3. 用 SK 加密同步数据
4. A 对称解密

前向安全: EK_B 临时生成用后销毁，即使 IK/SPK 泄露也无法推导历史 SK
```

#### 密钥轮换

- **Signed Pre-Key**：每 7 天自动轮换，旧密钥保留 14 天
- **One-Time Pre-Key**：用一次即废弃
- **Identity Key**：仅在密码变更或设备全部撤销时轮换

#### 加密持久化

```sql
CREATE TABLE IF NOT EXISTS encryption_keys (
    key_id       TEXT PRIMARY KEY,
    key_type     TEXT NOT NULL,          -- identity/device/signed_prekey/one_time_prekey
    public_key   TEXT NOT NULL,
    encrypted_private_key TEXT,
    device_id    TEXT,
    status       TEXT DEFAULT 'active',  -- active/revoked/expired
    expires_at   TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS key_revocation_list (
    key_id       TEXT PRIMARY KEY,
    revoked_at   TEXT NOT NULL DEFAULT (datetime('now')),
    reason       TEXT
);
```

---

## 第 6 节：工作流增强

### 6.1 工作流 DSL

```json
{
  "workflow_id": "wf_daily_report",
  "name": "每日工作汇报",
  "trigger": {
    "type": "schedule",
    "cron": "0 18 * * 1-5"
  },
  "steps": [
    {
      "id": "step_1",
      "type": "action",
      "agent": "task_agent",
      "tool": "local_task_manager",
      "params": {"action": "get_weekly_plan"},
      "output_key": "weekly_tasks"
    },
    {
      "id": "step_2",
      "type": "condition",
      "branches": [
        {"when": "{{weekly_tasks.total}} > 5", "next": "step_3a"},
        {"when": "else", "next": "step_3b"}
      ]
    },
    {
      "id": "step_3a",
      "type": "action",
      "agent": "sandbox_agent",
      "tool": "code_interpreter",
      "params": {"language": "python", "code": "generate_detailed_report({{weekly_tasks}})"},
      "output_key": "report"
    },
    {
      "id": "step_3b",
      "type": "action",
      "agent": "task_agent",
      "tool": "local_task_manager",
      "params": {"action": "get_weekly_plan"},
      "output_key": "report"
    },
    {
      "id": "step_4",
      "type": "parallel",
      "tasks": [
        {"agent": "download_agent", "tool": "local_safe_downloader", "params": {"url": "https://...", "category": "misc"}},
        {"agent": "task_agent", "tool": "local_task_manager", "params": {"action": "add_task", "task_name": "检查报告", "due_time": "{{tomorrow_9am}}"}}
      ]
    }
  ]
}
```

### 6.2 Step 类型

| Step 类型 | 用途 | 关键字段 |
|-----------|------|---------|
| `action` | 调用单个工具/Agent | `agent`, `tool`, `params`, `output_key` |
| `condition` | 条件分支 | `branches: [{when, next}]` |
| `parallel` | 并行执行多个任务 | `tasks: [{agent, tool, params}]` |
| `loop` | 循环执行 | `over`, `step`, `max_iterations` |
| `subworkflow` | 调用另一个工作流 | `workflow_id`, `params` |
| `delay` | 延迟等待 | `seconds` / `until` |
| `human_approval` | 等待人工确认 | `message`, `timeout_seconds` |

### 6.3 触发器类型

| 触发器 | 配置 | 示例 |
|--------|------|------|
| `webhook` | `{method, path, auth}` | 外部系统推送 |
| `schedule` | `{cron}` | `0 9 * * 1-5` |
| `event` | `{event_type, filter}` | `task.completed` |
| `manual` | 无特殊配置 | UI 手动触发 |

### 6.4 执行引擎

```python
class WorkflowEngine:
    async def execute(self, workflow_id: str, context: dict = None):
        workflow = await self.load_workflow(workflow_id)
        ctx = WorkflowContext(workflow, context or {})
        for step in workflow.steps:
            if ctx.should_skip(step.id):
                continue
            result = await self._execute_step(step, ctx)
            ctx.set_step_result(step.id, result)
            if step.type == "condition":
                next_step = ctx.evaluate_branches(step.branches, result)
                ctx.set_next_step(next_step)
            elif step.type == "human_approval":
                approved = await self._wait_for_approval(step, ctx)
                if not approved:
                    ctx.set_next_step(step.on_reject or "end")
            if result.get("status") == "error" and step.on_error != "continue":
                await self._handle_step_error(step, result, ctx)
                break
        await self._save_execution_log(ctx)

class WorkflowContext:
    def resolve_template(self, template_str: str) -> str:
        """解析 {{variable}} 模板引用"""
        pass

    def evaluate_branches(self, branches, data) -> str:
        """评估条件分支，返回下一个 step_id"""
        pass
```

### 6.5 执行状态持久化

```sql
CREATE TABLE IF NOT EXISTS workflow_executions (
    execution_id  TEXT PRIMARY KEY,
    workflow_id   TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'running',
    trigger_type  TEXT,
    current_step  TEXT,
    step_results  TEXT,
    context_vars  TEXT,
    started_at    TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at  TEXT,
    error         TEXT,
    FOREIGN KEY (workflow_id) REFERENCES workflows(workflow_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS workflows (
    workflow_id   TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    description   TEXT,
    trigger       TEXT NOT NULL,          -- JSON: trigger 配置
    steps         TEXT NOT NULL,          -- JSON: steps 定义
    status        TEXT DEFAULT 'active',  -- active/disabled/deleted
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
);
```

### 6.6 事件总线

```python
class EventBus:
    _subscribers: dict[str, list[Callable]] = {}

    @classmethod
    async def emit(cls, event_type: str, payload: dict):
        for handler in cls._subscribers.get(event_type, []):
            asyncio.create_task(handler(payload))

    @classmethod
    def on(cls, event_type: str, handler: Callable):
        cls._subscribers.setdefault(event_type, []).append(handler)
```

内置事件源：`task.created/completed/deleted`、`download.completed/failed`、`pomodoro.completed/interrupted`、`habit.checked_in`、`sync.conflict_detected`。

各领域服务在关键操作后 `await EventBus.emit(...)`，工作流引擎订阅后自动触发。

### 6.7 与 AI 多 Agent 集成

工作流 `action` 步骤通过 Orchestrator 路由到对应 Agent 执行。定时触发由 `apscheduler` 调度，到期调用 `WorkflowEngine.execute()`。

---

## 第 7 节：Web UI 组件化

### 7.1 技术选型

引入 Alpine.js（约 15KB gzip）：
- 无构建步骤，CDN 引入
- 模板语法直写在 HTML 中
- 响应式数据绑定替代手动 DOM 操作
- 保持零构建依赖优势

### 7.2 组件拆分结构

```
static/
├── index.html
├── style.css
├── app.js                  # 全局配置 + Alpine.store
├── components/
│   ├── task-manager.js
│   ├── ai-chat.js          # 含流式显示
│   ├── download-panel.js
│   ├── pomodoro-timer.js
│   ├── calendar-view.js
│   ├── note-editor.js
│   ├── habit-tracker.js
│   ├── search-bar.js       # 统一搜索
│   ├── workflow-editor.js
│   └── dashboard.js
├── stores/
│   ├── notification.js
│   └── sync-status.js
└── utils/
    ├── api.js              # HTTP + SSE 流式封装
    └── helpers.js          # 格式化、日期处理
```

### 7.3 组件接口规范

每个组件以 IIFE 注册到 Alpine 全局，HTML 中通过 `x-data="taskManager()"` 使用：

```javascript
// components/task-manager.js
document.addEventListener('alpine:init', () => {
    Alpine.data('taskManager', () => ({
        tasks: [],
        loading: false,
        filter: 'active',
        keyword: '',
        page: 1,

        async init() {
            await this.loadTasks();
            this.$eventBus.on('task.created', () => this.loadTasks());
        },

        async loadTasks() {
            this.loading = true;
            const data = await api.get('/api/task/list', {
                status_filter: this.filter,
                keyword: this.keyword,
                page: this.page
            });
            this.tasks = data.tasks;
            this.loading = false;
        },

        async completeTask(taskId) {
            await api.post('/api/task/complete', { task_id: taskId });
            this.$eventBus.emit('task.completed', { task_id: taskId });
            await this.loadTasks();
        }
    }));
});
```

### 7.4 通信机制

| 方式 | 用途 | 实现 |
|------|------|------|
| **Alpine.store** | 全局共享状态 | `Alpine.store('app', {...})` |
| **事件总线** | 组件间松耦合通信 | `Alpine.magic('eventBus', () => new EventTarget())` |
| **API 层** | HTTP/SSE 请求统一封装 | `utils/api.js`，含自动重试和错误处理 |

### 7.5 流式 AI 对话 UI

```javascript
async sendMessage() {
    const userMsg = this.inputText;
    this.inputText = '';
    this.messages.push({ role: 'user', content: userMsg });
    this.isStreaming = true;

    const eventSource = api.stream('/api/chat/stream', {
        message: userMsg,
        conversation_id: this.conversationId
    });

    let assistantMsg = { role: 'assistant', content: '', status: 'thinking' };
    this.messages.push(assistantMsg);

    for await (const event of eventSource) {
        if (event.type === 'thinking') {
            assistantMsg.status = 'thinking';
        } else if (event.type === 'assistant_chunk') {
            assistantMsg.content += event.content;
            assistantMsg.status = 'streaming';
        } else if (event.type === 'agent_dispatch') {
            assistantMsg.agentInfo = event;
        } else if (event.type === 'confirmation_required') {
            this.pendingConfirmation = event;
            assistantMsg.status = 'awaiting_confirmation';
            break;
        } else if (event.type === 'done') {
            assistantMsg.status = 'done';
        }
        this.scrollToBottom();
    }
    this.isStreaming = false;
}
```

### 7.6 PWA 适配

- Service Worker 更新策略：组件文件变更时更新缓存版本号
- 离线优先：API 请求失败自动写入离线队列（复用 sync_offline_queue）
- 后台同步：注册 `sync` 事件，网络恢复时自动重放离线操作

---

## 实施批次

### 第一批：架构根基

1. task_service 拆分为 6 个领域服务
2. 搜索统一（file_search + fulltext_search 合并）
3. 日历统一（calendar_events 迁入 calendar_service）

### 第二批：功能增强

4. AI 对话全面增强（上下文管理 + 多 Agent + 流式 + 安全检查点）
5. 工作流增强（DSL + 执行引擎 + 事件总线 + 定时触发）

### 第三批：深度优化

6. 下载性能优化（Event 驱动 + 令牌桶 + Job 持久化）
7. 同步 + 加密全面增强（向量时钟 + 冲突解决 + X3DH + 密钥层级）
8. Web UI 组件化（Alpine.js + 组件拆分 + 流式 UI）
