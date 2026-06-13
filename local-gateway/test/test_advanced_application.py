from unittest.mock import AsyncMock, patch

import pytest

from application import advanced_actions


@pytest.mark.asyncio
async def test_create_tag_action_refreshes_tag_list_after_success():
    with patch(
        "application.advanced_actions.tag_service.create_tag",
        new=AsyncMock(return_value={"status": "success"}),
    ) as create_mock, patch(
        "application.advanced_actions.tag_service.get_all_tags",
        new=AsyncMock(return_value=[{"tag_id": 1, "name": "工作"}]),
    ) as list_mock:
        result = await advanced_actions.create_tag_action("工作", "#ff0000")

    create_mock.assert_awaited_once_with("工作", "#ff0000")
    list_mock.assert_awaited_once_with()
    assert result == {"status": "success", "tags": [{"tag_id": 1, "name": "工作"}]}


@pytest.mark.asyncio
async def test_create_subtask_action_refreshes_subtasks_after_success():
    with patch(
        "application.advanced_actions.subtask_service.create_subtask",
        new=AsyncMock(return_value={"status": "success"}),
    ) as create_mock, patch(
        "application.advanced_actions.subtask_service.get_subtasks",
        new=AsyncMock(return_value=[{"subtask_id": "sub_1", "name": "拆解"}]),
    ) as list_mock:
        result = await advanced_actions.create_subtask_action("task_1", "拆解")

    create_mock.assert_awaited_once_with("task_1", "拆解")
    list_mock.assert_awaited_once_with("task_1")
    assert result["status"] == "success"
    assert result["subtasks"][0]["subtask_id"] == "sub_1"


@pytest.mark.asyncio
async def test_start_pomodoro_action_returns_active_session():
    with patch(
        "application.advanced_actions.pomodoro_service.start_pomodoro",
        new=AsyncMock(return_value={"status": "success"}),
    ) as start_mock, patch(
        "application.advanced_actions.pomodoro_service.get_active_pomodoro",
        new=AsyncMock(return_value={"session_id": "p1"}),
    ) as active_mock:
        result = await advanced_actions.start_pomodoro_action("task_1", 25)

    start_mock.assert_awaited_once_with("task_1", 25)
    active_mock.assert_awaited_once_with()
    assert result == {"status": "success", "active_session": {"session_id": "p1"}}


@pytest.mark.asyncio
async def test_batch_update_tasks_action_normalizes_optional_tag_lists():
    with patch(
        "application.advanced_actions.task_command_service.batch_update_tasks",
        new=AsyncMock(return_value={"status": "success", "updated": 2}),
    ) as mocked:
        result = await advanced_actions.batch_update_tasks_action(
            task_ids=["task_1", "task_2"],
            priority=1,
            due_time="2026-06-13T10:00:00",
            tags_add=None,
            tags_remove=None,
        )

    mocked.assert_awaited_once_with(
        task_ids=["task_1", "task_2"],
        priority=1,
        due_time="2026-06-13T10:00:00",
        tags_add=[],
        tags_remove=[],
    )
    assert result["status"] == "success"


@pytest.mark.asyncio
async def test_get_task_detail_action_delegates_to_task_detail_service():
    with patch(
        "application.advanced_actions.task_detail_service.get_task_detail",
        new=AsyncMock(return_value={"status": "success", "task": {"task_id": "task_1"}}),
    ) as mocked:
        result = await advanced_actions.get_task_detail_action("task_1")

    mocked.assert_awaited_once_with("task_1")
    assert result["status"] == "success"
    assert result["task"]["task_id"] == "task_1"
