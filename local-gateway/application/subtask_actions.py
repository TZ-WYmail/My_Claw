"""
Subtask application entrypoints.
"""
from __future__ import annotations

from services import subtask_service


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
