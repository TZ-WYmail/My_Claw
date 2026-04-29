"""
数据同步路由 — 多端同步 API
设备、离线队列均持久化到 SQLite
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

import aiosqlite
from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from config import DB_PATH
from services.sync_service import sync_engine

router = APIRouter(prefix="/sync", tags=["sync"])


# ============================================================
# 请求/响应模型
# ============================================================

class OfflineOperation(BaseModel):
    operation: str = "unknown"
    table_name: Optional[str] = None
    record_id: Optional[str] = None
    data: Optional[dict] = None
    source: str = "unknown"


class SyncPayload(BaseModel):
    """同步数据包"""
    device_id: str
    timestamp: str
    since: Optional[str] = None
    changes: list[dict] = Field(default_factory=list)


class SyncResponse(BaseModel):
    """同步响应"""
    status: str
    device_id: str
    results: Optional[dict] = None


class DeviceInfo(BaseModel):
    """设备信息"""
    device_id: str
    device_name: Optional[str] = None
    device_type: Optional[str] = None  # mobile/desktop/web
    last_seen: Optional[str] = None


# ============================================================
# 共享：离线队列入库
# ============================================================

async def _enqueue_operation(db: aiosqlite.Connection, op: OfflineOperation):
    await db.execute("""
        INSERT INTO sync_offline_queue (operation, table_name, record_id, data, source)
        VALUES (?, ?, ?, ?, ?)
    """, (
        op.operation,
        op.table_name,
        op.record_id,
        json.dumps(op.data, ensure_ascii=False) if op.data else None,
        op.source,
    ))


# ============================================================
# API 端点
# ============================================================

@router.get("/status")
async def get_sync_status():
    """获取同步状态"""
    return await sync_engine.get_sync_status()


@router.post("/push")
async def push_changes(payload: SyncPayload):
    """
    推送变更到服务器
    客户端将本地变更发送到服务器
    """
    result = await sync_engine.apply_sync_payload(payload.model_dump())
    return result


@router.post("/pull")
async def pull_changes(since: Optional[str] = None):
    """
    从服务器拉取变更
    客户端获取服务器的变更
    """
    payload = await sync_engine.generate_sync_payload(since)
    return {
        "status": "success",
        "payload": payload,
    }


@router.post("/full")
async def full_sync():
    """执行完整同步"""
    return await sync_engine.full_sync()


# ============================================================
# 设备管理 (持久化到 SQLite)
# ============================================================

@router.post("/device/register")
async def register_device(info: DeviceInfo):
    """注册设备"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR REPLACE INTO sync_devices (device_id, device_name, device_type, last_seen, registered_at)
            VALUES (?, ?, ?, ?, COALESCE(
                (SELECT registered_at FROM sync_devices WHERE device_id = ?),
                datetime('now')
            ))
        """, (info.device_id, info.device_name, info.device_type,
              datetime.now().isoformat(), info.device_id))
        await db.commit()

    return {
        "status": "success",
        "message": "设备已注册",
        "device_id": info.device_id,
    }


@router.get("/devices")
async def list_devices():
    """列出所有已注册设备"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM sync_devices ORDER BY last_seen DESC")
        rows = await cursor.fetchall()
        devices = [dict(r) for r in rows]

    return {
        "status": "success",
        "devices": devices,
        "total": len(devices),
    }


@router.post("/device/{device_id}/heartbeat")
async def device_heartbeat(device_id: str):
    """设备心跳"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "UPDATE sync_devices SET last_seen = ? WHERE device_id = ?",
            (datetime.now().isoformat(), device_id),
        )
        await db.commit()

        if cursor.rowcount == 0:
            return {"status": "error", "message": "设备未注册"}

    return {"status": "success", "message": "心跳已更新"}


# ============================================================
# 离线队列 (持久化到 SQLite)
# ============================================================

@router.post("/offline/queue")
async def add_offline_operation(operation: OfflineOperation):
    """添加离线操作到队列"""
    async with aiosqlite.connect(DB_PATH) as db:
        await _enqueue_operation(db, operation)
        await db.commit()
        cursor = await db.execute("SELECT COUNT(*) FROM sync_offline_queue WHERE synced = 0")
        pending = (await cursor.fetchone())[0]

    return {
        "status": "success",
        "message": "操作已加入离线队列",
        "queue_size": pending,
    }


@router.get("/offline/queue")
async def get_offline_queue():
    """获取离线队列"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM sync_offline_queue WHERE synced = 0 ORDER BY queued_at ASC"
        )
        pending = [dict(r) for r in await cursor.fetchall()]
        cursor = await db.execute("SELECT COUNT(*) FROM sync_offline_queue")
        total = (await cursor.fetchone())[0]

    return {
        "status": "success",
        "pending": len(pending),
        "total": total,
        "operations": pending,
    }


@router.post("/offline/sync")
async def sync_offline_queue():
    """同步离线队列 — 批量标记已同步"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT id FROM sync_offline_queue WHERE synced = 0 ORDER BY queued_at ASC"
        )
        ids = [r[0] for r in await cursor.fetchall()]

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
