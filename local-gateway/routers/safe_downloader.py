"""
POST /api/download — 安全下载端点
GET  /api/download/queue — 下载队列状态
POST /api/download/queue — 添加到下载队列
POST /api/download/pause — 暂停下载
POST /api/download/resume — 恢复下载
POST /api/download/cancel — 取消下载
"""
from fastapi import APIRouter, Query

from models.schemas import SafeDownloaderRequest, SafeDownloaderResponse
from services.download_service import (
    add_to_queue,
    cancel_download,
    get_bandwidth_limit,
    get_queue_status,
    pause_download,
    resume_download,
    safe_download,
    set_bandwidth_limit,
)

router = APIRouter()


@router.post("/download", response_model=SafeDownloaderResponse)
async def handle_download(request: SafeDownloaderRequest):
    """处理安全下载请求（大文件自动走队列）"""
    result = await safe_download(
        url=request.url,
        category=request.category.value,
        filename=request.filename,
    )
    return SafeDownloaderResponse(**result)


@router.get("/download/queue")
async def get_download_queue():
    """获取下载队列状态"""
    return get_queue_status()


@router.post("/download/queue")
async def add_download_to_queue(
    url: str,
    category: str,
    filename: str = None,
    priority: int = Query(5, ge=1, le=10),
):
    """添加下载到队列（priority: 1-10，数字越小优先级越高）"""
    result = await add_to_queue(url, category, filename, priority)
    return result


@router.post("/download/pause/{job_id}")
async def pause_download_job(job_id: str):
    """暂停下载"""
    return await pause_download(job_id)


@router.post("/download/resume/{job_id}")
async def resume_download_job(job_id: str):
    """恢复下载"""
    return await resume_download(job_id)


@router.post("/download/cancel/{job_id}")
async def cancel_download_job(job_id: str):
    """取消下载"""
    return await cancel_download(job_id)


@router.get("/download/bandwidth")
async def get_download_bandwidth():
    """获取当前带宽限制"""
    return get_bandwidth_limit()


@router.post("/download/bandwidth")
async def set_download_bandwidth(kb_per_second: int = Query(..., ge=0)):
    """设置带宽限制 (KB/s), 0 表示无限制"""
    return set_bandwidth_limit(kb_per_second)
