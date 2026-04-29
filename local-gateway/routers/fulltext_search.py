"""
全文检索路由
GET  /api/search/fulltext — 全文搜索
POST /api/search/index — 构建索引
GET  /api/search/index/stats — 索引统计
POST /api/search/index/rebuild — 重建索引
"""
from fastapi import APIRouter, Query

from services.fulltext_search_service import (
    get_index_stats,
    index_all_files,
    rebuild_index,
    search_fulltext,
)

router = APIRouter(prefix="/search", tags=["fulltext_search"])


@router.get("/fulltext")
async def fulltext_search(
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
    """重建搜索索引（清空后重新构建）"""
    return await rebuild_index()
