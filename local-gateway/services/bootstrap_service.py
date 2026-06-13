"""
Bootstrap service.

This module owns database/bootstrap initialization so `task_service` does not
remain the global startup entrypoint for unrelated subsystems.
"""
from __future__ import annotations

import aiosqlite

from config import DB_PATH
from services import dashboard_query_service
from services import runtime_log_service
from services import runtime_state_service
from services import task_command_service
from services import task_detail_service
from services import task_planning_service
from services import task_query_service
from services.task_db_schema import TASK_SCHEMA_SQL


def _sync_paths() -> None:
    task_command_service.DB_PATH = DB_PATH
    task_detail_service.DB_PATH = DB_PATH
    task_query_service.DB_PATH = DB_PATH
    task_planning_service.DB_PATH = DB_PATH
    runtime_state_service.DB_PATH = DB_PATH
    runtime_log_service.DB_PATH = DB_PATH
    dashboard_query_service.DB_PATH = DB_PATH


async def init_db() -> None:
    _sync_paths()
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(str(DB_PATH)) as db:
        await db.executescript(TASK_SCHEMA_SQL)
        await db.commit()

    from services.tag_service import init_tag_db
    await init_tag_db()

    from services.subtask_service import init_subtask_db
    await init_subtask_db()

    from services.pomodoro_service import init_pomodoro_db
    await init_pomodoro_db()

    from services.habit_service import init_habit_db
    await init_habit_db()

    from services.note_service import init_note_db
    await init_note_db()

    from services.calendar_sync_service import init_calendar_db
    await init_calendar_db()

    async with aiosqlite.connect(str(DB_PATH)) as db:
        cursor = await db.execute("PRAGMA table_info(tasks)")
        existing_columns = {row[1] for row in await cursor.fetchall()}
        for col in ("start_time", "end_time", "completed_at"):
            if col not in existing_columns:
                await db.execute(f"ALTER TABLE tasks ADD COLUMN {col} TEXT")
        await db.commit()
