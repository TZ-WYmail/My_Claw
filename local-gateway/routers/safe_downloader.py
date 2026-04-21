"""
POST /api/download — 安全下载端点
"""
from fastapi import APIRouter

from models.schemas import SafeDownloaderRequest, SafeDownloaderResponse
from services.download_service import safe_download

router = APIRouter()


@router.post("/download", response_model=SafeDownloaderResponse)
async def handle_download(request: SafeDownloaderRequest):
    """处理安全下载请求"""
    result = await safe_download(
        url=request.url,
        category=request.category.value,
        filename=request.filename,
    )
    return SafeDownloaderResponse(**result)
