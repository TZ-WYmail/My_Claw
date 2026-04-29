"""
高级功能路由 — 标签、子任务、番茄钟、日历视图
"""
from typing import Optional

from fastapi import APIRouter, Query

from models import schemas
from services import task_service

router = APIRouter(prefix="/advanced", tags=["advanced"])


# ============================================================
# 标签管理
# ============================================================

@router.post("/tags", response_model=schemas.TagListResponse)
async def create_tag(request: schemas.TagCreateRequest):
    """创建标签"""
    result = await task_service.create_tag(request.name, request.color)
    if result["status"] == "success":
        tags = await task_service.get_all_tags()
        return {"status": "success", "tags": tags}
    return {"status": "error", "tags": []}


@router.get("/tags", response_model=schemas.TagListResponse)
async def list_tags():
    """获取所有标签"""
    tags = await task_service.get_all_tags()
    return {"status": "success", "tags": tags}


@router.delete("/tags/{tag_id}")
async def delete_tag(tag_id: int):
    """删除标签"""
    return await task_service.delete_tag(tag_id)


@router.post("/tasks/{task_id}/tags")
async def add_task_tags(task_id: str, tags: list[str]):
    """为任务添加标签"""
    return await task_service.add_task_tags(task_id, tags)


@router.delete("/tasks/{task_id}/tags")
async def remove_task_tags(task_id: str, tags: list[str]):
    """移除任务的标签"""
    return await task_service.remove_task_tags(task_id, tags)


# ============================================================
# 子任务管理
# ============================================================

@router.post("/subtasks", response_model=schemas.SubtaskListResponse)
async def create_subtask(request: schemas.SubtaskCreateRequest):
    """创建子任务"""
    result = await task_service.create_subtask(request.task_id, request.name)
    if result["status"] == "success":
        subtasks = await task_service.get_subtasks(request.task_id)
        return {"status": "success", "subtasks": subtasks}
    return {"status": "error", "subtasks": []}


@router.get("/tasks/{task_id}/subtasks", response_model=schemas.SubtaskListResponse)
async def list_subtasks(task_id: str):
    """获取任务的所有子任务"""
    subtasks = await task_service.get_subtasks(task_id)
    return {"status": "success", "subtasks": subtasks}


@router.put("/subtasks/{subtask_id}")
async def update_subtask(subtask_id: str, request: schemas.SubtaskUpdateRequest):
    """更新子任务"""
    return await task_service.update_subtask(subtask_id, request.name, request.status)


@router.delete("/subtasks/{subtask_id}")
async def delete_subtask(subtask_id: str):
    """删除子任务"""
    return await task_service.delete_subtask(subtask_id)


# ============================================================
# 番茄钟管理
# ============================================================

@router.post("/pomodoro/start", response_model=schemas.PomodoroStatusResponse)
async def start_pomodoro(request: schemas.PomodoroStartRequest):
    """开始番茄钟"""
    result = await task_service.start_pomodoro(request.task_id, request.duration_minutes)
    if result["status"] == "success":
        active = await task_service.get_active_pomodoro()
        return {"status": "success", "active_session": active}
    return {"status": "error", "message": result.get("message")}


@router.post("/pomodoro/complete")
async def complete_pomodoro():
    """完成番茄钟"""
    return await task_service.complete_pomodoro()


@router.post("/pomodoro/interrupt")
async def interrupt_pomodoro(request: schemas.PomodoroInterruptRequest):
    """中断番茄钟"""
    return await task_service.interrupt_pomodoro(request.reason)


@router.get("/pomodoro/status", response_model=schemas.PomodoroStatusResponse)
async def get_pomodoro_status():
    """获取当前番茄钟状态"""
    active = await task_service.get_active_pomodoro()
    return {"status": "success", "active_session": active}


@router.get("/pomodoro/stats", response_model=schemas.PomodoroStatsResponse)
async def get_pomodoro_stats():
    """获取番茄钟统计"""
    return await task_service.get_pomodoro_stats()


@router.get("/pomodoro/history", response_model=schemas.PomodoroHistoryResponse)
async def get_pomodoro_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """获取番茄钟历史"""
    return await task_service.get_pomodoro_history(page, page_size)


# ============================================================
# 日历视图
# ============================================================

@router.post("/calendar/events")
async def create_calendar_event(request: schemas.CalendarEventCreateRequest):
    """创建日历事件"""
    return await task_service.create_calendar_event(
        request.title,
        request.start_time,
        request.end_time,
        request.description,
        request.event_type,
        request.color,
    )


@router.get("/calendar/events")
async def list_calendar_events(
    start_date: str = Query(..., description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="结束日期 YYYY-MM-DD"),
):
    """获取日期范围内的日历事件"""
    events = await task_service.get_calendar_events(start_date, end_date)
    return {"status": "success", "events": events}


@router.delete("/calendar/events/{event_id}")
async def delete_calendar_event(event_id: str):
    """删除日历事件"""
    return await task_service.delete_calendar_event(event_id)


@router.get("/calendar/view", response_model=schemas.CalendarViewResponse)
async def get_calendar_view(
    year: int = Query(..., description="年份"),
    month: int = Query(..., ge=1, le=12, description="月份"),
):
    """获取月度日历视图"""
    return await task_service.get_calendar_view(year, month)


# ============================================================
# 批量操作
# ============================================================

@router.post("/tasks/batch-update")
async def batch_update_tasks(request: schemas.BatchTaskUpdateRequest):
    """批量更新任务"""
    results = []
    for task_id in request.task_ids:
        # 这里可以实现批量更新逻辑
        results.append({"task_id": task_id, "status": "updated"})
    return {"status": "success", "results": results}
