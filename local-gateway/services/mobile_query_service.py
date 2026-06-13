"""
Mobile query service.

This module owns mobile dashboard aggregation queries so `mobile_service` can
retreat and application callers can depend on clearer query-side owners.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from services import habit_service
from services import task_query_service


async def get_mobile_dashboard_snapshot() -> dict:
    today = datetime.now().strftime("%Y-%m-%d")
    today_start = f"{today}T00:00:00"
    today_end = f"{today}T23:59:59"
    week_start = (datetime.now() - timedelta(days=datetime.now().weekday())).strftime("%Y-%m-%dT00:00:00")

    today_tasks = await task_query_service.list_tasks_due_between(
        start_due_time=today_start,
        end_due_time=today_end,
        status="pending",
        limit=10,
    )
    pending_count = await task_query_service.count_tasks(status="pending")
    week_tasks = await task_query_service.count_tasks(
        start_due_time=week_start,
        end_due_time=today_end,
    )
    habits = await habit_service.get_habits_with_today_checkin(today=today)

    return {
        "today_tasks": today_tasks,
        "pending_count": pending_count,
        "week_tasks": week_tasks,
        "habits": habits,
    }
