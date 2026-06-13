"""
统一搜索端点
POST   /api/search            — 统一搜索（文件 + 任务 + 笔记 + 习惯）
POST   /api/search/legacy     — 旧文件搜索端点（兼容）
"""
from fastapi import APIRouter

from application.ai_tools import execute_local_file_search
from models.schemas import FileSearchRequest, FileSearchResponse, UnifiedSearchRequest, UnifiedSearchResponse
from services.unified_search_service import unified_search

router = APIRouter(prefix="/search", tags=["search"])


@router.post("", response_model=UnifiedSearchResponse)
async def handle_unified_search(request: UnifiedSearchRequest):
    """统一搜索：文件 + 任务 + 笔记 + 习惯"""
    result = await execute_local_file_search(request.model_dump())
    return UnifiedSearchResponse(**result)


@router.post("/legacy", response_model=FileSearchResponse)
async def handle_legacy_search(request: FileSearchRequest):
    """旧文件搜索端点（兼容）"""
    result = await unified_search(
        keyword=request.keyword,
        scope="files",
        category=request.category.value,
    )
    files = result.get("results", {}).get("files", {})
    return FileSearchResponse(
        status="success",
        total=files.get("total", 0),
        files=files.get("items", []),
    )
