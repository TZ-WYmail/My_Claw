"""
Task detail service.

This module owns cross-domain task detail aggregation so `task_query_service`
can stay focused on task-domain list/detail reads.
"""
from __future__ import annotations

import aiosqlite

from config import DB_PATH
from services.note_service import get_all_notes
from services.pomodoro_service import get_active_pomodoro
from services.subtask_service import get_subtasks
from services.tag_service import get_task_tags_batch
from services.task_query_service import get_task_by_id


async def get_task_detail(task_id: str) -> dict:
    task = await get_task_by_id(task_id)
    if not task:
        return {"status": "error", "message": f"任务 {task_id} 不存在"}

    notes_result = await get_all_notes(page_size=100)
    notes = [note for note in notes_result.get("notes", []) if note.get("task_id") == task_id]
    subtasks = await get_subtasks(task_id)
    active_pomodoro = await get_active_pomodoro()

    due_date = task["due_time"][:10]
    async with aiosqlite.connect(str(DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT task_id, task_name, due_time, recurrence, status, priority,
                      description, estimated_minutes, created_at, updated_at,
                      start_time, end_time, completed_at
               FROM tasks
               WHERE status != 'deleted'
                 AND task_id != ?
                 AND (date(due_time) = ? OR date(start_time) = ?)
               ORDER BY priority ASC, due_time ASC
               LIMIT 8""",
            (task_id, due_date, due_date),
        )
        rows = await cursor.fetchall()

    neighbor_ids = [row["task_id"] for row in rows]
    tags_map = await get_task_tags_batch(neighbor_ids)
    weekly_neighbors = []
    for row in rows:
        item = dict(row)
        item["tags"] = tags_map.get(row["task_id"], [])
        weekly_neighbors.append(item)

    return {
        "status": "success",
        "task": task,
        "notes": notes,
        "subtasks": subtasks,
        "active_pomodoro": active_pomodoro,
        "weekly_neighbors": weekly_neighbors,
    }
