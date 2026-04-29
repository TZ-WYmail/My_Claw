"""
服务单元测试 — 不依赖 HTTP 服务器，直接测试服务函数
运行: cd local-gateway && conda run -n claude python -m pytest test/test_services.py -v
"""
import asyncio
import pytest

from services import task_service
from services import tag_service, subtask_service, pomodoro_service
from services import calendar_sync_service, note_service, habit_service
from services.shortcut_service import (
    get_all_shortcuts,
    register_shortcut,
    validate_key_combo,
)


@pytest.fixture(scope="module")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


class TestTags:
    """标签管理测试"""

    @pytest.mark.asyncio
    async def test_create_and_get_tags(self):
        """创建和获取标签"""
        result = await tag_service.create_tag("测试标签", "#ff0000")
        assert result["status"] == "success"
        tag_id = result["tag_id"]

        tags = await tag_service.get_all_tags()
        assert len(tags) > 0

        await tag_service.delete_tag(tag_id)


class TestSubtasks:
    """子任务管理测试"""

    @pytest.mark.asyncio
    async def test_create_subtask(self):
        """创建子任务"""
        task_result = await task_service.add_task(
            task_name="父任务测试",
            due_time="2026-04-22T10:00:00",
        )
        assert task_result["status"] == "success"
        task_id = task_result["task_id"]

        subtask_result = await subtask_service.create_subtask(task_id, "子任务1")
        assert subtask_result["status"] == "success"

        subtasks = await subtask_service.get_subtasks(task_id)
        assert len(subtasks) > 0


class TestPomodoro:
    """番茄钟测试"""

    @pytest.mark.asyncio
    async def test_pomodoro_stats(self):
        """获取番茄钟统计"""
        stats = await pomodoro_service.get_pomodoro_stats()
        assert stats["status"] == "success"
        assert "today_count" in stats
        assert "today_minutes" in stats


class TestCalendar:
    """日历视图测试"""

    @pytest.mark.asyncio
    async def test_calendar_view(self):
        """获取月历视图"""
        result = await calendar_sync_service.get_calendar_view(2026, 4)
        assert result["status"] == "success"
        assert result["view_type"] == "month"
        assert "days" in result


class TestShortcuts:
    """快捷键测试"""

    def test_validate_shortcut(self):
        """验证快捷键格式"""
        valid, msg = validate_key_combo("ctrl+k")
        assert valid is True

        valid, msg = validate_key_combo("invalid")
        assert valid is False

    def test_get_shortcuts(self):
        """获取所有快捷键"""
        result = get_all_shortcuts()
        assert result["status"] == "success"
        assert "shortcuts" in result


class TestNotes:
    """笔记管理测试"""

    @pytest.mark.asyncio
    async def test_create_note(self):
        """创建笔记"""
        result = await note_service.create_note(
            title="测试笔记",
            content="笔记内容",
            tags=["test", "笔记"],
        )
        assert result["status"] == "success"
        note_id = result["note_id"]

        note = await note_service.get_note(note_id)
        assert note is not None
        assert note["title"] == "测试笔记"

        await note_service.delete_note(note_id)


class TestHabits:
    """习惯管理测试"""

    @pytest.mark.asyncio
    async def test_create_habit(self):
        """创建习惯"""
        result = await habit_service.create_habit(
            name="每日测试",
            description="测试习惯",
            frequency="daily",
        )
        assert result["status"] == "success"
        habit_id = result["habit_id"]

        habits = await habit_service.get_all_habits()
        assert len(habits) > 0


class TestTasksAdvanced:
    """任务高级属性测试"""

    @pytest.mark.asyncio
    async def test_create_task_with_priority(self):
        """创建带优先级的任务"""
        result = await task_service.add_task(
            task_name="高优先级任务",
            due_time="2026-04-22T10:00:00",
            priority=0,  # 紧急
            description="这是描述",
            estimated_minutes=60,
            tags=["紧急", "工作"],
        )
        assert result["status"] == "success"
        task_id = result["task_id"]

        tasks = await task_service.get_all_tasks(
            status_filter="active",
            keyword="高优先级",
        )
        assert tasks["status"] == "success"
