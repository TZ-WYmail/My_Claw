"""
POST /api/sandbox — 沙盒执行端点
"""
from fastapi import APIRouter

from models.schemas import SandboxExecutorRequest, SandboxExecutorResponse
from services.sandbox_service import execute_in_sandbox

router = APIRouter()


@router.post("/sandbox", response_model=SandboxExecutorResponse)
async def handle_sandbox(request: SandboxExecutorRequest):
    """处理沙盒执行请求"""
    result = await execute_in_sandbox(
        tool_name=request.tool_name.value,
        execution_command=request.execution_command,
        setup_commands=request.setup_commands,
        dynamic_files=request.dynamic_files,
        input_files=request.input_files,
    )
    return SandboxExecutorResponse(**result)
