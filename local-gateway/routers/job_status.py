"""
POST /api/job/status — 异步任务状态查询端点
"""
from fastapi import APIRouter

from application.ai_tools import execute_local_job_status
from models.schemas import JobStatusRequest, JobStatusResponse

router = APIRouter()


@router.post("/job/status", response_model=JobStatusResponse)
async def handle_job_status(request: JobStatusRequest):
    """查询异步任务状态"""
    result = await execute_local_job_status(request.model_dump())
    return JobStatusResponse(**result)
