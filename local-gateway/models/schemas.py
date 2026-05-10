"""
Pydantic 请求/响应模型 — 严格对应 5 个 Tool Schema
"""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


# ============================================================
# 通用枚举
# ============================================================

class TaskAction(str, enum.Enum):
    add_task = "add_task"
    delete_task = "delete_task"
    get_weekly_plan = "get_weekly_plan"
    complete_task = "complete_task"
    batch_complete = "batch_complete"
    batch_delete = "batch_delete"
    get_pending_tasks = "get_pending_tasks"


class Recurrence(str, enum.Enum):
    once = "once"
    daily = "daily"
    weekly = "weekly"
    monthly = "monthly"


class DownloadCategory(str, enum.Enum):
    paper = "paper"
    video = "video"
    code = "code"
    misc = "misc"


class SearchCategory(str, enum.Enum):
    paper = "paper"
    video = "video"
    code = "code"
    misc = "misc"
    all = "all"


class SandboxTool(str, enum.Enum):
    python = "python"
    node = "node"
    ffmpeg = "ffmpeg"
    pandoc = "pandoc"


# ============================================================
# Tool 1: local_task_manager
# ============================================================

class Priority(int, enum.Enum):
    urgent = 0
    high = 1
    medium = 2
    low = 3


class TaskManagerRequest(BaseModel):
    action: TaskAction
    task_name: Optional[str] = Field(
        None,
        description="任务名称，add_task 时必填",
    )
    task_id: Optional[str] = Field(
        None,
        description="任务唯一标识符，delete_task / complete_task 时必填",
    )
    task_ids: Optional[list[str]] = Field(
        None,
        description="任务 ID 列表，batch_complete / batch_delete 时必填",
    )
    due_time: Optional[str] = Field(
        None,
        description="ISO 8601 截止/提醒时间，add_task 时必填",
    )
    start_time: Optional[str] = Field(
        None,
        description="ISO 8601 任务执行开始时间",
    )
    end_time: Optional[str] = Field(
        None,
        description="ISO 8601 任务执行结束时间",
    )
    recurrence: Optional[Recurrence] = None
    priority: Optional[Priority] = Field(
        Priority.medium,
        description="优先级: 0=紧急, 1=高, 2=中, 3=低",
    )
    description: Optional[str] = Field(None, description="任务描述")
    estimated_minutes: Optional[int] = Field(None, description="预估时间（分钟）")
    tags: Optional[list[str]] = Field(None, description="标签列表")

    @field_validator("due_time")
    @classmethod
    def validate_due_time(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        # 基本校验：尝试解析 ISO 8601
        from datetime import datetime as _dt
        _dt.fromisoformat(v)
        return v


class TaskInfo(BaseModel):
    task_id: str
    task_name: str
    due_time: str
    recurrence: str
    status: str  # pending / completed / deleted
    priority: int = 2  # 0=urgent, 1=high, 2=medium, 3=low
    description: Optional[str] = None
    estimated_minutes: Optional[int] = None
    tags: list[str] = []
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    completed_at: Optional[str] = None
    overdue: Optional[bool] = None


class TaskManagerResponse(BaseModel):
    status: str  # success / error
    task_id: Optional[str] = None
    message: Optional[str] = None
    next_reminder: Optional[str] = None
    tasks: Optional[list[TaskInfo]] = None
    warnings: Optional[list[str]] = None
    total: Optional[int] = None
    overdue_count: Optional[int] = None


# ============================================================
# 批量任务编排
# ============================================================

class BatchTaskItem(BaseModel):
    task_name: str = Field(..., description="任务名称")
    due_time: str = Field(..., description="截止时间，支持宽松格式如 '3月22日' 或 ISO 8601")
    recurrence: str = Field("once", description="重复周期: once/daily/weekly/monthly")
    priority: Optional[Priority] = Field(Priority.medium, description="优先级")
    description: Optional[str] = Field(None, description="任务描述")
    estimated_minutes: Optional[int] = Field(None, description="预估时间（分钟）")
    start_time: Optional[str] = Field(None, description="任务执行开始时间（ISO 8601）")
    end_time: Optional[str] = Field(None, description="任务执行结束时间（ISO 8601）")


class BatchTaskRequest(BaseModel):
    action: str = Field(..., description="操作: 'preview' 预览分析 | 'create' 批量创建")
    tasks: list[BatchTaskItem] = Field(..., description="任务列表")


class BatchTaskResponse(BaseModel):
    status: str
    total: int = 0
    success_count: int = 0
    error_count: int = 0
    results: Optional[list[dict]] = None
    analyzed: Optional[list[dict]] = None
    timeline: Optional[list[str]] = None
    daily_plan: Optional[dict] = None
    daily_timeline: Optional[list[str]] = None
    by_date: Optional[dict] = None
    existing_tasks: Optional[list[dict]] = None
    message: Optional[str] = None


# ============================================================
# Tool 2: local_safe_downloader
# ============================================================

class SafeDownloaderRequest(BaseModel):
    url: str = Field(..., description="下载资源 URL")
    category: DownloadCategory = Field(..., description="归档分类")
    filename: Optional[str] = Field(
        None,
        description="保存文件名，不指定则自动生成",
    )


class SafeDownloaderResponse(BaseModel):
    status: str  # success / error / async
    file_path: Optional[str] = None
    file_size: Optional[str] = None
    security_scan: Optional[str] = None  # passed / failed
    message: Optional[str] = None
    # 异步字段
    mode: Optional[str] = None  # async
    job_id: Optional[str] = None
    estimated_seconds: Optional[int] = None
    position: Optional[int] = None  # 队列位置


class DownloadQueueItem(BaseModel):
    job_id: str
    filename: str
    status: str  # queued/downloading/paused/completed/failed
    progress: int  # 0-100
    speed_kb_s: int
    retry_count: int


class DownloadQueueResponse(BaseModel):
    status: str
    queue_length: int
    active_downloads: int
    max_concurrent: int
    items: list[DownloadQueueItem]


class BandwidthResponse(BaseModel):
    status: str
    limit_kb_s: int


# ============================================================
# Tool 3: local_file_search
# ============================================================

class FileSearchRequest(BaseModel):
    keyword: str = Field(..., description="搜索关键词")
    category: SearchCategory = Field(..., description="搜索分类")


class FileInfo(BaseModel):
    filename: str
    category: str
    path: str
    size: str
    downloaded_at: Optional[str] = None


class FileSearchResponse(BaseModel):
    status: str  # success / error
    total: int = 0
    files: list[FileInfo] = []


# ============================================================
# 统一搜索 (Batch 1 Task 7)
# ============================================================

class SearchScope(str, enum.Enum):
    all = "all"
    files = "files"
    tasks = "tasks"
    notes = "notes"
    habits = "habits"


class UnifiedSearchRequest(BaseModel):
    keyword: str = Field(..., min_length=1, description="搜索关键词")
    scope: SearchScope = Field(SearchScope.all, description="搜索范围")
    category: Optional[str] = Field("all", description="文件分类（仅 files scope 时有效）")
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)


class UnifiedSearchResponse(BaseModel):
    status: str
    results: dict = Field(default_factory=dict)
    total: int = 0
    scope: str = "all"


# ============================================================
# Tool 4: local_sandbox_executor
# ============================================================

class SandboxExecutorRequest(BaseModel):
    tool_name: SandboxTool
    execution_command: str = Field(..., description="主执行命令")
    setup_commands: Optional[list[str]] = Field(
        None,
        description="前置准备命令（如安装依赖）",
    )
    dynamic_files: Optional[dict[str, str]] = Field(
        None,
        description="动态写入文件 {filename: content}",
    )
    input_files: Optional[list[str]] = Field(
        None,
        description="宿主机文件挂载路径列表",
    )


class SandboxExecutorResponse(BaseModel):
    status: str  # success / error / async
    exit_code: Optional[int] = None
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    output_files: Optional[list[str]] = None
    copied_to: Optional[list[str]] = None
    duration_seconds: Optional[float] = None
    message: Optional[str] = None
    # 异步字段
    mode: Optional[str] = None
    job_id: Optional[str] = None


# ============================================================
# Tool 5: local_job_status
# ============================================================

class JobStatusRequest(BaseModel):
    job_id: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str  # pending / running / completed / failed
    result: Optional[dict[str, Any]] = None
    message: Optional[str] = None
    # 下载完成后的字段
    file_path: Optional[str] = None
    file_size: Optional[str] = None
    security_scan: Optional[str] = None
    duration_seconds: Optional[float] = None


# ============================================================
# 健康检查
# ============================================================

class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


# ============================================================
# 新增：仪表盘 / 下载历史 / 日志 / 全部任务
# ============================================================

class DashboardResponse(BaseModel):
    status: str
    tasks: dict = {}
    downloads: dict = {}
    storage: dict = {}
    recent_logs: list[dict] = []
    recent_downloads: list[dict] = []
    streak: dict = {}


class DownloadHistoryResponse(BaseModel):
    status: str
    records: list[dict] = []
    total: int = 0
    page: int = 1
    page_size: int = 20


class LogsResponse(BaseModel):
    status: str
    logs: list[dict] = []
    total: int = 0
    page: int = 1
    page_size: int = 50


class AllTasksResponse(BaseModel):
    status: str
    tasks: list[dict] = []
    total: int = 0
    page: int = 1
    page_size: int = 20
    total_pages: int = 0


# ============================================================
# AI 对话
# ============================================================

class ChatRequest(BaseModel):
    message: str = Field(..., description="用户消息")
    conversation_id: str = Field("default", description="对话 ID")


class ChatResponse(BaseModel):
    status: str  # success / error
    reply: str = ""
    message: Optional[str] = None


class AIConfigRequest(BaseModel):
    api_base: str = Field("", description="AI API 地址")
    api_key: str = Field("", description="AI API Key")
    model: str = Field("", description="模型名称")


class AIConfigResponse(BaseModel):
    status: str
    config: Optional[dict] = None
    message: Optional[str] = None


class AITestResponse(BaseModel):
    status: str
    reply: str = ""
    message: Optional[str] = None
    test_reply: Optional[str] = None


# ============================================================
# 标签管理
# ============================================================

class TagCreateRequest(BaseModel):
    name: str = Field(..., description="标签名称")
    color: str = Field("#3498db", description="标签颜色")


class TagResponse(BaseModel):
    tag_id: int
    name: str
    color: str


class TagListResponse(BaseModel):
    status: str
    tags: list[TagResponse]


# ============================================================
# 子任务管理
# ============================================================

class SubtaskCreateRequest(BaseModel):
    task_id: str = Field(..., description="父任务ID")
    name: str = Field(..., description="子任务名称")


class SubtaskUpdateRequest(BaseModel):
    subtask_id: str = Field(..., description="子任务ID")
    name: Optional[str] = None
    status: Optional[str] = None  # pending/completed


class SubtaskInfo(BaseModel):
    subtask_id: str
    task_id: str
    name: str
    status: str
    sort_order: int


class SubtaskListResponse(BaseModel):
    status: str
    subtasks: list[SubtaskInfo]


# ============================================================
# 番茄钟管理
# ============================================================

class PomodoroStartRequest(BaseModel):
    task_id: Optional[str] = Field(None, description="关联任务ID（可选）")
    duration_minutes: int = Field(25, description="番茄钟时长（分钟）")


class PomodoroInterruptRequest(BaseModel):
    session_id: str = Field(..., description="会话ID")
    reason: Optional[str] = Field(None, description="中断原因")


class PomodoroSession(BaseModel):
    session_id: str
    task_id: Optional[str]
    task_name: Optional[str] = None
    start_time: str
    end_time: Optional[str]
    duration_minutes: int
    actual_minutes: Optional[int]
    status: str  # running/completed/interrupted
    interrupt_reason: Optional[str]


class PomodoroStatusResponse(BaseModel):
    status: str
    active_session: Optional[PomodoroSession] = None
    message: Optional[str] = None


class PomodoroStatsResponse(BaseModel):
    status: str
    today_count: int  # 今日完成数
    today_minutes: int  # 今日专注分钟
    week_count: int  # 本周完成数
    week_minutes: int  # 本周专注分钟
    total_count: int  # 总计完成数
    total_minutes: int  # 总计专注分钟
    daily_stats: list[dict]  # 最近7天统计


class PomodoroHistoryResponse(BaseModel):
    status: str
    sessions: list[PomodoroSession]
    total: int
    page: int
    page_size: int


# ============================================================
# 日历视图
# ============================================================

class CalendarEventCreateRequest(BaseModel):
    title: str = Field(..., description="事件标题")
    description: Optional[str] = None
    start_time: str = Field(..., description="开始时间 ISO 8601")
    end_time: str = Field(..., description="结束时间 ISO 8601")
    event_type: str = Field("personal", description="事件类型")
    color: Optional[str] = None


class CalendarEvent(BaseModel):
    event_id: str
    title: str
    description: Optional[str]
    start_time: str
    end_time: str
    event_type: str
    color: str


class CalendarViewRequest(BaseModel):
    view_type: str = Field(..., description="month/week/day")
    year: int
    month: int
    day: Optional[int] = None  # week/day 视图需要


class CalendarDay(BaseModel):
    date: str  # YYYY-MM-DD
    weekday: int  # 0=Monday
    is_today: bool
    is_current_month: bool
    tasks: list[TaskInfo]
    events: list[CalendarEvent]
    pomodoro_count: int


class CalendarViewResponse(BaseModel):
    status: str
    view_type: str
    year: int
    month: int
    days: list[CalendarDay]


# ============================================================
# 批量任务更新
# ============================================================

class BatchTaskUpdateRequest(BaseModel):
    task_ids: list[str]
    priority: Optional[Priority] = None
    tags_add: Optional[list[str]] = None
    tags_remove: Optional[list[str]] = None
    due_time: Optional[str] = None


# ============================================================
# 笔记管理
# ============================================================

class NoteInfo(BaseModel):
    note_id: str
    title: str
    content: str
    content_type: str
    tags: list[str]
    task_id: Optional[str]
    created_at: str
    updated_at: str


class NoteListResponse(BaseModel):
    status: str
    notes: list[NoteInfo]
    total: int
    page: int
    page_size: int


# ============================================================
# 习惯管理
# ============================================================

class HabitInfo(BaseModel):
    habit_id: str
    name: str
    description: str
    frequency: str
    target_count: int
    reminder_time: Optional[str]
    color: str
    created_at: str
    streak: int = 0


class HabitCheckin(BaseModel):
    checkin_id: int
    checkin_date: str
    count: int
    note: str


class HabitDetail(BaseModel):
    habit_id: str
    name: str
    description: str
    frequency: str
    target_count: int
    reminder_time: Optional[str]
    color: str
    created_at: str
    checkins: list[HabitCheckin]
    streak: int


class HabitStatsResponse(BaseModel):
    status: str
    total_count: int
    total_days: int
    week_count: int
    month_count: int
