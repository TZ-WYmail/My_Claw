"""
任务管理服务 — SQLite CRUD + APScheduler 定时提醒 + 批量任务编排
"""
from __future__ import annotations

import asyncio
import json
import re
import sqlite3
import uuid
from datetime import datetime, timedelta
from typing import Optional

import aiosqlite

from config import DB_PATH
from services.security_service import validate_update_columns
from services.utils import human_size
from services.tag_service import add_task_tags, get_task_tags_batch


# ============================================================
# 数据库初始化
# ============================================================

_schema = """
CREATE TABLE IF NOT EXISTS tasks (
    task_id      TEXT PRIMARY KEY,
    task_name    TEXT NOT NULL,
    due_time     TEXT NOT NULL,
    recurrence   TEXT NOT NULL DEFAULT 'once',
    status       TEXT NOT NULL DEFAULT 'pending',
    priority     INTEGER NOT NULL DEFAULT 2,  -- 0=urgent, 1=high, 2=medium, 3=low
    description  TEXT,
    estimated_minutes INTEGER,  -- 预估时间（分钟）
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS download_history (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    url          TEXT NOT NULL,
    filename     TEXT,
    category     TEXT NOT NULL,
    file_path    TEXT,
    file_size    TEXT,
    security_scan TEXT DEFAULT 'pending',
    status       TEXT NOT NULL DEFAULT 'downloading',
    job_id       TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS operation_logs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    operation    TEXT NOT NULL,
    endpoint     TEXT NOT NULL,
    params       TEXT,
    result       TEXT DEFAULT 'success',
    detail       TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

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

-- 日历事件表（用于非任务类事件）
CREATE TABLE IF NOT EXISTS calendar_events (
    event_id     TEXT PRIMARY KEY,
    title        TEXT NOT NULL,
    description  TEXT,
    start_time   TEXT NOT NULL,
    end_time     TEXT NOT NULL,
    event_type   TEXT DEFAULT 'personal',  -- personal/work/meeting/deadline
    color        TEXT DEFAULT '#3498db',
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

-- 笔记表
CREATE TABLE IF NOT EXISTS notes (
    note_id      TEXT PRIMARY KEY,
    title        TEXT NOT NULL,
    content      TEXT,                    -- Markdown 内容
    content_type TEXT DEFAULT 'markdown', -- markdown/plain/text
    tags         TEXT,                    -- JSON 数组
    task_id      TEXT,                    -- 关联任务（可选）
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

-- 习惯表
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

-- 习惯打卡记录
CREATE TABLE IF NOT EXISTS habit_checkins (
    checkin_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    habit_id     TEXT NOT NULL,
    checkin_date TEXT NOT NULL,           -- YYYY-MM-DD
    count        INTEGER DEFAULT 1,
    note         TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (habit_id) REFERENCES habits(habit_id) ON DELETE CASCADE
);

-- 同步设备表
CREATE TABLE IF NOT EXISTS sync_devices (
    device_id    TEXT PRIMARY KEY,
    device_name  TEXT,
    device_type  TEXT,                    -- mobile/desktop/web
    last_seen    TEXT NOT NULL DEFAULT (datetime('now')),
    registered_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- 离线操作队列
CREATE TABLE IF NOT EXISTS sync_offline_queue (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    operation    TEXT NOT NULL,           -- create/update/delete
    table_name   TEXT,
    record_id    TEXT,
    data         TEXT,                    -- JSON
    source       TEXT DEFAULT 'unknown',
    synced       INTEGER DEFAULT 0,       -- 0=pending, 1=synced
    error        TEXT,
    queued_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

-- 推送令牌表
CREATE TABLE IF NOT EXISTS push_tokens (
    device_id    TEXT PRIMARY KEY,
    token        TEXT NOT NULL,
    platform     TEXT NOT NULL,           -- ios/android
    registered_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


async def init_db():
    """初始化数据库表结构"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(str(DB_PATH)) as db:
        await db.executescript(_schema)
        await db.commit()

    # 初始化标签相关表
    from services.tag_service import init_tag_db
    await init_tag_db()

    # 初始化子任务相关表
    from services.subtask_service import init_subtask_db
    await init_subtask_db()


# ============================================================
# CRUD 操作
# ============================================================

async def add_task(
    task_name: str,
    due_time: str,
    recurrence: str = "once",
    priority: int = 2,
    description: str = None,
    estimated_minutes: int = None,
    tags: list[str] = None,
) -> dict:
    """添加任务并返回任务信息"""
    task_id = f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"

    async with aiosqlite.connect(str(DB_PATH)) as db:
        await db.execute(
            """INSERT INTO tasks (task_id, task_name, due_time, recurrence, priority, description, estimated_minutes)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (task_id, task_name, due_time, recurrence, priority, description, estimated_minutes),
        )
        await db.commit()

    # 添加标签
    if tags:
        await add_task_tags(task_id, tags)

    # 计算下次提醒时间
    next_reminder = _calc_next_reminder(due_time, recurrence)

    return {
        "status": "success",
        "task_id": task_id,
        "message": f"任务已添加，将在 {_human_readable_time(due_time)} 触发提醒",
        "next_reminder": next_reminder,
    }


async def delete_task(task_id: str) -> dict:
    """软删除任务"""
    async with aiosqlite.connect(str(DB_PATH)) as db:
        cursor = await db.execute(
            "UPDATE tasks SET status = 'deleted', updated_at = datetime('now') WHERE task_id = ?",
            (task_id,),
        )
        await db.commit()
        if cursor.rowcount == 0:
            return {"status": "error", "message": f"任务 {task_id} 不存在"}
    return {"status": "success", "message": f"任务 {task_id} 已删除"}


async def complete_task(task_id: str) -> dict:
    """标记任务完成"""
    async with aiosqlite.connect(str(DB_PATH)) as db:
        cursor = await db.execute(
            "UPDATE tasks SET status = 'completed', updated_at = datetime('now') WHERE task_id = ?",
            (task_id,),
        )
        await db.commit()
        if cursor.rowcount == 0:
            return {"status": "error", "message": f"任务 {task_id} 不存在"}
    return {"status": "success", "message": f"任务 {task_id} 已完成"}


async def get_weekly_plan(monday_iso: str = "", sunday_iso: str = "") -> dict:
    """获取指定周的任务列表。不传参则取当前周。"""
    if monday_iso and sunday_iso:
        monday_str = monday_iso
        sunday_str = sunday_iso
    else:
        now = datetime.now()
        monday = now - timedelta(days=now.weekday())
        sunday = monday + timedelta(days=6)
        monday_str = monday.strftime("%Y-%m-%dT00:00:00")
        sunday_str = sunday.strftime("%Y-%m-%dT23:59:59")

    async with aiosqlite.connect(str(DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT task_id, task_name, due_time, recurrence, status, priority, description, estimated_minutes
            FROM tasks
            WHERE status != 'deleted'
              AND due_time >= ? AND due_time <= ?
            ORDER BY priority ASC, due_time ASC
            """,
            (monday_str, sunday_str),
        )
        rows = await cursor.fetchall()

    # 批量获取标签，避免N+1查询
    task_ids = [row["task_id"] for row in rows]
    tags_map = await get_task_tags_batch(task_ids)

    tasks = []
    for row in rows:
        task = {
            "task_id": row["task_id"],
            "task_name": row["task_name"],
            "due_time": row["due_time"],
            "recurrence": row["recurrence"],
            "status": _translate_status(row["status"]),
            "priority": row["priority"],
            "description": row["description"],
            "estimated_minutes": row["estimated_minutes"],
            "tags": tags_map.get(row["task_id"], []),
        }
        tasks.append(task)

    return {
        "status": "success",
        "tasks": tasks,
        "message": f"本周共有 {len(tasks)} 项任务",
    }


# ============================================================
# 批量任务编排
# ============================================================

async def batch_add_tasks(tasks: list[dict]) -> dict:
    """
    批量添加任务。
    每个任务 dict: {"task_name": str, "due_time": str, "recurrence": str}
    due_time 应为 ISO 8601 格式。
    返回创建结果列表。
    """
    results = []
    success_count = 0
    error_count = 0

    async with aiosqlite.connect(str(DB_PATH)) as db:
        for t in tasks:
            task_name = t.get("task_name", "").strip()
            due_time = t.get("due_time", "").strip()
            recurrence = t.get("recurrence", "once").strip()

            if not task_name or not due_time:
                results.append({
                    "task_name": task_name or "(空)",
                    "status": "error",
                    "message": "缺少 task_name 或 due_time",
                })
                error_count += 1
                continue

            # 验证时间格式
            try:
                dt = datetime.fromisoformat(due_time)
            except (ValueError, TypeError):
                results.append({
                    "task_name": task_name,
                    "status": "error",
                    "message": f"时间格式无效: {due_time}",
                })
                error_count += 1
                continue

            task_id = f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"

            try:
                await db.execute(
                    "INSERT INTO tasks (task_id, task_name, due_time, recurrence) VALUES (?, ?, ?, ?)",
                    (task_id, task_name, due_time, recurrence),
                )
                results.append({
                    "task_id": task_id,
                    "task_name": task_name,
                    "due_time": due_time,
                    "recurrence": recurrence,
                    "status": "success",
                    "message": f"✅ {task_name} → {_human_readable_time(due_time)}",
                })
                success_count += 1
            except Exception as e:
                results.append({
                    "task_name": task_name,
                    "status": "error",
                    "message": str(e),
                })
                error_count += 1

        await db.commit()

    return {
        "status": "success",
        "total": len(tasks),
        "success_count": success_count,
        "error_count": error_count,
        "results": results,
        "message": f"批量创建完成: {success_count} 成功, {error_count} 失败",
    }


async def analyze_tasks(raw_tasks: list[dict]) -> dict:
    """
    分析一批原始任务数据，返回解析结果供预览。
    不写入数据库，只做解析、分组、冲突检测。
    raw_tasks 每项: {"task_name": str, "due_time": str, ...}
    due_time 可以是宽松格式，此函数尝试标准化。
    """
    analyzed = []
    # 按日期分组
    by_date: dict[str, list] = {}

    # 预估工时映射（基于任务名称关键词）
    def _estimate_hours(name: str) -> float:
        name_lower = name.lower()
        if any(k in name_lower for k in ["学习", "阅读", "整理", "review", "内容整理"]):
            return 4.0
        if any(k in name_lower for k in ["定稿", "报告", "汇报", "演讲", "答辩"]):
            return 8.0
        if any(k in name_lower for k in ["提交", "补全", "准备", "证明"]):
            return 2.0
        if any(k in name_lower for k in ["推进", "调优"]):
            return 6.0
        return 4.0  # 默认 4 小时

    for t in raw_tasks:
        task_name = t.get("task_name", "").strip()
        due_time = t.get("due_time", "").strip()
        recurrence = t.get("recurrence", "once")

        # 尝试标准化时间
        iso_time = _normalize_time(due_time)

        conflict = ""
        overdue = False
        if iso_time:
            try:
                dt = datetime.fromisoformat(iso_time)
                if dt < datetime.now():
                    overdue = True
            except (ValueError, TypeError):
                pass
            if iso_time[:10] in by_date:
                if len(by_date[iso_time[:10]]) >= 3:
                    conflict = f"⚠️ {iso_time[:10]} 已有 {len(by_date[iso_time[:10]])} 项任务"

        if iso_time:
            date_key = iso_time[:10]
            if date_key not in by_date:
                by_date[date_key] = []
            by_date[date_key].append(task_name)

        analyzed.append({
            "task_name": task_name,
            "due_time": iso_time or due_time,
            "recurrence": recurrence,
            "time_valid": bool(iso_time),
            "conflict": conflict,
            "overdue": overdue,
            "estimated_hours": _estimate_hours(task_name) if iso_time else 0,
        })

    # 生成每日分布规划（将任务按时间线分配到每天）
    daily_plan = _generate_daily_plan(analyzed)

    # 生成时间线摘要
    timeline = []
    for date_key in sorted(by_date.keys()):
        names = by_date[date_key]
        weekday = _date_to_weekday(date_key)
        timeline.append(f"📅 {date_key} ({weekday}) — {len(names)} 项截止: {', '.join(names)}")

    # 生成每日工作分布摘要
    daily_timeline = []
    for day in sorted(daily_plan.keys()):
        info = daily_plan[day]
        weekday = _date_to_weekday(day)
        tasks_str = "; ".join([f"{t['task_name']}({t['hours']}h)" for t in info["tasks"]])
        daily_timeline.append(f"📅 {day} ({weekday}) — {info['total_hours']}h: {tasks_str}")

    return {
        "status": "success",
        "total": len(raw_tasks),
        "analyzed": analyzed,
        "timeline": timeline,
        "daily_plan": daily_plan,
        "daily_timeline": daily_timeline,
        "by_date": {k: v for k, v in sorted(by_date.items())},
        "message": f"解析完成: {len(analyzed)} 项任务, 跨 {len(by_date)} 个截止日, 分布到 {len(daily_plan)} 个工作日",
    }


def _generate_daily_plan(analyzed: list[dict]) -> dict[str, dict]:
    """
    根据任务截止日期和预估工时，自动规划每日工作分布。
    规则：
    1. 大任务（≥6h）提前 3 天开始拆分
    2. 中任务（4h）提前 2 天开始
    3. 小任务（≤2h）提前 1 天
    4. 每天总工作量不超过 6 小时
    5. 按截止日期排序，越紧急越优先安排
    """
    # 收集有有效时间的任务
    valid = [a for a in analyzed if a["time_valid"]]
    if not valid:
        return {}

    # 按截止日期排序
    valid.sort(key=lambda x: x["due_time"][:10])

    daily: dict[str, list] = {}  # date -> [{task_name, hours}]

    for task in valid:
        due_date_str = task["due_time"][:10]
        try:
            due_date = datetime.strptime(due_date_str, "%Y-%m-%d")
        except ValueError:
            continue

        est = task.get("estimated_hours", 4.0)
        name = task["task_name"]

        # 确定提前天数
        if est >= 6:
            lead_days = 3
        elif est >= 4:
            lead_days = 2
        else:
            lead_days = 1

        # 将工时分配到多天
        hours_per_day = round(est / lead_days, 1)
        hours_per_day = max(hours_per_day, 0.5)

        start_date = due_date - timedelta(days=lead_days)
        for d in range(lead_days):
            work_date = start_date + timedelta(days=d)
            date_str = work_date.strftime("%Y-%m-%d")
            if date_str not in daily:
                daily[date_str] = []
            daily[date_str].append({
                "task_name": name,
                "hours": hours_per_day if d < lead_days - 1 else round(est - hours_per_day * (lead_days - 1), 1),
                "due_date": due_date_str,
                "progress": f"第{d+1}/{lead_days}天",
            })

    # 按日期汇总
    result = {}
    for date_str in sorted(daily.keys()):
        tasks = daily[date_str]
        total_h = round(sum(t["hours"] for t in tasks), 1)
        weekday = _date_to_weekday(date_str)
        result[date_str] = {
            "weekday": weekday,
            "tasks": tasks,
            "total_hours": total_h,
            "overload": total_h > 6,
        }

    return result


def _normalize_time(time_str: str) -> str:
    """
    尝试将各种时间格式转为 ISO 8601。
    支持: "3月22日" → "2026-03-22T09:00:00", "2026-03-22" → "2026-03-22T09:00:00"
    """
    if not time_str:
        return ""



    # 已经是完整 ISO 格式
    try:
        dt = datetime.fromisoformat(time_str)
        return dt.isoformat()
    except (ValueError, TypeError):
        pass

    # "X月X日" 格式 (中文)
    m = re.match(r"(\d{1,2})月(\d{1,2})日?", time_str)
    if m:
        month, day = int(m.group(1)), int(m.group(2))
        year = datetime.now().year
        try:
            dt = datetime(year, month, day, 9, 0, 0)
            # 如果已过，不自动推到明年——保留当年，让 AI 在回复中提醒用户
            return dt.isoformat()
        except ValueError:
            return ""

    # "MM-DD" 格式
    m = re.match(r"(\d{1,2})-(\d{1,2})$", time_str)
    if m:
        month, day = int(m.group(1)), int(m.group(2))
        year = datetime.now().year
        try:
            dt = datetime(year, month, day, 9, 0, 0)
            return dt.isoformat()
        except ValueError:
            return ""

    # "YYYY-MM-DD" 格式
    m = re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})$", time_str)
    if m:
        try:
            dt = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), 9, 0, 0)
            return dt.isoformat()
        except ValueError:
            return ""

    return ""


def _date_to_weekday(date_str: str) -> str:
    """YYYY-MM-DD → 周X"""
    weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return weekdays[dt.weekday()]
    except Exception:
        return ""


# ============================================================
# 辅助函数
# ============================================================

def _calc_next_reminder(due_time: str, recurrence: str) -> str:
    """根据周期计算下次提醒时间"""
    dt = datetime.fromisoformat(due_time)
    now = datetime.now(dt.tzinfo)

    if recurrence == "once":
        return due_time
    elif recurrence == "daily":
        next_dt = dt + timedelta(days=1)
    elif recurrence == "weekly":
        next_dt = dt + timedelta(weeks=1)
    elif recurrence == "monthly":
        # 简单处理：加30天
        next_dt = dt + timedelta(days=30)
    else:
        return due_time

    return next_dt.isoformat()


def _human_readable_time(iso_time: str) -> str:
    """ISO 8601 → 人类可读"""
    try:
        dt = datetime.fromisoformat(iso_time)
        weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        return f"{dt.strftime('%m-%d %H:%M')} ({weekdays[dt.weekday()]})"
    except Exception:
        return iso_time


def _translate_status(status: str) -> str:
    status_map = {
        "pending": "待执行",
        "completed": "已完成",
        "deleted": "已删除",
    }
    return status_map.get(status, status)


# ============================================================
# 全部任务查询（带筛选）
# ============================================================

async def get_all_tasks(
    status_filter: str = "active",
    keyword: str = "",
    tag: str = "",
    priority: int = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """获取全部任务，支持状态筛选、关键词搜索、标签和优先级过滤"""
    conditions = []
    params = []

    if status_filter == "active":
        conditions.append("status != 'deleted'")
    elif status_filter in ("pending", "completed", "deleted"):
        conditions.append("status = ?")
        params.append(status_filter)

    if keyword:
        conditions.append("(task_name LIKE ? OR description LIKE ?)")
        params.extend([f"%{keyword}%", f"%{keyword}%"])

    if priority is not None:
        conditions.append("priority = ?")
        params.append(priority)

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    async with aiosqlite.connect(str(DB_PATH)) as db:
        # 总数（考虑标签过滤）
        if tag:
            cursor = await db.execute(
                f"""SELECT COUNT(DISTINCT t.task_id) FROM tasks t
                    JOIN task_tags tt ON t.task_id = tt.task_id
                    JOIN tags tg ON tt.tag_id = tg.tag_id
                    WHERE {where_clause} AND tg.name = ?""",
                params + [tag]
            )
        else:
            cursor = await db.execute(
                f"SELECT COUNT(*) FROM tasks WHERE {where_clause}", params
            )
        total = (await cursor.fetchone())[0]

        # 分页查询
        offset = (page - 1) * page_size
        db.row_factory = aiosqlite.Row

        if tag:
            cursor = await db.execute(
                f"""
                SELECT t.task_id, t.task_name, t.due_time, t.recurrence, t.status,
                       t.priority, t.description, t.estimated_minutes, t.created_at
                FROM tasks t
                JOIN task_tags tt ON t.task_id = tt.task_id
                JOIN tags tg ON tt.tag_id = tg.tag_id
                WHERE {where_clause} AND tg.name = ?
                ORDER BY t.priority ASC, t.due_time ASC
                LIMIT ? OFFSET ?
                """,
                params + [tag, page_size, offset],
            )
        else:
            cursor = await db.execute(
                f"""
                SELECT task_id, task_name, due_time, recurrence, status,
                       priority, description, estimated_minutes, created_at
                FROM tasks WHERE {where_clause}
                ORDER BY priority ASC, due_time ASC
                LIMIT ? OFFSET ?
                """,
                params + [page_size, offset],
            )
        rows = await cursor.fetchall()

    # 批量获取标签，避免N+1查询
    task_ids = [row["task_id"] for row in rows]
    tags_map = await get_task_tags_batch(task_ids)

    tasks = []
    for row in rows:
        task = {
            "task_id": row["task_id"],
            "task_name": row["task_name"],
            "due_time": row["due_time"],
            "recurrence": row["recurrence"],
            "status": _translate_status(row["status"]),
            "priority": row["priority"],
            "description": row["description"],
            "estimated_minutes": row["estimated_minutes"],
            "created_at": row["created_at"],
            "tags": tags_map.get(row["task_id"], []),
        }
        tasks.append(task)

    return {
        "status": "success",
        "tasks": tasks,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


# ============================================================
# 下载历史记录
# ============================================================

async def add_download_record(
    url: str,
    category: str,
    filename: str = "",
    file_path: str = "",
    file_size: str = "",
    security_scan: str = "pending",
    status: str = "downloading",
    job_id: str = "",
) -> int:
    """记录下载历史"""
    async with aiosqlite.connect(str(DB_PATH)) as db:
        cursor = await db.execute(
            """INSERT INTO download_history (url, filename, category, file_path, file_size, security_scan, status, job_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (url, filename, category, file_path, file_size, security_scan, status, job_id),
        )
        await db.commit()
        return cursor.lastrowid


async def update_download_record(record_id: int, **kwargs):
    """更新下载记录（列名经过白名单校验，防止 SQL 注入）"""
    # 白名单校验列名
    valid, invalid = validate_update_columns("download_history", set(kwargs.keys()))
    if not valid:
        logger.warning(f"update_download_record 拒绝非法列名: {invalid}")
        return

    sets = []
    vals = []
    for k, v in kwargs.items():
        sets.append(f"{k} = ?")
        vals.append(v)
    if not sets:
        return
    vals.append(record_id)
    async with aiosqlite.connect(str(DB_PATH)) as db:
        await db.execute(
            f"UPDATE download_history SET {', '.join(sets)} WHERE id = ?",
            vals,
        )
        await db.commit()


async def get_download_history(
    category: str = "",
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """获取下载历史"""
    conditions = []
    params = []

    if category and category != "all":
        conditions.append("category = ?")
        params.append(category)

    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

    async with aiosqlite.connect(str(DB_PATH)) as db:
        cursor = await db.execute(
            f"SELECT COUNT(*) FROM download_history {where_clause}", params
        )
        total = (await cursor.fetchone())[0]

        offset = (page - 1) * page_size
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            f"""
            SELECT id, url, filename, category, file_path, file_size, security_scan, status, job_id, created_at
            FROM download_history {where_clause}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            params + [page_size, offset],
        )
        rows = await cursor.fetchall()

    records = [dict(row) for row in rows]

    return {
        "status": "success",
        "records": records,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# ============================================================
# 操作日志
# ============================================================

async def add_log(operation: str, endpoint: str, params: str = "", result: str = "success", detail: str = ""):
    """添加操作日志"""
    async with aiosqlite.connect(str(DB_PATH)) as db:
        await db.execute(
            """INSERT INTO operation_logs (operation, endpoint, params, result, detail)
               VALUES (?, ?, ?, ?, ?)""",
            (operation, endpoint, params, result, detail),
        )
        await db.commit()


async def get_logs(
    page: int = 1,
    page_size: int = 50,
    operation: str = "",
) -> dict:
    """获取操作日志"""
    conditions = []
    params = []

    if operation:
        conditions.append("operation = ?")
        params.append(operation)

    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

    async with aiosqlite.connect(str(DB_PATH)) as db:
        cursor = await db.execute(
            f"SELECT COUNT(*) FROM operation_logs {where_clause}", params
        )
        total = (await cursor.fetchone())[0]

        offset = (page - 1) * page_size
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            f"""
            SELECT id, operation, endpoint, params, result, detail, created_at
            FROM operation_logs {where_clause}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            params + [page_size, offset],
        )
        rows = await cursor.fetchall()

    logs = [dict(row) for row in rows]
    return {
        "status": "success",
        "logs": logs,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# ============================================================
# 仪表盘统计
# ============================================================

async def get_dashboard_stats() -> dict:
    """获取仪表盘统计信息"""
    async with aiosqlite.connect(str(DB_PATH)) as db:
        # 任务统计
        cursor = await db.execute("SELECT COUNT(*) FROM tasks WHERE status = 'pending'")
        tasks_pending = (await cursor.fetchone())[0]

        cursor = await db.execute("SELECT COUNT(*) FROM tasks WHERE status = 'completed'")
        tasks_completed = (await cursor.fetchone())[0]

        # 下载统计
        cursor = await db.execute("SELECT COUNT(*) FROM download_history")
        downloads_total = (await cursor.fetchone())[0]

        cursor = await db.execute("SELECT COUNT(*) FROM download_history WHERE status = 'completed'")
        downloads_completed = (await cursor.fetchone())[0]

        # 磁盘统计（在线程池中执行，避免阻塞事件循环）
        total_size, file_count = await asyncio.to_thread(_calc_disk_stats)

        # 最近操作
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT operation, endpoint, result, created_at FROM operation_logs ORDER BY created_at DESC LIMIT 10"
        )
        recent_logs = [dict(row) for row in await cursor.fetchall()]

        # 最近下载
        cursor = await db.execute(
            "SELECT filename, category, file_size, status, created_at FROM download_history ORDER BY created_at DESC LIMIT 5"
        )
        recent_downloads = [dict(row) for row in await cursor.fetchall()]

    return {
        "status": "success",
        "tasks": {"pending": tasks_pending, "completed": tasks_completed},
        "downloads": {"total": downloads_total, "completed": downloads_completed},
        "storage": {
            "total_size": human_size(total_size),
            "total_size_bytes": total_size,
            "file_count": file_count,
        },
        "recent_logs": recent_logs,
        "recent_downloads": recent_downloads,
    }


def _calc_disk_stats():
    """同步计算磁盘统计（供线程池调用）"""
    from config import DOWNLOADS_DIR
    total_size = 0
    file_count = 0
    if DOWNLOADS_DIR.exists():
        for f in DOWNLOADS_DIR.rglob("*"):
            if f.is_file():
                total_size += f.stat().st_size
                file_count += 1
    return total_size, file_count


# human_size 已移至 services.utils


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


# ============================================================
# 日历事件管理
# ============================================================

async def create_calendar_event(
    title: str,
    start_time: str,
    end_time: str,
    description: str = None,
    event_type: str = "personal",
    color: str = None,
) -> dict:
    """创建日历事件"""
    event_id = f"evt_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"

    # 默认颜色
    if not color:
        color_map = {
            "work": "#e74c3c",
            "meeting": "#9b59b6",
            "deadline": "#e67e22",
            "personal": "#3498db",
        }
        color = color_map.get(event_type, "#3498db")

    async with aiosqlite.connect(str(DB_PATH)) as db:
        await db.execute(
            """INSERT INTO calendar_events (event_id, title, description, start_time, end_time, event_type, color)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (event_id, title, description, start_time, end_time, event_type, color),
        )
        await db.commit()

    return {
        "status": "success",
        "event_id": event_id,
        "title": title,
        "start_time": start_time,
        "end_time": end_time,
    }


async def get_calendar_events(start_date: str, end_date: str) -> list[dict]:
    """获取日期范围内的日历事件"""
    async with aiosqlite.connect(str(DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT event_id, title, description, start_time, end_time, event_type, color
               FROM calendar_events
               WHERE date(start_time) >= date(?) AND date(start_time) <= date(?)
               ORDER BY start_time""",
            (start_date, end_date),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def delete_calendar_event(event_id: str) -> dict:
    """删除日历事件"""
    async with aiosqlite.connect(str(DB_PATH)) as db:
        cursor = await db.execute(
            "DELETE FROM calendar_events WHERE event_id = ?", (event_id,)
        )
        await db.commit()
        if cursor.rowcount == 0:
            return {"status": "error", "message": f"事件 {event_id} 不存在"}
    return {"status": "success", "message": f"事件 {event_id} 已删除"}


# ============================================================
# 日历视图数据
# ============================================================

async def get_calendar_view(year: int, month: int) -> dict:
    """获取月度日历视图数据"""
    import calendar

    # 获取该月第一天和最后一天
    first_day = datetime(year, month, 1)
    if month == 12:
        last_day = datetime(year + 1, 1, 1) - timedelta(days=1)
    else:
        last_day = datetime(year, month + 1, 1) - timedelta(days=1)

    # 计算日历显示范围（包含前后月的日期）
    cal = calendar.Calendar(firstweekday=0)  # 周一为一周开始
    month_days = cal.monthdayscalendar(year, month)

    start_date = datetime(year, month, 1) - timedelta(days=first_day.weekday())
    end_date = datetime(year, month, last_day.day) + timedelta(days=6 - last_day.weekday())

    # 获取该范围内的所有任务
    async with aiosqlite.connect(str(DB_PATH)) as db:
        db.row_factory = aiosqlite.Row

        # 任务（包括子任务计数）
        cursor = await db.execute(
            """SELECT t.task_id, t.task_name, t.due_time, t.recurrence, t.status, t.priority,
                      COUNT(s.subtask_id) as subtask_count,
                      SUM(CASE WHEN s.status = 'completed' THEN 1 ELSE 0 END) as completed_subtasks
               FROM tasks t
               LEFT JOIN subtasks s ON t.task_id = s.task_id
               WHERE t.status != 'deleted'
                 AND date(t.due_time) >= date(?) AND date(t.due_time) <= date(?)
               GROUP BY t.task_id
               ORDER BY t.due_time""",
            (start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")),
        )
        task_rows = await cursor.fetchall()

        # 批量获取标签，避免 N+1 查询
        task_ids = [row["task_id"] for row in task_rows]
        tags_map = await get_task_tags_batch(task_ids)

        tasks_by_date = {}
        for row in task_rows:
            task = dict(row)
            due_date = task["due_time"][:10]
            task["tags"] = tags_map.get(task["task_id"], [])

            if due_date not in tasks_by_date:
                tasks_by_date[due_date] = []
            tasks_by_date[due_date].append(task)

        # 日历事件
        cursor = await db.execute(
            """SELECT event_id, title, description, start_time, end_time, event_type, color
               FROM calendar_events
               WHERE date(start_time) >= date(?) AND date(start_time) <= date(?)
               ORDER BY start_time""",
            (start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")),
        )
        event_rows = await cursor.fetchall()
        events_by_date = {}
        for row in event_rows:
            event = dict(row)
            event_date = event["start_time"][:10]
            if event_date not in events_by_date:
                events_by_date[event_date] = []
            events_by_date[event_date].append(event)

        # 每日番茄钟计数
        cursor = await db.execute(
            """SELECT date(start_time) as date, COUNT(*) as count
               FROM pomodoro_sessions
               WHERE status = 'completed'
                 AND date(start_time) >= date(?) AND date(start_time) <= date(?)
               GROUP BY date(start_time)""",
            (start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")),
        )
        pomodoro_counts = {row[0]: row[1] for row in await cursor.fetchall()}

    # 构建日历天数
    days = []
    today_str = datetime.now().strftime("%Y-%m-%d")
    current_date = start_date

    while current_date <= end_date:
        date_str = current_date.strftime("%Y-%m-%d")
        is_current_month = current_date.month == month

        day_data = {
            "date": date_str,
            "weekday": current_date.weekday(),
            "is_today": date_str == today_str,
            "is_current_month": is_current_month,
            "tasks": tasks_by_date.get(date_str, []),
            "events": events_by_date.get(date_str, []),
            "pomodoro_count": pomodoro_counts.get(date_str, 0),
        }
        days.append(day_data)
        current_date += timedelta(days=1)

    return {
        "status": "success",
        "view_type": "month",
        "year": year,
        "month": month,
        "days": days,
    }


# ============================================================
# 笔记管理
# ============================================================

async def create_note(
    title: str,
    content: str = "",
    content_type: str = "markdown",
    tags: list[str] = None,
    task_id: str = None,
) -> dict:
    """创建笔记"""
    note_id = f"note_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    tags_json = json.dumps(tags or [])

    async with aiosqlite.connect(str(DB_PATH)) as db:
        await db.execute(
            """INSERT INTO notes (note_id, title, content, content_type, tags, task_id)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (note_id, title, content, content_type, tags_json, task_id),
        )
        await db.commit()

    return {
        "status": "success",
        "note_id": note_id,
        "title": title,
        "message": "笔记创建成功",
    }


async def get_note(note_id: str) -> Optional[dict]:
    """获取单个笔记"""
    async with aiosqlite.connect(str(DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM notes WHERE note_id = ?",
            (note_id,),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        note = dict(row)
        note["tags"] = json.loads(note.get("tags", "[]"))
        return note


async def update_note(
    note_id: str,
    title: str = None,
    content: str = None,
    tags: list[str] = None,
) -> dict:
    """更新笔记"""
    updates = []
    params = []

    if title is not None:
        updates.append("title = ?")
        params.append(title)
    if content is not None:
        updates.append("content = ?")
        params.append(content)
    if tags is not None:
        updates.append("tags = ?")
        params.append(json.dumps(tags))

    if not updates:
        return {"status": "error", "message": "没有要更新的字段"}

    updates.append("updated_at = datetime('now')")
    params.append(note_id)

    async with aiosqlite.connect(str(DB_PATH)) as db:
        cursor = await db.execute(
            f"UPDATE notes SET {', '.join(updates)} WHERE note_id = ?",
            params,
        )
        await db.commit()
        if cursor.rowcount == 0:
            return {"status": "error", "message": f"笔记 {note_id} 不存在"}

    return {"status": "success", "message": "笔记已更新"}


async def delete_note(note_id: str) -> dict:
    """删除笔记"""
    async with aiosqlite.connect(str(DB_PATH)) as db:
        cursor = await db.execute(
            "DELETE FROM notes WHERE note_id = ?",
            (note_id,),
        )
        await db.commit()
        if cursor.rowcount == 0:
            return {"status": "error", "message": f"笔记 {note_id} 不存在"}
    return {"status": "success", "message": "笔记已删除"}


async def get_all_notes(
    keyword: str = "",
    tag: str = "",
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """获取笔记列表"""
    conditions = []
    params = []

    if keyword:
        conditions.append("(title LIKE ? OR content LIKE ?)")
        params.extend([f"%{keyword}%", f"%{keyword}%"])

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    async with aiosqlite.connect(str(DB_PATH)) as db:
        cursor = await db.execute(
            f"SELECT COUNT(*) FROM notes WHERE {where_clause}",
            params,
        )
        total = (await cursor.fetchone())[0]

        db.row_factory = aiosqlite.Row
        offset = (page - 1) * page_size
        cursor = await db.execute(
            f"""SELECT note_id, title, content, content_type, tags, task_id,
                       created_at, updated_at
                FROM notes WHERE {where_clause}
                ORDER BY updated_at DESC
                LIMIT ? OFFSET ?""",
            params + [page_size, offset],
        )
        rows = await cursor.fetchall()

    notes = []
    for row in rows:
        note = dict(row)
        note["tags"] = json.loads(note.get("tags", "[]"))
        # 按标签过滤
        if tag and tag not in note["tags"]:
            continue
        notes.append(note)

    return {
        "status": "success",
        "notes": notes,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# ============================================================
# 习惯管理
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

