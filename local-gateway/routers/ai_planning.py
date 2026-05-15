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
    confirm_task_plan,
    decompose_task,
    estimate_task_time,
    generate_task_plan,
    get_smart_suggestions,
    preview_task_plan,
    replan_tasks,
    replan_tasks_with_acceptance,
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


class PreviewRequest(BaseModel):
    tasks: list[dict] = Field(..., description="任务列表")
    constraints: dict = Field(None, description="约束条件")


class ConfirmPlanRequest(BaseModel):
    preview_id: str = Field(..., description="预览 ID")
    selected_variant: str = Field("balanced", description="选择的方案")
    user_adjustments: dict = Field(None, description="用户调整")


class ReplanRequest(BaseModel):
    tasks: list[dict] = Field(..., description="任务列表")
    constraints: dict = Field(None, description="约束条件")
    interrupt_task: dict = Field(None, description="突发任务")


class ReplanAcceptanceRequest(BaseModel):
    tasks: list[dict] = Field(..., description="任务列表")
    constraints: dict = Field(None, description="约束条件")
    interrupt_task: dict = Field(None, description="突发任务")
    accepted_task_names: list[str] = Field(default_factory=list, description="接受建议的任务名列表")


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


@router.post("/plan/preview")
async def ai_preview_plan(request: PreviewRequest):
    """结构化预览任务计划"""
    return await preview_task_plan(request.tasks, request.constraints)


@router.post("/plan/confirm")
async def ai_confirm_plan(request: ConfirmPlanRequest):
    """确认并创建任务计划"""
    return await confirm_task_plan(
        request.preview_id,
        request.selected_variant,
        request.user_adjustments,
    )


@router.post("/plan/replan")
async def ai_replan(request: ReplanRequest):
    """插入任务或任务变更后的重排"""
    return await replan_tasks(request.tasks, request.constraints, request.interrupt_task)


@router.post("/plan/replan/accept")
async def ai_replan_with_acceptance(request: ReplanAcceptanceRequest):
    """接受部分建议后生成新的重排方案"""
    return await replan_tasks_with_acceptance(
        request.tasks,
        request.constraints,
        request.interrupt_task,
        request.accepted_task_names,
    )


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
