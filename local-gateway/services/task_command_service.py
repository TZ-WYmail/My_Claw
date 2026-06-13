"""
Task command service.

This module owns write-side task operations and task planning mutations,
extracted from `task_service` to reduce command/query coupling.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta

import aiosqlite

from config import DB_PATH
from services import task_planning_service
from services import task_query_service
from services.security_service import validate_update_columns
from services.tag_service import add_task_tags


async def _check_conflicts(start_time: str, end_time: str, exclude_task_id: str = None) -> list[str]:
    if not start_time or not end_time:
        return []

    warnings = []

    try:
        task_date = start_time[:10]
        task_start = datetime.fromisoformat(start_time)
        task_end = datetime.fromisoformat(end_time)
    except (ValueError, TypeError):
        return []

    if task_start >= task_end:
        return []

    async with aiosqlite.connect(str(DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT task_id, task_name, start_time, end_time, due_time, estimated_minutes
               FROM tasks
               WHERE status = 'pending'
               AND (date(start_time) = ? OR date(due_time) = ?)
               AND start_time IS NOT NULL AND end_time IS NOT NULL""",
            (task_date, task_date),
        )
        rows = await cursor.fetchall()

        total_hours = 0
        for row in rows:
            if exclude_task_id and row["task_id"] == exclude_task_id:
                continue

            try:
                existing_start = datetime.fromisoformat(row["start_time"])
                existing_end = datetime.fromisoformat(row["end_time"])
                duration = (existing_end - existing_start).total_seconds() / 3600
                total_hours += duration

                if task_start < existing_end and task_end > existing_start:
                    warnings.append(
                        f"{task_start.strftime('%H:%M')}-{task_end.strftime('%H:%M')} 与已有任务「{row['task_name']}」时间冲突"
                    )
            except (ValueError, TypeError):
                continue

        new_hours = (task_end - task_start).total_seconds() / 3600
        total_hours += new_hours

        if total_hours > 8:
            warnings.append(f"当日任务总工时已达 {total_hours:.1f}h，超过 8h 上限")

    return warnings


async def add_task(
    task_name: str,
    due_time: str,
    recurrence: str = "once",
    priority: int = 2,
    description: str = None,
    estimated_minutes: int = None,
    tags: list[str] = None,
    start_time: str = None,
    end_time: str = None,
) -> dict:
    task_id = f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"

    async with aiosqlite.connect(str(DB_PATH)) as db:
        await db.execute(
            """INSERT INTO tasks (task_id, task_name, due_time, recurrence, priority, description, estimated_minutes, start_time, end_time)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (task_id, task_name, due_time, recurrence, priority, description, estimated_minutes, start_time, end_time),
        )
        await db.commit()

    if tags:
        await add_task_tags(task_id, tags)

    next_reminder = task_planning_service.calc_next_reminder(due_time, recurrence)
    warnings = []
    if start_time and end_time:
        warnings = await _check_conflicts(start_time, end_time)

    try:
        from services.notification_service import schedule_task_reminders
        schedule_task_reminders(task_id, start_time=start_time, due_time=due_time, task_name=task_name)
    except Exception:
        pass

    return {
        "status": "success",
        "task_id": task_id,
        "message": f"任务已添加，将在 {task_planning_service.human_readable_time(due_time)} 触发提醒",
        "next_reminder": next_reminder,
        "start_time": start_time,
        "end_time": end_time,
        "warnings": warnings,
    }


async def delete_task(task_id: str) -> dict:
    async with aiosqlite.connect(str(DB_PATH)) as db:
        cursor = await db.execute(
            "UPDATE tasks SET status = 'deleted', updated_at = datetime('now') WHERE task_id = ?",
            (task_id,),
        )
        await db.commit()
        if cursor.rowcount == 0:
            return {"status": "error", "message": f"任务 {task_id} 不存在"}

    try:
        from services.notification_service import cancel_task_reminders
        cancel_task_reminders(task_id)
    except Exception:
        pass
    return {"status": "success", "message": f"任务 {task_id} 已删除"}


async def complete_task(task_id: str) -> dict:
    async with aiosqlite.connect(str(DB_PATH)) as db:
        cursor = await db.execute(
            "UPDATE tasks SET status = 'completed', completed_at = datetime('now'), updated_at = datetime('now') WHERE task_id = ?",
            (task_id,),
        )
        await db.commit()
        if cursor.rowcount == 0:
            return {"status": "error", "message": f"任务 {task_id} 不存在"}

    try:
        from services.notification_service import cancel_task_reminders
        cancel_task_reminders(task_id)
    except Exception:
        pass
    return {"status": "success", "message": f"任务 {task_id} 已完成"}


async def update_task(
    task_id: str,
    task_name: str = None,
    due_time: str = None,
    recurrence: str = None,
    priority: int = None,
    description: str = None,
    estimated_minutes: int = None,
    start_time: str = None,
    end_time: str = None,
    tags: list[str] = None,
) -> dict:
    updates = []
    params = []

    if task_name is not None:
        updates.append("task_name = ?")
        params.append(task_name)
    if due_time is not None:
        updates.append("due_time = ?")
        params.append(due_time)
    if recurrence is not None:
        updates.append("recurrence = ?")
        params.append(recurrence)
    if priority is not None:
        updates.append("priority = ?")
        params.append(priority)
    if description is not None:
        updates.append("description = ?")
        params.append(description)
    if estimated_minutes is not None:
        updates.append("estimated_minutes = ?")
        params.append(estimated_minutes)
    if start_time is not None:
        updates.append("start_time = ?")
        params.append(start_time)
    if end_time is not None:
        updates.append("end_time = ?")
        params.append(end_time)

    if not updates and tags is None:
        return {"status": "error", "message": "没有要更新的字段"}

    if updates:
        updates.append("updated_at = datetime('now')")
        params.append(task_id)
        async with aiosqlite.connect(str(DB_PATH)) as db:
            cursor = await db.execute(
                f"UPDATE tasks SET {', '.join(updates)} WHERE task_id = ?",
                params,
            )
            await db.commit()
            if cursor.rowcount == 0:
                return {"status": "error", "message": f"任务 {task_id} 不存在"}

    if tags is not None:
        from services.tag_service import set_task_tags
        await set_task_tags(task_id, tags)

    warnings = []
    if start_time and end_time:
        warnings = await _check_conflicts(start_time, end_time, exclude_task_id=task_id)

    try:
        from services.notification_service import cancel_task_reminders, schedule_task_reminders

        cancel_task_reminders(task_id)
        if due_time or start_time:
            async with aiosqlite.connect(str(DB_PATH)) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute(
                    "SELECT task_name, due_time, start_time FROM tasks WHERE task_id = ?",
                    (task_id,),
                )
                row = await cursor.fetchone()
            if row:
                schedule_task_reminders(
                    task_id,
                    start_time=row["start_time"],
                    due_time=row["due_time"],
                    task_name=row["task_name"],
                )
    except Exception:
        pass

    return {"status": "success", "message": "任务已更新", "warnings": warnings}


async def batch_update_tasks(
    task_ids: list[str],
    priority: int = None,
    due_time: str = None,
    tags_add: list[str] = None,
    tags_remove: list[str] = None,
) -> dict:
    if not task_ids:
        return {"status": "error", "message": "task_ids 不能为空"}

    results = []
    success_count = 0
    error_count = 0

    for task_id in task_ids:
        if not await task_query_service.get_task_by_id(task_id):
            error_count += 1
            results.append({
                "task_id": task_id,
                "status": "error",
                "message": f"任务 {task_id} 不存在",
                "warnings": [],
            })
            continue

        result = {"status": "success", "message": "标签已更新", "warnings": []}
        if due_time is not None or priority is not None:
            result = await update_task(
                task_id=task_id,
                due_time=due_time,
                priority=priority,
            )

        if result.get("status") == "success":
            if tags_add:
                from services.tag_service import add_task_tags
                await add_task_tags(task_id, tags_add)
            if tags_remove:
                from services.tag_service import remove_task_tags
                await remove_task_tags(task_id, tags_remove)
            success_count += 1
        else:
            error_count += 1

        results.append({
            "task_id": task_id,
            "status": result.get("status", "error"),
            "message": result.get("message"),
            "warnings": result.get("warnings", []),
        })

    return {
        "status": "success",
        "message": f"批量更新完成，成功 {success_count} 项，失败 {error_count} 项",
        "success_count": success_count,
        "error_count": error_count,
        "results": results,
    }


async def batch_complete_tasks(task_ids: list[str]) -> dict:
    if not task_ids:
        return {"status": "error", "message": "task_ids 不能为空"}
    placeholders = ",".join("?" for _ in task_ids)
    async with aiosqlite.connect(str(DB_PATH)) as db:
        cursor = await db.execute(
            f"UPDATE tasks SET status = 'completed', completed_at = datetime('now'), updated_at = datetime('now') WHERE task_id IN ({placeholders}) AND status != 'deleted'",
            task_ids,
        )
        await db.commit()
        count = cursor.rowcount
    return {"status": "success", "message": f"已完成 {count} 项任务", "success_count": count}


async def batch_delete_tasks(task_ids: list[str]) -> dict:
    if not task_ids:
        return {"status": "error", "message": "task_ids 不能为空"}
    placeholders = ",".join("?" for _ in task_ids)
    async with aiosqlite.connect(str(DB_PATH)) as db:
        cursor = await db.execute(
            f"UPDATE tasks SET status = 'deleted', updated_at = datetime('now') WHERE task_id IN ({placeholders}) AND status != 'deleted'",
            task_ids,
        )
        await db.commit()
        count = cursor.rowcount
    return {"status": "success", "message": f"已删除 {count} 项任务", "success_count": count}


async def batch_add_tasks(tasks: list[dict]) -> dict:
    results = []
    success_count = 0
    error_count = 0

    async with aiosqlite.connect(str(DB_PATH)) as db:
        for task in tasks:
            task_name = task.get("task_name", "").strip()
            due_time = task.get("due_time", "").strip()
            recurrence = task.get("recurrence", "once").strip()

            if not task_name or not due_time:
                results.append({
                    "task_name": task_name or "(空)",
                    "status": "error",
                    "message": "缺少 task_name 或 due_time",
                })
                error_count += 1
                continue

            try:
                datetime.fromisoformat(due_time)
            except (ValueError, TypeError):
                results.append({
                    "task_name": task_name,
                    "status": "error",
                    "message": f"时间格式无效: {due_time}",
                })
                error_count += 1
                continue

            task_id = f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
            task_start_time = task.get("start_time")
            task_end_time = task.get("end_time")
            task_description = task.get("description")
            task_estimated_minutes = task.get("estimated_minutes")
            task_priority = task.get("priority", 2)

            try:
                await db.execute(
                    """INSERT INTO tasks (
                        task_id, task_name, due_time, recurrence, start_time, end_time, description, estimated_minutes, priority
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        task_id,
                        task_name,
                        due_time,
                        recurrence,
                        task_start_time,
                        task_end_time,
                        task_description,
                        task_estimated_minutes,
                        task_priority,
                    ),
                )
                task_warnings = []
                if task.get("start_time") and task.get("end_time"):
                    task_warnings = await _check_conflicts(task.get("start_time"), task.get("end_time"))
                results.append({
                    "task_id": task_id,
                    "task_name": task_name,
                    "due_time": due_time,
                    "recurrence": recurrence,
                    "start_time": task_start_time,
                    "end_time": task_end_time,
                    "description": task_description,
                    "estimated_minutes": task_estimated_minutes,
                    "priority": task_priority,
                    "status": "success",
                    "message": f"✅ {task_name} → {task_planning_service.human_readable_time(due_time)}",
                    "warnings": task_warnings,
                })
                success_count += 1
            except Exception as exc:
                results.append({
                    "task_name": task_name,
                    "status": "error",
                    "message": str(exc),
                })
                error_count += 1

        await db.commit()

    return {
        "status": "success",
        "total": len(tasks),
        "success_count": success_count,
        "error_count": error_count,
        "results": results,
        "message": f"批量创建完成: {success_count} 成功, {error_count} 失败",
    }


async def analyze_tasks(raw_tasks: list[dict]) -> dict:
    task_planning_service.DB_PATH = DB_PATH
    return await task_planning_service.analyze_tasks(raw_tasks)
