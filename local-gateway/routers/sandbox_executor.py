"""
POST /api/sandbox — 沙盒执行端点
"""
from fastapi import APIRouter

from application.ai_tools import execute_local_sandbox_executor
from models.schemas import SandboxExecutorRequest, SandboxExecutorResponse

router = APIRouter()


@router.post("/sandbox", response_model=SandboxExecutorResponse)
async def handle_sandbox(request: SandboxExecutorRequest):
    """处理沙盒执行请求"""
    result = await execute_local_sandbox_executor(request.model_dump())
    return SandboxExecutorResponse(**result)
