"""
Calendar application entrypoints.
"""
from __future__ import annotations

from services import calendar_sync_service


async def create_calendar_event_action(
    title: str,
    start_time: str,
    end_time: str,
    description: str | None = None,
    event_type: str = "meeting",
    color: str | None = None,
) -> dict:
    return await calendar_sync_service.create_calendar_event(
        title,
        start_time,
        end_time,
        description,
        event_type,
        color,
    )


async def list_calendar_events_action(start_date: str, end_date: str) -> dict:
    events = await calendar_sync_service.get_calendar_events(start_date, end_date)
    return {"status": "success", "events": events}


async def delete_calendar_event_action(event_id: str) -> dict:
    return await calendar_sync_service.delete_calendar_event(event_id)


async def get_calendar_view_action(year: int, month: int) -> dict:
    return await calendar_sync_service.get_calendar_view(year, month)
