"""
Dashboard application entrypoints.

This module centralizes dashboard-oriented query use cases so routers remain
transport-only and future internal callers can reuse the same query path.
"""
from __future__ import annotations

from services import task_query_service
from services.streak_service import get_streak_info


async def get_dashboard_action() -> dict:
    return await task_query_service.get_dashboard_stats()


async def get_download_history_action(
    category: str = "",
    page: int = 1,
    page_size: int = 20,
) -> dict:
    return await task_query_service.get_download_history(
        category=category,
        page=page,
        page_size=page_size,
    )


async def get_logs_action(
    operation: str = "",
    page: int = 1,
    page_size: int = 50,
) -> dict:
    return await task_query_service.get_logs(
        page=page,
        page_size=page_size,
        operation=operation,
    )


async def get_all_tasks_action(
    status: str = "active",
    keyword: str = "",
    tag: str = "",
    priority: int | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    return await task_query_service.get_all_tasks(
        status_filter=status,
        keyword=keyword,
        tag=tag,
        priority=priority,
        page=page,
        page_size=page_size,
    )


async def get_streak_action() -> dict:
    info = await get_streak_info()
    return {"status": "success", **info}
