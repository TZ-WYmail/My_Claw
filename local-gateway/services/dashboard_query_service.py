"""
Dashboard query service.

This module owns dashboard/history/log queries that are not core task read-side
behavior, so `task_query_service` can shrink toward task-domain queries.
"""
from __future__ import annotations

import asyncio

import aiosqlite

from config import DB_PATH
from services.streak_service import get_streak_info
from services.utils import human_size


async def get_download_history(
    category: str = "",
    page: int = 1,
    page_size: int = 20,
) -> dict:
    conditions = []
    params = []

    if category and category != "all":
        conditions.append("category = ?")
        params.append(category)

    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

    async with aiosqlite.connect(str(DB_PATH)) as db:
        cursor = await db.execute(
            f"SELECT COUNT(*) FROM download_history {where_clause}",
            params,
        )
        total = (await cursor.fetchone())[0]

        offset = (page - 1) * page_size
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            f"""
            SELECT id, url, filename, category, file_path, file_size, security_scan, status, job_id, created_at
            FROM download_history {where_clause}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            params + [page_size, offset],
        )
        rows = await cursor.fetchall()

    return {
        "status": "success",
        "records": [dict(row) for row in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


async def get_logs(
    page: int = 1,
    page_size: int = 50,
    operation: str = "",
) -> dict:
    conditions = []
    params = []

    if operation:
        conditions.append("operation = ?")
        params.append(operation)

    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

    async with aiosqlite.connect(str(DB_PATH)) as db:
        cursor = await db.execute(
            f"SELECT COUNT(*) FROM operation_logs {where_clause}",
            params,
        )
        total = (await cursor.fetchone())[0]

        offset = (page - 1) * page_size
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            f"""
            SELECT id, operation, endpoint, params, result, detail, created_at
            FROM operation_logs {where_clause}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            params + [page_size, offset],
        )
        rows = await cursor.fetchall()

    return {
        "status": "success",
        "logs": [dict(row) for row in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


async def get_dashboard_stats() -> dict:
    async with aiosqlite.connect(str(DB_PATH)) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM tasks WHERE status != 'deleted'")
        tasks_active = (await cursor.fetchone())[0]

        cursor = await db.execute("SELECT COUNT(*) FROM tasks WHERE status = 'pending'")
        tasks_pending = (await cursor.fetchone())[0]

        cursor = await db.execute("SELECT COUNT(*) FROM tasks WHERE status = 'completed'")
        tasks_completed = (await cursor.fetchone())[0]

        cursor = await db.execute("SELECT COUNT(*) FROM download_history")
        downloads_total = (await cursor.fetchone())[0]

        cursor = await db.execute("SELECT COUNT(*) FROM download_history WHERE status = 'completed'")
        downloads_completed = (await cursor.fetchone())[0]

        total_size, file_count = await asyncio.to_thread(_calc_disk_stats)

        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT operation, endpoint, result, created_at FROM operation_logs ORDER BY created_at DESC LIMIT 10"
        )
        recent_logs = [dict(row) for row in await cursor.fetchall()]

        cursor = await db.execute(
            "SELECT filename, category, file_size, security_scan, status, created_at FROM download_history ORDER BY created_at DESC LIMIT 5"
        )
        recent_downloads = [dict(row) for row in await cursor.fetchall()]

    streak_info = await get_streak_info()

    return {
        "status": "success",
        "tasks": {"active": tasks_active, "pending": tasks_pending, "completed": tasks_completed},
        "downloads": {"total": downloads_total, "completed": downloads_completed},
        "storage": {
            "total_size": human_size(total_size),
            "total_size_bytes": total_size,
            "file_count": file_count,
        },
        "recent_logs": recent_logs,
        "recent_downloads": recent_downloads,
        "streak": streak_info,
    }


def _calc_disk_stats():
    from config import DOWNLOADS_DIR

    total_size = 0
    file_count = 0
    if DOWNLOADS_DIR.exists():
        for file_path in DOWNLOADS_DIR.rglob("*"):
            if file_path.is_file():
                total_size += file_path.stat().st_size
                file_count += 1
    return total_size, file_count
