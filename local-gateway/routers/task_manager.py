"""
POST /api/task — 任务管理端点
POST /api/task/batch — 批量任务编排（预览/创建）
"""
from fastapi import APIRouter

from application.task_actions import (
    execute_batch_task_manager,
    execute_local_task_manager,
    update_task_action,
)
from models.schemas import TaskManagerRequest, TaskManagerResponse, BatchTaskRequest, BatchTaskResponse, TaskUpdateRequest

router = APIRouter()


@router.post("/task", response_model=TaskManagerResponse)
async def handle_task(request: TaskManagerRequest):
    """处理任务管理请求"""
    result = await execute_local_task_manager(request.model_dump())
    return TaskManagerResponse(**result)


@router.put("/task/{task_id}")
async def update_task(task_id: str, request: TaskUpdateRequest):
    """更新单个任务"""
    return await update_task_action(task_id, request.model_dump())


@router.post("/task/batch", response_model=BatchTaskResponse)
async def handle_batch_task(request: BatchTaskRequest):
    """
    批量任务编排。
    action='preview': 仅解析分析，不写入数据库（供用户预览确认）
    action='create': 批量写入数据库
    """
    result = await execute_batch_task_manager(request.model_dump())
    return BatchTaskResponse(**result)
