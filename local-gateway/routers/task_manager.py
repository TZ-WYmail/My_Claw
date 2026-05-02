"""
POST /api/task — 任务管理端点
POST /api/task/batch — 批量任务编排（预览/创建）
"""
from fastapi import APIRouter

from models.schemas import TaskManagerRequest, TaskManagerResponse, BatchTaskRequest, BatchTaskResponse
from services import task_service

router = APIRouter()


@router.post("/task", response_model=TaskManagerResponse)
async def handle_task(request: TaskManagerRequest):
    """处理任务管理请求"""
    if request.action.value == "add_task":
        if not request.task_name:
            return TaskManagerResponse(
                status="error",
                message="add_task 需要提供 task_name",
            )
        if not request.due_time:
            return TaskManagerResponse(
                status="error",
                message="add_task 需要提供 due_time",
            )
        result = await task_service.add_task(
            task_name=request.task_name,
            due_time=request.due_time,
            recurrence=request.recurrence.value if request.recurrence else "once",
            priority=request.priority.value if request.priority else 2,
            description=request.description,
            estimated_minutes=request.estimated_minutes,
            tags=request.tags,
        )

    elif request.action.value == "delete_task":
        if not request.task_id:
            return TaskManagerResponse(
                status="error",
                message="delete_task 需要提供 task_id",
            )
        result = await task_service.delete_task(request.task_id)

    elif request.action.value == "complete_task":
        if not request.task_id:
            return TaskManagerResponse(
                status="error",
                message="complete_task 需要提供 task_id",
            )
        result = await task_service.complete_task(request.task_id)

    elif request.action.value == "batch_complete":
        if not request.task_ids:
            return TaskManagerResponse(
                status="error",
                message="batch_complete 需要提供 task_ids",
            )
        result = await task_service.batch_complete_tasks(request.task_ids)

    elif request.action.value == "batch_delete":
        if not request.task_ids:
            return TaskManagerResponse(
                status="error",
                message="batch_delete 需要提供 task_ids",
            )
        result = await task_service.batch_delete_tasks(request.task_ids)

    elif request.action.value == "get_weekly_plan":
        # 支持传入日期范围（前端日历导航用）
        monday = request.due_time or ""
        sunday = request.task_name or ""  # 复用字段传 sunday
        result = await task_service.get_weekly_plan(monday, sunday)

    else:
        result = {"status": "error", "message": f"未知操作: {request.action}"}

    return TaskManagerResponse(**result)


@router.post("/task/batch", response_model=BatchTaskResponse)
async def handle_batch_task(request: BatchTaskRequest):
    """
    批量任务编排。
    action='preview': 仅解析分析，不写入数据库（供用户预览确认）
    action='create': 批量写入数据库
    """
    task_dicts = [
        {
            "task_name": t.task_name,
            "due_time": t.due_time,
            "recurrence": t.recurrence,
            "priority": getattr(t, 'priority', 2),
            "description": getattr(t, 'description', None),
            "estimated_minutes": getattr(t, 'estimated_minutes', None),
        }
        for t in request.tasks
    ]

    if request.action == "preview":
        result = await task_service.analyze_tasks(task_dicts)
    elif request.action == "create":
        # 先解析标准化时间
        analyzed = await task_service.analyze_tasks(task_dicts)
        # 只创建时间有效的任务
        valid_tasks = [
            {
                "task_name": a["task_name"],
                "due_time": a["due_time"],
                "recurrence": a["recurrence"],
                "priority": a.get("priority", 2),
                "description": a.get("description"),
                "estimated_minutes": a.get("estimated_minutes"),
            }
            for a in analyzed["analyzed"]
            if a["time_valid"]
        ]
        result = await task_service.batch_add_tasks(valid_tasks)
        result["timeline"] = analyzed.get("timeline", [])
        result["daily_timeline"] = analyzed.get("daily_timeline", [])
    else:
        result = {"status": "error", "message": f"未知操作: {request.action}"}

    return BatchTaskResponse(**result)
