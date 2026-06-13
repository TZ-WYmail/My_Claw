from fastapi import APIRouter, Query

from application.pomodoro_actions import (
    complete_pomodoro_action,
    get_pomodoro_history_action,
    get_pomodoro_stats_action,
    get_pomodoro_status_action,
    interrupt_pomodoro_action,
    start_pomodoro_action,
)
from models import schemas

router = APIRouter(prefix="/pomodoro", tags=["pomodoro"])


@router.post("/start", response_model=schemas.PomodoroStatusResponse)
async def start_pomodoro(request: schemas.PomodoroStartRequest):
    return await start_pomodoro_action(request.task_id, request.duration_minutes)


@router.post("/complete")
async def complete_pomodoro():
    return await complete_pomodoro_action()


@router.post("/interrupt")
async def interrupt_pomodoro(request: schemas.PomodoroInterruptRequest):
    return await interrupt_pomodoro_action(request.reason)


@router.get("/status", response_model=schemas.PomodoroStatusResponse)
async def get_pomodoro_status():
    return await get_pomodoro_status_action()


@router.get("/stats", response_model=schemas.PomodoroStatsResponse)
async def get_pomodoro_stats():
    return await get_pomodoro_stats_action()


@router.get("/history", response_model=schemas.PomodoroHistoryResponse)
async def get_pomodoro_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    return await get_pomodoro_history_action(page, page_size)
