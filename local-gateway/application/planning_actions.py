"""
AI planning application entrypoints.

This module centralizes planning use cases so routers and future internal
callers share one orchestration layer above the planning service.
"""
from __future__ import annotations

from services import ai_planning_service


async def decompose_task_action(task_name: str, description: str | None = None) -> dict:
    return await ai_planning_service.decompose_task(task_name, description)


async def generate_task_plan_action(tasks: list[dict], constraints: dict | None = None) -> dict:
    return await ai_planning_service.generate_task_plan(tasks, constraints)


async def preview_task_plan_action(tasks: list[dict], constraints: dict | None = None) -> dict:
    return await ai_planning_service.preview_task_plan(tasks, constraints)


async def confirm_task_plan_action(
    preview_id: str,
    selected_variant: str = "balanced",
    user_adjustments: dict | None = None,
) -> dict:
    return await ai_planning_service.confirm_task_plan(
        preview_id,
        selected_variant,
        user_adjustments,
    )


async def replan_tasks_action(
    tasks: list[dict],
    constraints: dict | None = None,
    interrupt_task: dict | None = None,
) -> dict:
    return await ai_planning_service.replan_tasks(tasks, constraints, interrupt_task)


async def replan_tasks_with_acceptance_action(
    tasks: list[dict],
    constraints: dict | None = None,
    interrupt_task: dict | None = None,
    accepted_task_names: list[str] | None = None,
) -> dict:
    return await ai_planning_service.replan_tasks_with_acceptance(
        tasks,
        constraints,
        interrupt_task,
        accepted_task_names or [],
    )


async def estimate_task_time_action(
    task_name: str,
    description: str | None = None,
    category: str | None = None,
) -> dict:
    return await ai_planning_service.estimate_task_time(task_name, description, category)


async def get_smart_suggestions_action(user_context: dict | None = None) -> dict:
    return await ai_planning_service.get_smart_suggestions(user_context)


async def analyze_task_patterns_action() -> dict:
    return await ai_planning_service.analyze_task_patterns()
