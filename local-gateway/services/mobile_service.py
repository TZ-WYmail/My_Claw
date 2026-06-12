"""
Mobile service.

This module owns mobile-specific data aggregation queries that do not fit any
single existing domain service cleanly.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import aiosqlite

from config import DB_PATH


async def get_mobile_dashboard_snapshot() -> dict:
    today = datetime.now().strftime("%Y-%m-%d")
    today_start = f"{today}T00:00:00"
    today_end = f"{today}T23:59:59"
    week_start = (datetime.now() - timedelta(days=datetime.now().weekday())).strftime("%Y-%m-%d")

    async with aiosqlite.connect(str(DB_PATH)) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute(
            """
            SELECT * FROM tasks
            WHERE due_time BETWEEN ? AND ?
            AND status = 'pending'
            ORDER BY priority ASC, due_time ASC
            LIMIT 10
            """,
            (today_start, today_end),
        )
        today_tasks = [dict(row) for row in await cursor.fetchall()]

        cursor = await db.execute("SELECT COUNT(*) as count FROM tasks WHERE status = 'pending'")
        pending_count = (await cursor.fetchone())[0]

        cursor = await db.execute(
            """
            SELECT COUNT(*) as count FROM tasks
            WHERE due_time BETWEEN ? AND ?
            """,
            (week_start, today_end),
        )
        week_tasks = (await cursor.fetchone())[0]

        cursor = await db.execute(
            """
            SELECT h.*, COUNT(hc.checkin_id) as today_count
            FROM habits h
            LEFT JOIN habit_checkins hc ON h.habit_id = hc.habit_id
            AND hc.checkin_date = ?
            GROUP BY h.habit_id
            """,
            (today,),
        )
        habits = []
        for row in await cursor.fetchall():
            habit = dict(row)
            habit["checked_in"] = habit["today_count"] > 0
            habits.append(habit)

    return {
        "today_tasks": today_tasks,
        "pending_count": pending_count,
        "week_tasks": week_tasks,
        "habits": habits,
    }
