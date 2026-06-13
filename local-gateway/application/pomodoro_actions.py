"""
Pomodoro application entrypoints.
"""
from __future__ import annotations

from services import pomodoro_service


async def start_pomodoro_action(task_id: str, duration_minutes: int) -> dict:
    result = await pomodoro_service.start_pomodoro(task_id, duration_minutes)
    if result["status"] == "success":
        return {"status": "success", "active_session": await pomodoro_service.get_active_pomodoro()}
    return {"status": "error", "message": result.get("message")}


async def complete_pomodoro_action() -> dict:
    return await pomodoro_service.complete_pomodoro()


async def interrupt_pomodoro_action(reason: str) -> dict:
    return await pomodoro_service.interrupt_pomodoro(reason)


async def get_pomodoro_status_action() -> dict:
    return {"status": "success", "active_session": await pomodoro_service.get_active_pomodoro()}


async def get_pomodoro_stats_action() -> dict:
    return await pomodoro_service.get_pomodoro_stats()


async def get_pomodoro_history_action(page: int = 1, page_size: int = 20) -> dict:
    return await pomodoro_service.get_pomodoro_history(page, page_size)
