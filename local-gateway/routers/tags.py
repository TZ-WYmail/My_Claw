from fastapi import APIRouter

from application.tag_actions import (
    add_task_tags_action,
    create_tag_action,
    delete_tag_action,
    list_tags_action,
    remove_task_tags_action,
)
from models import schemas

router = APIRouter(tags=["tags"])


@router.post("/tags", response_model=schemas.TagListResponse)
async def create_tag(request: schemas.TagCreateRequest):
    return await create_tag_action(request.name, request.color)


@router.get("/tags", response_model=schemas.TagListResponse)
async def list_tags():
    return await list_tags_action()


@router.delete("/tags/{tag_id}")
async def delete_tag(tag_id: int):
    return await delete_tag_action(tag_id)


@router.post("/tasks/{task_id}/tags")
async def add_task_tags(task_id: str, tags: list[str]):
    return await add_task_tags_action(task_id, tags)


@router.delete("/tasks/{task_id}/tags")
async def remove_task_tags(task_id: str, tags: list[str]):
    return await remove_task_tags_action(task_id, tags)
