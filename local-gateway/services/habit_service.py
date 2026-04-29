"""
习惯管理服务 — SQLite CRUD + 打卡记录 + 统计功能
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional

import aiosqlite

from config import DB_PATH


# ============================================================
# 数据库初始化
# ============================================================

_schema = """
CREATE TABLE IF NOT EXISTS habits (
    habit_id     TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    description  TEXT,
    frequency    TEXT NOT NULL,           -- daily/weekly/monthly
    target_count INTEGER DEFAULT 1,       -- 目标次数
    reminder_time TEXT,                   -- 提醒时间
    color        TEXT DEFAULT '#27ae60',
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS habit_checkins (
    checkin_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    habit_id     TEXT NOT NULL,
    checkin_date TEXT NOT NULL,           -- YYYY-MM-DD
    count        INTEGER DEFAULT 1,
    note         TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (habit_id) REFERENCES habits(habit_id) ON DELETE CASCADE
);
"""


async def init_habit_db():
    """初始化习惯相关数据库表结构"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(str(DB_PATH)) as db:
        await db.executescript(_schema)
        await db.commit()


# ============================================================
# 习惯管理 CRUD 操作
# ============================================================

async def create_habit(
    name: str,
    description: str = "",
    frequency: str = "daily",
    target_count: int = 1,
    reminder_time: str = None,
    color: str = "#27ae60",
) -> dict:
    """创建习惯"""
    habit_id = f"habit_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"

    async with aiosqlite.connect(str(DB_PATH)) as db:
        await db.execute(
            """INSERT INTO habits (habit_id, name, description, frequency, target_count, reminder_time, color)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (habit_id, name, description, frequency, target_count, reminder_time, color),
        )
        await db.commit()

    return {
        "status": "success",
        "habit_id": habit_id,
        "name": name,
        "message": "习惯创建成功",
    }


async def get_all_habits() -> list[dict]:
    """获取所有习惯"""
    async with aiosqlite.connect(str(DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM habits ORDER BY created_at DESC"
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_habit(habit_id: str) -> Optional[dict]:
    """获取单个习惯详情（含打卡记录）"""
    async with aiosqlite.connect(str(DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM habits WHERE habit_id = ?",
            (habit_id,),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        habit = dict(row)

        # 获取最近30天打卡记录
        cursor = await db.execute(
            """SELECT * FROM habit_checkins
               WHERE habit_id = ? AND checkin_date >= date('now', '-30 days')
               ORDER BY checkin_date DESC""",
            (habit_id,),
        )
        checkins = [dict(r) for r in await cursor.fetchall()]
        habit["checkins"] = checkins
        habit["streak"] = _calculate_streak(checkins)

    return habit


def _calculate_streak(checkins: list[dict]) -> int:
    """计算连续打卡天数"""
    if not checkins:
        return 0

    dates = sorted([c["checkin_date"] for c in checkins], reverse=True)
    streak = 1
    today = datetime.now().strftime("%Y-%m-%d")

    # 如果今天没打卡，从昨天开始算
    if dates[0] != today:
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        if dates[0] != yesterday:
            return 0

    for i in range(1, len(dates)):
        prev_date = datetime.strptime(dates[i-1], "%Y-%m-%d")
        curr_date = datetime.strptime(dates[i], "%Y-%m-%d")
        if (prev_date - curr_date).days == 1:
            streak += 1
        else:
            break

    return streak


async def checkin_habit(habit_id: str, count: int = 1, note: str = "") -> dict:
    """习惯打卡"""
    today = datetime.now().strftime("%Y-%m-%d")

    async with aiosqlite.connect(str(DB_PATH)) as db:
        # 检查今天是否已打卡
        cursor = await db.execute(
            "SELECT checkin_id FROM habit_checkins WHERE habit_id = ? AND checkin_date = ?",
            (habit_id, today),
        )
        existing = await cursor.fetchone()

        if existing:
            # 更新打卡次数
            await db.execute(
                "UPDATE habit_checkins SET count = count + ?, note = ? WHERE checkin_id = ?",
                (count, note, existing[0]),
            )
        else:
            await db.execute(
                """INSERT INTO habit_checkins (habit_id, checkin_date, count, note)
                   VALUES (?, ?, ?, ?)""",
                (habit_id, today, count, note),
            )

        await db.commit()

    return {"status": "success", "message": "打卡成功"}


async def get_habit_stats(habit_id: str) -> dict:
    """获取习惯统计"""
    async with aiosqlite.connect(str(DB_PATH)) as db:
        # 总打卡次数
        cursor = await db.execute(
            "SELECT SUM(count) FROM habit_checkins WHERE habit_id = ?",
            (habit_id,),
        )
        total_count = (await cursor.fetchone())[0] or 0

        # 打卡天数
        cursor = await db.execute(
            "SELECT COUNT(DISTINCT checkin_date) FROM habit_checkins WHERE habit_id = ?",
            (habit_id,),
        )
        total_days = (await cursor.fetchone())[0] or 0

        # 最近7天
        cursor = await db.execute(
            """SELECT COUNT(*) FROM habit_checkins
               WHERE habit_id = ? AND checkin_date >= date('now', '-7 days')""",
            (habit_id,),
        )
        week_count = (await cursor.fetchone())[0] or 0

        # 本月
        cursor = await db.execute(
            """SELECT COUNT(*) FROM habit_checkins
               WHERE habit_id = ? AND strftime('%Y-%m', checkin_date) = strftime('%Y-%m', 'now')""",
            (habit_id,),
        )
        month_count = (await cursor.fetchone())[0] or 0

    return {
        "status": "success",
        "total_count": total_count,
        "total_days": total_days,
        "week_count": week_count,
        "month_count": month_count,
    }


async def delete_habit(habit_id: str) -> dict:
    """删除习惯"""
    async with aiosqlite.connect(str(DB_PATH)) as db:
        cursor = await db.execute(
            "DELETE FROM habits WHERE habit_id = ?",
            (habit_id,),
        )
        await db.commit()
        if cursor.rowcount == 0:
            return {"status": "error", "message": f"习惯 {habit_id} 不存在"}
    return {"status": "success", "message": "习惯已删除"}
