from unittest.mock import AsyncMock, patch

import pytest

from application import planning_actions


@pytest.mark.asyncio
async def test_preview_task_plan_action_delegates_to_service():
    with patch(
        "application.planning_actions.ai_planning_service.preview_task_plan",
        new=AsyncMock(return_value={"status": "success", "preview_id": "p1"}),
    ) as mocked:
        result = await planning_actions.preview_task_plan_action(
            [{"task_name": "写周报", "due_time": "2026-06-13"}],
            {"default_daily_hours": 6},
        )

    mocked.assert_awaited_once_with(
        [{"task_name": "写周报", "due_time": "2026-06-13"}],
        {"default_daily_hours": 6},
    )
    assert result["status"] == "success"
    assert result["preview_id"] == "p1"


@pytest.mark.asyncio
async def test_confirm_task_plan_action_delegates_to_service():
    with patch(
        "application.planning_actions.ai_planning_service.confirm_task_plan",
        new=AsyncMock(return_value={"status": "success", "selected_variant": "balanced"}),
    ) as mocked:
        result = await planning_actions.confirm_task_plan_action(
            "preview_1",
            "balanced",
            {"keep_existing": True},
        )

    mocked.assert_awaited_once_with("preview_1", "balanced", {"keep_existing": True})
    assert result["status"] == "success"
    assert result["selected_variant"] == "balanced"


@pytest.mark.asyncio
async def test_replan_tasks_with_acceptance_action_defaults_to_empty_names():
    with patch(
        "application.planning_actions.ai_planning_service.replan_tasks_with_acceptance",
        new=AsyncMock(return_value={"status": "success", "accepted_task_names": []}),
    ) as mocked:
        result = await planning_actions.replan_tasks_with_acceptance_action(
            [{"task_name": "写周报", "due_time": "2026-06-13"}],
            {"default_daily_hours": 6},
            {"task_name": "插入任务", "due_time": "2026-06-12"},
            None,
        )

    mocked.assert_awaited_once_with(
        [{"task_name": "写周报", "due_time": "2026-06-13"}],
        {"default_daily_hours": 6},
        {"task_name": "插入任务", "due_time": "2026-06-12"},
        [],
    )
    assert result["status"] == "success"


@pytest.mark.asyncio
async def test_get_smart_suggestions_action_passes_user_context():
    with patch(
        "application.planning_actions.ai_planning_service.get_smart_suggestions",
        new=AsyncMock(return_value={"status": "success", "suggestions": []}),
    ) as mocked:
        result = await planning_actions.get_smart_suggestions_action({"timezone": "Asia/Shanghai"})

    mocked.assert_awaited_once_with({"timezone": "Asia/Shanghai"})
    assert result["status"] == "success"
