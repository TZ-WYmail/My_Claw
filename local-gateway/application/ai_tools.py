"""
AI tool application entrypoints.

This module centralizes the internal execution path for the core tool actions
used by the AI runtime, so internal callers do not need to loop back through
HTTP endpoints.
"""
from __future__ import annotations

import warnings

from models.schemas import (
    JobStatusRequest,
    JobStatusResponse,
    SafeDownloaderRequest,
    SafeDownloaderResponse,
    SandboxExecutorRequest,
    SandboxExecutorResponse,
    UnifiedSearchRequest,
    UnifiedSearchResponse,
)
from application.task_actions import execute_batch_task_manager, execute_local_task_manager
from services.download_service import get_job_status, safe_download
from services.sandbox_service import execute_in_sandbox
from services.unified_search_service import unified_search

async def execute_local_safe_downloader(payload: dict) -> dict:
    request = SafeDownloaderRequest(**payload)
    result = await safe_download(
        url=request.url,
        category=request.category.value,
        filename=request.filename,
    )
    return SafeDownloaderResponse(**result).model_dump()


async def execute_local_unified_search(payload: dict) -> dict:
    """Canonical AI tool entrypoint for unified search."""
    # Prefer the unified search path used by the current API surface.
    request = UnifiedSearchRequest(**payload)
    result = await unified_search(
        keyword=request.keyword,
        scope=request.scope.value,
        category=request.category or "all",
        page=request.page,
        page_size=request.page_size,
    )
    files = result.get("results", {}).get("files", {})
    tasks = result.get("results", {}).get("tasks", {})
    notes = result.get("results", {}).get("notes", {})
    habits = result.get("results", {}).get("habits", {})
    return UnifiedSearchResponse(
        **result,
        files=files.get("items", []),
        tasks=tasks.get("items", []),
        notes=notes.get("items", []),
        habits=habits.get("items", []),
    ).model_dump()


async def execute_local_file_search(payload: dict) -> dict:
    """Deprecated compatibility alias for the former AI search tool name."""
    warnings.warn(
        "AI tool name local_file_search is deprecated; use local_unified_search instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return await execute_local_unified_search(payload)


async def execute_local_sandbox_executor(payload: dict) -> dict:
    request = SandboxExecutorRequest(**payload)
    result = await execute_in_sandbox(
        tool_name=request.tool_name.value,
        execution_command=request.execution_command,
        setup_commands=request.setup_commands,
        dynamic_files=request.dynamic_files,
        input_files=request.input_files,
    )
    return SandboxExecutorResponse(**result).model_dump()


async def execute_local_job_status(payload: dict) -> dict:
    request = JobStatusRequest(**payload)
    job = get_job_status(request.job_id)
    if not job:
        return JobStatusResponse(
            job_id=request.job_id,
            status="not_found",
            message=f"任务 {request.job_id} 不存在或已过期",
        ).model_dump()

    return JobStatusResponse(
        job_id=request.job_id,
        status=job.get("status", "unknown"),
        message=job.get("message"),
        file_path=job.get("file_path"),
        file_size=job.get("file_size"),
        security_scan=job.get("security_scan"),
        duration_seconds=job.get("duration_seconds"),
        result=job,
    ).model_dump()


AI_TOOL_EXECUTORS = {
    "local_task_manager": execute_local_task_manager,
    "batch_task_manager": execute_batch_task_manager,
    "local_safe_downloader": execute_local_safe_downloader,
    "local_unified_search": execute_local_unified_search,
    "local_file_search": execute_local_file_search,
    "local_sandbox_executor": execute_local_sandbox_executor,
    "local_job_status": execute_local_job_status,
}


async def execute_ai_tool(name: str, payload: dict) -> dict:
    executor = AI_TOOL_EXECUTORS.get(name)
    if not executor:
        return {"status": "error", "message": f"未知工具: {name}"}
    return await executor(payload)
