"""
数据同步路由 — 多端同步 API
设备、离线队列均持久化到 SQLite
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query

from application.sync_actions import (
    add_offline_operation_action,
    device_heartbeat_action,
    full_sync_action,
    get_offline_queue_action,
    get_sync_status_action,
    list_devices_action,
    pull_changes_action,
    push_changes_action,
    register_device_action,
    sync_offline_queue_action,
)
from models.sync_models import DeviceInfo, OfflineOperation, SyncPayload

router = APIRouter(prefix="/sync", tags=["sync"])


# ============================================================
# API 端点
# ============================================================

@router.get("/status")
async def get_sync_status():
    """获取同步状态"""
    return await get_sync_status_action()


@router.post("/push")
async def push_changes(payload: SyncPayload):
    """
    推送变更到服务器
    客户端将本地变更发送到服务器
    """
    return await push_changes_action(payload.model_dump())


@router.post("/pull")
async def pull_changes(since: Optional[str] = None):
    """
    从服务器拉取变更
    客户端获取服务器的变更
    """
    return await pull_changes_action(since)


@router.post("/full")
async def full_sync():
    """执行完整同步"""
    return await full_sync_action()


# ============================================================
# 设备管理 (持久化到 SQLite)
# ============================================================

@router.post("/device/register")
async def register_device(info: DeviceInfo):
    """注册设备"""
    return await register_device_action(info.model_dump())


@router.get("/devices")
async def list_devices():
    """列出所有已注册设备"""
    return await list_devices_action()


@router.post("/device/{device_id}/heartbeat")
async def device_heartbeat(device_id: str):
    """设备心跳"""
    return await device_heartbeat_action(device_id)


# ============================================================
# 离线队列 (持久化到 SQLite)
# ============================================================

@router.post("/offline/queue")
async def add_offline_operation(operation: OfflineOperation):
    """添加离线操作到队列"""
    return await add_offline_operation_action(operation.model_dump())


@router.get("/offline/queue")
async def get_offline_queue():
    """获取离线队列"""
    return await get_offline_queue_action()


@router.post("/offline/sync")
async def sync_offline_queue():
    """同步离线队列 — 批量标记已同步"""
    return await sync_offline_queue_action()
