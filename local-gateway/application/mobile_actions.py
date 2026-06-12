"""
Mobile application entrypoints.

This module centralizes mobile-specific orchestration so the mobile router no
longer mixes transport, SQL access, and cross-module coordination.
"""
from __future__ import annotations
from services import habit_service
from services import mobile_service
from services import pomodoro_service
from services import runtime_state_service
from services import task_command_service
from services.sync_service import sync_engine
from services import voice_service


_QUICK_ACTION_DISPATCH = {
    "complete_task": task_command_service.complete_task,
    "start_pomodoro": pomodoro_service.start_pomodoro,
    "checkin_habit": habit_service.checkin_habit,
}


async def get_mobile_dashboard_action() -> dict:
    snapshot = await mobile_service.get_mobile_dashboard_snapshot()
    pomodoro_stats = await pomodoro_service.get_pomodoro_stats()
    sync_status = await sync_engine.get_sync_status()

    return {
        "status": "success",
        "data": {
            "today": {
                "tasks": snapshot["today_tasks"],
                "task_count": len(snapshot["today_tasks"]),
                "pomodoro_count": pomodoro_stats.get("today_count", 0),
            },
            "summary": {
                "pending_tasks": snapshot["pending_count"],
                "week_tasks": snapshot["week_tasks"],
            },
            "habits": snapshot["habits"],
            "sync_status": sync_status,
        },
    }


async def quick_action_action(action_type: str, target_id: str) -> dict:
    handler = _QUICK_ACTION_DISPATCH.get(action_type)
    if not handler:
        return {"status": "error", "message": f"Unknown action type: {action_type}"}

    result = await handler(target_id)
    return {"status": "success", "action": action_type, "result": result}


async def voice_create_task_action(audio_base64: str) -> dict:
    result = await voice_service.process_voice(
        audio_base64,
        source="mobile",
    )
    if result.get("status") == "error":
        return {
            "status": "error",
            "message": result.get("message", "语音处理失败"),
            "recognized_text": result.get("text", ""),
        }

    if result.get("task_created"):
        return {
            "status": "success",
            "recognized_text": result.get("text", ""),
            "task": result.get("task"),
        }

    return {
        "status": "success",
        "recognized_text": result.get("text", ""),
        "message": result.get("message", "未识别到任务创建意图"),
    }


async def register_push_token_action(device_id: str, token: str, platform: str) -> dict:
    return await runtime_state_service.register_push_token(device_id, token, platform)


async def unregister_push_token_action(device_id: str) -> dict:
    return await runtime_state_service.unregister_push_token(device_id)


async def test_push_notification_action(device_id: str) -> dict:
    token_row = await runtime_state_service.get_push_token(device_id)
    if not token_row:
        return {"status": "error", "message": "Device not registered"}

    return {
        "status": "success",
        "message": f"Test notification sent to {token_row['platform']}",
        "target": device_id,
    }


async def queue_offline_batch_action(operations: list[dict]) -> dict:
    queued_count = await runtime_state_service.enqueue_offline_operations_batch(operations)
    return {"status": "success", "queued_count": queued_count}


async def get_pending_operations_action(device_id: str) -> dict:
    result = await runtime_state_service.get_pending_offline_queue(source=device_id)
    return {
        "status": "success",
        "pending": result["pending"],
        "operations": result["operations"],
    }


async def get_delta_sync_action(since: str, tables: str | None = None) -> dict:
    payload = await sync_engine.generate_sync_payload(since)

    if tables:
        table_list = tables.split(",")
        payload["changes"] = [
            change for change in payload["changes"]
            if change.get("table_name") in table_list
        ]

    by_table: dict[str, int] = {}
    for change in payload["changes"]:
        table = change.get("table_name", "unknown")
        by_table[table] = by_table.get(table, 0) + 1

    payload["stats"] = {"total_changes": len(payload["changes"]), "by_table": by_table}

    return {"status": "success", "payload": payload}


async def get_mobile_settings_action() -> dict:
    return {
        "status": "success",
        "settings": {
            "theme": "auto",
            "language": "zh-CN",
            "notification_enabled": True,
            "pomodoro_duration": 25,
            "break_duration": 5,
            "sync_interval": 300,
            "offline_mode": False,
        },
    }


async def update_mobile_settings_action(settings: dict) -> dict:
    return {"status": "success", "message": "Settings updated", "settings": settings}
