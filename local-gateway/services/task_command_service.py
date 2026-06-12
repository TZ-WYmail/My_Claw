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

    next_reminder = _calc_next_reminder(due_time, recurrence)
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
        "message": f"任务已添加，将在 {_human_readable_time(due_time)} 触发提醒",
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
                    "message": f"✅ {task_name} → {_human_readable_time(due_time)}",
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
    analyzed = []
    by_date: dict[str, list] = {}

    def _estimate_hours(name: str) -> float:
        lowered = name.lower()
        if any(keyword in lowered for keyword in ["学习", "阅读", "整理", "review", "内容整理"]):
            return 4.0
        if any(keyword in lowered for keyword in ["定稿", "报告", "汇报", "演讲", "答辩"]):
            return 8.0
        if any(keyword in lowered for keyword in ["提交", "补全", "准备", "证明"]):
            return 2.0
        if any(keyword in lowered for keyword in ["推进", "调优"]):
            return 6.0
        return 4.0

    for task in raw_tasks:
        task_name = task.get("task_name", "").strip()
        due_time = task.get("due_time", "").strip()
        recurrence = task.get("recurrence", "once")

        iso_time = _normalize_time(due_time)
        conflict = ""
        overdue = False
        if iso_time:
            try:
                dt = datetime.fromisoformat(iso_time)
                if dt < datetime.now():
                    overdue = True
            except (ValueError, TypeError):
                pass
            if iso_time[:10] in by_date and len(by_date[iso_time[:10]]) >= 3:
                conflict = f"⚠️ {iso_time[:10]} 已有 {len(by_date[iso_time[:10]])} 项任务"

        if iso_time:
            by_date.setdefault(iso_time[:10], []).append(task_name)

        analyzed.append({
            "task_name": task_name,
            "due_time": iso_time or due_time,
            "recurrence": recurrence,
            "time_valid": bool(iso_time),
            "conflict": conflict,
            "overdue": overdue,
            "estimated_hours": _estimate_hours(task_name) if iso_time else 0,
            "start_time": task.get("start_time"),
            "end_time": task.get("end_time"),
        })

    daily_plan = _generate_daily_plan(analyzed)
    timeline = []
    for date_key in sorted(by_date.keys()):
        names = by_date[date_key]
        weekday = _date_to_weekday(date_key)
        timeline.append(f"📅 {date_key} ({weekday}) — {len(names)} 项截止: {', '.join(names)}")

    daily_timeline = []
    for day in sorted(daily_plan.keys()):
        info = daily_plan[day]
        weekday = _date_to_weekday(day)
        tasks_str = "; ".join([f"{task['task_name']}({task['hours']}h)" for task in info["tasks"]])
        daily_timeline.append(f"📅 {day} ({weekday}) — {info['total_hours']}h: {tasks_str}")

    existing_tasks = []
    if by_date:
        date_list = list(by_date.keys())
        placeholders = ",".join("?" for _ in date_list)
        async with aiosqlite.connect(str(DB_PATH)) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                f"""SELECT task_id, task_name, due_time, start_time, end_time, priority, status
                   FROM tasks
                   WHERE status = 'pending'
                   AND (date(start_time) IN ({placeholders}) OR date(due_time) IN ({placeholders}))""",
                date_list * 2,
            )
            existing_tasks = [dict(row) for row in await cursor.fetchall()]

    return {
        "status": "success",
        "total": len(raw_tasks),
        "analyzed": analyzed,
        "timeline": timeline,
        "daily_plan": daily_plan,
        "daily_timeline": daily_timeline,
        "by_date": {key: value for key, value in sorted(by_date.items())},
        "existing_tasks": existing_tasks,
        "message": f"解析完成: {len(analyzed)} 项任务, 跨 {len(by_date)} 个截止日, 分布到 {len(daily_plan)} 个工作日",
    }


def _generate_daily_plan(analyzed: list[dict]) -> dict[str, dict]:
    valid = [item for item in analyzed if item["time_valid"]]
    if not valid:
        return {}

    valid.sort(key=lambda item: item["due_time"][:10])
    daily: dict[str, list] = {}

    for task in valid:
        due_date_str = task["due_time"][:10]
        try:
            due_date = datetime.strptime(due_date_str, "%Y-%m-%d")
        except ValueError:
            continue

        est = task.get("estimated_hours", 4.0)
        name = task["task_name"]

        if est >= 6:
            lead_days = 3
        elif est >= 4:
            lead_days = 2
        else:
            lead_days = 1

        hours_per_day = round(est / lead_days, 1)
        hours_per_day = max(hours_per_day, 0.5)

        start_date = due_date - timedelta(days=lead_days)
        for index in range(lead_days):
            work_date = start_date + timedelta(days=index)
            date_str = work_date.strftime("%Y-%m-%d")
            daily.setdefault(date_str, []).append({
                "task_name": name,
                "hours": hours_per_day if index < lead_days - 1 else round(est - hours_per_day * (lead_days - 1), 1),
                "due_date": due_date_str,
                "progress": f"第{index+1}/{lead_days}天",
            })

    result = {}
    for date_str in sorted(daily.keys()):
        tasks = daily[date_str]
        total_h = round(sum(task["hours"] for task in tasks), 1)
        weekday = _date_to_weekday(date_str)
        result[date_str] = {
            "weekday": weekday,
            "tasks": tasks,
            "total_hours": total_h,
            "overload": total_h > 6,
        }
    return result


def _normalize_time(time_str: str) -> str:
    if not time_str:
        return ""

    try:
        return datetime.fromisoformat(time_str).isoformat()
    except (ValueError, TypeError):
        pass

    match = re.match(r"(\d{1,2})月(\d{1,2})日?", time_str)
    if match:
        month, day = int(match.group(1)), int(match.group(2))
        year = datetime.now().year
        try:
            return datetime(year, month, day, 9, 0, 0).isoformat()
        except ValueError:
            return ""

    match = re.match(r"(\d{1,2})-(\d{1,2})$", time_str)
    if match:
        month, day = int(match.group(1)), int(match.group(2))
        year = datetime.now().year
        try:
            return datetime(year, month, day, 9, 0, 0).isoformat()
        except ValueError:
            return ""

    match = re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})$", time_str)
    if match:
        try:
            return datetime(int(match.group(1)), int(match.group(2)), int(match.group(3)), 9, 0, 0).isoformat()
        except ValueError:
            return ""

    return ""


def _date_to_weekday(date_str: str) -> str:
    weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    try:
        return weekdays[datetime.strptime(date_str, "%Y-%m-%d").weekday()]
    except Exception:
        return ""


def _calc_next_reminder(due_time: str, recurrence: str) -> str:
    dt = datetime.fromisoformat(due_time)

    if recurrence == "once":
        return due_time
    if recurrence == "daily":
        next_dt = dt + timedelta(days=1)
    elif recurrence == "weekly":
        next_dt = dt + timedelta(weeks=1)
    elif recurrence == "monthly":
        next_dt = dt + timedelta(days=30)
    else:
        return due_time
    return next_dt.isoformat()


def _human_readable_time(iso_time: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_time)
        weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        return f"{dt.strftime('%m-%d %H:%M')} ({weekdays[dt.weekday()]})"
    except Exception:
        return iso_time
