"""
统一搜索端点
POST   /api/search            — 统一搜索（文件 + 任务 + 笔记 + 习惯）
POST   /api/search/legacy     — 旧文件搜索端点（兼容）
GET    /api/search/fulltext   — 全文搜索
POST   /api/search/index      — 构建索引
GET    /api/search/index/stats — 索引统计
POST   /api/search/index/rebuild — 重建索引
"""
from fastapi import APIRouter, Query

from models.schemas import FileSearchRequest, FileSearchResponse, UnifiedSearchRequest, UnifiedSearchResponse
from services.unified_search_service import (
    get_index_stats,
    index_all_files,
    rebuild_index,
    search_fulltext,
    unified_search,
)

router = APIRouter(prefix="/search", tags=["search"])


@router.post("", response_model=UnifiedSearchResponse)
async def handle_unified_search(request: UnifiedSearchRequest):
    """统一搜索：文件 + 任务 + 笔记 + 习惯"""
    result = await unified_search(
        keyword=request.keyword,
        scope=request.scope.value,
        category=request.category or "all",
        page=request.page,
        page_size=request.page_size,
    )
    files = result.get("results", {}).get("files", {})
    tasks = result.get("results", {}).get("tasks", {})
    notes = result.get("results", {}).get("notes", {})
    habits = result.get("results", {}).get("habits", {})
    return UnifiedSearchResponse(
        **result,
        files=files.get("items", []),
        tasks=tasks.get("items", []),
        notes=notes.get("items", []),
        habits=habits.get("items", []),
    )


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


@router.get("/fulltext")
async def fulltext_search_endpoint(
    q: str = Query(..., description="搜索关键词"),
    category: str = Query(None, description="分类筛选"),
    top_k: int = Query(20, ge=1, le=100),
):
    """全文搜索下载的文件内容"""
    return await search_fulltext(q, category, top_k)


@router.post("/index")
async def build_index(category: str = Query(None, description="指定分类索引")):
    """构建/更新搜索索引"""
    return await index_all_files(category)


@router.get("/index/stats")
async def index_statistics():
    """获取索引统计"""
    return await get_index_stats()


@router.post("/index/rebuild")
async def rebuild_search_index():
    """重建搜索索引"""
    return await rebuild_index()
