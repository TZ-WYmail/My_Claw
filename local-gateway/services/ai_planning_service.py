"""
AI 智能规划服务 — 任务拆解、智能建议、时间估算
"""
from __future__ import annotations

import json
import logging
from math import ceil
from datetime import datetime, timedelta
from typing import Optional

import httpx

from config import ai_config
from services import task_service
from services import pomodoro_service
from services import calendar_sync_service

logger = logging.getLogger(__name__)

_planning_previews: dict[str, dict] = {}


async def decompose_task(task_name: str, description: str = None) -> dict:
    """
    使用 AI 将复杂任务拆解为子任务
    """
    if not ai_config.api_key:
        return {
            "status": "error",
            "message": "AI API Key 未配置",
        }

    prompt = f"""请将以下任务拆解为具体的子任务列表。

任务名称: {task_name}
任务描述: {description or "无"}

要求:
1. 将任务拆解为 3-8 个可执行的子任务
2. 每个子任务应有明确的名称和预估完成时间（分钟）
3. 子任务之间有逻辑顺序，标明依赖关系
4. 返回 JSON 格式

返回格式:
{{
    "subtasks": [
        {{
            "name": "子任务名称",
            "estimated_minutes": 30,
            "description": "子任务描述",
            "depends_on": []  // 依赖的子任务索引（空表示无依赖）
        }}
    ],
    "total_estimated_minutes": 120,
    "difficulty": "easy|medium|hard",
    "tips": ["执行建议1", "执行建议2"]
}}
"""

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{ai_config.api_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {ai_config.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": ai_config.model,
                    "messages": [
                        {"role": "system", "content": "你是一个任务规划专家，擅长将复杂任务拆解为可执行的子任务。"},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.3,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]

            # 提取 JSON
            try:
                # 尝试直接解析
                result = json.loads(content)
            except json.JSONDecodeError:
                # 尝试从 markdown 代码块中提取
                import re
                json_match = re.search(r'```json\n(.*?)\n```', content, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group(1))
                else:
                    # 尝试从文本中提取 JSON
                    json_match = re.search(r'\{.*\}', content, re.DOTALL)
                    if json_match:
                        result = json.loads(json_match.group())
                    else:
                        raise ValueError("无法解析 AI 响应")

            return {
                "status": "success",
                "decomposition": result,
            }

    except Exception as e:
        logger.exception("AI 任务拆解失败")
        return {
            "status": "error",
            "message": f"AI 任务拆解失败: {e}",
        }


async def generate_task_plan(tasks: list[dict], constraints: dict = None) -> dict:
    """
    基于任务列表和约束条件生成优化的时间安排
    """
    if not ai_config.api_key:
        return {
            "status": "error",
            "message": "AI API Key 未配置",
        }

    tasks_str = json.dumps(tasks, ensure_ascii=False, indent=2)
    constraints_str = json.dumps(constraints or {}, ensure_ascii=False, indent=2)

    prompt = f"""作为时间管理专家，请为以下任务制定最优执行计划。

待规划任务:
{tasks_str}

约束条件:
{constraints_str}

要求:
1. 考虑任务优先级和截止日期
2. 合理安排每日工作量（不超过6小时/天）
3. 为高优先级任务预留缓冲时间
4. 识别可以并行处理的任务
5. 返回详细的每日计划

返回 JSON 格式:
{{
    "daily_plans": [
        {{
            "date": "2026-04-22",
            "total_hours": 5.5,
            "tasks": [
                {{
                    "task_name": "任务名",
                    "allocated_hours": 2,
                    "time_slot": "09:00-11:00",
                    "notes": "执行建议"
                }}
            ]
        }}
    ],
    "parallel_groups": [["任务1", "任务2"]],  // 可并行任务
    "risk_warnings": ["风险提示"],
    "optimization_tips": ["优化建议"]
}}
"""

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{ai_config.api_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {ai_config.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": ai_config.model,
                    "messages": [
                        {"role": "system", "content": "你是时间管理专家，擅长制定高效的任务执行计划。"},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.3,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]

            # 提取 JSON
            try:
                result = json.loads(content)
            except json.JSONDecodeError:
                import re
                json_match = re.search(r'```json\n(.*?)\n```', content, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group(1))
                else:
                    json_match = re.search(r'\{.*\}', content, re.DOTALL)
                    if json_match:
                        result = json.loads(json_match.group())
                    else:
                        raise ValueError("无法解析 AI 响应")

            return {
                "status": "success",
                "plan": result,
            }

    except Exception as e:
        logger.exception("AI 计划生成失败")
        return {
            "status": "error",
            "message": f"AI 计划生成失败: {e}",
        }


def _build_preview_id() -> str:
    return f"preview_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"


def _normalize_tasks(tasks: list[dict]) -> list[dict]:
    normalized = []
    for task in tasks:
        due_raw = (task.get("due_time") or "").strip()
        due_norm = task_service._normalize_time(due_raw) if due_raw else ""
        earliest_start_raw = (task.get("earliest_start") or "").strip()
        earliest_start_norm = task_service._normalize_time(earliest_start_raw) if earliest_start_raw else ""
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


def _capacity_template(constraints: dict | None) -> dict:
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


def _variant_definitions(capacity: dict) -> list[dict]:
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


async def _collect_calendar_load(date_from: str, date_to: str) -> dict[str, float]:
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


async def _collect_calendar_events(date_from: str, date_to: str) -> dict[str, list[dict]]:
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


def _build_variant_plan(
    normalized_tasks: list[dict],
    analyzed: dict,
    variant: dict,
    calendar_load: dict[str, float],
    calendar_events: dict[str, list[dict]],
) -> dict:
    capacity = variant["constraints"]
    strategy = variant["id"]
    daily_plan: dict[str, dict] = {}
    conflicts = []
    overload_days = []
    infeasible_tasks = []
    completion_days: dict[str, str] = {}

    def ensure_day(day: str) -> dict:
        if day not in daily_plan:
            weekday = task_service._date_to_weekday(day)
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
    valid_tasks, dependency_conflicts = _topological_sort_tasks(valid_tasks)
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
        weekday = info.get("weekday") or task_service._date_to_weekday(day)
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


def _select_variant_plan(preview: dict, selected_variant: str) -> dict:
    variant_plans = preview.get("variant_plans", {})
    return (
        variant_plans.get(selected_variant)
        or variant_plans.get("balanced")
        or next(iter(variant_plans.values()), {})
    )


def _task_schedule_from_variant(task: dict, variant_plan: dict) -> dict:
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


def _topological_sort_tasks(tasks: list[dict]) -> tuple[list[dict], list[dict]]:
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


async def preview_task_plan(tasks: list[dict], constraints: dict | None = None) -> dict:
    normalized_tasks = _normalize_tasks(tasks)
    analyzed = await task_service.analyze_tasks(normalized_tasks)
    capacity = _capacity_template(constraints)
    variant_defs = _variant_definitions(capacity)

    valid_dates = [task["due_time"][:10] for task in normalized_tasks if task.get("time_valid")]
    if valid_dates:
        date_from, date_to = min(valid_dates), max(valid_dates)
        calendar_load = await _collect_calendar_load(date_from, date_to)
        calendar_events = await _collect_calendar_events(date_from, date_to)
    else:
        calendar_load = {}
        calendar_events = {}
    variant_plans = {
        variant["id"]: _build_variant_plan(
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

    preview_id = _build_preview_id()
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
    _planning_previews[preview_id] = result
    return result


async def confirm_task_plan(preview_id: str, selected_variant: str = "balanced", user_adjustments: dict | None = None) -> dict:
    preview = _planning_previews.get(preview_id)
    if not preview:
        return {"status": "error", "message": "preview_id 不存在或已过期"}

    tasks = preview["normalized_tasks"]
    variant_plan = _select_variant_plan(preview, selected_variant)
    if user_adjustments:
        task_overrides = user_adjustments.get("tasks", {})
        adjusted = []
        for task in tasks:
            override = task_overrides.get(task["task_name"], {})
            adjusted.append({**task, **override})
        tasks = adjusted

    create_payload = [
        {
            "task_name": task["task_name"],
            "due_time": task["due_time"],
            "start_time": _task_schedule_from_variant(task, variant_plan).get("start_time"),
            "end_time": _task_schedule_from_variant(task, variant_plan).get("end_time"),
            "recurrence": task.get("recurrence", "once"),
            "estimated_minutes": task.get("estimated_minutes"),
            "description": (
                task.get("description")
                or f"AI 安排任务方案：{variant_plan.get('label', selected_variant)}；"
                   f"计划执行日：{'、'.join(_task_schedule_from_variant(task, variant_plan).get('scheduled_days', [])) or task['due_time'][:10]}；"
                   f"时间块：{'、'.join(block['time_slot'] for block in _task_schedule_from_variant(task, variant_plan).get('time_blocks', [])) or '待定'}"
            ),
            "priority": task.get("priority", 2),
        }
        for task in tasks if task.get("time_valid")
    ]

    created = await task_service.batch_add_tasks(create_payload)
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


async def replan_tasks(tasks: list[dict], constraints: dict | None = None, interrupt_task: dict | None = None) -> dict:
    merged_tasks = list(tasks)
    affected_tasks = []
    if interrupt_task:
        merged_tasks.append(interrupt_task)
        affected_tasks = [task.get("task_name") for task in tasks]

    preview = await preview_task_plan(merged_tasks, constraints)
    selected_plan = _select_variant_plan(preview, preview.get("selected_variant", "balanced"))
    postpone_candidates = []
    impact_summary = []
    risk_changes = []
    for day in sorted(selected_plan.get("daily_plan", {}).keys()):
        info = selected_plan["daily_plan"][day]
        if not info.get("overload"):
            continue
        ranked = sorted(
            info.get("tasks", []),
            key=lambda item: (item.get("hours", 0), item.get("due_date", "")),
            reverse=True,
        )
        for item in ranked:
            if item["task_name"] not in postpone_candidates:
                postpone_candidates.append(item["task_name"])
        if len(postpone_candidates) >= 5:
            break

    if interrupt_task:
        impact_summary.append(f"已插入突发任务「{interrupt_task.get('task_name', '')}」")
    if selected_plan.get("summary", {}).get("overload_day_count", 0) > 0:
        impact_summary.append(f"当前方案出现 {selected_plan['summary']['overload_day_count']} 个过载日")
    if postpone_candidates:
        impact_summary.append(f"建议优先后移：{'、'.join(postpone_candidates[:3])}")
    for conflict in selected_plan.get("conflicts", []):
        if conflict.get("type") in {"capacity_shortage", "dependency_violation_risk", "earliest_start_pressure"}:
            risk_changes.append(conflict["message"])

    return {
        "status": "success",
        "affected_tasks": affected_tasks,
        "postpone_candidates": postpone_candidates,
        "impact_summary": impact_summary,
        "risk_changes": risk_changes[:5],
        "new_plan": preview,
    }


async def estimate_task_time(task_name: str, description: str = None, category: str = None) -> dict:
    """
    基于历史数据和AI分析估算任务完成时间
    """
    # 先查询历史相似任务
    historical_data = await _get_historical_task_data(task_name, category)

    if not ai_config.api_key:
        # 使用历史数据估算
        if historical_data:
            avg_time = sum(h["estimated_minutes"] for h in historical_data) / len(historical_data)
            return {
                "status": "success",
                "estimated_minutes": int(avg_time),
                "source": "historical",
                "confidence": "medium",
                "based_on": len(historical_data),
            }
        return {
            "status": "success",
            "estimated_minutes": 60,
            "source": "default",
            "confidence": "low",
        }

    historical_str = json.dumps(historical_data, ensure_ascii=False, indent=2)

    prompt = f"""请估算以下任务的完成时间。

任务名称: {task_name}
任务描述: {description or "无"}
任务类别: {category or "未分类"}

历史相似任务数据:
{historical_str}

要求:
1. 综合考虑任务复杂度、历史数据和常见工作模式
2. 给出乐观、正常、悲观三种估算
3. 返回 JSON 格式

返回格式:
{{
    "estimated_minutes": 120,
    "optimistic": 90,
    "pessimistic": 180,
    "confidence": "high|medium|low",
    "reasoning": "估算理由...",
    "factors": ["影响因素1", "影响因素2"]
}}
"""

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{ai_config.api_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {ai_config.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": ai_config.model,
                    "messages": [
                        {"role": "system", "content": "你是项目管理专家，擅长估算任务完成时间。"},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.2,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]

            try:
                result = json.loads(content)
            except json.JSONDecodeError:
                import re
                json_match = re.search(r'```json\n(.*?)\n```', content, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group(1))
                else:
                    json_match = re.search(r'\{.*\}', content, re.DOTALL)
                    if json_match:
                        result = json.loads(json_match.group())
                    else:
                        raise ValueError("无法解析 AI 响应")

            result["source"] = "ai"
            return {
                "status": "success",
                "estimation": result,
            }

    except Exception as e:
        logger.exception("AI 时间估算失败")
        # 回退到历史数据
        if historical_data:
            avg_time = sum(h["estimated_minutes"] for h in historical_data) / len(historical_data)
            return {
                "status": "success",
                "estimated_minutes": int(avg_time),
                "source": "historical_fallback",
                "confidence": "medium",
            }
        return {
            "status": "error",
            "message": f"AI 时间估算失败: {e}",
        }


async def _get_historical_task_data(task_name: str, category: str = None) -> list[dict]:
    """获取历史相似任务数据"""
    # 从数据库查询已完成的任务
    result = await task_service.get_all_tasks(
        status_filter="completed",
        keyword=task_name.split()[0] if task_name else "",
        page=1,
        page_size=10,
    )

    historical = []
    for task in result.get("tasks", []):
        if task.get("estimated_minutes"):
            historical.append({
                "task_name": task["task_name"],
                "estimated_minutes": task["estimated_minutes"],
                "created_at": task.get("created_at"),
            })

    return historical


async def get_smart_suggestions(user_context: dict = None) -> dict:
    """
    基于当前任务状态提供智能建议
    """
    # 获取当前任务状态
    weekly_plan = await task_service.get_weekly_plan()
    pending_tasks = [t for t in weekly_plan.get("tasks", []) if t["status"] == "待执行"]

    # 获取番茄钟统计
    pomodoro_stats = await pomodoro_service.get_pomodoro_stats()

    suggestions = []

    # 分析任务优先级分布
    urgent_count = sum(1 for t in pending_tasks if t.get("priority", 2) == 0)
    high_count = sum(1 for t in pending_tasks if t.get("priority", 2) == 1)

    if urgent_count > 0:
        suggestions.append({
            "type": "urgent",
            "priority": "high",
            "message": f"有 {urgent_count} 个紧急任务需要立即处理",
            "action": "查看紧急任务",
        })

    if high_count > 3:
        suggestions.append({
            "type": "warning",
            "priority": "medium",
            "message": "高优先级任务较多，建议重新评估优先级",
            "action": "调整优先级",
        })

    # 番茄钟专注度分析
    today_minutes = pomodoro_stats.get("today_minutes", 0)
    if today_minutes < 60:
        suggestions.append({
            "type": "tip",
            "priority": "low",
            "message": "今日专注时间较短，建议开启番茄钟提升效率",
            "action": "开始番茄钟",
        })

    # 截止日期提醒
    now = datetime.now()
    for task in pending_tasks:
        try:
            due = datetime.fromisoformat(task["due_time"].replace("Z", "+00:00"))
            if (due - now).days <= 1:
                suggestions.append({
                    "type": "deadline",
                    "priority": "high",
                    "message": f"任务 '{task['task_name']}' 即将到期",
                    "action": "立即处理",
                    "task_id": task["task_id"],
                })
        except:
            pass

    # 工作负载平衡建议
    if len(pending_tasks) > 10:
        suggestions.append({
            "type": "workload",
            "priority": "medium",
            "message": f"本周有 {len(pending_tasks)} 个待办任务，建议拆分或推迟部分任务",
            "action": "重新规划",
        })

    return {
        "status": "success",
        "suggestions": suggestions,
        "stats": {
            "pending_count": len(pending_tasks),
            "urgent_count": urgent_count,
            "high_count": high_count,
            "today_focus_minutes": today_minutes,
        },
    }


async def analyze_task_patterns() -> dict:
    """
    分析用户任务完成模式，提供效率洞察
    """
    # 获取所有任务
    all_tasks = await task_service.get_all_tasks(
        status_filter="completed",
        page=1,
        page_size=100,
    )

    completed_tasks = all_tasks.get("tasks", [])

    if len(completed_tasks) < 5:
        return {
            "status": "success",
            "message": "数据不足，请继续使用以生成分析报告",
            "insights": [],
        }

    # 分析完成时间分布
    weekday_counts = {i: 0 for i in range(7)}
    hour_counts = {i: 0 for i in range(24)}

    for task in completed_tasks:
        try:
            created = datetime.fromisoformat(task.get("created_at", "").replace("Z", "+00:00"))
            weekday_counts[created.weekday()] += 1
            hour_counts[created.hour] += 1
        except:
            pass

    # 找出最高效的时间段
    best_weekday = max(weekday_counts, key=weekday_counts.get)
    best_hour = max(hour_counts, key=hour_counts.get)

    weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

    insights = [
        {
            "type": "pattern",
            "title": "高效时间段",
            "description": f"你在 {weekdays[best_weekday]} {best_hour}:00 左右完成任务最多",
            "recommendation": "建议将重要任务安排在这个时间段",
        },
        {
            "type": "stats",
            "title": "任务完成统计",
            "description": f"已完成 {len(completed_tasks)} 个任务",
            "details": {
                "avg_per_day": round(len(completed_tasks) / 7, 1),
                "most_productive_day": weekdays[best_weekday],
            },
        },
    ]

    return {
        "status": "success",
        "insights": insights,
        "weekday_distribution": weekday_counts,
        "hour_distribution": hour_counts,
    }
