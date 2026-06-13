"""
AI planning preview service.

This module owns preview/confirm lifecycle for planning variants so
`ai_planning_service` can focus on higher-level planning workflows.
"""
from __future__ import annotations

from datetime import datetime
from math import ceil

from services import calendar_sync_service
from services import runtime_state_service
from services import task_command_service
from services import task_planning_service


def build_preview_id() -> str:
    return f"preview_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"


def normalize_tasks(tasks: list[dict]) -> list[dict]:
    normalized = []
    for task in tasks:
        due_raw = (task.get("due_time") or "").strip()
        due_norm = task_planning_service.normalize_time(due_raw) if due_raw else ""
        earliest_start_raw = (task.get("earliest_start") or "").strip()
        earliest_start_norm = task_planning_service.normalize_time(earliest_start_raw) if earliest_start_raw else ""
        estimated_minutes = task.get("estimated_minutes")
        if not estimated_minutes:
            name = (task.get("task_name") or "").lower()
            if any(key in name for key in ["汇报", "报告", "方案", "论文", "开发"]):
                estimated_minutes = 180
            elif any(key in name for key in ["邮件", "报销", "提交", "登记", "预约"]):
                estimated_minutes = 30
            else:
                estimated_minutes = 60

        normalized.append({
            "task_name": (task.get("task_name") or "").strip(),
            "due_time_raw": due_raw,
            "due_time": due_norm or due_raw,
            "time_valid": bool(due_norm),
            "earliest_start_raw": earliest_start_raw,
            "earliest_start": earliest_start_norm or earliest_start_raw,
            "earliest_start_valid": bool(earliest_start_norm) if earliest_start_raw else False,
            "estimated_minutes": int(estimated_minutes),
            "priority": task.get("priority", 2),
            "description": task.get("description"),
            "depends_on": list(task.get("depends_on") or []),
            "start_time": task.get("start_time"),
            "end_time": task.get("end_time"),
            "recurrence": task.get("recurrence", "once"),
            "work_domain": task.get("work_domain", "default"),
        })
    return normalized


def capacity_template(constraints: dict | None) -> dict:
    base = {
        "default_daily_hours": 6,
        "weekend_daily_hours": 4,
        "buffer_ratio": 0.2,
        "focus_start_hour": 9,
        "focus_end_hour": 18,
        "lunch_start_hour": 12,
        "lunch_end_hour": 13,
        "protect_evening_after": 19,
        "deep_work_start_hour": 9,
        "deep_work_end_hour": 11,
    }
    if constraints:
        base.update({k: v for k, v in constraints.items() if v is not None})
    return base


def variant_definitions(capacity: dict) -> list[dict]:
    return [
        {
            "id": "balanced",
            "label": "平衡方案",
            "description": "默认工作量与缓冲并存",
            "constraints": capacity,
        },
        {
            "id": "conservative",
            "label": "稳妥方案",
            "description": "降低每日容量，增加缓冲，优先降低过载风险",
            "constraints": {
                **capacity,
                "default_daily_hours": max(4, capacity["default_daily_hours"] - 1),
                "weekend_daily_hours": max(2, capacity["weekend_daily_hours"] - 1),
                "buffer_ratio": min(0.4, capacity["buffer_ratio"] + 0.15),
            },
        },
        {
            "id": "aggressive",
            "label": "激进方案",
            "description": "提高每日可用时长，适合短期冲刺或救火",
            "constraints": {
                **capacity,
                "default_daily_hours": capacity["default_daily_hours"] + 2,
                "weekend_daily_hours": capacity["weekend_daily_hours"] + 1,
                "buffer_ratio": max(0.05, capacity["buffer_ratio"] - 0.1),
            },
        },
    ]


def select_variant_plan(preview: dict, selected_variant: str) -> dict:
    variant_plans = preview.get("variant_plans", {})
    return (
        variant_plans.get(selected_variant)
        or variant_plans.get("balanced")
        or next(iter(variant_plans.values()), {})
    )


def task_schedule_from_variant(task: dict, variant_plan: dict) -> dict:
    due_day = (task.get("due_time") or "")[:10]
    matching_slots = []
    task_blocks = []
    for day, info in (variant_plan.get("daily_plan") or {}).items():
        for item in info.get("tasks", []):
            if item.get("task_name") == task["task_name"]:
                matching_slots.append((day, item))
        for block in info.get("time_blocks", []):
            if block.get("task_name") == task["task_name"]:
                task_blocks.append(block)

    scheduled_days = [day for day, _ in matching_slots]
    planned_start_day = min(scheduled_days) if scheduled_days else due_day
    planned_due_day = max(scheduled_days) if scheduled_days else due_day

    derived_start_time = task.get("start_time")
    derived_end_time = task.get("end_time")
    if task_blocks:
        derived_start_time = derived_start_time or task_blocks[0]["start_time"]
        derived_end_time = derived_end_time or task_blocks[-1]["end_time"]
    else:
        if planned_start_day and not derived_start_time:
            derived_start_time = f"{planned_start_day}T09:00:00"
        if planned_due_day and not derived_end_time:
            derived_end_time = f"{planned_due_day}T18:00:00"

    return {
        "planned_start_day": planned_start_day,
        "planned_due_day": planned_due_day,
        "scheduled_days": scheduled_days,
        "time_blocks": task_blocks,
        "start_time": derived_start_time,
        "end_time": derived_end_time,
    }


async def collect_calendar_load(date_from: str, date_to: str) -> dict[str, float]:
    events = await calendar_sync_service.get_calendar_events(date_from, date_to)
    load = {}
    for event in events:
        try:
            start = datetime.fromisoformat(event["start_time"])
            end = datetime.fromisoformat(event["end_time"])
            hours = max(0, round((end - start).total_seconds() / 3600, 1))
            day = event["start_time"][:10]
            load[day] = round(load.get(day, 0) + hours, 1)
        except Exception:
            continue
    return load


async def collect_calendar_events(date_from: str, date_to: str) -> dict[str, list[dict]]:
    events = await calendar_sync_service.get_calendar_events(date_from, date_to)
    grouped: dict[str, list[dict]] = {}
    for event in events:
        day = event.get("start_time", "")[:10]
        if not day:
            continue
        grouped.setdefault(day, []).append({
            "title": event.get("title"),
            "start_time": event.get("start_time"),
            "end_time": event.get("end_time"),
            "event_type": event.get("event_type"),
            "color": event.get("color"),
        })
    return grouped


async def preview_task_plan(
    tasks: list[dict],
    constraints: dict | None,
    build_variant_plan_fn,
) -> dict:
    normalized_tasks = normalize_tasks(tasks)
    task_planning_service.DB_PATH = task_command_service.DB_PATH
    analyzed = await task_planning_service.analyze_tasks(normalized_tasks)
    capacity = capacity_template(constraints)
    variant_defs = variant_definitions(capacity)

    valid_dates = [task["due_time"][:10] for task in normalized_tasks if task.get("time_valid")]
    if valid_dates:
        date_from, date_to = min(valid_dates), max(valid_dates)
        calendar_load = await collect_calendar_load(date_from, date_to)
        calendar_events = await collect_calendar_events(date_from, date_to)
    else:
        calendar_load = {}
        calendar_events = {}

    variant_plans = {
        variant["id"]: build_variant_plan_fn(
            normalized_tasks,
            analyzed,
            variant,
            calendar_load,
            calendar_events,
        )
        for variant in variant_defs
    }
    selected_plan = variant_plans["balanced"]
    variants = [
        {
            "id": variant["id"],
            "label": variant["label"],
            "description": variant["description"],
            "constraints": variant["constraints"],
            "summary": variant_plans[variant["id"]]["summary"],
        }
        for variant in variant_defs
    ]

    preview_id = build_preview_id()
    result = {
        "status": "success",
        "preview_id": preview_id,
        "normalized_tasks": normalized_tasks,
        "selected_variant": selected_plan["id"],
        "daily_plan": selected_plan["daily_plan"],
        "calendar_load": calendar_load,
        "calendar_events": calendar_events,
        "daily_timeline": selected_plan["daily_timeline"],
        "timeline": analyzed.get("timeline", []),
        "existing_tasks": analyzed.get("existing_tasks", []),
        "conflicts": selected_plan["conflicts"],
        "overload_days": selected_plan["overload_days"],
        "infeasible_tasks": selected_plan["infeasible_tasks"],
        "variants": variants,
        "variant_plans": variant_plans,
        "explanation": {
            "summary": "已根据截止时间、多天分摊、日历占用和每日容量生成预览。",
            "next_step": "请确认方案或调整约束后再创建。",
        },
    }
    await runtime_state_service.save_planning_preview(
        preview_id=preview_id,
        payload=result,
        selected_variant=selected_plan["id"],
        source="ai_planning.preview",
    )
    return result


async def confirm_task_plan(
    preview_id: str,
    selected_variant: str,
    user_adjustments: dict | None,
) -> tuple[dict | None, dict | None, list[dict] | None]:
    preview_record = await runtime_state_service.get_planning_preview(preview_id)
    if not preview_record:
        return None, {"status": "error", "message": "preview_id 不存在或已过期"}, None

    expire_at = preview_record.get("expire_at")
    if expire_at:
        try:
            if datetime.fromisoformat(expire_at) <= datetime.now():
                await runtime_state_service.delete_planning_preview(preview_id)
                return None, {"status": "error", "message": "preview_id 不存在或已过期"}, None
        except ValueError:
            pass

    preview = preview_record["payload"]
    tasks = preview["normalized_tasks"]
    variant_plan = select_variant_plan(preview, selected_variant)
    if user_adjustments:
        task_overrides = user_adjustments.get("tasks", {})
        adjusted = []
        for task in tasks:
            override = task_overrides.get(task["task_name"], {})
            adjusted.append({**task, **override})
        tasks = adjusted

    return preview, variant_plan, tasks


async def finalize_confirmed_preview(preview_id: str) -> None:
    await runtime_state_service.delete_planning_preview(preview_id)


def build_create_payload(tasks: list[dict], variant_plan: dict, selected_variant: str) -> list[dict]:
    payload = []
    for task in tasks:
        if not task.get("time_valid"):
            continue

        schedule = task_schedule_from_variant(task, variant_plan)
        payload.append({
            "task_name": task["task_name"],
            "due_time": task["due_time"],
            "start_time": schedule.get("start_time"),
            "end_time": schedule.get("end_time"),
            "recurrence": task.get("recurrence", "once"),
            "estimated_minutes": task.get("estimated_minutes"),
            "description": (
                task.get("description")
                or f"AI 安排任务方案：{variant_plan.get('label', selected_variant)}；"
                   f"计划执行日：{'、'.join(schedule.get('scheduled_days', [])) or task['due_time'][:10]}；"
                   f"时间块：{'、'.join(block['time_slot'] for block in schedule.get('time_blocks', [])) or '待定'}"
            ),
            "priority": task.get("priority", 2),
        })
    return payload


def count_variant_summary(tasks: list[dict], variant_plan: dict, selected_variant: str, created: dict, preview_id: str) -> dict:
    return {
        "status": created.get("status", "success"),
        "preview_id": preview_id,
        "selected_variant": variant_plan.get("id", selected_variant),
        "selected_plan_summary": variant_plan.get("summary", {}),
        "created_tasks": created.get("results", []),
        "success_count": created.get("success_count", 0),
        "error_count": created.get("error_count", 0),
        "skipped_tasks": [task for task in tasks if not task.get("time_valid")],
        "warnings": variant_plan.get("conflicts", []),
    }


def topological_sort_tasks(tasks: list[dict]) -> tuple[list[dict], list[dict]]:
    by_name = {task["task_name"]: task for task in tasks}
    indegree = {task["task_name"]: 0 for task in tasks}
    graph: dict[str, list[str]] = {task["task_name"]: [] for task in tasks}
    dependency_conflicts = []

    for task in tasks:
        for dependency in task.get("depends_on", []):
            if dependency not in by_name:
                dependency_conflicts.append({
                    "type": "missing_dependency",
                    "task_name": task["task_name"],
                    "message": f"任务「{task['task_name']}」依赖的「{dependency}」不存在",
                })
                continue
            graph[dependency].append(task["task_name"])
            indegree[task["task_name"]] += 1

    queue = sorted([name for name, degree in indegree.items() if degree == 0])
    ordered_names = []
    while queue:
        current = queue.pop(0)
        ordered_names.append(current)
        for neighbor in graph[current]:
            indegree[neighbor] -= 1
            if indegree[neighbor] == 0:
                queue.append(neighbor)
                queue.sort()

    if len(ordered_names) != len(tasks):
        cyclic = [name for name, degree in indegree.items() if degree > 0]
        for name in cyclic:
            dependency_conflicts.append({
                "type": "dependency_cycle",
                "task_name": name,
                "message": f"任务「{name}」存在循环依赖，当前仅按截止时间兜底安排",
            })
        remaining = [task["task_name"] for task in tasks if task["task_name"] not in ordered_names]
        ordered_names.extend(sorted(remaining))

    return [by_name[name] for name in ordered_names], dependency_conflicts


def extract_conflict_chain(variant_plan: dict) -> list[dict]:
    affected = {}
    for conflict in variant_plan.get("conflicts", []):
        task_name = conflict.get("task_name")
        if not task_name:
            continue
        bucket = affected.setdefault(task_name, {"task_name": task_name, "reasons": [], "dates": set()})
        if conflict.get("message"):
            bucket["reasons"].append(conflict["message"])
        if conflict.get("date"):
            bucket["dates"].add(conflict["date"])

    for overload in variant_plan.get("overload_days", []):
        day = overload.get("date")
        info = (variant_plan.get("daily_plan") or {}).get(day, {})
        for task in info.get("tasks", []):
            bucket = affected.setdefault(task["task_name"], {"task_name": task["task_name"], "reasons": [], "dates": set()})
            bucket["reasons"].append(f"{day} 过载，任务参与冲突链")
            bucket["dates"].add(day)

    chain = []
    for item in affected.values():
        chain.append({
            "task_name": item["task_name"],
            "dates": sorted(item["dates"]),
            "reasons": item["reasons"],
        })
    chain.sort(key=lambda item: (len(item["dates"]), len(item["reasons"])), reverse=True)
    return chain


def build_replan_context(tasks: list[dict], preview: dict, interrupt_task: dict | None = None) -> dict:
    selected_plan = select_variant_plan(preview, preview.get("selected_variant", "balanced"))
    conflict_chain = extract_conflict_chain(selected_plan)
    return {
        "tasks": tasks,
        "interrupt_task": interrupt_task,
        "selected_variant": selected_plan.get("id"),
        "summary": selected_plan.get("summary", {}),
        "overload_days": selected_plan.get("overload_days", []),
        "conflict_chain": conflict_chain,
    }
