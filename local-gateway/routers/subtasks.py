from fastapi import APIRouter

from application.subtask_actions import (
    create_subtask_action,
    delete_subtask_action,
    list_subtasks_action,
    update_subtask_action,
)
from models import schemas

router = APIRouter(tags=["subtasks"])


@router.post("/subtasks", response_model=schemas.SubtaskListResponse)
async def create_subtask(request: schemas.SubtaskCreateRequest):
    return await create_subtask_action(request.task_id, request.name)


@router.get("/tasks/{task_id}/subtasks", response_model=schemas.SubtaskListResponse)
async def list_subtasks(task_id: str):
    return await list_subtasks_action(task_id)


@router.put("/subtasks/{subtask_id}")
async def update_subtask(subtask_id: str, request: schemas.SubtaskUpdateRequest):
    return await update_subtask_action(subtask_id, request.name, request.status)


@router.delete("/subtasks/{subtask_id}")
async def delete_subtask(subtask_id: str):
    return await delete_subtask_action(subtask_id)
