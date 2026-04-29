# LocalCommandCenter 架构优化文档

**文档版本**: v1.0
**编写日期**: 2026-04-26
**基于审查**: COMPREHENSIVE_CODE_REVIEW.md

---

## 一、当前架构问题总览

### 1.1 架构债务热力图

```
                    严重程度
模块            严重    高      中      低
------------------------------------------------
安全架构        ████    ███     ██      █
状态管理        ████    ████    ██      
异步模型        ███     ████    ███     █
服务分层        ██      ███     ████    ██
数据持久化      ████    ███     ███     █
API 设计        █       ███     ████    ███
前端架构        ███     ███     ██      ██
测试体系        ██      ████    ███     █
部署运维        █       ██      ███     ████
```

### 1.2 核心架构缺陷

| 缺陷类别 | 具体问题 | 影响 |
|----------|----------|------|
| **零安全边界** | 无认证/授权，CORS=*，敏感端点裸奔 | 任何可访问网络的实体均可操控本地系统 |
| **内存状态孤岛** | 12+ 模块使用全局字典/列表存储状态 | 进程重启数据全失，多 worker 状态不共享 |
| **同步阻塞污染** | Docker SDK、pydub、rglob、open 等同步调用混入 async 路由 | 高并发下单请求可卡死整个事件循环 |
| **职责边界模糊** | task_service 承担下载历史、dashboard 直接磁盘遍历、job 系统依附 download | 模块耦合度高，单点变更引发连锁问题 |
| **持久化层混乱** | SQLite + JSON 文件 + 内存字典并存，无统一事务 | 数据不一致、文件损坏、竞争条件 |
| **API 范式混乱** | 万能 POST+action、Query 传业务数据、状态码单一 | 客户端难以维护，RESTful 工具链无法生效 |
| **测试反模式** | 依赖外部服务器、无事务隔离、大量 skip、存在性测试凑数 | 测试不可信，无法 CI，回归无保障 |

---

## 二、目标架构设计

### 2.1 整体架构蓝图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              接入层 (Gateway Layer)                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │  HTTP API   │  │  WebSocket  │  │  Webhooks   │  │  Static/PWA Assets  │  │
│  │  (FastAPI)  │  │  (实时推送)  │  │  (入站/出站) │  │  (SPA + ServiceWkr) │  │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘  │
└─────────┼────────────────┼────────────────┼────────────────────┼─────────────┘
          │                │                │                    │
          └────────────────┴────────────────┴────────────────────┘
                                    │
                          ┌─────────┴─────────┐
                          │   中间件管道        │
                          │  Auth → RateLimit │
                          │  → CORS → Logging │
                          │  → RequestID      │
                          └─────────┬─────────┘
                                    │
┌───────────────────────────────────┼───────────────────────────────────────────┐
│                           应用层 (Application Layer)                            │
│                                                                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │   Router    │  │   Schema    │  │  Dependency │  │    Background       │  │
│  │   (薄层)     │  │  Validation │  │  Injection  │  │    Workers          │  │
│  │             │  │  (Pydantic) │  │  (FastAPI)  │  │  (APScheduler/      │  │
│  │  HTTP 语义   │  │  输入/输出   │  │  认证/数据库   │  │   asyncio.create_   │  │
│  │  参数解析    │  │  严格约束    │  │  连接/配置    │  │   task)             │  │
│  └──────┬──────┘  └─────────────┘  └─────────────┘  └─────────────────────┘  │
│         │                                                                     │
└─────────┼─────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           领域层 (Domain Layer)                               │
│                                                                               │
│  ┌───────────────────────────────────────────────────────────────────────┐   │
│  │                        Service Layer                                   │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────┐  │   │
│  │  │  Task    │ │ Download │ │  Search  │ │ Sandbox  │ │    AI      │  │   │
│  │  │ Service  │ │ Service  │ │ Service  │ │ Service  │ │  Service   │  │   │
│  │  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └─────┬──────┘  │   │
│  │       │            │            │            │             │         │   │
│  │  ┌────┴─────┐ ┌────┴─────┐ ┌────┴─────┐ ┌────┴─────┐ ┌────┴──────┐  │   │
│  │  │ Calendar │ │  Voice   │ │  Sync    │ │ Workflow │ │ Webhook  │  │   │
│  │  │ Service  │ │ Service  │ │ Service  │ │ Engine   │ │ Service  │  │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └───────────┘  │   │
│  └───────────────────────────────────────────────────────────────────────┘   │
│                                                                               │
│  ┌───────────────────────────────────────────────────────────────────────┐   │
│  │                        Core / Shared Services                          │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐  │   │
│  │  │   Job    │  │  Config  │  │ Security │  │  Event Bus (async)   │  │   │
│  │  │ Service  │  │  Manager │  │  Engine  │  │  (解耦跨领域通信)      │  │   │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────────────────┘  │   │
│  └───────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          基础设施层 (Infrastructure Layer)                     │
│                                                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐ │
│  │   SQLite     │  │    Redis     │  │   Docker     │  │   File System    │ │
│  │  (aiosqlite) │  │   (可选缓存)  │  │    Engine    │  │   (aiofiles)     │ │
│  │  主数据库     │  │  会话/队列    │  │   沙箱隔离    │  │   异步文件操作    │ │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────────┘ │
│                                                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐ │
│  │  Full-Text   │  │    Keyring   │  │   httpx      │  │   APScheduler    │ │
│  │    SQLite    │  │   (系统密钥环) │  │  (连接池)     │  │   (定时任务)      │ │
│  │    FTS5      │  │   凭证加密    │  │              │  │                  │ │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 关键设计原则

| 原则 | 说明 | 当前违反点 |
|------|------|-----------|
| **防御纵深 (Defense in Depth)** | 安全校验在路由、服务、数据层逐层加固 | 路由层几乎零校验，全部依赖 service |
| **Fail Fast, Fail Safe** | 异常立即暴露，不安全状态不继续 | 配置加载异常吞没，继续以默认状态运行 |
| **最小权限 (Least Privilege)** | 每个模块/进程只拥有必要权限 | 沙箱容器有 root + 完整网络 |
| **显式优于隐式** | 状态变更、副作用必须显式声明 | 配置保存后隐式清空对话历史 |
| **单一职责 (SRP)** | 每个模块只有一个变更理由 | task_service 承担任务+下载历史+日志+统计 |
| **依赖倒置 (DIP)** | 高层模块不依赖低层具体实现 | 路由直接依赖全局单例 service |

---

## 三、模块拆分与职责边界

### 3.1 当前模块职责矩阵（问题版）

```
职责 \ 模块          task    download    search    sandbox    ai      dashboard
--------------------------------------------------------------------------------
任务 CRUD            ●●●                                    
下载历史查询         ●●●      ○                          ○
操作日志查询         ●●●                                    ○
磁盘统计计算         ●●●                                    ○
标签/子任务管理      ●●●                                    
番茄钟状态           ●●●                                    
日历事件             ●●●                                    
笔记/习惯            ●●●                                    
安全下载             ○        ●●●                          
队列管理                      ●●●                          
带宽限速                      ●●●                          
文件搜索                                 ●●●
沙箱执行                                          ●●●
AI 对话                                                        ●●●
Function Calling                                               ●●●
Code Interpreter                                               ●●●
Shell 执行                                                     ●●●
仪表盘聚合                                                               ●●●

图例: ●●● = 主要职责   ○ = 越界职责
```

### 3.2 目标模块拆分方案

#### 3.2.1 核心领域服务（必须拆分）

**① Job Service（独立抽象）**

```python
# services/job_service.py — 目前缺失的独立模块
"""
职责：统一管理所有异步长时间运行的作业（下载、沙箱执行、工作流等）
状态：持久化到 SQLite（非内存字典）
能力：
  - create_job(type, payload) -> job_id
  - get_job_status(job_id) -> JobStatus
  - cancel_job(job_id)
  - list_jobs(filters) -> list[JobSummary]
  - cleanup_expired(ttl)
"""
```

当前问题：`download_service` 内部维护 `_jobs` 字典，`job_status` 路由直接依赖 `download_service.get_job_status`，沙箱执行另起炉灶。

**② Config Manager（配置治理）**

```python
# services/config_service.py — 替代全局 AIConfig 单例
"""
职责：运行时配置的统一读写、校验、持久化、审计
能力：
  - get(key) / set(key, value) — 带类型校验
  - encrypt_sensitive(value) — 敏感字段加密
  - audit_log(key, old, new, actor) — 变更审计
  - hot_reload(keys) — 支持部分热重载
存储：SQLite（配置表）+ keyring（敏感凭证）
"""
```

当前问题：`AIConfig` 是全局可变单例，模块级变量 `AI_API_BASE` 等导入时快照，修改后不同步。

**③ Event Bus（领域事件解耦）**

```python
# services/event_bus.py — 新增模块
"""
职责：跨领域事件的发布/订阅，消除服务间直接调用
场景：
  - download_complete -> task_service 记录历史
  - task_created -> webhook_service 广播事件
  - workflow_triggered -> job_service 创建执行作业
实现：基于 asyncio.Queue 的内存总线（本地场景足够）
"""
```

当前问题：`download_service` 直接导入 `task_service` 记录历史，耦合度高。

#### 3.2.2 现有服务拆分

| 当前服务 | 拆分后 | 迁出内容 |
|----------|--------|----------|
| `task_service.py` (1500+ 行) | `task_service.py` | 仅保留任务 CRUD、批量编排、任务查询 |
| | `history_service.py` | 下载历史、操作日志（从 task_service 迁出） |
| | `pomodoro_service.py` | 番茄钟状态管理（带锁） |
| | `tag_service.py` | 标签 CRUD（可选，若逻辑简单可保留在 task_service） |
| `download_service.py` | `download_service.py` | 下载核心逻辑（URL 校验、下载执行） |
| | `queue_service.py` | 下载队列管理（状态机、优先级、并发控制） |
| `ai_service.py` | `ai_service.py` | AI API 调用、Function Calling 路由 |
| | `code_interpreter_service.py` | 代码执行（必须在 Docker 沙箱内） |
| | `shell_service.py` | Shell 执行（必须在 Docker 沙箱内，或完全移除） |

#### 3.2.3 新增基础设施服务

| 服务 | 职责 | 优先级 |
|------|------|--------|
| `security_service.py` | 统一的安全校验（路径遍历、SSRF、命令注入、XSS 过滤） | P0 |
| `storage_service.py` | 文件系统抽象（路径安全解析、分类目录映射、异步读写） | P0 |
| `notification_service.py` | 通知抽象（推送、WebSocket、Webhook 统一出口） | P1 |
| `metrics_service.py` | 指标收集（仪表盘统计后台计算、缓存） | P1 |

---

## 四、状态管理重构

### 4.1 当前状态存储分布

```
内存字典（进程重启丢失）:
  - download_service._jobs           → 下载作业状态
  - download_service._queue          → 下载队列
  - download_service._bandwidth_limit → 带宽限制
  - ai_service._conversations        → 对话历史
  - ai_service._conversation_timestamps → 对话 TTL
  - mobile._push_tokens              → 推送令牌
  - mobile._offline_queue            → 离线操作队列
  - sync._devices                    → 设备列表
  - sync._offline_queue              → 同步离线队列
  - shortcut_service._shortcuts      → 快捷键配置
  - webhook_service._webhook_manager  → Webhook 注册表
  - workflow_service._workflows      → 工作流定义
  - workflow_service._active_timers  → 定时触发器

JSON 文件（无锁、易损坏）:
  - data/ai_config.json              → AI 配置（含 API Key）
  - data/calendar_tokens.json        → OAuth Token
  - data/shortcuts.json              → 快捷键配置
  - data/webhooks.json               → Webhook 配置
  - data/workflows.json              → 工作流配置
  - fulltext_search.index_file       → 全文索引

SQLite（正确持久化）:
  - data/tasks.db                    → 任务、下载历史、操作日志、
                                       标签、子任务、番茄钟、日历、
                                       笔记、习惯
```

### 4.2 目标统一状态存储架构

```
┌────────────────────────────────────────────────────────────┐
│                     状态分层存储策略                         │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  ┌────────────────────────────────────────────────────┐   │
│  │  Layer 1: SQLite (主存储)                           │   │
│  │  — 所有业务实体持久化                                │   │
│  │                                                     │   │
│  │  tasks          │ habits          │ pomodoro        │   │
│  │  subtasks       │ calendar_events │ notes           │   │
│  │  tags           │ download_history│ operation_logs  │   │
│  │  task_tags      │ jobs            │ devices         │   │
│  │  shortcuts      │ webhooks        │ workflows       │   │
│  │  sync_changes   │ push_tokens     │ config          │   │
│  └────────────────────────────────────────────────────┘   │
│                          ▲                                 │
│                          │ 读写                             │
│  ┌────────────────────────────────────────────────────┐   │
│  │  Layer 2: 内存缓存 (LRU Cache)                      │   │
│  │  — 只缓存只读热点数据，不缓存写入状态                │   │
│  │                                                     │   │
│  │  - 仪表盘统计 (TTL 60s)                             │   │
│  │  - 模型列表 (TTL 300s)                              │   │
│  │  - 快捷键配置 (TTL 30s)                             │   │
│  └────────────────────────────────────────────────────┘   │
│                          ▲                                 │
│                          │ 读取（缓存未命中回源）            │
│  ┌────────────────────────────────────────────────────┐   │
│  │  Layer 3: 连接池 (单例长连接)                        │   │
│  │                                                     │   │
│  │  - aiosqlite connection pool (max 5 connections)    │   │
│  │  - httpx.AsyncClient (module-level, connection pool)│   │
│  │  - docker.DockerClient (asyncio.to_thread 包装)     │   │
│  └────────────────────────────────────────────────────┘   │
│                                                            │
│  ┌────────────────────────────────────────────────────┐   │
│  │  Layer 4: 密钥安全存储                               │   │
│  │                                                     │   │
│  │  - 系统 keyring (API Key, OAuth Token)              │   │
│  │  - 环境变量覆盖 (开发/容器场景)                      │   │
│  └────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────┘
```

### 4.3 具体迁移方案

| 当前存储 | 目标存储 | 迁移说明 |
|----------|----------|----------|
| `_jobs` 内存字典 | SQLite `jobs` 表 | 新增表：`id`, `type`, `status`, `payload`, `result`, `created_at`, `expires_at` |
| `_queue` 内存字典 | SQLite `download_queue` 表 | 从内存队列改为数据库存储的优先级队列 |
| `_conversations` 内存字典 | SQLite `conversations` + `conversation_messages` 表 | 或保留内存但启用 LRU + TTL，重启后丢失可接受 |
| `ai_config.json` | SQLite `config` 表 + keyring | 敏感字段走 keyring，普通配置走 SQLite |
| `calendar_tokens.json` | keyring | OAuth Token 必须加密存储 |
| `shortcuts.json` | SQLite `shortcuts` 表 | 迁移时需加文件锁避免并发损坏 |
| `webhooks.json` | SQLite `webhooks` 表 | 同上 |
| `workflows.json` | SQLite `workflows` 表 | 工作流定义持久化 |
| 全文索引 JSON | SQLite FTS5 | 利用 SQLite 内置全文检索 |

---

## 五、异步架构规范化

### 5.1 当前异步问题拓扑

```
async def route() ────────────────────────┐
    │                                      │
    ▼                                      │
sync def search_files() ──► rglob()  ─────┤─── 阻塞事件循环！
    │                                      │
    ▼                                      │
docker_client.containers.create() ────────┤─── 同步 SDK 阻塞！
    │                                      │
    ▼                                      │
open(path, "wb").write(chunk) ────────────┤─── 同步文件 I/O！
    │                                      │
    ▼                                      │
pydub.AudioSegment.from_file() ───────────┤─── 同步音频处理！
    │                                      │
    ▼                                      │
subprocess.run(command, shell=True) ──────┤─── 同步子进程！
    │                                      │
    ▼                                      │
socket.getaddrinfo(hostname, ...) ────────┘─── 同步 DNS！
```

### 5.2 异步规范矩阵

| 操作类型 | 当前实现 | 目标实现 | 工具/方法 |
|----------|----------|----------|-----------|
| 文件系统遍历 (rglob) | 直接调用 | `await asyncio.to_thread(rglob, ...)` | `asyncio.to_thread` |
| 文件读写 (open) | 直接调用 | `await aiofiles.open(...)` 或 `to_thread` | `aiofiles` |
| Docker SDK | 直接调用 | `await asyncio.to_thread(client.containers.create, ...)` | `asyncio.to_thread` |
| 音频处理 (pydub) | 直接调用 | `await asyncio.to_thread(AudioSegment.from_file, ...)` | `asyncio.to_thread` |
| DNS 解析 | `socket.getaddrinfo` | `await asyncio.get_event_loop().getaddrinfo(...)` | 异步 DNS |
| 子进程 (shell) | `subprocess.run` | `await asyncio.create_subprocess_exec(...)` | asyncio subprocess |
| HTTP 请求 | 每次新建 Client | 模块级 `httpx.AsyncClient` | `httpx` 连接池 |
| SQLite 查询 | 每次新建连接 | 连接池或单例长连接 | `aiosqlite` + pool |

### 5.3 推荐包装模式

```python
# infrastructure/async_wrappers.py
"""所有同步阻塞操作的统一异步包装"""

import asyncio
from functools import partial
from typing import Callable, TypeVar

T = TypeVar("T")

async def run_in_thread(func: Callable[..., T], *args, **kwargs) -> T:
    """在线程池中执行同步函数，不阻塞事件循环"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, partial(func, *args, **kwargs))

# Docker SDK 包装示例
class AsyncDockerClient:
    def __init__(self):
        self._client = None  # 延迟初始化
    
    async def init(self):
        import docker
        self._client = docker.from_env()
    
    async def create_container(self, **kwargs):
        return await run_in_thread(self._client.containers.create, **kwargs)
    
    async def close(self):
        if self._client:
            await run_in_thread(self._client.close)
```

---

## 六、安全架构重塑

### 6.1 目标安全架构

```
┌────────────────────────────────────────────────────────────────────┐
│                         安全防线分层                                │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  Layer 1: 网络边界                                                  │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │  • CORS: 白名单域名，禁止 * + credentials                   │   │
│  │  • Rate Limit: 按端点/IP 限流 (slowapi)                     │   │
│  │  • TLS: 生产环境强制 HTTPS                                   │   │
│  └────────────────────────────────────────────────────────────┘   │
│                              │                                     │
│  Layer 2: 认证授权                                                │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │  • API Key Header (X-API-Key)                              │   │
│  │  • 会话 Token (可选，用于 Web UI)                           │   │
│  │  • 端点分级: Public / User / Admin                          │   │
│  └────────────────────────────────────────────────────────────┘   │
│                              │                                     │
│  Layer 3: 输入校验                                                │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │  • Pydantic Schema: 严格类型 + 字段校验                      │   │
│  │  • Security Service: 路径遍历、SSRF、命令注入统一拦截         │   │
│  │  • 文件上传: MIME 白名单 + 大小限制 + 文件名净化              │   │
│  └────────────────────────────────────────────────────────────┘   │
│                              │                                     │
│  Layer 4: 执行隔离                                                │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │  • Docker 沙箱: 网络隔离 + 非 root + cap_drop ALL           │   │
│  │  • 资源限制: CPU / 内存 / 磁盘 / 时间                        │   │
│  │  • 代码执行: 黑名单 → 白名单 → 容器隔离（渐进）              │   │
│  └────────────────────────────────────────────────────────────┘   │
│                              │                                     │
│  Layer 5: 数据保护                                                │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │  • 凭证加密: keyring / AES-256                              │   │
│  │  • 审计日志: 所有配置变更、敏感操作记录                       │   │
│  │  • 最小返回: 错误信息脱敏，不暴露内部路径/堆栈                │   │
│  └────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────┘
```

### 6.2 认证中间件设计

```python
# middleware/auth.py
from fastapi import Depends, HTTPException, Header, status
from functools import wraps

async def require_api_key(x_api_key: str = Header(None)):
    """基础 API Key 校验"""
    if not x_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing API Key")
    if not secrets.compare_digest(x_api_key, get_stored_api_key()):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid API Key")
    return x_api_key

# 端点分级
Public = lambda: None  # 无依赖
User = Depends(require_api_key)
Admin = Depends(require_admin_key)  # 更严格的校验

# 使用示例
@app.post("/api/tasks", dependencies=[User])
async def create_task(...)

@app.post("/api/sandbox/execute", dependencies=[Admin])  # 沙箱需要更高权限
async def execute_sandbox(...)
```

### 6.3 安全服务统一拦截

```python
# services/security_service.py
"""所有安全校验的统一入口"""

class SecurityService:
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """净化文件名：禁止路径分隔符、..、空字节"""
        # 实现...
    
    @staticmethod
    def validate_url(url: str) -> None:
        """SSRF 防护：校验协议、解析 IP、禁止私有地址、追踪重定向"""
        # 实现...
    
    @staticmethod
    def validate_command(command: list[str]) -> None:
        """命令注入防护：只允许白名单命令和参数"""
        # 实现...
    
    @staticmethod
    def escape_html(text: str) -> str:
        """XSS 防护：HTML 实体编码"""
        # 实现...
```

---

## 七、API 设计规范化

### 7.1 RESTful 路由重构

当前路由范式问题：`POST /api/task` + `{"action": "add_task"}`

目标路由设计：

```
# 任务管理
POST   /api/tasks                    → 创建任务
GET    /api/tasks                    → 查询任务列表（支持过滤/分页）
GET    /api/tasks/{id}               → 获取单个任务
PATCH  /api/tasks/{id}               → 更新任务
DELETE /api/tasks/{id}               → 删除任务
PATCH  /api/tasks/{id}/complete      → 完成任务
POST   /api/tasks/batch              → 批量创建
GET    /api/tasks/weekly-plan        → 周计划视图

# 下载服务
POST   /api/downloads                → 创建下载（即时/队列）
GET    /api/downloads                → 下载历史
GET    /api/downloads/queue          → 下载队列状态
POST   /api/downloads/queue/{id}/pause   → 暂停队列项
POST   /api/downloads/queue/{id}/resume  → 恢复队列项
DELETE /api/downloads/queue/{id}         → 取消队列项
PUT    /api/downloads/bandwidth      → 设置带宽限制

# 搜索服务
GET    /api/search/files             → 文件搜索
GET    /api/search/fulltext          → 全文检索

# 沙箱执行
POST   /api/sandbox/executions       → 提交执行
GET    /api/sandbox/executions/{id}  → 查询执行状态
GET    /api/jobs/{id}                → 通用作业状态（跨下载/沙箱/工作流）

# AI 对话
POST   /api/conversations            → 创建对话
POST   /api/conversations/{id}/messages → 发送消息
DELETE /api/conversations/{id}       → 清空对话
GET    /api/conversations/{id}       → 获取对话历史

# 配置管理
GET    /api/config/ai                → 获取 AI 配置（脱敏）
PUT    /api/config/ai                → 更新 AI 配置
POST   /api/config/ai/test           → 测试连接

# 仪表盘/管理
GET    /api/dashboard/stats          → 仪表盘统计
GET    /api/logs                     → 操作日志（需 Admin）
GET    /api/health                   → 健康检查（Public）
```

### 7.2 统一响应包装器

```python
# models/response.py
from typing import Generic, TypeVar, Optional
from pydantic import BaseModel

T = TypeVar("T")

class ApiResponse(BaseModel, Generic[T]):
    """统一 API 响应结构"""
    success: bool
    data: Optional[T] = None
    error: Optional[ErrorDetail] = None
    request_id: str  # 用于分布式追踪

class ErrorDetail(BaseModel):
    code: str        # 机器可读错误码，如 "DOWNLOAD_INVALID_URL"
    message: str     # 用户可读错误信息
    detail: Optional[dict] = None  # 额外上下文（DEBUG 模式才包含）

class PaginatedResponse(BaseModel, Generic[T]):
    """分页响应"""
    items: list[T]
    total: int
    page: int
    page_size: int
    has_more: bool
```

### 7.3 统一异常处理

```python
# middleware/exceptions.py
from fastapi import Request, status
from fastapi.responses import JSONResponse

class BusinessException(Exception):
    """业务异常，映射为结构化错误响应"""
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code

@app.exception_handler(BusinessException)
async def business_exception_handler(request: Request, exc: BusinessException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {"code": exc.code, "message": exc.message},
            "request_id": get_request_id(request),
        },
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """未捕获异常：生产环境不暴露内部详情"""
    logger.exception("Unhandled exception")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "服务器内部错误" if not DEBUG else str(exc),
            },
            "request_id": get_request_id(request),
        },
    )
```

---

## 八、数据层优化

### 8.1 数据库 Schema 演进

当前 Schema 问题：外键未启用、复合主键处理缺失、无连接池、N+1 查询。

目标 Schema 设计（关键变更）：

```sql
-- 启用外键
PRAGMA foreign_keys = ON;

-- 新增 jobs 表（替代内存字典）
CREATE TABLE jobs (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL CHECK(type IN ('download', 'sandbox', 'workflow')),
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK(status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
    payload TEXT NOT NULL,  -- JSON
    result TEXT,            -- JSON
    error_message TEXT,
    progress INTEGER DEFAULT 0 CHECK(progress BETWEEN 0 AND 100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP    -- TTL 清理
);
CREATE INDEX idx_jobs_status ON jobs(status);
CREATE INDEX idx_jobs_expires ON jobs(expires_at);

-- 新增 config 表（替代 ai_config.json）
CREATE TABLE config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    is_sensitive INTEGER DEFAULT 0 CHECK(is_sensitive IN (0, 1)),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 新增 conversations 表（可选，若需要持久化对话）
CREATE TABLE conversations (
    id TEXT PRIMARY KEY,
    title TEXT,
    model TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE conversation_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK(role IN ('system', 'user', 'assistant', 'tool')),
    content TEXT NOT NULL,
    tool_calls TEXT,  -- JSON
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_messages_conversation ON conversation_messages(conversation_id, created_at);

-- 新增 devices 表（替代内存字典）
CREATE TABLE devices (
    device_id TEXT PRIMARY KEY,
    device_name TEXT,
    device_type TEXT,
    push_token TEXT,
    last_seen TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 新增 webhooks 表（替代 JSON 文件）
CREATE TABLE webhooks (
    id TEXT PRIMARY KEY,
    url TEXT NOT NULL,
    events TEXT NOT NULL,  -- JSON array
    secret_hash TEXT,      -- 存储哈希而非明文
    is_active INTEGER DEFAULT 1,
    success_count INTEGER DEFAULT 0,
    fail_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 新增 workflows 表（替代 JSON 文件）
CREATE TABLE workflows (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    trigger_type TEXT NOT NULL,
    trigger_config TEXT NOT NULL,  -- JSON
    actions TEXT NOT NULL,         -- JSON array
    is_active INTEGER DEFAULT 1,
    last_run_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 全文检索：使用 SQLite FTS5（替代内存索引）
CREATE VIRTUAL TABLE documents_fts USING fts5(
    filename,
    content,
    filepath,
    tokenize='porter unicode61'
);
```

### 8.2 查询优化策略

| 问题 | 当前 | 目标 |
|------|------|------|
| N+1 查询（日历视图标签） | 每任务单独查标签 | JOIN + 批量查询 |
| 分页计数不一致 | Python 层二次过滤 | SQL WHERE 统一过滤 |
| 仪表盘统计阻塞 | 每次请求遍历磁盘 | 后台定时任务 + 缓存 |
| 无连接池 | 每次操作新建连接 | 连接池（max 5）或单例 |

---

## 九、测试架构重构

### 9.1 当前测试金字塔（畸形）

```
         /\
        /  \      E2E 测试（依赖外部服务器）— 占比过高
       /----\     16 个 API 测试，全部依赖 localhost:8900
      /      \
     /--------\   集成测试 — 几乎为零
    /          \
   /------------\ 单元测试 — 被安全测试替代，业务逻辑覆盖不足
  /   44 安全    \ 大量存在性测试、被 skip 的测试
 /     测试      \
/________________\
```

### 9.2 目标测试金字塔

```
         /\
        /  \      E2E 测试（使用 TestClient）— 20%
       /----\     快速、无外部依赖、事务隔离
      /      \
     /--------\   集成测试 — 30%
    /          \   Service + DB（内存数据库）、外部 API mock
   /------------\ 
  /              \ 单元测试 — 50%
 /   安全 + 业务   \ 纯逻辑、无 I/O、快速反馈
/     逻辑测试     \
/__________________\
```

### 9.3 测试基础设施

```python
# test/conftest.py
import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport
import aiosqlite

@pytest.fixture(scope="function")
async def db():
    """每个测试使用独立内存数据库"""
    conn = await aiosqlite.connect(":memory:")
    await init_schema(conn)  # 迁移 Schema
    yield conn
    await conn.close()

@pytest.fixture(scope="function")
def client(db):
    """FastAPI TestClient，自动使用内存数据库"""
    app.dependency_overrides[get_db] = lambda: db
    transport = ASGITransport(app=app)
    with TestClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()

@pytest.fixture(autouse=True)
def reset_global_state():
    """每次测试后清理全局状态"""
    yield
    # 清理内存缓存、重置限流器等
```

### 9.4 测试分层策略

| 层级 | 工具 | 范围 | 速度 |
|------|------|------|------|
| 单元 | `pytest` + `unittest.mock` | Service 纯逻辑、安全校验规则 | `< 1s` |
| 集成 | `TestClient` + `:memory:` SQLite | Router + Service + DB | `< 5s` |
| E2E | `TestClient` + 文件系统 mock | 完整请求链路 | `< 10s` |
| 安全 | `pytest` + 参数化 | 攻击 payload 覆盖 | `< 3s` |

---

## 十、部署与运维架构

### 10.1 目标部署架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                           用户层                                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐   │
│  │  Web UI  │  │  GLM 智能体 │  │ 移动 App  │  │  第三方 Webhooks  │   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────────┬─────────┘   │
└───────┼─────────────┼─────────────┼─────────────────┼───────────────┘
        │             │             │                 │
        └─────────────┴─────────────┴─────────────────┘
                          │
                   ┌──────┴──────┐
                   │   反向代理   │
                   │  (nginx/    │
                   │   traefik)  │
                   └──────┬──────┘
                          │
┌─────────────────────────┼───────────────────────────────────────────┐
│                         ▼                                           │
│              ┌──────────────────────┐                                │
│              │   LocalCommandCenter │                                │
│              │   (FastAPI + uvicorn)│                                │
│              │   workers: 1 (本地)   │                                │
│              │   或 workers: 4+ (稍重)│                               │
│              └──────────────────────┘                                │
│                         │                                           │
│              ┌──────────┼──────────┐                                │
│              ▼          ▼          ▼                                │
│         ┌────────┐ ┌────────┐ ┌────────┐                          │
│         │SQLite  │ │Docker  │ │FileSys │                          │
│         │(data/) │ │Socket  │ │(downloads/)│                      │
│         └────────┘ └────────┘ └────────┘                          │
│                                                                     │
│  可选增强：                                                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                        │
│  │  Redis   │  │  Prometheus │  │  Grafana  │                       │
│  │ (缓存/锁) │  │  (指标采集) │  │  (可视化) │                       │
│  └──────────┘  └──────────┘  └──────────┘                        │
└─────────────────────────────────────────────────────────────────────┘
```

### 10.2 配置环境分离

```python
# config/environments.py
from enum import Enum

class Environment(Enum):
    DEVELOPMENT = "dev"
    TESTING = "test"
    PRODUCTION = "prod"

ENV = Environment(os.getenv("GATEWAY_ENV", "dev"))

# 环境专属默认值
if ENV == Environment.PRODUCTION:
    CORS_ORIGINS_DEFAULT = []  # 必须显式配置
    ALLOW_CREDENTIALS = False  # 生产环境默认关闭
    DOCS_URL = None            # 关闭 Swagger
    REDOC_URL = None
    DEBUG = False
    LOG_LEVEL = "INFO"
else:
    CORS_ORIGINS_DEFAULT = ["http://localhost:8900", "http://localhost:5173"]
    ALLOW_CREDENTIALS = True
    DOCS_URL = "/docs"
    REDOC_URL = "/redoc"
    DEBUG = True
    LOG_LEVEL = "DEBUG"
```

### 10.3 容器化建议

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
# 非 root 运行
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8900
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8900", "--workers", "1"]
```

```yaml
# docker-compose.yml (可选增强)
version: '3.8'
services:
  gateway:
    build: .
    ports:
      - "8900:8900"
    volumes:
      - ./data:/app/data
      - ./downloads:/app/downloads
    environment:
      - GATEWAY_ENV=production
      - CORS_ORIGINS=http://localhost:8900
    restart: unless-stopped
  
  # 可选：Redis 用于多实例状态共享
  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
    restart: unless-stopped

volumes:
  redis_data:
```

---

## 十一、演进路线图

### 11.1 阶段规划

```
Phase A: 安全加固（2-3 周）
├── [P0] 认证中间件（API Key）
├── [P0] CORS 收紧 + Rate Limit
├── [P0] 安全服务统一（路径遍历/SSRF/命令注入拦截）
├── [P0] 凭证加密存储（keyring）
├── [P0] 沙箱容器加固（非 root、无网络、cap_drop）
├── [P0] 前端 XSS 修复（escapeHtml + 移除 onclick）
└── [P0] 测试：补充路径遍历、SQL 注入、SSRF 绕过测试

Phase B: 状态持久化（2 周）
├── [P1] SQLite Schema 扩展（jobs、config、devices、webhooks、workflows）
├── [P1] 内存状态迁移到数据库（队列、Token、设备）
├── [P1] JSON 文件迁移到数据库（shortcuts、workflows、webhooks）
├── [P1] 全文索引 SQLite FTS5 替换
└── [P1] 连接池 + 数据库连接生命周期管理

Phase C: 异步规范化（1-2 周）
├── [P1] 同步 I/O 全面排查（rglob、open、pydub、Docker SDK）
├── [P1] asyncio.to_thread / aiofiles 包装
├── [P1] httpx 模块级 Client 复用
└── [P1] 子进程统一使用 asyncio.create_subprocess_exec

Phase D: 服务拆分（2-3 周）
├── [P2] Job Service 独立抽象
├── [P2] Config Manager 替代 AIConfig 单例
├── [P2] Event Bus 解耦服务间依赖
├── [P2] task_service 职责边界清理（迁出下载历史）
├── [P2] 统一响应模型 + 异常处理器
└── [P2] RESTful 路由重构（task_manager、safe_downloader）

Phase E: 测试重构（1-2 周）
├── [P2] TestClient 替换外部服务器依赖
├── [P2] conftest.py 事务隔离 + 自动清理
├── [P2] 移除无意义的存在性测试和 skip
├── [P2] 测试金字塔：50% 单元 + 30% 集成 + 20% E2E
└── [P2] CI 流水线（GitHub Actions）

Phase F: 架构增强（长期）
├── [P3] WebSocket 实时推送（替代轮询）
├── [P3] 后台 Worker（APScheduler 定时任务、仪表盘统计缓存）
├── [P3] 监控指标（Prometheus / OpenTelemetry）
├── [P3] 日志结构化（JSON）+ 集中收集
├── [P3] 插件系统（工作流动作动态加载）
└── [P3] 多 worker 状态共享（Redis）
```

### 11.2 优先级决策矩阵

| 优化项 | 安全风险 | 稳定性 | 性能 | 可维护性 | 推荐阶段 |
|--------|----------|--------|------|----------|----------|
| 认证中间件 | 极高 | 高 | — | 中 | A |
| CORS 收紧 | 极高 | 高 | — | 低 | A |
| 凭证加密 | 极高 | 中 | — | 低 | A |
| 沙箱加固 | 极高 | 高 | — | 中 | A |
| XSS 修复 | 极高 | 中 | — | 低 | A |
| 状态持久化 | 高 | 极高 | 中 | 高 | B |
| 异步规范化 | 中 | 高 | 极高 | 中 | C |
| 服务拆分 | 中 | 高 | 中 | 极高 | D |
| 测试重构 | 中 | 极高 | — | 极高 | E |
| RESTful 重构 | 低 | 中 | — | 高 | D |
| 监控指标 | 低 | 中 | 中 | 高 | F |

---

## 十二、关键指标（优化前后对比）

| 指标 | 当前 | 目标 | 测量方式 |
|------|------|------|----------|
| 严重安全漏洞数 | 24 | 0 | 安全审查 |
| 认证覆盖率 | 0% | 100%（敏感端点） | 端点审计 |
| 状态持久化率 | ~30% | 100%（业务数据） | 存储审计 |
| 同步阻塞调用数 | 15+ | 0 | 代码扫描 |
| 测试执行时间 | 不可行（需外部服务） | < 30s | pytest |
| 测试可靠性 | 低（数据污染） | 高（事务隔离） | CI 通过率 |
| 路由响应模型覆盖率 | ~40% | 100% | 代码扫描 |
| 错误处理一致性 | 混乱 | 统一 | 代码审查 |
| 服务平均代码行数 | 800+ | < 400 | 代码统计 |
| 模块间耦合度 | 高 | 低 | 依赖分析 |

---

## 十三、附录

### A. 推荐依赖栈

| 用途 | 当前 | 推荐 | 说明 |
|------|------|------|------|
| 异步文件 I/O | 无 | `aiofiles` | 异步文件读写 |
| 连接池 | 无 | `aiosqlite` 自带 / `asyncpg` | 数据库连接复用 |
| 限流 | 无 | `slowapi` | FastAPI 限流中间件 |
| 定时任务 | 无 | `APScheduler` | 后台定时任务 |
| 密钥存储 | 无 | `keyring` | 系统密钥环 |
| 全文检索 | 内存索引 | `sqlite-fts5` | SQLite 内置 FTS5 |
| 任务队列 | 内存字典 | `arq` / `celery` | 可选，若需要分布式 |
| 缓存 | 无 | `cachetools` / `redis` | LRU 内存缓存 |
| 配置管理 | 自定义 | `pydantic-settings` | 类型安全的环境变量 |
| 测试 | `httpx` | `TestClient` + `pytest-asyncio` | FastAPI 官方测试 |
| 监控 | 无 | `prometheus-client` | 指标暴露 |

### B. 文件重组建议

```
local-gateway/
├── main.py                          # 入口（精简至 100 行内）
├── config/
│   ├── __init__.py
│   ├── settings.py                  # Pydantic Settings（替代 config.py）
│   └── environments.py              # 环境分离
├── models/
│   ├── schemas.py                   # 请求/响应模型（拆分）
│   ├── enums.py                     # 所有枚举定义集中
│   └── responses.py                 # 统一响应包装器
├── routers/
│   ├── __init__.py
│   ├── tasks.py                     # RESTful 路由（重命名）
│   ├── downloads.py
│   ├── search.py
│   ├── sandbox.py
│   ├── chat.py
│   ├── dashboard.py
│   └── ...                          # 其他路由
├── services/
│   ├── __init__.py
│   ├── domain/                      # 领域服务
│   │   ├── task_service.py
│   │   ├── download_service.py
│   │   └── ...
│   ├── core/                        # 核心服务
│   │   ├── job_service.py           # 新增
│   │   ├── config_service.py        # 新增
│   │   ├── security_service.py      # 新增
│   │   └── event_bus.py             # 新增
│   └── infrastructure/              # 基础设施
│       ├── db.py                    # 连接池/事务
│       ├── storage.py               # 文件存储抽象
│       └── async_wrappers.py        # 同步调用包装
├── middleware/
│   ├── auth.py                      # 认证中间件
│   ├── rate_limit.py                # 限流中间件
│   ├── logging.py                   # 请求日志/追踪 ID
│   └── exceptions.py                # 统一异常处理
├── static/                          # 前端资源
├── test/
│   ├── conftest.py                  # 测试基础设施
│   ├── unit/                        # 单元测试
│   ├── integration/                 # 集成测试
│   └── e2e/                         # 端到端测试
└── data/                            # SQLite 数据库
```

---

*本文档应与 `COMPREHENSIVE_CODE_REVIEW.md` 配套阅读，审查报告中的具体问题在本文档中映射到架构层面的系统性解决方案。*
