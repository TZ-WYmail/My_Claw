"""
高级功能测试 — 标签、子任务、番茄钟、日历
运行: cd local-gateway && python -m pytest test/test_advanced_features.py -v
"""
import pytest
import httpx

BASE_URL = "http://localhost:8900"


@pytest.fixture
def client():
    return httpx.Client(base_url=BASE_URL, timeout=10.0)


class TestTags:
    """标签管理测试"""

    def test_create_and_list_tags(self, client):
        """创建标签并列出"""
        # 创建标签
        resp = client.post("/api/advanced/tags", json={"name": "测试标签", "color": "#ff0000"})
        assert resp.status_code == 200

        # 列出标签
        resp = client.get("/api/advanced/tags")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert len(data["tags"]) > 0

    def test_add_tags_to_task(self, client):
        """为任务添加标签"""
        # 先创建任务
        resp = client.post("/api/task", json={
            "action": "add_task",
            "task_name": "标签测试任务",
            "due_time": "2026-04-22T10:00:00+08:00",
        })
        assert resp.status_code == 200
        task_id = resp.json().get("task_id")

        # 添加标签
        resp = client.post(f"/api/advanced/tasks/{task_id}/tags", json=["工作", "紧急"])
        assert resp.status_code == 200


class TestSubtasks:
    """子任务管理测试"""

    def test_create_subtask(self, client):
        """创建子任务"""
        # 先创建父任务
        resp = client.post("/api/task", json={
            "action": "add_task",
            "task_name": "父任务",
            "due_time": "2026-04-22T10:00:00+08:00",
        })
        assert resp.status_code == 200
        task_id = resp.json().get("task_id")

        # 创建子任务
        resp = client.post("/api/advanced/subtasks", json={
            "task_id": task_id,
            "name": "子任务1",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"

    def test_list_subtasks(self, client):
        """列出子任务"""
        # 先创建任务和子任务
        resp = client.post("/api/task", json={
            "action": "add_task",
            "task_name": "子任务测试父任务",
            "due_time": "2026-04-22T10:00:00+08:00",
        })
        task_id = resp.json().get("task_id")

        client.post("/api/advanced/subtasks", json={"task_id": task_id, "name": "子任务A"})

        # 列出子任务
        resp = client.get(f"/api/advanced/tasks/{task_id}/subtasks")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert len(data["subtasks"]) > 0


class TestPomodoro:
    """番茄钟测试"""

    def test_pomodoro_status(self, client):
        """获取番茄钟状态"""
        resp = client.get("/api/advanced/pomodoro/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"

    def test_pomodoro_stats(self, client):
        """获取番茄钟统计"""
        resp = client.get("/api/advanced/pomodoro/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert "today_count" in data
        assert "today_minutes" in data


class TestCalendar:
    """日历视图测试"""

    def test_calendar_view(self, client):
        """获取月历视图"""
        resp = client.get("/api/advanced/calendar/view?year=2026&month=4")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["view_type"] == "month"
        assert data["year"] == 2026
        assert data["month"] == 4
        assert "days" in data

    def test_create_calendar_event(self, client):
        """创建日历事件"""
        resp = client.post("/api/advanced/calendar/events", json={
            "title": "测试事件",
            "start_time": "2026-04-22T10:00:00+08:00",
            "end_time": "2026-04-22T11:00:00+08:00",
            "event_type": "meeting",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"


class TestShortcuts:
    """快捷键测试"""

    def test_list_shortcuts(self, client):
        """列出所有快捷键"""
        resp = client.get("/api/shortcuts/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert "shortcuts" in data

    def test_validate_shortcut(self, client):
        """验证快捷键格式"""
        resp = client.get("/api/shortcuts/validate?key_combo=ctrl+k")
        assert resp.status_code == 200
        data = resp.json()
        assert "valid" in data


class TestDownloadQueue:
    """下载队列测试"""

    def test_get_queue_status(self, client):
        """获取队列状态"""
        resp = client.get("/api/download/queue")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert "queue_length" in data
        assert "active_downloads" in data

    def test_bandwidth_limit(self, client):
        """带宽限制"""
        resp = client.post("/api/download/bandwidth?kb_per_second=1024")
        assert resp.status_code == 200

        resp = client.get("/api/download/bandwidth")
        assert resp.status_code == 200
        data = resp.json()
        assert data["limit_kb_s"] == 1024
