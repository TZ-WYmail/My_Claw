"""
Tag application entrypoints.
"""
from __future__ import annotations

from services import tag_service


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
