"""
Runtime state service.

This module centralizes lightweight runtime/persistence operations previously
handled inside routers, including sync device state, offline queue, and push
token storage.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

import aiosqlite

from config import DB_PATH


async def enqueue_offline_operation(
    operation: str = "unknown",
    table_name: Optional[str] = None,
    record_id: Optional[str] = None,
    data: Optional[dict] = None,
    source: str = "unknown",
) -> None:
    async with aiosqlite.connect(str(DB_PATH)) as db:
        await _enqueue_offline_operation_with_connection(
            db=db,
            operation=operation,
            table_name=table_name,
            record_id=record_id,
            data=data,
            source=source,
        )
        await db.commit()


async def _enqueue_offline_operation_with_connection(
    db: aiosqlite.Connection,
    operation: str = "unknown",
    table_name: Optional[str] = None,
    record_id: Optional[str] = None,
    data: Optional[dict] = None,
    source: str = "unknown",
) -> None:
    await db.execute(
        """
        INSERT INTO sync_offline_queue (operation, table_name, record_id, data, source)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            operation,
            table_name,
            record_id,
            json.dumps(data, ensure_ascii=False) if data else None,
            source,
        ),
    )


async def enqueue_offline_operations_batch(operations: list[dict]) -> int:
    async with aiosqlite.connect(str(DB_PATH)) as db:
        for op in operations:
            await _enqueue_offline_operation_with_connection(
                db=db,
                operation=op.get("operation", "unknown"),
                table_name=op.get("table_name"),
                record_id=op.get("record_id"),
                data=op.get("data"),
                source=op.get("source", "unknown"),
            )
        await db.commit()
    return len(operations)


async def get_pending_offline_queue(source: Optional[str] = None) -> dict:
    async with aiosqlite.connect(str(DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        if source is None:
            cursor = await db.execute(
                "SELECT * FROM sync_offline_queue WHERE synced = 0 ORDER BY queued_at ASC"
            )
        else:
            cursor = await db.execute(
                "SELECT * FROM sync_offline_queue WHERE synced = 0 AND source = ? ORDER BY queued_at ASC",
                (source,),
            )
        operations = [dict(row) for row in await cursor.fetchall()]

        if source is None:
            cursor = await db.execute("SELECT COUNT(*) FROM sync_offline_queue")
            total = (await cursor.fetchone())[0]
        else:
            total = len(operations)

    return {
        "status": "success",
        "pending": len(operations),
        "total": total,
        "operations": operations,
    }


async def mark_all_pending_offline_operations_synced() -> dict:
    async with aiosqlite.connect(str(DB_PATH)) as db:
        cursor = await db.execute(
            "SELECT id FROM sync_offline_queue WHERE synced = 0 ORDER BY queued_at ASC"
        )
        ids = [row[0] for row in await cursor.fetchall()]

        if ids:
            placeholders = ",".join(["?"] * len(ids))
            await db.execute(
                f"UPDATE sync_offline_queue SET synced = 1 WHERE id IN ({placeholders})",
                ids,
            )
            await db.commit()

    return {
        "status": "success",
        "synced": len(ids),
        "errors": [],
    }


async def get_pending_offline_queue_size() -> int:
    async with aiosqlite.connect(str(DB_PATH)) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM sync_offline_queue WHERE synced = 0")
        return (await cursor.fetchone())[0]


async def register_sync_device(
    device_id: str,
    device_name: Optional[str] = None,
    device_type: Optional[str] = None,
) -> dict:
    async with aiosqlite.connect(str(DB_PATH)) as db:
        await db.execute(
            """
            INSERT OR REPLACE INTO sync_devices (device_id, device_name, device_type, last_seen, registered_at)
            VALUES (?, ?, ?, ?, COALESCE(
                (SELECT registered_at FROM sync_devices WHERE device_id = ?),
                datetime('now')
            ))
            """,
            (device_id, device_name, device_type, datetime.now().isoformat(), device_id),
        )
        await db.commit()

    return {
        "status": "success",
        "message": "设备已注册",
        "device_id": device_id,
    }


async def list_sync_devices() -> dict:
    async with aiosqlite.connect(str(DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM sync_devices ORDER BY last_seen DESC")
        devices = [dict(row) for row in await cursor.fetchall()]

    return {
        "status": "success",
        "devices": devices,
        "total": len(devices),
    }


async def heartbeat_sync_device(device_id: str) -> dict:
    async with aiosqlite.connect(str(DB_PATH)) as db:
        cursor = await db.execute(
            "UPDATE sync_devices SET last_seen = ? WHERE device_id = ?",
            (datetime.now().isoformat(), device_id),
        )
        await db.commit()

        if cursor.rowcount == 0:
            return {"status": "error", "message": "设备未注册"}

    return {"status": "success", "message": "心跳已更新"}


async def register_push_token(device_id: str, token: str, platform: str) -> dict:
    async with aiosqlite.connect(str(DB_PATH)) as db:
        await db.execute(
            """
            INSERT OR REPLACE INTO push_tokens (device_id, token, platform, registered_at)
            VALUES (?, ?, ?, datetime('now'))
            """,
            (device_id, token, platform),
        )
        await db.commit()

    return {"status": "success", "message": "Push token registered"}


async def unregister_push_token(device_id: str) -> dict:
    async with aiosqlite.connect(str(DB_PATH)) as db:
        await db.execute("DELETE FROM push_tokens WHERE device_id = ?", (device_id,))
        await db.commit()

    return {"status": "success", "message": "Push token unregistered"}


async def get_push_token(device_id: str) -> Optional[dict]:
    async with aiosqlite.connect(str(DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM push_tokens WHERE device_id = ?",
            (device_id,),
        )
        row = await cursor.fetchone()
    return dict(row) if row else None
