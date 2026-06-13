from unittest.mock import AsyncMock, patch

import pytest

from application import dashboard_actions


@pytest.mark.asyncio
async def test_get_dashboard_action_delegates_to_service():
    with patch(
        "application.dashboard_actions.dashboard_query_service.get_dashboard_stats",
        new=AsyncMock(return_value={"status": "success", "today_completed": 3}),
    ) as mocked:
        result = await dashboard_actions.get_dashboard_action()

    mocked.assert_awaited_once_with()
    assert result["status"] == "success"
    assert result["today_completed"] == 3


@pytest.mark.asyncio
async def test_get_all_tasks_action_maps_status_to_status_filter():
    with patch(
        "application.dashboard_actions.task_query_service.get_all_tasks",
        new=AsyncMock(return_value={"status": "success", "tasks": [], "total": 0}),
    ) as mocked:
        result = await dashboard_actions.get_all_tasks_action(
            status="pending",
            keyword="周报",
            tag="work",
            priority=1,
            page=2,
            page_size=50,
        )

    mocked.assert_awaited_once_with(
        status_filter="pending",
        keyword="周报",
        tag="work",
        priority=1,
        page=2,
        page_size=50,
    )
    assert result["status"] == "success"


@pytest.mark.asyncio
async def test_get_streak_action_wraps_service_result():
    with patch(
        "application.dashboard_actions.get_streak_info",
        new=AsyncMock(return_value={"current_streak": 7, "completion_rate": 0.8}),
    ) as mocked:
        result = await dashboard_actions.get_streak_action()

    mocked.assert_awaited_once_with()
    assert result == {
        "status": "success",
        "current_streak": 7,
        "completion_rate": 0.8,
    }
