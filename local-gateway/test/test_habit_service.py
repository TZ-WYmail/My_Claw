"""
习惯管理服务测试
"""
import tempfile
from pathlib import Path
import pytest

from services.habit_service import (
    create_habit,
    get_all_habits,
    get_habit,
    checkin_habit,
    get_habit_stats,
    delete_habit,
    init_habit_db,
)


@pytest.fixture(autouse=True)
async def setup_db(tmp_path, monkeypatch):
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_db_path = Path(temp_dir) / "test_habits.db"
        monkeypatch.setattr('config.DB_PATH', temp_db_path)
        monkeypatch.setattr('services.habit_service.DB_PATH', temp_db_path)
        await init_habit_db()
        yield


@pytest.mark.asyncio
async def test_create_habit():
    """测试创建习惯"""
    result = await create_habit(
        name="每天阅读",
        description="每天阅读30分钟",
        frequency="daily",
        target_count=1,
        reminder_time="09:00",
        color="#27ae60"
    )
    assert result["status"] == "success"
    assert result["name"] == "每天阅读"
    assert "habit_id" in result


@pytest.mark.asyncio
async def test_get_all_habits():
    """测试获取所有习惯"""
    # 创建两个习惯
    await create_habit(name="习惯1", frequency="daily")
    await create_habit(name="习惯2", frequency="weekly")

    habits = await get_all_habits()
    assert len(habits) == 2
    assert any(habit["name"] == "习惯1" for habit in habits)
    assert any(habit["name"] == "习惯2" for habit in habits)


@pytest.mark.asyncio
async def test_checkin_habit():
    """测试习惯打卡"""
    # 创建习惯
    create_result = await create_habit(name="每天运动", frequency="daily")
    habit_id = create_result["habit_id"]

    # 打卡
    checkin_result = await checkin_habit(habit_id, count=1, note="跑步30分钟")
    assert checkin_result["status"] == "success"

    # 验证打卡记录
    habit = await get_habit(habit_id)
    assert len(habit["checkins"]) == 1
    assert habit["checkins"][0]["count"] == 1
    assert habit["checkins"][0]["note"] == "跑步30分钟"


@pytest.mark.asyncio
async def test_get_habit_stats():
    """测试获取习惯统计"""
    # 创建习惯
    create_result = await create_habit(name="每天学习", frequency="daily")
    habit_id = create_result["habit_id"]

    # 打卡
    await checkin_habit(habit_id)

    # 获取统计
    stats = await get_habit_stats(habit_id)
    assert stats["status"] == "success"
    assert stats["total_count"] >= 1
    assert stats["total_days"] >= 1
    assert stats["week_count"] >= 1


@pytest.mark.asyncio
async def test_delete_habit():
    """测试删除习惯"""
    # 创建习惯
    create_result = await create_habit(name="临时习惯", frequency="daily")
    habit_id = create_result["habit_id"]

    # 删除习惯
    delete_result = await delete_habit(habit_id)
    assert delete_result["status"] == "success"

    # 验证已删除
    habit = await get_habit(habit_id)
    assert habit is None
