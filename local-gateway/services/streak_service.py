"""
任务连续完成（Streak）引擎
追踪每日任务完成情况，计算连续天数和里程碑。
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from config import BASE_DIR

logger = logging.getLogger(__name__)

_STREAK_FILE = BASE_DIR / "data" / "streak.json"


def _load_streak_data() -> dict:
    if not _STREAK_FILE.exists():
        return {
            "current_streak": 0,
            "longest_streak": 0,
            "last_check_date": "",
            "history": [],
        }
    try:
        with open(_STREAK_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"加载 streak 数据失败: {e}")
        return {"current_streak": 0, "longest_streak": 0, "last_check_date": "", "history": []}


def _save_streak_data(data: dict):
    _STREAK_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(_STREAK_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"保存 streak 数据失败: {e}")


async def check_and_update_streak() -> dict:
    """
    检查并更新 streak 状态。
    - 昨天有任务且全部完成 → streak + 1
    - 昨天有任务且未全完成 → streak 归零
    - 昨天无任务 → streak 不变
    幂等：如果 last_check_date 已是今天，跳过。
    """
    import aiosqlite
    from config import DB_PATH

    today = datetime.now().strftime("%Y-%m-%d")
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    data = _load_streak_data()

    if data["last_check_date"] == today:
        return data

    async with aiosqlite.connect(str(DB_PATH)) as db:
        cursor = await db.execute(
            """SELECT status FROM tasks
               WHERE status != 'deleted'
               AND (date(due_time) = ? OR date(start_time) = ?)""",
            (yesterday, yesterday),
        )
        rows = await cursor.fetchall()

    total = len(rows)
    completed = sum(1 for r in rows if r[0] == "completed")
    all_done = total > 0 and completed == total

    # 更新 streak
    if total > 0:
        if all_done:
            data["current_streak"] += 1
        else:
            data["current_streak"] = 0
    # total == 0: 无任务，streak 不变

    # 更新最长纪录
    if data["current_streak"] > data["longest_streak"]:
        data["longest_streak"] = data["current_streak"]

    # 更新历史记录（最近 30 天）
    history = data.get("history", [])
    history.append({
        "date": yesterday,
        "total": total,
        "completed": completed,
        "all_done": all_done,
    })
    if len(history) > 30:
        history = history[-30:]
    data["history"] = history

    data["last_check_date"] = today
    _save_streak_data(data)

    return data


async def get_streak_info() -> dict:
    """获取 streak 信息"""
    data = _load_streak_data()

    history = data.get("history", [])
    recent_7 = history[-7:] if len(history) >= 7 else history
    if recent_7:
        days_all_done = sum(1 for h in recent_7 if h.get("all_done"))
        weekly_rate = round(days_all_done / len(recent_7) * 100)
    else:
        weekly_rate = 0

    today = datetime.now().strftime("%Y-%m-%d")
    import aiosqlite
    from config import DB_PATH

    today_total = 0
    today_completed = 0
    async with aiosqlite.connect(str(DB_PATH)) as db:
        cursor = await db.execute(
            """SELECT status FROM tasks
               WHERE status != 'deleted'
               AND (date(due_time) = ? OR date(start_time) = ?)""",
            (today, today),
        )
        rows = await cursor.fetchall()
        today_total = len(rows)
        today_completed = sum(1 for r in rows if r[0] == "completed")

    return {
        "current_streak": data["current_streak"],
        "longest_streak": data["longest_streak"],
        "weekly_rate": weekly_rate,
        "today_total": today_total,
        "today_completed": today_completed,
        "history": history,
    }


async def get_weekly_stats() -> dict:
    """获取本周统计"""
    now = datetime.now()
    monday = now - timedelta(days=now.weekday())
    last_monday = monday - timedelta(days=7)
    sunday = monday + timedelta(days=6)
    last_sunday = last_monday + timedelta(days=6)

    import aiosqlite
    from config import DB_PATH

    this_week_dates = [(monday + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]
    last_week_dates = [(last_monday + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]

    this_week_map = {d: {"total": 0, "completed": 0} for d in this_week_dates}
    last_week_map = {d: {"total": 0, "completed": 0} for d in last_week_dates}
    all_dates = set(this_week_dates + last_week_dates)

    async with aiosqlite.connect(str(DB_PATH)) as db:
        date_list = ",".join("?" for _ in all_dates)
        cursor = await db.execute(
            f"""SELECT COALESCE(date(due_time), date(start_time)) AS day, status, COUNT(*) AS cnt
               FROM tasks
               WHERE status != 'deleted'
               AND (date(due_time) IN ({date_list}) OR date(start_time) IN ({date_list}))
               GROUP BY day, status""",
            list(all_dates) * 2,
        )
        rows = await cursor.fetchall()

    for row in rows:
        day, status, cnt = row[0], row[1], row[2]
        if day in this_week_map:
            this_week_map[day]["total"] += cnt
            if status == "completed":
                this_week_map[day]["completed"] += cnt
        if day in last_week_map:
            last_week_map[day]["total"] += cnt
            if status == "completed":
                last_week_map[day]["completed"] += cnt

    days_stats = []
    this_week_total = 0
    this_week_completed = 0
    for day_str in this_week_dates:
        info = this_week_map[day_str]
        total = info["total"]
        completed = info["completed"]
        this_week_total += total
        this_week_completed += completed
        days_stats.append({
            "date": day_str,
            "total": total,
            "completed": completed,
            "rate": round(completed / total * 100) if total > 0 else 0,
        })

    last_week_total = sum(info["total"] for info in last_week_map.values())
    last_week_completed = sum(info["completed"] for info in last_week_map.values())

    this_rate = round(this_week_completed / this_week_total * 100) if this_week_total > 0 else 0
    last_rate = round(last_week_completed / last_week_total * 100) if last_week_total > 0 else 0

    return {
        "days": days_stats,
        "this_week": {"total": this_week_total, "completed": this_week_completed, "rate": this_rate},
        "last_week": {"total": last_week_total, "completed": last_week_completed, "rate": last_rate},
        "change": this_rate - last_rate,
    }


def check_milestones(streak: int, previous_streak: int) -> list[str]:
    """
    检查是否刚达到某个里程碑。
    返回达到的里程碑列表，如 ["streak_7"]。
    """
    milestones = [7, 14, 30, 60, 100]
    reached = []
    for m in milestones:
        if streak >= m and previous_streak < m:
            reached.append(f"streak_{m}")
    return reached


def get_milestone_message(milestone: str) -> str:
    """获取里程碑祝贺语"""
    messages = {
        "streak_7": "坚持了一周，好习惯正在养成！🌱",
        "streak_14": "两周连续完成，你比 90% 的人更自律！💪",
        "streak_30": "一个月！这是真正的习惯力量！🔥",
        "streak_60": "两个月不间断，自律已成本能！🏆",
        "streak_100": "百日坚持！你是时间管理大师！👑",
    }
    return messages.get(milestone, f"连续完成 {milestone.replace('streak_', '')} 天，太棒了！")
