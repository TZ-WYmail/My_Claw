"""
高级功能路由 — 标签、子任务、番茄钟、日历视图
"""

from fastapi import APIRouter, Query

from application.advanced_actions import (
    add_task_tags_action,
    batch_update_tasks_action,
    complete_pomodoro_action,
    create_calendar_event_action,
    create_subtask_action,
    create_tag_action,
    delete_calendar_event_action,
    delete_subtask_action,
    delete_tag_action,
    get_calendar_view_action,
    get_pomodoro_history_action,
    get_pomodoro_stats_action,
    get_pomodoro_status_action,
    get_task_detail_action,
    interrupt_pomodoro_action,
    list_calendar_events_action,
    list_subtasks_action,
    list_tags_action,
    remove_task_tags_action,
    start_pomodoro_action,
    update_subtask_action,
)
from models import schemas

router = APIRouter(prefix="/advanced", tags=["advanced"])


# ============================================================
# 标签管理
# ============================================================

@router.post("/tags", response_model=schemas.TagListResponse)
async def create_tag(request: schemas.TagCreateRequest):
    """创建标签"""
    return await create_tag_action(request.name, request.color)


@router.get("/tags", response_model=schemas.TagListResponse)
async def list_tags():
    """获取所有标签"""
    return await list_tags_action()


@router.delete("/tags/{tag_id}")
async def delete_tag(tag_id: int):
    """删除标签"""
    return await delete_tag_action(tag_id)


@router.post("/tasks/{task_id}/tags")
async def add_task_tags(task_id: str, tags: list[str]):
    """为任务添加标签"""
    return await add_task_tags_action(task_id, tags)


@router.delete("/tasks/{task_id}/tags")
async def remove_task_tags(task_id: str, tags: list[str]):
    """移除任务的标签"""
    return await remove_task_tags_action(task_id, tags)


# ============================================================
# 子任务管理
# ============================================================

@router.post("/subtasks", response_model=schemas.SubtaskListResponse)
async def create_subtask(request: schemas.SubtaskCreateRequest):
    """创建子任务"""
    return await create_subtask_action(request.task_id, request.name)


@router.get("/tasks/{task_id}/subtasks", response_model=schemas.SubtaskListResponse)
async def list_subtasks(task_id: str):
    """获取任务的所有子任务"""
    return await list_subtasks_action(task_id)


@router.put("/subtasks/{subtask_id}")
async def update_subtask(subtask_id: str, request: schemas.SubtaskUpdateRequest):
    """更新子任务"""
    return await update_subtask_action(subtask_id, request.name, request.status)


@router.delete("/subtasks/{subtask_id}")
async def delete_subtask(subtask_id: str):
    """删除子任务"""
    return await delete_subtask_action(subtask_id)


# ============================================================
# 番茄钟管理
# ============================================================

@router.post("/pomodoro/start", response_model=schemas.PomodoroStatusResponse)
async def start_pomodoro(request: schemas.PomodoroStartRequest):
    """开始番茄钟"""
    return await start_pomodoro_action(request.task_id, request.duration_minutes)


@router.post("/pomodoro/complete")
async def complete_pomodoro():
    """完成番茄钟"""
    return await complete_pomodoro_action()


@router.post("/pomodoro/interrupt")
async def interrupt_pomodoro(request: schemas.PomodoroInterruptRequest):
    """中断番茄钟"""
    return await interrupt_pomodoro_action(request.reason)


@router.get("/pomodoro/status", response_model=schemas.PomodoroStatusResponse)
async def get_pomodoro_status():
    """获取当前番茄钟状态"""
    return await get_pomodoro_status_action()


@router.get("/pomodoro/stats", response_model=schemas.PomodoroStatsResponse)
async def get_pomodoro_stats():
    """获取番茄钟统计"""
    return await get_pomodoro_stats_action()


@router.get("/pomodoro/history", response_model=schemas.PomodoroHistoryResponse)
async def get_pomodoro_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """获取番茄钟历史"""
    return await get_pomodoro_history_action(page, page_size)


# ============================================================
# 日历视图
# ============================================================

@router.post("/calendar/events")
async def create_calendar_event(request: schemas.CalendarEventCreateRequest):
    """创建日历事件"""
    return await create_calendar_event_action(
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
    return await list_calendar_events_action(start_date, end_date)


@router.delete("/calendar/events/{event_id}")
async def delete_calendar_event(event_id: str):
    """删除日历事件"""
    return await delete_calendar_event_action(event_id)


@router.get("/calendar/view", response_model=schemas.CalendarViewResponse)
async def get_calendar_view(
    year: int = Query(..., description="年份"),
    month: int = Query(..., ge=1, le=12, description="月份"),
):
    """获取月度日历视图"""
    return await get_calendar_view_action(year, month)


# ============================================================
# 批量操作
# ============================================================

@router.post("/tasks/batch-update")
async def batch_update_tasks(request: schemas.BatchTaskUpdateRequest):
    """批量更新任务"""
    return await batch_update_tasks_action(
        task_ids=request.task_ids,
        priority=request.priority.value if request.priority is not None else None,
        due_time=request.due_time,
        tags_add=request.tags_add or [],
        tags_remove=request.tags_remove or [],
    )


@router.get("/tasks/{task_id}/detail", response_model=schemas.TaskDetailResponse)
async def get_task_detail(task_id: str):
    """获取任务聚合详情"""
    result = await get_task_detail_action(task_id)
    return schemas.TaskDetailResponse(**result)
