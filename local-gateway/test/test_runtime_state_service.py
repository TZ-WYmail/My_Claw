import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


with tempfile.TemporaryDirectory() as temp_dir:
    temp_db_path = Path(temp_dir) / "test_runtime_state.db"
    with patch("config.DB_PATH", temp_db_path), \
         patch("services.task_service.DB_PATH", temp_db_path), \
         patch("services.runtime_state_service.DB_PATH", temp_db_path):
        from services import runtime_state_service, task_service


@pytest.fixture(autouse=True)
async def setup_db():
    await task_service.init_db()
    yield


@pytest.mark.asyncio
async def test_register_and_fetch_push_token():
    result = await runtime_state_service.register_push_token("device_1", "token_1", "ios")
    token = await runtime_state_service.get_push_token("device_1")

    assert result["status"] == "success"
    assert token is not None
    assert token["platform"] == "ios"


@pytest.mark.asyncio
async def test_enqueue_and_query_offline_queue_by_source():
    await runtime_state_service.mark_all_pending_offline_operations_synced()

    await runtime_state_service.enqueue_offline_operation(
        operation="update",
        table_name="tasks",
        record_id="task_1",
        data={"task_name": "周报"},
        source="device_a",
    )
    await runtime_state_service.enqueue_offline_operation(
        operation="delete",
        table_name="tasks",
        record_id="task_2",
        data=None,
        source="device_b",
    )

    result = await runtime_state_service.get_pending_offline_queue(source="device_a")

    assert result["status"] == "success"
    assert result["pending"] == 1
    assert result["operations"][0]["source"] == "device_a"


@pytest.mark.asyncio
async def test_register_device_and_heartbeat():
    created = await runtime_state_service.register_sync_device("device_1", "My Phone", "mobile")
    heartbeat = await runtime_state_service.heartbeat_sync_device("device_1")
    devices = await runtime_state_service.list_sync_devices()

    assert created["status"] == "success"
    assert heartbeat["status"] == "success"
    assert devices["total"] >= 1
    assert any(device["device_id"] == "device_1" for device in devices["devices"])
