"""
Task application entrypoints.

This module centralizes task-related use cases so routers and AI tool dispatch
can share the same internal path instead of each coordinating with task
services directly.
"""
from __future__ import annotations

from models.schemas import BatchTaskResponse, TaskManagerRequest, TaskManagerResponse, TaskUpdateRequest
from services import task_command_service
from services import task_planning_service
from services import task_query_service


async def execute_local_task_manager(payload: dict) -> dict:
    request = TaskManagerRequest(**payload)

    if request.action.value == "add_task":
        if not request.task_name:
            return TaskManagerResponse(status="error", message="add_task 需要提供 task_name").model_dump()
        if not request.due_time:
            return TaskManagerResponse(status="error", message="add_task 需要提供 due_time").model_dump()
        result = await task_command_service.add_task(
            task_name=request.task_name,
            due_time=request.due_time,
            recurrence=request.recurrence.value if request.recurrence else "once",
            priority=request.priority.value if request.priority else 2,
            description=request.description,
            estimated_minutes=request.estimated_minutes,
            tags=request.tags,
            start_time=request.start_time,
            end_time=request.end_time,
        )
    elif request.action.value == "delete_task":
        if not request.task_id:
            return TaskManagerResponse(status="error", message="delete_task 需要提供 task_id").model_dump()
        result = await task_command_service.delete_task(request.task_id)
    elif request.action.value == "complete_task":
        if not request.task_id:
            return TaskManagerResponse(status="error", message="complete_task 需要提供 task_id").model_dump()
        result = await task_command_service.complete_task(request.task_id)
    elif request.action.value == "batch_complete":
        if not request.task_ids:
            return TaskManagerResponse(status="error", message="batch_complete 需要提供 task_ids").model_dump()
        result = await task_command_service.batch_complete_tasks(request.task_ids)
    elif request.action.value == "batch_delete":
        if not request.task_ids:
            return TaskManagerResponse(status="error", message="batch_delete 需要提供 task_ids").model_dump()
        result = await task_command_service.batch_delete_tasks(request.task_ids)
    elif request.action.value == "get_weekly_plan":
        monday = request.due_time or ""
        sunday = request.task_name or ""
        result = await task_query_service.get_weekly_plan(monday, sunday)
    elif request.action.value == "get_pending_tasks":
        result = await task_query_service.get_pending_tasks(today_only=bool(request.today_only))
    else:
        result = {"status": "error", "message": f"未知操作: {request.action}"}

    return TaskManagerResponse(**result).model_dump()


async def execute_batch_task_manager(payload: dict) -> dict:
    action = payload.get("action")
    tasks = payload.get("tasks", [])
    task_dicts = [
        {
            "task_name": task.get("task_name"),
            "due_time": task.get("due_time"),
            "recurrence": task.get("recurrence", "once"),
            "priority": task.get("priority", 2),
            "description": task.get("description"),
            "estimated_minutes": task.get("estimated_minutes"),
            "start_time": task.get("start_time"),
            "end_time": task.get("end_time"),
        }
        for task in tasks
    ]

    if action == "preview":
        result = await task_planning_service.analyze_tasks(task_dicts)
    elif action == "create":
        analyzed = await task_planning_service.analyze_tasks(task_dicts)
        valid_tasks = [
            {
                "task_name": item["task_name"],
                "due_time": item["due_time"],
                "recurrence": item["recurrence"],
                "priority": item.get("priority", 2),
                "description": item.get("description"),
                "estimated_minutes": item.get("estimated_minutes"),
                "start_time": item.get("start_time"),
                "end_time": item.get("end_time"),
            }
            for item in analyzed["analyzed"]
            if item["time_valid"]
        ]
        result = await task_command_service.batch_add_tasks(valid_tasks)
        result["timeline"] = analyzed.get("timeline", [])
        result["daily_timeline"] = analyzed.get("daily_timeline", [])
    else:
        result = {"status": "error", "message": f"未知操作: {action}"}

    return BatchTaskResponse(**result).model_dump()


async def update_task_action(task_id: str, payload: dict) -> dict:
    request = TaskUpdateRequest(**payload)
    return await task_command_service.update_task(
        task_id=task_id,
        task_name=request.task_name,
        due_time=request.due_time,
        recurrence=request.recurrence.value if request.recurrence else None,
        priority=request.priority.value if request.priority is not None else None,
        description=request.description,
        estimated_minutes=request.estimated_minutes,
        start_time=request.start_time,
        end_time=request.end_time,
        tags=request.tags,
    )
