"""
AI planning replan service.

This module owns LLM-assisted conflict-chain reordering and acceptance/apply
logic so `ai_planning_service` can focus on public API orchestration.
"""
from __future__ import annotations

import json
import logging

import httpx

from config import ai_config

logger = logging.getLogger(__name__)


def estimate_impact_scope(task_name: str, context: dict, suggestion: dict | None = None) -> dict:
    conflict_chain = context.get("conflict_chain", [])
    matched = next((item for item in conflict_chain if item.get("task_name") == task_name), None)
    if not matched:
        return {"days": 1, "tasks": 1, "dependency_changes": False}

    reason_text = " ".join(matched.get("reasons", []))
    return {
        "days": max(1, len(matched.get("dates", [])) or 1),
        "tasks": max(1, len(conflict_chain)),
        "dependency_changes": "依赖" in reason_text or (suggestion or {}).get("reason_type") == "dependency_conflict",
    }


def parse_json_response(content: str) -> dict:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        import re

        json_match = re.search(r"```json\n(.*?)\n```", content, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(1))
        json_match = re.search(r"\{.*\}", content, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        raise ValueError("无法解析 AI 响应")


async def llm_reorder_conflict_tasks(context: dict) -> dict:
    if not ai_config.api_key:
        return {"status": "skipped", "reason": "AI API Key 未配置"}

    prompt = f"""你是任务重排专家。请针对一组存在连锁冲突的任务，给出重排建议。

当前任务:
{json.dumps(context["tasks"], ensure_ascii=False, indent=2)}

突发任务:
{json.dumps(context.get("interrupt_task"), ensure_ascii=False, indent=2)}

当前方案摘要:
{json.dumps(context["summary"], ensure_ascii=False, indent=2)}

过载日期:
{json.dumps(context["overload_days"], ensure_ascii=False, indent=2)}

冲突链:
{json.dumps(context["conflict_chain"], ensure_ascii=False, indent=2)}

要求:
1. 识别连锁冲突，不要只调整单个任务。
2. 优先通过重新排序、前移、后移、拆分来解决冲突。
3. 给出受影响任务顺序和建议动作。
4. 返回 JSON。

返回格式:
{{
  "reordered_tasks": [
    {{
      "task_name": "任务名",
      "suggestion": "advance|delay|split|keep",
      "reason": "原因",
      "target_day": "2026-05-20",
      "confidence": 0.8,
      "severity": "must_change|optional",
      "reason_type": "capacity_conflict|dependency_conflict|calendar_conflict|time_window_conflict|optimization",
      "impact_scope": {{
        "days": 2,
        "tasks": 3,
        "dependency_changes": true
      }}
    }}
  ],
  "chain_summary": ["冲突链说明1", "冲突链说明2"],
  "operator_notes": ["执行建议1", "执行建议2"]
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
                        {"role": "system", "content": "你擅长处理多任务连锁冲突与重排。"},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.2,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            parsed = parse_json_response(content)
            for item in parsed.get("reordered_tasks", []):
                if "confidence" not in item:
                    item["confidence"] = 0.7
                if "severity" not in item:
                    item["severity"] = "must_change" if item.get("suggestion") in {"advance", "delay", "split"} else "optional"
                if "reason_type" not in item:
                    item["reason_type"] = "optimization"
                if "impact_scope" not in item:
                    item["impact_scope"] = estimate_impact_scope(item.get("task_name", ""), context, item)
            return {"status": "success", **parsed}
    except Exception as exc:
        logger.exception("LLM 冲突链重排失败")
        return {"status": "error", "message": str(exc)}


def fallback_reorder_conflict_tasks(context: dict) -> dict:
    summary = []
    reordered_tasks = []
    operator_notes = []
    overload_days = context.get("overload_days", [])
    conflict_chain = context.get("conflict_chain", [])
    seen = set()

    for item in conflict_chain:
        task_name = item["task_name"]
        if task_name in seen:
            continue
        seen.add(task_name)
        target_day = item["dates"][0] if item["dates"] else ""
        suggestion = "delay"
        reason_type = "capacity_conflict"
        if any("依赖" in reason for reason in item["reasons"]):
            suggestion = "advance"
            reason_type = "dependency_conflict"
        elif any("时间块" in reason or "最早开始" in reason for reason in item["reasons"]):
            reason_type = "time_window_conflict"
        reordered_tasks.append({
            "task_name": task_name,
            "suggestion": suggestion,
            "reason": "；".join(item["reasons"][:2]) or "参与冲突链",
            "target_day": target_day,
            "confidence": 0.65 if suggestion == "delay" else 0.75,
            "severity": "must_change" if len(item["dates"]) >= 1 else "optional",
            "reason_type": reason_type,
            "impact_scope": estimate_impact_scope(task_name, context, {"reason_type": reason_type}),
        })

    if overload_days:
        summary.append(f"发现 {len(overload_days)} 个过载日，需按链路整体重排")
    if conflict_chain:
        summary.append(f"识别到 {len(conflict_chain)} 个冲突任务节点")
    operator_notes.append("优先处理依赖前置任务，再处理同日聚集任务")
    operator_notes.append("不要只延后单个任务，需保持链路顺序一致")

    return {
        "status": "success",
        "reordered_tasks": reordered_tasks,
        "chain_summary": summary,
        "operator_notes": operator_notes,
    }


def shift_task_day(task: dict, target_day: str, keep_time: bool = True) -> dict:
    updated = dict(task)
    if not target_day:
        return updated

    original_due = task.get("due_time", "")
    due_time_part = "09:00:00"
    if "T" in original_due:
        due_time_part = original_due.split("T", 1)[1]
    updated["due_time"] = f"{target_day}T{due_time_part}" if keep_time else f"{target_day}T09:00:00"

    for field in ("earliest_start", "start_time", "end_time"):
        value = task.get(field)
        if not value or "T" not in value:
            continue
        time_part = value.split("T", 1)[1]
        updated[field] = f"{target_day}T{time_part}"
    return updated


def apply_reorder_suggestions(
    tasks: list[dict],
    reordered_tasks: list[dict],
    accepted_task_names: list[str] | None = None,
) -> tuple[list[dict], list[dict]]:
    if not reordered_tasks:
        return tasks, []

    suggestion_map = {item["task_name"]: item for item in reordered_tasks if item.get("task_name")}
    accepted_set = set(accepted_task_names or suggestion_map.keys())
    updated_tasks = []
    applied_actions = []

    for task in tasks:
        suggestion = suggestion_map.get(task.get("task_name"))
        if not suggestion:
            updated_tasks.append(task)
            continue

        action = suggestion.get("suggestion", "keep")
        target_day = suggestion.get("target_day", "")
        updated_task = dict(task)
        accepted = task.get("task_name") in accepted_set

        if not accepted:
            applied_actions.append({
                "task_name": task["task_name"],
                "action": "rejected",
                "target_day": task.get("due_time", "")[:10],
                "reason": suggestion.get("reason", ""),
                "confidence": suggestion.get("confidence"),
                "severity": suggestion.get("severity"),
                "reason_type": suggestion.get("reason_type"),
                "impact_scope": suggestion.get("impact_scope"),
            })
            updated_tasks.append(updated_task)
            continue

        if action in {"advance", "delay"} and target_day:
            updated_task = shift_task_day(updated_task, target_day)
            applied_actions.append({
                "task_name": task["task_name"],
                "action": action,
                "target_day": target_day,
                "reason": suggestion.get("reason", ""),
                "confidence": suggestion.get("confidence"),
                "severity": suggestion.get("severity"),
                "reason_type": suggestion.get("reason_type"),
                "impact_scope": suggestion.get("impact_scope"),
            })
        elif action == "split" and target_day:
            updated_task = shift_task_day(updated_task, target_day)
            updated_task["estimated_minutes"] = max(30, int(updated_task.get("estimated_minutes", 60) * 0.8))
            applied_actions.append({
                "task_name": task["task_name"],
                "action": action,
                "target_day": target_day,
                "reason": suggestion.get("reason", ""),
                "confidence": suggestion.get("confidence"),
                "severity": suggestion.get("severity"),
                "reason_type": suggestion.get("reason_type"),
                "impact_scope": suggestion.get("impact_scope"),
            })
        else:
            applied_actions.append({
                "task_name": task["task_name"],
                "action": "keep",
                "target_day": updated_task.get("due_time", "")[:10],
                "reason": suggestion.get("reason", ""),
                "confidence": suggestion.get("confidence"),
                "severity": suggestion.get("severity"),
                "reason_type": suggestion.get("reason_type"),
                "impact_scope": suggestion.get("impact_scope"),
            })

        updated_tasks.append(updated_task)

    return updated_tasks, applied_actions
