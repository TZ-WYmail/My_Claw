from fastapi import APIRouter

from application.task_detail_actions import batch_update_tasks_action, get_task_detail_action
from models import schemas

router = APIRouter(tags=["task_detail"])


@router.post("/tasks/batch-update")
async def batch_update_tasks(request: schemas.BatchTaskUpdateRequest):
    return await batch_update_tasks_action(
        task_ids=request.task_ids,
        priority=request.priority.value if request.priority is not None else None,
        due_time=request.due_time,
        tags_add=request.tags_add or [],
        tags_remove=request.tags_remove or [],
    )


@router.get("/tasks/{task_id}/detail", response_model=schemas.TaskDetailResponse)
async def get_task_detail(task_id: str):
    result = await get_task_detail_action(task_id)
    return schemas.TaskDetailResponse(**result)
