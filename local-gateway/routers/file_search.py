"""
旧文件搜索兼容端点
POST /api/search/legacy — 旧文件搜索端点（兼容）
"""
from fastapi import APIRouter

from models.schemas import FileSearchRequest, FileSearchResponse
from services.unified_search_service import unified_search

router = APIRouter(prefix="/search", tags=["search_legacy"])


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
