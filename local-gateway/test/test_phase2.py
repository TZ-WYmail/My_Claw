"""
Phase 2 功能测试 — AI规划、笔记、习惯、语音
运行: cd local-gateway && python -m pytest test/test_phase2.py -v
"""
import pytest
import httpx

BASE_URL = "http://localhost:8900"


@pytest.fixture
def client():
    return httpx.Client(base_url=BASE_URL, timeout=10.0)


class TestAIPlanning:
    """AI 规划功能测试"""

    def test_ai_suggestions(self, client):
        """获取智能建议"""
        resp = client.get("/api/ai/suggestions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert "suggestions" in data

    def test_ai_insights(self, client):
        """获取效率洞察"""
        resp = client.get("/api/ai/insights")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"

    def test_ai_estimate_time(self, client):
        """AI 时间估算"""
        resp = client.post("/api/ai/estimate", json={
            "task_name": "完成项目文档",
            "description": "撰写详细的技术文档",
            "category": "文档"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ["success", "error"]  # 可能没有 API key


class TestNotes:
    """笔记功能测试"""

    def test_create_note(self, client):
        """创建笔记"""
        resp = client.post("/api/notes/", json={
            "title": "测试笔记",
            "content": "这是笔记内容",
            "tags": ["test", "笔记"]
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        return data.get("note_id")

    def test_list_notes(self, client):
        """获取笔记列表"""
        resp = client.get("/api/notes/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert "notes" in data


class TestHabits:
    """习惯功能测试"""

    def test_create_habit(self, client):
        """创建习惯"""
        resp = client.post("/api/habits/", json={
            "name": "每日阅读",
            "description": "每天至少阅读30分钟",
            "frequency": "daily",
            "target_count": 1
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        return data.get("habit_id")

    def test_list_habits(self, client):
        """获取习惯列表"""
        resp = client.get("/api/habits/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert "habits" in data


class TestVoice:
    """语音功能测试（基础）"""

    def test_voice_memos_list(self, client):
        """获取语音备忘录列表"""
        resp = client.get("/api/voice/memos")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert "memos" in data
