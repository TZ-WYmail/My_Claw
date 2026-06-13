"""
Task planning service.

This module owns task planning helpers, time normalization, and batch preview
analysis so command-side task mutations do not also carry scheduling logic.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta

import aiosqlite

from config import DB_PATH


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

        iso_time = normalize_time(due_time)
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

    daily_plan = generate_daily_plan(analyzed)
    timeline = []
    for date_key in sorted(by_date.keys()):
        names = by_date[date_key]
        weekday = date_to_weekday(date_key)
        timeline.append(f"📅 {date_key} ({weekday}) — {len(names)} 项截止: {', '.join(names)}")

    daily_timeline = []
    for day in sorted(daily_plan.keys()):
        info = daily_plan[day]
        weekday = date_to_weekday(day)
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


def generate_daily_plan(analyzed: list[dict]) -> dict[str, dict]:
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
        weekday = date_to_weekday(date_str)
        result[date_str] = {
            "weekday": weekday,
            "tasks": tasks,
            "total_hours": total_h,
            "overload": total_h > 6,
        }
    return result


def normalize_time(time_str: str) -> str:
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


def date_to_weekday(date_str: str) -> str:
    weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    try:
        return weekdays[datetime.strptime(date_str, "%Y-%m-%d").weekday()]
    except Exception:
        return ""


def calc_next_reminder(due_time: str, recurrence: str) -> str:
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


def human_readable_time(iso_time: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_time)
        weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        return f"{dt.strftime('%m-%d %H:%M')} ({weekdays[dt.weekday()]})"
    except Exception:
        return iso_time
