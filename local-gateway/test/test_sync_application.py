from unittest.mock import AsyncMock, patch

import pytest

from application import sync_actions


@pytest.mark.asyncio
async def test_register_device_action_delegates_to_runtime_service():
    with patch(
        "application.sync_actions.runtime_state_service.register_sync_device",
        new=AsyncMock(return_value={"status": "success", "device_id": "dev_1"}),
    ) as mocked:
        result = await sync_actions.register_device_action({
            "device_id": "dev_1",
            "device_name": "Phone",
            "device_type": "mobile",
        })

    mocked.assert_awaited_once_with(
        device_id="dev_1",
        device_name="Phone",
        device_type="mobile",
    )
    assert result["status"] == "success"


@pytest.mark.asyncio
async def test_add_offline_operation_action_reports_queue_size():
    with patch(
        "application.sync_actions.runtime_state_service.enqueue_offline_operation",
        new=AsyncMock(return_value=None),
    ) as enqueue_mock, patch(
        "application.sync_actions.runtime_state_service.get_pending_offline_queue_size",
        new=AsyncMock(return_value=5),
    ) as size_mock:
        result = await sync_actions.add_offline_operation_action({
            "operation": "update",
            "table_name": "tasks",
            "record_id": "task_1",
            "data": {"task_name": "周报"},
            "source": "mobile_1",
        })

    enqueue_mock.assert_awaited_once_with(
        operation="update",
        table_name="tasks",
        record_id="task_1",
        data={"task_name": "周报"},
        source="mobile_1",
    )
    size_mock.assert_awaited_once_with()
    assert result["queue_size"] == 5


@pytest.mark.asyncio
async def test_pull_changes_action_wraps_payload():
    with patch(
        "application.sync_actions.sync_engine.generate_sync_payload",
        new=AsyncMock(return_value={"device_id": "dev_1", "changes": []}),
    ) as mocked:
        result = await sync_actions.pull_changes_action("2026-06-13T00:00:00")

    mocked.assert_awaited_once_with("2026-06-13T00:00:00")
    assert result == {"status": "success", "payload": {"device_id": "dev_1", "changes": []}}
