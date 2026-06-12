from unittest.mock import AsyncMock, patch

import pytest

from application import mobile_actions


@pytest.mark.asyncio
async def test_quick_action_action_returns_error_for_unknown_action():
    result = await mobile_actions.quick_action_action("unknown", "target_1")

    assert result["status"] == "error"
    assert "Unknown action type" in result["message"]


@pytest.mark.asyncio
async def test_quick_action_action_delegates_to_handler():
    with patch.dict(
        "application.mobile_actions._QUICK_ACTION_DISPATCH",
        {"complete_task": AsyncMock(return_value={"status": "success", "task_id": "task_1"})},
        clear=True,
    ):
        result = await mobile_actions.quick_action_action("complete_task", "task_1")

    assert result == {
        "status": "success",
        "action": "complete_task",
        "result": {"status": "success", "task_id": "task_1"},
    }


@pytest.mark.asyncio
async def test_get_mobile_dashboard_action_aggregates_snapshot_and_runtime():
    with patch(
        "application.mobile_actions.mobile_service.get_mobile_dashboard_snapshot",
        new=AsyncMock(return_value={
            "today_tasks": [{"task_id": "task_1"}],
            "pending_count": 3,
            "week_tasks": 6,
            "habits": [{"habit_id": "habit_1", "checked_in": True}],
        }),
    ) as snapshot_mock, patch(
        "application.mobile_actions.pomodoro_service.get_pomodoro_stats",
        new=AsyncMock(return_value={"today_count": 2}),
    ) as pomodoro_mock, patch(
        "application.mobile_actions.sync_engine.get_sync_status",
        new=AsyncMock(return_value={"status": "success", "device_id": "dev_1"}),
    ) as sync_mock:
        result = await mobile_actions.get_mobile_dashboard_action()

    snapshot_mock.assert_awaited_once_with()
    pomodoro_mock.assert_awaited_once_with()
    sync_mock.assert_awaited_once_with()
    assert result["status"] == "success"
    assert result["data"]["today"]["task_count"] == 1
    assert result["data"]["today"]["pomodoro_count"] == 2
    assert result["data"]["summary"]["pending_tasks"] == 3


@pytest.mark.asyncio
async def test_voice_create_task_action_returns_created_task():
    with patch(
        "application.mobile_actions.voice_service.process_voice",
        new=AsyncMock(return_value={
            "status": "success",
            "text": "明天下午交周报",
            "task_created": True,
            "task": {"task_id": "task_1", "task_name": "交周报"},
        }),
    ) as mocked:
        result = await mobile_actions.voice_create_task_action("base64data")

    mocked.assert_awaited_once_with("base64data", source="mobile")
    assert result["status"] == "success"
    assert result["task"]["task_id"] == "task_1"


@pytest.mark.asyncio
async def test_queue_offline_batch_action_delegates_to_runtime_service():
    with patch(
        "application.mobile_actions.runtime_state_service.enqueue_offline_operations_batch",
        new=AsyncMock(return_value=2),
    ) as mocked:
        result = await mobile_actions.queue_offline_batch_action([
            {"operation": "update", "source": "device_1"},
            {"operation": "delete", "source": "device_1"},
        ])

    mocked.assert_awaited_once_with([
        {"operation": "update", "source": "device_1"},
        {"operation": "delete", "source": "device_1"},
    ])
    assert result == {"status": "success", "queued_count": 2}
