"""
POST /api/search — 文件检索端点
"""
from fastapi import APIRouter

from models.schemas import FileSearchRequest, FileSearchResponse
from services.search_service import search_files

router = APIRouter()


@router.post("/search", response_model=FileSearchResponse)
async def handle_search(request: FileSearchRequest):
    """处理文件检索请求"""
    result = search_files(
        keyword=request.keyword,
        category=request.category.value,
    )
    return FileSearchResponse(**result)
