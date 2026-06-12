"""
Sync application entrypoints.

This module centralizes sync and runtime state use cases above sync/runtime
services so routers remain transport-only.
"""
from __future__ import annotations

from services import runtime_state_service
from services.sync_service import sync_engine


async def get_sync_status_action() -> dict:
    return await sync_engine.get_sync_status()


async def push_changes_action(payload: dict) -> dict:
    return await sync_engine.apply_sync_payload(payload)


async def pull_changes_action(since: str | None = None) -> dict:
    payload = await sync_engine.generate_sync_payload(since)
    return {
        "status": "success",
        "payload": payload,
    }


async def full_sync_action() -> dict:
    return await sync_engine.full_sync()


async def register_device_action(payload: dict) -> dict:
    return await runtime_state_service.register_sync_device(
        device_id=payload["device_id"],
        device_name=payload.get("device_name"),
        device_type=payload.get("device_type"),
    )


async def list_devices_action() -> dict:
    return await runtime_state_service.list_sync_devices()


async def device_heartbeat_action(device_id: str) -> dict:
    return await runtime_state_service.heartbeat_sync_device(device_id)


async def add_offline_operation_action(payload: dict) -> dict:
    await runtime_state_service.enqueue_offline_operation(
        operation=payload.get("operation", "unknown"),
        table_name=payload.get("table_name"),
        record_id=payload.get("record_id"),
        data=payload.get("data"),
        source=payload.get("source", "unknown"),
    )
    pending = await runtime_state_service.get_pending_offline_queue_size()
    return {
        "status": "success",
        "message": "操作已加入离线队列",
        "queue_size": pending,
    }


async def get_offline_queue_action() -> dict:
    return await runtime_state_service.get_pending_offline_queue()


async def sync_offline_queue_action() -> dict:
    return await runtime_state_service.mark_all_pending_offline_operations_synced()
