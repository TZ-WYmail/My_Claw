"""
AI 智能规划路由
POST /api/ai/decompose — 任务拆解
POST /api/ai/plan — 生成计划
POST /api/ai/estimate — 时间估算
GET  /api/ai/suggestions — 智能建议
GET  /api/ai/insights — 效率洞察
"""
from fastapi import APIRouter

from models.schemas import BaseModel, Field
from services.ai_planning_service import (
    analyze_task_patterns,
    decompose_task,
    estimate_task_time,
    generate_task_plan,
    get_smart_suggestions,
)

router = APIRouter(prefix="/ai", tags=["ai_planning"])


class DecomposeRequest(BaseModel):
    task_name: str = Field(..., description="任务名称")
    description: str = Field(None, description="任务描述")


class DecomposeResponse(BaseModel):
    status: str
    decomposition: dict = None
    message: str = None


class PlanRequest(BaseModel):
    tasks: list[dict] = Field(..., description="任务列表")
    constraints: dict = Field(None, description="约束条件")


class EstimateRequest(BaseModel):
    task_name: str = Field(..., description="任务名称")
    description: str = Field(None, description="任务描述")
    category: str = Field(None, description="任务类别")


@router.post("/decompose", response_model=DecomposeResponse)
async def ai_decompose_task(request: DecomposeRequest):
    """AI任务拆解 - 将复杂任务分解为子任务"""
    result = await decompose_task(request.task_name, request.description)
    return result


@router.post("/plan")
async def ai_generate_plan(request: PlanRequest):
    """AI生成任务计划 - 基于约束条件优化安排"""
    result = await generate_task_plan(request.tasks, request.constraints)
    return result


@router.post("/estimate")
async def ai_estimate_time(request: EstimateRequest):
    """AI时间估算 - 智能预估任务完成时间"""
    result = await estimate_task_time(
        request.task_name,
        request.description,
        request.category,
    )
    return result


@router.get("/suggestions")
async def ai_suggestions():
    """智能建议 - 基于当前任务状态提供建议"""
    result = await get_smart_suggestions()
    return result


@router.get("/insights")
async def ai_insights():
    """效率洞察 - 分析任务完成模式"""
    result = await analyze_task_patterns()
    return result
