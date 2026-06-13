from fastapi import APIRouter, Query

from application.calendar_actions import (
    create_calendar_event_action,
    delete_calendar_event_action,
    get_calendar_view_action,
    list_calendar_events_action,
)
from models import schemas

router = APIRouter(prefix="/calendar", tags=["calendar"])


@router.post("/events")
async def create_calendar_event(request: schemas.CalendarEventCreateRequest):
    return await create_calendar_event_action(
        request.title,
        request.start_time,
        request.end_time,
        request.description,
        request.event_type,
        request.color,
    )


@router.get("/events")
async def list_calendar_events(
    start_date: str = Query(..., description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="结束日期 YYYY-MM-DD"),
):
    return await list_calendar_events_action(start_date, end_date)


@router.delete("/events/{event_id}")
async def delete_calendar_event(event_id: str):
    return await delete_calendar_event_action(event_id)


@router.get("/view", response_model=schemas.CalendarViewResponse)
async def get_calendar_view(
    year: int = Query(..., description="年份"),
    month: int = Query(..., ge=1, le=12, description="月份"),
):
    return await get_calendar_view_action(year, month)
