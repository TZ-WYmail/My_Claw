"""
番茄钟管理服务 — 独立的番茄钟会话管理模块
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Optional

import aiosqlite

from config import DB_PATH


# ============================================================
# 数据库初始化
# ============================================================

_schema = """
-- 番茄钟会话表
CREATE TABLE IF NOT EXISTS pomodoro_sessions (
    session_id   TEXT PRIMARY KEY,
    task_id      TEXT,
    start_time   TEXT NOT NULL,
    end_time     TEXT,
    duration_minutes INTEGER NOT NULL,  -- 计划时长
    actual_minutes   INTEGER,           -- 实际时长
    status       TEXT NOT NULL DEFAULT 'running',  -- running/completed/interrupted
    interrupt_reason TEXT,
    FOREIGN KEY (task_id) REFERENCES tasks(task_id) ON DELETE SET NULL
);
"""


async def init_pomodoro_db():
    """初始化番茄钟相关数据库表结构"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(str(DB_PATH)) as db:
        await db.executescript(_schema)
        await db.commit()


# ============================================================
# 番茄钟管理
# ============================================================

_active_pomodoro: Optional[dict] = None  # 内存中存储当前进行中的番茄钟


async def start_pomodoro(task_id: str = None, duration_minutes: int = 25) -> dict:
    """开始番茄钟"""
    global _active_pomodoro

    # 检查是否有进行中的番茄钟
    if _active_pomodoro:
        return {
            "status": "error",
            "message": "已有进行中的番茄钟",
            "active_session": _active_pomodoro,
        }

    session_id = f"pom_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    start_time = datetime.now().isoformat()

    async with aiosqlite.connect(str(DB_PATH)) as db:
        await db.execute(
            "INSERT INTO pomodoro_sessions (session_id, task_id, start_time, duration_minutes) VALUES (?, ?, ?, ?)",
            (session_id, task_id, start_time, duration_minutes),
        )
        await db.commit()

        task_name = None
        if task_id:
            cursor = await db.execute(
                "SELECT task_name FROM tasks WHERE task_id = ?", (task_id,)
            )
            row = await cursor.fetchone()
            if row:
                task_name = row[0]

    _active_pomodoro = {
        "session_id": session_id,
        "task_id": task_id,
        "start_time": start_time,
        "duration_minutes": duration_minutes,
        "status": "running",
    }

    return {
        "status": "success",
        "session_id": session_id,
        "start_time": start_time,
        "duration_minutes": duration_minutes,
        "task_name": task_name,
    }


async def complete_pomodoro() -> dict:
    """完成番茄钟"""
    global _active_pomodoro

    if not _active_pomodoro:
        return {"status": "error", "message": "没有进行中的番茄钟"}

    session_id = _active_pomodoro["session_id"]
    end_time = datetime.now().isoformat()

    # 计算实际时长
    start = datetime.fromisoformat(_active_pomodoro["start_time"])
    end = datetime.fromisoformat(end_time)
    actual_minutes = int((end - start).total_seconds() / 60)

    async with aiosqlite.connect(str(DB_PATH)) as db:
        await db.execute(
            "UPDATE pomodoro_sessions SET end_time = ?, actual_minutes = ?, status = 'completed' WHERE session_id = ?",
            (end_time, actual_minutes, session_id),
        )
        await db.commit()

    result = {
        "status": "success",
        "session_id": session_id,
        "actual_minutes": actual_minutes,
    }

    _active_pomodoro = None
    return result


async def interrupt_pomodoro(reason: str = None) -> dict:
    """中断番茄钟"""
    global _active_pomodoro

    if not _active_pomodoro:
        return {"status": "error", "message": "没有进行中的番茄钟"}

    session_id = _active_pomodoro["session_id"]
    end_time = datetime.now().isoformat()

    start = datetime.fromisoformat(_active_pomodoro["start_time"])
    end = datetime.fromisoformat(end_time)
    actual_minutes = int((end - start).total_seconds() / 60)

    async with aiosqlite.connect(str(DB_PATH)) as db:
        await db.execute(
            "UPDATE pomodoro_sessions SET end_time = ?, actual_minutes = ?, status = 'interrupted', interrupt_reason = ? WHERE session_id = ?",
            (end_time, actual_minutes, reason, session_id),
        )
        await db.commit()

    result = {
        "status": "success",
        "session_id": session_id,
        "actual_minutes": actual_minutes,
        "reason": reason,
    }

    _active_pomodoro = None
    return result


async def get_active_pomodoro() -> Optional[dict]:
    """获取当前进行中的番茄钟"""
    return _active_pomodoro


async def get_pomodoro_stats(days: int = 7) -> dict:
    """获取番茄钟统计"""
    today = datetime.now().strftime("%Y-%m-%d")
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

    async with aiosqlite.connect(str(DB_PATH)) as db:
        # 今日统计
        cursor = await db.execute(
            """SELECT COUNT(*), COALESCE(SUM(actual_minutes), 0)
               FROM pomodoro_sessions
               WHERE date(start_time) = date('now') AND status = 'completed'"""
        )
        today_count, today_minutes = await cursor.fetchone()

        # 本周统计
        cursor = await db.execute(
            """SELECT COUNT(*), COALESCE(SUM(actual_minutes), 0)
               FROM pomodoro_sessions
               WHERE date(start_time) >= date('now', '-7 days') AND status = 'completed'"""
        )
        week_count, week_minutes = await cursor.fetchone()

        # 总计
        cursor = await db.execute(
            """SELECT COUNT(*), COALESCE(SUM(actual_minutes), 0)
               FROM pomodoro_sessions WHERE status = 'completed'"""
        )
        total_count, total_minutes = await cursor.fetchone()

        # 最近7天每日统计（单次 GROUP BY 查询替代7次循环查询）
        cursor = await db.execute(
            """SELECT date(start_time) as d, COUNT(*), COALESCE(SUM(actual_minutes), 0)
               FROM pomodoro_sessions
               WHERE date(start_time) >= date('now', '-6 days') AND status = 'completed'
               GROUP BY date(start_time)"""
        )
        daily_map = {r[0]: {"count": r[1], "minutes": r[2]} for r in await cursor.fetchall()}

        daily_stats = []
        for i in range(6, -1, -1):
            date_str = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            info = daily_map.get(date_str, {"count": 0, "minutes": 0})
            daily_stats.append({
                "date": date_str,
                "count": info["count"],
                "minutes": info["minutes"],
            })

    return {
        "status": "success",
        "today_count": today_count or 0,
        "today_minutes": today_minutes or 0,
        "week_count": week_count or 0,
        "week_minutes": week_minutes or 0,
        "total_count": total_count or 0,
        "total_minutes": total_minutes or 0,
        "daily_stats": daily_stats,
    }


async def get_pomodoro_history(page: int = 1, page_size: int = 20) -> dict:
    """获取番茄钟历史"""
    async with aiosqlite.connect(str(DB_PATH)) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute("SELECT COUNT(*) FROM pomodoro_sessions")
        total = (await cursor.fetchone())[0]

        offset = (page - 1) * page_size
        cursor = await db.execute(
            """SELECT p.*, t.task_name
               FROM pomodoro_sessions p
               LEFT JOIN tasks t ON p.task_id = t.task_id
               ORDER BY p.start_time DESC
               LIMIT ? OFFSET ?""",
            (page_size, offset),
        )
        rows = await cursor.fetchall()
        sessions = [dict(row) for row in rows]

    return {
        "status": "success",
        "sessions": sessions,
        "total": total,
        "page": page,
        "page_size": page_size,
    }
