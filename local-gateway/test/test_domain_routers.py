from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers import calendar, pomodoro, subtasks, tags, task_detail


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(tags.router, prefix="/api")
    app.include_router(subtasks.router, prefix="/api")
    app.include_router(pomodoro.router, prefix="/api")
    app.include_router(calendar.router, prefix="/api")
    app.include_router(task_detail.router, prefix="/api")
    return TestClient(app)


def test_tags_router_uses_tag_actions(client):
    with patch(
        "routers.tags.create_tag_action",
        new=AsyncMock(return_value={"status": "success", "tags": [{"tag_id": 1, "name": "工作", "color": "#ff0000"}]}),
    ) as mocked:
        response = client.post("/api/tags", json={"name": "工作", "color": "#ff0000"})

    assert response.status_code == 200
    mocked.assert_awaited_once_with("工作", "#ff0000")


def test_subtasks_router_uses_subtask_actions(client):
    with patch(
        "routers.subtasks.create_subtask_action",
        new=AsyncMock(return_value={"status": "success", "subtasks": []}),
    ) as mocked:
        response = client.post("/api/subtasks", json={"task_id": "task_1", "name": "拆解"})

    assert response.status_code == 200
    mocked.assert_awaited_once_with("task_1", "拆解")


def test_pomodoro_router_uses_pomodoro_actions(client):
    with patch(
        "routers.pomodoro.get_pomodoro_status_action",
        new=AsyncMock(return_value={"status": "success", "active_session": None}),
    ) as mocked:
        response = client.get("/api/pomodoro/status")

    assert response.status_code == 200
    mocked.assert_awaited_once_with()


def test_calendar_router_uses_calendar_actions(client):
    with patch(
        "routers.calendar.get_calendar_view_action",
        new=AsyncMock(return_value={"status": "success", "view_type": "month", "year": 2026, "month": 6, "days": []}),
    ) as mocked:
        response = client.get("/api/calendar/view", params={"year": 2026, "month": 6})

    assert response.status_code == 200
    mocked.assert_awaited_once_with(2026, 6)


def test_task_detail_router_uses_task_detail_actions(client):
    with patch(
        "routers.task_detail.get_task_detail_action",
        new=AsyncMock(return_value={"status": "success", "task": None, "notes": [], "subtasks": [], "active_pomodoro": None, "weekly_neighbors": []}),
    ) as mocked:
        response = client.get("/api/tasks/task_1/detail")

    assert response.status_code == 200
    mocked.assert_awaited_once_with("task_1")
