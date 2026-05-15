"""
AI 规划日历联动测试
"""
import pytest
import httpx

BASE_URL = "http://localhost:8900"


@pytest.fixture
def client():
    return httpx.Client(base_url=BASE_URL, timeout=10.0)


class TestAIPlanningCalendar:
    def test_preview_includes_calendar_conflict_data(self, client):
        event_resp = client.post("/api/advanced/calendar/events", json={
            "title": "测试会议",
            "start_time": "2026-05-20T09:00:00+08:00",
            "end_time": "2026-05-20T11:00:00+08:00",
            "event_type": "meeting",
        })
        assert event_resp.status_code == 200

        resp = client.post("/api/ai/plan/preview", json={
            "tasks": [
                {"task_name": "写周报", "due_time": "2026-05-20", "estimated_minutes": 120},
                {"task_name": "整理邮件", "due_time": "2026-05-20", "estimated_minutes": 30},
            ],
            "constraints": {
                "default_daily_hours": 6,
                "weekend_daily_hours": 4,
                "buffer_ratio": 0.2,
            },
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert "calendar_load" in data
        assert "calendar_events" in data
        assert isinstance(data["daily_plan"], dict)
        assert "variant_plans" in data
        assert "balanced" in data["variant_plans"]
