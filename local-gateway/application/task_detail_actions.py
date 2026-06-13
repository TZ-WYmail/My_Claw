"""
Task detail application entrypoints.
"""
from __future__ import annotations

from services import task_command_service
from services import task_detail_service


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
