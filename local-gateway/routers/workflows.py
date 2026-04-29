"""
工作流路由 — 自动化工作流管理
"""
from fastapi import APIRouter, Query

from models.schemas import BaseModel, Field
from services.workflow_service import (
    ACTION_TYPES,
    TRIGGER_TYPES,
    workflow_engine,
)

router = APIRouter(prefix="/workflows", tags=["workflows"])


class WorkflowCreateRequest(BaseModel):
    name: str = Field(..., description="工作流名称")
    description: str = Field("", description="工作流描述")
    trigger: dict = Field(..., description="触发器配置")
    actions: list[dict] = Field(..., description="动作列表")
    enabled: bool = Field(True, description="是否启用")


class WorkflowTriggerRequest(BaseModel):
    context: dict = Field({}, description="上下文数据")


@router.get("/")
async def list_workflows():
    """获取所有工作流"""
    return workflow_engine.get()


@router.post("/")
async def create_workflow(request: WorkflowCreateRequest):
    """创建工作流"""
    return workflow_engine.create(
        name=request.name,
        trigger=request.trigger,
        actions=request.actions,
        description=request.description,
        enabled=request.enabled,
    )


@router.get("/{workflow_id}")
async def get_workflow(workflow_id: str):
    """获取工作流详情"""
    return workflow_engine.get(workflow_id)


@router.delete("/{workflow_id}")
async def delete_workflow(workflow_id: str):
    """删除工作流"""
    return workflow_engine.delete(workflow_id)


@router.post("/{workflow_id}/toggle")
async def toggle_workflow(
    workflow_id: str,
    enabled: bool = Query(..., description="启用/禁用"),
):
    """启用/禁用工作流"""
    return workflow_engine.toggle(workflow_id, enabled)


@router.post("/{workflow_id}/execute")
async def execute_workflow(
    workflow_id: str,
    request: WorkflowTriggerRequest,
):
    """手动执行工作流"""
    return await workflow_engine.execute(workflow_id, request.context)


@router.get("/{workflow_id}/executions")
async def get_workflow_executions(
    workflow_id: str,
    limit: int = Query(50, ge=1, le=100),
):
    """获取工作流执行记录"""
    return workflow_engine.get_executions(workflow_id, limit)


@router.get("/types/triggers")
async def list_trigger_types():
    """获取支持的触发器类型"""
    return {
        "status": "success",
        "types": TRIGGER_TYPES,
    }


@router.get("/types/actions")
async def list_action_types():
    """获取支持的动作类型"""
    return {
        "status": "success",
        "types": ACTION_TYPES,
    }


@router.post("/trigger/{trigger_type}")
async def trigger_workflows(
    trigger_type: str,
    context: dict = {},
):
    """
    触发指定类型的工作流

    用于手动触发或通过 Webhook 触发
    """
    results = await workflow_engine.trigger(trigger_type, context)
    return {
        "status": "success",
        "triggered": len(results),
        "results": results,
    }
