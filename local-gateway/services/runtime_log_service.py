"""
Runtime log service.

This module owns lightweight runtime write-side records such as download
history and operation logs so `task_service` does not keep unrelated helpers.
"""
from __future__ import annotations

import logging

import aiosqlite

from config import DB_PATH
from services.security_service import validate_update_columns

logger = logging.getLogger(__name__)


async def add_download_record(
    url: str,
    category: str,
    filename: str = "",
    file_path: str = "",
    file_size: str = "",
    security_scan: str = "pending",
    status: str = "downloading",
    job_id: str = "",
) -> int:
    async with aiosqlite.connect(str(DB_PATH)) as db:
        cursor = await db.execute(
            """INSERT INTO download_history (url, filename, category, file_path, file_size, security_scan, status, job_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (url, filename, category, file_path, file_size, security_scan, status, job_id),
        )
        await db.commit()
        return cursor.lastrowid


async def update_download_record(record_id: int, **kwargs):
    valid, invalid = validate_update_columns("download_history", set(kwargs.keys()))
    if not valid:
        logger.warning(f"update_download_record 拒绝非法列名: {invalid}")
        return

    sets = []
    vals = []
    for key, value in kwargs.items():
        sets.append(f"{key} = ?")
        vals.append(value)
    if not sets:
        return
    vals.append(record_id)
    async with aiosqlite.connect(str(DB_PATH)) as db:
        await db.execute(
            f"UPDATE download_history SET {', '.join(sets)} WHERE id = ?",
            vals,
        )
        await db.commit()


async def add_log(
    operation: str,
    endpoint: str,
    params: str = "",
    result: str = "success",
    detail: str = "",
):
    async with aiosqlite.connect(str(DB_PATH)) as db:
        await db.execute(
            """INSERT INTO operation_logs (operation, endpoint, params, result, detail)
               VALUES (?, ?, ?, ?, ?)""",
            (operation, endpoint, params, result, detail),
        )
        await db.commit()
