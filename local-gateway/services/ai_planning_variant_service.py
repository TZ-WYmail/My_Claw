"""
AI planning variant service.

This module owns scheduling strategy and variant-plan construction so
`ai_planning_service` can focus on orchestration and LLM-assisted reordering.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from math import ceil

from services import ai_planning_preview_service
from services import task_planning_service


def _format_hhmm(dt: datetime) -> str:
    return dt.strftime("%H:%M")


def _merge_busy_ranges(ranges: list[tuple[datetime, datetime]]) -> list[tuple[datetime, datetime]]:
    if not ranges:
        return []
    ranges = sorted(ranges, key=lambda item: item[0])
    merged = [ranges[0]]
    for start, end in ranges[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged


def _compute_free_ranges(day: str, capacity: dict, events: list[dict]) -> list[tuple[datetime, datetime]]:
    focus_start = datetime.fromisoformat(f"{day}T{int(capacity['focus_start_hour']):02d}:00:00")
    protected_end_hour = min(int(capacity["focus_end_hour"]), int(capacity["protect_evening_after"]))
    focus_end = datetime.fromisoformat(f"{day}T{protected_end_hour:02d}:00:00")
    busy_ranges = []
    lunch_start = datetime.fromisoformat(f"{day}T{int(capacity['lunch_start_hour']):02d}:00:00")
    lunch_end = datetime.fromisoformat(f"{day}T{int(capacity['lunch_end_hour']):02d}:00:00")
    if lunch_start < lunch_end:
        busy_ranges.append((lunch_start, lunch_end))
    for event in events:
        try:
            start = datetime.fromisoformat(event["start_time"]).replace(tzinfo=None)
            end = datetime.fromisoformat(event["end_time"]).replace(tzinfo=None)
        except Exception:
            continue
        clipped_start = max(start, focus_start)
        clipped_end = min(end, focus_end)
        if clipped_start < clipped_end:
            busy_ranges.append((clipped_start, clipped_end))

    merged_busy = _merge_busy_ranges(busy_ranges)
    cursor = focus_start
    free_ranges = []
    for busy_start, busy_end in merged_busy:
        if cursor < busy_start:
            free_ranges.append((cursor, busy_start))
        cursor = max(cursor, busy_end)
    if cursor < focus_end:
        free_ranges.append((cursor, focus_end))
    return free_ranges


def _task_energy_type(task: dict) -> str:
    name = (task.get("task_name") or "").lower()
    domain = (task.get("work_domain") or "").lower()
    if any(key in name for key in ["汇报", "方案", "开发", "论文", "设计", "编码"]) or domain in {"engineering", "writing", "strategy"}:
        return "deep"
    if any(key in name for key in ["邮件", "报销", "登记", "整理", "同步", "回复"]) or domain in {"admin", "ops"}:
        return "shallow"
    return "normal"


def _sort_tasks_for_blocks(tasks: list[dict]) -> list[dict]:
    def sort_key(task: dict):
        energy_rank = {"deep": 0, "normal": 1, "shallow": 2}.get(_task_energy_type(task), 1)
        domain = task.get("work_domain") or "default"
        priority = task.get("priority", 2)
        return (energy_rank, domain, priority, task.get("due_date", ""), task.get("task_name", ""))

    return sorted(tasks, key=sort_key)


def _assign_time_blocks(day: str, day_info: dict, capacity: dict) -> list[dict]:
    free_ranges = _compute_free_ranges(day, capacity, day_info.get("calendar_events", []))
    blocks = []
    deep_work_start = datetime.fromisoformat(f"{day}T{int(capacity['deep_work_start_hour']):02d}:00:00")
    deep_work_end = datetime.fromisoformat(f"{day}T{int(capacity['deep_work_end_hour']):02d}:00:00")
    sorted_tasks = _sort_tasks_for_blocks(day_info.get("tasks", []))

    for task in sorted_tasks:
        task["energy_type"] = _task_energy_type(task)

    range_index = 0
    range_cursor = free_ranges[0][0] if free_ranges else None

    for task in sorted_tasks:
        remaining_minutes = max(30, int(round(task.get("hours", 0) * 60)))
        task_blocks = []
        preferred_deep = task.get("energy_type") == "deep"
        while remaining_minutes > 0 and range_index < len(free_ranges):
            current_start, current_end = free_ranges[range_index]
            if range_cursor is None or range_cursor < current_start:
                range_cursor = current_start
            if range_cursor >= current_end:
                range_index += 1
                if range_index < len(free_ranges):
                    range_cursor = free_ranges[range_index][0]
                continue

            available_minutes = int((current_end - range_cursor).total_seconds() // 60)
            if available_minutes <= 0:
                range_index += 1
                if range_index < len(free_ranges):
                    range_cursor = free_ranges[range_index][0]
                continue

            block_start_cursor = range_cursor
            block_end_limit = current_end
            if preferred_deep and block_start_cursor < deep_work_end and block_end_limit > deep_work_start:
                block_start_cursor = max(block_start_cursor, deep_work_start)
                block_end_limit = min(block_end_limit, deep_work_end)
                available_minutes = int((block_end_limit - block_start_cursor).total_seconds() // 60)
                if available_minutes <= 0:
                    range_index += 1
                    if range_index < len(free_ranges):
                        range_cursor = free_ranges[range_index][0]
                    continue

            allocate_minutes = min(remaining_minutes, available_minutes)
            block_start = range_cursor
            if preferred_deep:
                block_start = block_start_cursor
            block_end = block_start + timedelta(minutes=allocate_minutes)
            block = {
                "task_name": task["task_name"],
                "start_time": block_start.isoformat(),
                "end_time": block_end.isoformat(),
                "time_slot": f"{_format_hhmm(block_start)}-{_format_hhmm(block_end)}",
                "minutes": allocate_minutes,
                "work_domain": task.get("work_domain"),
                "energy_type": task.get("energy_type"),
            }
            blocks.append(block)
            task_blocks.append(block)
            remaining_minutes -= allocate_minutes
            range_cursor = block_end

        if task_blocks:
            task["slot_start"] = task_blocks[0]["start_time"]
            task["slot_end"] = task_blocks[-1]["end_time"]
            task["time_slot"] = (
                f"{task_blocks[0]['time_slot'].split('-')[0]}-{task_blocks[-1]['time_slot'].split('-')[-1]}"
            )
            task["slot_minutes"] = sum(block["minutes"] for block in task_blocks)
        else:
            task["slot_start"] = None
            task["slot_end"] = None
            task["time_slot"] = "待定"
            task["slot_minutes"] = 0

    day_info["tasks"] = sorted_tasks
    return blocks


def build_variant_plan(
    normalized_tasks: list[dict],
    analyzed: dict,
    variant: dict,
    calendar_load: dict[str, float],
    calendar_events: dict[str, list[dict]],
) -> dict:
    del analyzed

    capacity = variant["constraints"]
    strategy = variant["id"]
    daily_plan: dict[str, dict] = {}
    conflicts = []
    overload_days = []
    infeasible_tasks = []
    completion_days: dict[str, str] = {}

    def ensure_day(day: str) -> dict:
        if day not in daily_plan:
            weekday = task_planning_service.date_to_weekday(day)
            is_weekend = datetime.strptime(day, "%Y-%m-%d").weekday() >= 5
            daily_capacity = capacity["weekend_daily_hours"] if is_weekend else capacity["default_daily_hours"]
            calendar_hours = calendar_load.get(day, 0)
            available_hours = max(0, round(daily_capacity * (1 - capacity["buffer_ratio"]) - calendar_hours, 1))
            daily_plan[day] = {
                "weekday": weekday,
                "tasks": [],
                "total_hours": 0,
                "overload": False,
                "calendar_hours": calendar_hours,
                "available_hours": available_hours,
                "capacity_hours": daily_capacity,
                "calendar_events": calendar_events.get(day, []),
            }
        return daily_plan[day]

    valid_tasks = [task for task in normalized_tasks if task.get("time_valid")]
    valid_tasks.sort(key=lambda item: (item.get("priority", 2), item.get("due_time", "")))
    valid_tasks, dependency_conflicts = ai_planning_preview_service.topological_sort_tasks(valid_tasks)
    conflicts.extend(dependency_conflicts)

    for task in valid_tasks:
        due_dt = datetime.fromisoformat(task["due_time"])
        due_day = due_dt.strftime("%Y-%m-%d")
        estimated_hours = max(0.5, round(task.get("estimated_minutes", 60) / 60, 1))
        earliest_allowed_day = ""
        if task.get("earliest_start_valid"):
            earliest_allowed_day = task["earliest_start"][:10]

        dependency_days = [completion_days.get(name) for name in task.get("depends_on", []) if completion_days.get(name)]
        if dependency_days:
            latest_dependency_day = max(dependency_days)
            earliest_allowed_day = max([day for day in [earliest_allowed_day, latest_dependency_day] if day], default="")

        if strategy == "conservative":
            spread_days = min(6, max(2, ceil(estimated_hours / 2.0)))
            preferred_days = [
                (due_dt - timedelta(days=offset)).strftime("%Y-%m-%d")
                for offset in range(spread_days - 1, -1, -1)
            ]
            max_chunk = 2.5
        elif strategy == "aggressive":
            spread_days = min(4, max(1, ceil(estimated_hours / 4.0)))
            preferred_days = [
                (due_dt - timedelta(days=offset)).strftime("%Y-%m-%d")
                for offset in range(0, spread_days)
            ]
            max_chunk = 5.0
        else:
            spread_days = min(5, max(1, ceil(estimated_hours / 3.0)))
            preferred_days = [
                (due_dt - timedelta(days=offset)).strftime("%Y-%m-%d")
                for offset in range(spread_days - 1, -1, -1)
            ]
            max_chunk = 3.5

        if earliest_allowed_day:
            preferred_days = [day for day in preferred_days if day >= earliest_allowed_day]
            if not preferred_days:
                preferred_days = [max(due_day, earliest_allowed_day)]
                conflicts.append({
                    "type": "earliest_start_pressure",
                    "task_name": task["task_name"],
                    "date": preferred_days[0],
                    "message": f"任务「{task['task_name']}」受最早开始时间或依赖限制，只能从 {preferred_days[0]} 开始",
                })

        remaining = estimated_hours
        assigned_days = []
        for index, day in enumerate(preferred_days):
            day_info = ensure_day(day)
            remaining_capacity = round(day_info["available_hours"] - day_info["total_hours"], 1)
            if remaining_capacity <= 0:
                continue
            allocated = min(remaining, remaining_capacity, max_chunk)
            if allocated <= 0:
                continue
            day_info["tasks"].append({
                "task_name": task["task_name"],
                "hours": round(allocated, 1),
                "due_date": due_day,
                "progress": f"规划执行 {index + 1}",
                "depends_on": task.get("depends_on", []),
            })
            day_info["total_hours"] = round(day_info["total_hours"] + allocated, 1)
            assigned_days.append(day)
            remaining = round(remaining - allocated, 1)
            if remaining <= 0:
                break

        if remaining > 0:
            fallback_day = due_day if strategy != "conservative" else preferred_days[-1]
            day_info = ensure_day(fallback_day)
            day_info["tasks"].append({
                "task_name": task["task_name"],
                "hours": round(remaining, 1),
                "due_date": due_day,
                "progress": "容量不足补位",
                "depends_on": task.get("depends_on", []),
            })
            day_info["total_hours"] = round(day_info["total_hours"] + remaining, 1)
            assigned_days.append(fallback_day)
            conflicts.append({
                "type": "capacity_shortage",
                "task_name": task["task_name"],
                "date": fallback_day,
                "message": f"任务「{task['task_name']}」在当前方案下容量不足，已压缩安排到 {fallback_day}",
            })

        if task.get("depends_on") and assigned_days:
            first_assigned = min(assigned_days)
            if dependency_days and first_assigned < max(dependency_days):
                conflicts.append({
                    "type": "dependency_violation_risk",
                    "task_name": task["task_name"],
                    "date": first_assigned,
                    "message": f"任务「{task['task_name']}」可能早于依赖任务完成，建议顺延",
                })
        if assigned_days:
            completion_days[task["task_name"]] = max(assigned_days)

    for day, info in daily_plan.items():
        info["overload"] = info["total_hours"] > info["available_hours"]
        info["time_blocks"] = _assign_time_blocks(day, info, capacity)
        unslotted_tasks = [task["task_name"] for task in info.get("tasks", []) if task.get("slot_minutes", 0) <= 0]
        if unslotted_tasks:
            conflicts.append({
                "type": "unslotted_tasks",
                "date": day,
                "message": f"{day} 存在未落到具体时间块的任务：{'、'.join(unslotted_tasks)}",
            })
        if info["overload"]:
            overload_days.append({
                "date": day,
                "total_hours": info["total_hours"],
                "available_hours": info["available_hours"],
                "calendar_hours": info["calendar_hours"],
                "overflow_hours": round(info["total_hours"] - info["available_hours"], 1),
            })

    for task in normalized_tasks:
        if not task.get("time_valid"):
            conflicts.append({
                "type": "ambiguous_date",
                "task_name": task["task_name"],
                "message": f"任务「{task['task_name']}」日期无法可靠解析",
            })
            continue
        due_day = task["due_time"][:10]
        day_info = daily_plan.get(due_day, {})
        if day_info.get("overload"):
            conflicts.append({
                "type": "overload",
                "task_name": task["task_name"],
                "date": due_day,
                "message": f"{due_day} 已超出可用容量",
            })
        if datetime.fromisoformat(task["due_time"]) < datetime.now():
            infeasible_tasks.append({
                "task_name": task["task_name"],
                "reason": "截止时间已过去",
            })

    daily_timeline = []
    for day in sorted(daily_plan.keys()):
        info = daily_plan[day]
        weekday = info.get("weekday") or task_planning_service.date_to_weekday(day)
        task_labels = []
        for item in info.get("tasks", []):
            slot_label = f" / {item.get('time_slot')}" if item.get("time_slot") else ""
            task_labels.append(f"{item['task_name']}({item['hours']}h{slot_label})")
        tasks_str = "; ".join(task_labels)
        extra = f" | 可用 {info.get('available_hours', 0)}h"
        if info.get("overload"):
            extra += " | 过载"
        daily_timeline.append(f"📅 {day} ({weekday}) — {info.get('total_hours', 0)}h: {tasks_str}{extra}")

    risk_level = "low"
    if infeasible_tasks or len(overload_days) >= 2:
        risk_level = "high"
    elif overload_days or conflicts:
        risk_level = "medium"

    return {
        "id": variant["id"],
        "label": variant["label"],
        "description": variant["description"],
        "constraints": capacity,
        "daily_plan": daily_plan,
        "daily_timeline": daily_timeline,
        "conflicts": conflicts,
        "overload_days": overload_days,
        "infeasible_tasks": infeasible_tasks,
        "summary": {
            "days": len(daily_plan),
            "conflict_count": len(conflicts),
            "overload_day_count": len(overload_days),
            "infeasible_count": len(infeasible_tasks),
            "risk_level": risk_level,
            "deep_work_days": sum(
                1
                for info in daily_plan.values()
                if any(task.get("energy_type") == "deep" for task in info.get("tasks", []))
            ),
        },
    }
