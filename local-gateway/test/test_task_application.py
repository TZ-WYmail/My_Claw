from unittest.mock import AsyncMock, patch

import pytest

from application import task_actions


@pytest.mark.asyncio
async def test_execute_local_task_manager_add_task_delegates_to_service():
    payload = {
        "action": "add_task",
        "task_name": "写周报",
        "due_time": "2026-06-13T10:00:00",
        "recurrence": "once",
        "priority": 1,
        "description": "整理本周进展",
        "estimated_minutes": 60,
        "tags": ["work"],
        "start_time": "2026-06-13T09:00:00",
        "end_time": "2026-06-13T10:00:00",
    }

    with patch("application.task_actions.task_command_service.add_task", new=AsyncMock(return_value={
        "status": "success",
        "task_id": "task_1",
        "message": "ok",
    })) as mocked:
        result = await task_actions.execute_local_task_manager(payload)

    mocked.assert_awaited_once_with(
        task_name="写周报",
        due_time="2026-06-13T10:00:00",
        recurrence="once",
        priority=1,
        description="整理本周进展",
        estimated_minutes=60,
        tags=["work"],
        start_time="2026-06-13T09:00:00",
        end_time="2026-06-13T10:00:00",
    )
    assert result["status"] == "success"
    assert result["task_id"] == "task_1"


@pytest.mark.asyncio
async def test_execute_local_task_manager_returns_validation_error_for_missing_task_id():
    result = await task_actions.execute_local_task_manager({
        "action": "complete_task",
    })

    assert result["status"] == "error"
    assert "task_id" in result["message"]


@pytest.mark.asyncio
async def test_execute_batch_task_manager_create_filters_invalid_tasks():
    analyzed = {
        "status": "success",
        "analyzed": [
            {
                "task_name": "有效任务",
                "due_time": "2026-06-13T10:00:00",
                "recurrence": "once",
                "priority": 2,
                "description": "ok",
                "estimated_minutes": 30,
                "time_valid": True,
            },
            {
                "task_name": "无效任务",
                "due_time": "bad",
                "recurrence": "once",
                "priority": 2,
                "description": "bad",
                "estimated_minutes": 20,
                "time_valid": False,
            },
        ],
        "timeline": ["timeline"],
        "daily_timeline": ["daily"],
    }

    with patch("application.task_actions.task_command_service.analyze_tasks", new=AsyncMock(return_value=analyzed)) as analyze_mock, \
         patch("application.task_actions.task_command_service.batch_add_tasks", new=AsyncMock(return_value={
             "status": "success",
             "total": 1,
             "success_count": 1,
             "error_count": 0,
             "results": [{"task_id": "task_1", "status": "success"}],
         })) as batch_mock:
        result = await task_actions.execute_batch_task_manager({
            "action": "create",
            "tasks": [
                {"task_name": "有效任务", "due_time": "2026-06-13T10:00:00"},
                {"task_name": "无效任务", "due_time": "bad"},
            ],
        })

    analyze_mock.assert_awaited_once()
    batch_mock.assert_awaited_once_with([
        {
            "task_name": "有效任务",
            "due_time": "2026-06-13T10:00:00",
            "recurrence": "once",
            "priority": 2,
            "description": "ok",
            "estimated_minutes": 30,
            "start_time": None,
            "end_time": None,
        }
    ])
    assert result["status"] == "success"
    assert result["timeline"] == ["timeline"]
    assert result["daily_timeline"] == ["daily"]


@pytest.mark.asyncio
async def test_update_task_action_delegates_to_service():
    payload = {
        "task_name": "改周报",
        "due_time": "2026-06-13T12:00:00",
        "recurrence": "daily",
        "priority": 0,
        "description": "补充数据",
        "estimated_minutes": 45,
        "start_time": "2026-06-13T11:15:00",
        "end_time": "2026-06-13T12:00:00",
        "tags": ["work", "report"],
    }

    with patch("application.task_actions.task_command_service.update_task", new=AsyncMock(return_value={
        "status": "success",
        "task_id": "task_1",
    })) as mocked:
        result = await task_actions.update_task_action("task_1", payload)

    mocked.assert_awaited_once_with(
        task_id="task_1",
        task_name="改周报",
        due_time="2026-06-13T12:00:00",
        recurrence="daily",
        priority=0,
        description="补充数据",
        estimated_minutes=45,
        start_time="2026-06-13T11:15:00",
        end_time="2026-06-13T12:00:00",
        tags=["work", "report"],
    )
    assert result["status"] == "success"
