"""
统一搜索主路由
POST /api/search — 统一搜索（文件 + 任务 + 笔记 + 习惯）
"""
from fastapi import APIRouter

from application.ai_tools import execute_local_file_search
from models.schemas import UnifiedSearchRequest, UnifiedSearchResponse

router = APIRouter(prefix="/search", tags=["search"])


@router.post("", response_model=UnifiedSearchResponse)
async def handle_unified_search(request: UnifiedSearchRequest):
    """统一搜索：文件 + 任务 + 笔记 + 习惯"""
    result = await execute_local_file_search(request.model_dump())
    return UnifiedSearchResponse(**result)
