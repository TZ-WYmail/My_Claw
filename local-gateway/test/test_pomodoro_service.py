"""
番茄钟服务测试 — 测试 pomodoro_service.py 的功能
"""
import tempfile
import pytest
from pathlib import Path
from datetime import datetime, timedelta

# 导入被测试的模块
from services.pomodoro_service import (
    init_pomodoro_db,
    start_pomodoro,
    complete_pomodoro,
    interrupt_pomodoro,
    get_active_pomodoro,
    get_pomodoro_stats,
    get_pomodoro_history,
    _active_pomodoro,
)


@pytest.fixture(autouse=True)
async def setup_db(tmp_path, monkeypatch):
    """测试前设置临时数据库，测试后清理"""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_db_path = Path(temp_dir) / "test_pomodoro.db"
        monkeypatch.setattr('config.DB_PATH', temp_db_path)
        monkeypatch.setattr('services.pomodoro_service.DB_PATH', temp_db_path)
        # 直接创建必要的表，避免循环导入
        import aiosqlite
        temp_db_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(str(temp_db_path)) as db:
            # 创建tasks表
            await db.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id      TEXT PRIMARY KEY,
                    task_name    TEXT NOT NULL,
                    due_time     TEXT NOT NULL,
                    recurrence   TEXT NOT NULL DEFAULT 'once',
                    status       TEXT NOT NULL DEFAULT 'pending',
                    priority     INTEGER NOT NULL DEFAULT 2,
                    description  TEXT,
                    estimated_minutes INTEGER,
                    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at   TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """)
            # 创建pomodoro_sessions表
            await db.execute("""
                CREATE TABLE IF NOT EXISTS pomodoro_sessions (
                    session_id   TEXT PRIMARY KEY,
                    task_id      TEXT,
                    start_time   TEXT NOT NULL,
                    end_time     TEXT,
                    duration_minutes INTEGER NOT NULL,
                    actual_minutes   INTEGER,
                    status       TEXT NOT NULL DEFAULT 'running',
                    interrupt_reason TEXT,
                    FOREIGN KEY (task_id) REFERENCES tasks(task_id) ON DELETE SET NULL
                )
            """)
            await db.commit()
        # 重置全局状态
        import services.pomodoro_service as mod
        mod._active_pomodoro = None
        yield


@pytest.mark.asyncio
async def test_start_pomodoro():
    """测试开始番茄钟"""
    result = await start_pomodoro(task_id=None, duration_minutes=25)

    assert result["status"] == "success"
    assert "session_id" in result
    assert "start_time" in result
    assert result["duration_minutes"] == 25

    # 检查全局状态是否已设置
    active = await get_active_pomodoro()
    assert active is not None
    assert active["session_id"] == result["session_id"]


@pytest.mark.asyncio
async def test_start_pomodoro_when_active():
    """测试当有进行中的番茄钟时再启动新的"""
    # 先启动一个
    result1 = await start_pomodoro(duration_minutes=25)
    assert result1["status"] == "success"

    # 再启动一个
    result2 = await start_pomodoro(duration_minutes=15)
    assert result2["status"] == "error"
    assert "已有进行中的番茄钟" in result2["message"]


@pytest.mark.asyncio
async def test_complete_pomodoro():
    """测试完成番茄钟"""
    # 先启动
    start_result = await start_pomodoro(duration_minutes=25)
    assert start_result["status"] == "success"

    # 完成
    complete_result = await complete_pomodoro()
    assert complete_result["status"] == "success"
    assert "session_id" in complete_result
    assert "actual_minutes" in complete_result

    # 检查全局状态是否已清空
    active = await get_active_pomodoro()
    assert active is None


@pytest.mark.asyncio
async def test_complete_pomodoro_when_none():
    """测试没有进行中的番茄钟时尝试完成"""
    result = await complete_pomodoro()
    assert result["status"] == "error"
    assert "没有进行中的番茄钟" in result["message"]


@pytest.mark.asyncio
async def test_interrupt_pomodoro():
    """测试中断番茄钟"""
    # 先启动
    start_result = await start_pomodoro(duration_minutes=25)
    assert start_result["status"] == "success"

    # 中断
    interrupt_result = await interrupt_pomodoro(reason="测试中断")
    assert interrupt_result["status"] == "success"
    assert "session_id" in interrupt_result
    assert "actual_minutes" in interrupt_result
    assert interrupt_result["reason"] == "测试中断"

    # 检查全局状态是否已清空
    active = await get_active_pomodoro()
    assert active is None


@pytest.mark.asyncio
async def test_get_active_pomodoro():
    """测试获取进行中的番茄钟"""
    # 初始状态
    active = await get_active_pomodoro()
    assert active is None

    # 启动后
    await start_pomodoro(duration_minutes=30)
    active = await get_active_pomodoro()
    assert active is not None
    assert active["duration_minutes"] == 30
    assert active["status"] == "running"


@pytest.mark.asyncio
async def test_get_pomodoro_stats():
    """测试获取番茄钟统计"""
    # 先启动并完成一个番茄钟
    await start_pomodoro(duration_minutes=25)
    await complete_pomodoro()

    # 获取历史记录来验证
    history = await get_pomodoro_history()
    assert history["status"] == "success"
    assert len(history["sessions"]) >= 1

    # 获取统计
    stats = await get_pomodoro_stats(days=7)
    assert stats["status"] == "success"
    assert stats["total_count"] >= 1
    assert "daily_stats" in stats
    assert isinstance(stats["daily_stats"], list)
