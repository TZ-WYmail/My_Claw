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
    due_time: Optional[str] = Field(
        None,
        description="ISO 8601 截止/提醒时间，add_task 时必填",
    )
    recurrence: Optional[Recurrence] = None

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


class TaskManagerResponse(BaseModel):
    status: str  # success / error
    task_id: Optional[str] = None
    message: Optional[str] = None
    next_reminder: Optional[str] = None
    tasks: Optional[list[TaskInfo]] = None


# ============================================================
# 批量任务编排
# ============================================================

class BatchTaskItem(BaseModel):
    task_name: str = Field(..., description="任务名称")
    due_time: str = Field(..., description="截止时间，支持宽松格式如 '3月22日' 或 ISO 8601")
    recurrence: str = Field("once", description="重复周期: once/daily/weekly/monthly")


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
