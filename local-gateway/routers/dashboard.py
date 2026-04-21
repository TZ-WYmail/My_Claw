"""
GET /api/dashboard — 仪表盘统计数据
GET /api/download/history — 下载历史
GET /api/logs — 操作日志
"""
from fastapi import APIRouter, Query

from models.schemas import (
    AllTasksResponse,
    DashboardResponse,
    DownloadHistoryResponse,
    LogsResponse,
)
from services import task_service

router = APIRouter()


@router.get("/dashboard", response_model=DashboardResponse)
async def dashboard():
    """仪表盘统计数据"""
    result = await task_service.get_dashboard_stats()
    return DashboardResponse(**result)


@router.get("/download/history", response_model=DownloadHistoryResponse)
async def download_history(
    category: str = Query("", description="分类筛选"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """下载历史记录"""
    result = await task_service.get_download_history(
        category=category, page=page, page_size=page_size,
    )
    return DownloadHistoryResponse(**result)


@router.get("/logs", response_model=LogsResponse)
async def logs(
    operation: str = Query("", description="操作类型筛选"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """操作日志"""
    result = await task_service.get_logs(
        page=page, page_size=page_size, operation=operation,
    )
    return LogsResponse(**result)


@router.get("/tasks/all", response_model=AllTasksResponse)
async def all_tasks(
    status: str = Query("active", description="状态筛选: active/pending/completed/deleted"),
    keyword: str = Query("", description="搜索关键词"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """全部任务（带筛选和分页）"""
    result = await task_service.get_all_tasks(
        status_filter=status, keyword=keyword, page=page, page_size=page_size,
    )
    return AllTasksResponse(**result)
