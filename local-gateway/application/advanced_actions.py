"""
Advanced feature application entrypoints.

This module centralizes orchestration for tags, subtasks, pomodoro, calendar,
and advanced task actions so the router remains transport-only.
"""
from __future__ import annotations

from services import calendar_sync_service
from services import pomodoro_service
from services import subtask_service
from services import tag_service
from services import task_command_service
from services import task_detail_service


async def create_tag_action(name: str, color: str) -> dict:
    result = await tag_service.create_tag(name, color)
    if result["status"] == "success":
        return {"status": "success", "tags": await tag_service.get_all_tags()}
    return {"status": "error", "tags": []}


async def list_tags_action() -> dict:
    return {"status": "success", "tags": await tag_service.get_all_tags()}


async def delete_tag_action(tag_id: int) -> dict:
    return await tag_service.delete_tag(tag_id)


async def add_task_tags_action(task_id: str, tags: list[str]) -> dict:
    return await tag_service.add_task_tags(task_id, tags)


async def remove_task_tags_action(task_id: str, tags: list[str]) -> dict:
    return await tag_service.remove_task_tags(task_id, tags)


async def create_subtask_action(task_id: str, name: str) -> dict:
    result = await subtask_service.create_subtask(task_id, name)
    if result["status"] == "success":
        return {"status": "success", "subtasks": await subtask_service.get_subtasks(task_id)}
    return {"status": "error", "subtasks": []}


async def list_subtasks_action(task_id: str) -> dict:
    return {"status": "success", "subtasks": await subtask_service.get_subtasks(task_id)}


async def update_subtask_action(subtask_id: str, name: str, status: str) -> dict:
    return await subtask_service.update_subtask(subtask_id, name, status)


async def delete_subtask_action(subtask_id: str) -> dict:
    return await subtask_service.delete_subtask(subtask_id)


async def start_pomodoro_action(task_id: str, duration_minutes: int) -> dict:
    result = await pomodoro_service.start_pomodoro(task_id, duration_minutes)
    if result["status"] == "success":
        return {"status": "success", "active_session": await pomodoro_service.get_active_pomodoro()}
    return {"status": "error", "message": result.get("message")}


async def complete_pomodoro_action() -> dict:
    return await pomodoro_service.complete_pomodoro()


async def interrupt_pomodoro_action(reason: str) -> dict:
    return await pomodoro_service.interrupt_pomodoro(reason)


async def get_pomodoro_status_action() -> dict:
    return {"status": "success", "active_session": await pomodoro_service.get_active_pomodoro()}


async def get_pomodoro_stats_action() -> dict:
    return await pomodoro_service.get_pomodoro_stats()


async def get_pomodoro_history_action(page: int = 1, page_size: int = 20) -> dict:
    return await pomodoro_service.get_pomodoro_history(page, page_size)


async def create_calendar_event_action(
    title: str,
    start_time: str,
    end_time: str,
    description: str | None = None,
    event_type: str = "meeting",
    color: str | None = None,
) -> dict:
    return await calendar_sync_service.create_calendar_event(
        title,
        start_time,
        end_time,
        description,
        event_type,
        color,
    )


async def list_calendar_events_action(start_date: str, end_date: str) -> dict:
    events = await calendar_sync_service.get_calendar_events(start_date, end_date)
    return {"status": "success", "events": events}


async def delete_calendar_event_action(event_id: str) -> dict:
    return await calendar_sync_service.delete_calendar_event(event_id)


async def get_calendar_view_action(year: int, month: int) -> dict:
    return await calendar_sync_service.get_calendar_view(year, month)


async def batch_update_tasks_action(
    task_ids: list[str],
    priority: int | None = None,
    due_time: str | None = None,
    tags_add: list[str] | None = None,
    tags_remove: list[str] | None = None,
) -> dict:
    return await task_command_service.batch_update_tasks(
        task_ids=task_ids,
        priority=priority,
        due_time=due_time,
        tags_add=tags_add or [],
        tags_remove=tags_remove or [],
    )


async def get_task_detail_action(task_id: str) -> dict:
    return await task_detail_service.get_task_detail(task_id)
