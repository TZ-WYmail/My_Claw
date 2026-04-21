"""
POST /api/job/status — 异步任务状态查询端点
"""
from fastapi import APIRouter

from models.schemas import JobStatusRequest, JobStatusResponse
from services.download_service import get_job_status

router = APIRouter()


@router.post("/job/status", response_model=JobStatusResponse)
async def handle_job_status(request: JobStatusRequest):
    """查询异步任务状态"""
    job = get_job_status(request.job_id)
    if not job:
        return JobStatusResponse(
            job_id=request.job_id,
            status="not_found",
            message=f"任务 {request.job_id} 不存在或已过期",
        )

    return JobStatusResponse(
        job_id=request.job_id,
        status=job.get("status", "unknown"),
        message=job.get("message"),
        file_path=job.get("file_path"),
        file_size=job.get("file_size"),
        security_scan=job.get("security_scan"),
        duration_seconds=job.get("duration_seconds"),
        result=job,
    )
