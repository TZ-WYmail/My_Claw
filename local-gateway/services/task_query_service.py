"""
Task query service.

This module owns task-domain read-side queries.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import aiosqlite

from config import DB_PATH
from services.note_service import get_all_notes
from services.pomodoro_service import get_active_pomodoro
from services.subtask_service import get_subtasks
from services.tag_service import get_task_tags_batch
from services.time_service import extract_system_date, is_overdue, system_now, system_today_iso


async def get_task_by_id(task_id: str) -> dict | None:
    async with aiosqlite.connect(str(DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT task_id, task_name, due_time, recurrence, status, priority,
                      description, estimated_minutes, created_at, updated_at,
                      start_time, end_time, completed_at
               FROM tasks WHERE task_id = ?""",
            (task_id,),
        )
        row = await cursor.fetchone()
        if not row:
            return None

    from services.tag_service import get_task_tags
    task = dict(row)
    task["tags"] = await get_task_tags(task_id)
    return task


async def get_weekly_plan(monday_iso: str = "", sunday_iso: str = "") -> dict:
    if monday_iso and sunday_iso:
        monday_str = monday_iso
        sunday_str = sunday_iso
    else:
        now = datetime.now()
        monday = now - timedelta(days=now.weekday())
        sunday = monday + timedelta(days=6)
        monday_str = monday.strftime("%Y-%m-%dT00:00:00")
        sunday_str = sunday.strftime("%Y-%m-%dT23:59:59")

    async with aiosqlite.connect(str(DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT task_id, task_name, due_time, recurrence, status, priority, description, estimated_minutes, start_time, end_time, completed_at
            FROM tasks
            WHERE status != 'deleted'
              AND due_time >= ? AND due_time <= ?
            ORDER BY priority ASC, due_time ASC
            """,
            (monday_str, sunday_str),
        )
        rows = await cursor.fetchall()

    task_ids = [row["task_id"] for row in rows]
    tags_map = await get_task_tags_batch(task_ids)

    tasks = []
    for row in rows:
        tasks.append({
            "task_id": row["task_id"],
            "task_name": row["task_name"],
            "due_time": row["due_time"],
            "recurrence": row["recurrence"],
            "status": row["status"],
            "priority": row["priority"],
            "description": row["description"],
            "estimated_minutes": row["estimated_minutes"],
            "start_time": row["start_time"],
            "end_time": row["end_time"],
            "completed_at": row["completed_at"],
            "tags": tags_map.get(row["task_id"], []),
        })

    return {
        "status": "success",
        "tasks": tasks,
        "message": f"本周共有 {len(tasks)} 项任务",
    }


async def get_pending_tasks(today_only: bool = False) -> dict:
    now = system_now()
    today = system_today_iso()

    async with aiosqlite.connect(str(DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT task_id, task_name, due_time, start_time, end_time, recurrence,
                      status, priority, description, estimated_minutes
               FROM tasks
               WHERE status = 'pending'
               ORDER BY priority ASC, due_time ASC""",
        )
        rows = await cursor.fetchall()

    task_ids = [row["task_id"] for row in rows]
    tags_map = await get_task_tags_batch(task_ids)

    tasks = []
    for row in rows:
        overdue = is_overdue(row["due_time"], now)
        due_date = extract_system_date(row["due_time"])
        start_date = extract_system_date(row["start_time"])
        is_today_related = overdue or due_date == today or start_date == today

        if today_only and not is_today_related:
            continue

        tasks.append({
            "task_id": row["task_id"],
            "task_name": row["task_name"],
            "due_time": row["due_time"],
            "start_time": row["start_time"],
            "end_time": row["end_time"],
            "recurrence": row["recurrence"],
            "status": row["status"],
            "priority": row["priority"],
            "description": row["description"],
            "estimated_minutes": row["estimated_minutes"],
            "overdue": overdue,
            "tags": tags_map.get(row["task_id"], []),
        })

    overdue_count = sum(1 for task in tasks if task["overdue"])
    scope_label = "今日相关待办" if today_only else "待办"

    return {
        "status": "success",
        "tasks": tasks,
        "total": len(tasks),
        "overdue_count": overdue_count,
        "message": f"共 {len(tasks)} 项{scope_label}，其中 {overdue_count} 项已逾期",
    }


async def get_all_tasks(
    status_filter: str = "active",
    keyword: str = "",
    tag: str = "",
    priority: int = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    conditions = []
    params = []

    if status_filter == "active":
        conditions.append("status != 'deleted'")
    elif status_filter in ("pending", "completed", "deleted"):
        conditions.append("status = ?")
        params.append(status_filter)

    if keyword:
        conditions.append("(task_name LIKE ? OR description LIKE ?)")
        params.extend([f"%{keyword}%", f"%{keyword}%"])

    if priority is not None:
        conditions.append("priority = ?")
        params.append(priority)

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    async with aiosqlite.connect(str(DB_PATH)) as db:
        if tag:
            cursor = await db.execute(
                f"""SELECT COUNT(DISTINCT t.task_id) FROM tasks t
                    JOIN task_tags tt ON t.task_id = tt.task_id
                    JOIN tags tg ON tt.tag_id = tg.tag_id
                    WHERE {where_clause} AND tg.name = ?""",
                params + [tag],
            )
        else:
            cursor = await db.execute(
                f"SELECT COUNT(*) FROM tasks WHERE {where_clause}",
                params,
            )
        total = (await cursor.fetchone())[0]

        offset = (page - 1) * page_size
        db.row_factory = aiosqlite.Row

        if tag:
            cursor = await db.execute(
                f"""
                SELECT t.task_id, t.task_name, t.due_time, t.recurrence, t.status,
                       t.priority, t.description, t.estimated_minutes, t.created_at,
                       t.start_time, t.end_time, t.completed_at
                FROM tasks t
                JOIN task_tags tt ON t.task_id = tt.task_id
                JOIN tags tg ON tt.tag_id = tg.tag_id
                WHERE {where_clause} AND tg.name = ?
                ORDER BY t.priority ASC, t.due_time ASC
                LIMIT ? OFFSET ?
                """,
                params + [tag, page_size, offset],
            )
        else:
            cursor = await db.execute(
                f"""
                SELECT task_id, task_name, due_time, recurrence, status,
                       priority, description, estimated_minutes, created_at,
                       start_time, end_time, completed_at
                FROM tasks WHERE {where_clause}
                ORDER BY priority ASC, due_time ASC
                LIMIT ? OFFSET ?
                """,
                params + [page_size, offset],
            )
        rows = await cursor.fetchall()

    task_ids = [row["task_id"] for row in rows]
    tags_map = await get_task_tags_batch(task_ids)

    tasks = []
    for row in rows:
        tasks.append({
            "task_id": row["task_id"],
            "task_name": row["task_name"],
            "due_time": row["due_time"],
            "recurrence": row["recurrence"],
            "status": row["status"],
            "priority": row["priority"],
            "description": row["description"],
            "estimated_minutes": row["estimated_minutes"],
            "created_at": row["created_at"],
            "start_time": row["start_time"],
            "end_time": row["end_time"],
            "completed_at": row["completed_at"],
            "tags": tags_map.get(row["task_id"], []),
        })

    return {
        "status": "success",
        "tasks": tasks,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }

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
