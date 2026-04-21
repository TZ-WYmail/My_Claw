"""
任务管理服务 — SQLite CRUD + APScheduler 定时提醒 + 批量任务编排
"""
from __future__ import annotations

import asyncio
import sqlite3
import uuid
from datetime import datetime, timedelta
from typing import Optional

import aiosqlite

from config import DB_PATH


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
"""


async def init_db():
    """初始化数据库表结构"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(str(DB_PATH)) as db:
        await db.executescript(_schema)
        await db.commit()


# ============================================================
# CRUD 操作
# ============================================================

async def add_task(
    task_name: str,
    due_time: str,
    recurrence: str = "once",
) -> dict:
    """添加任务并返回任务信息"""
    task_id = f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"

    async with aiosqlite.connect(str(DB_PATH)) as db:
        await db.execute(
            "INSERT INTO tasks (task_id, task_name, due_time, recurrence) VALUES (?, ?, ?, ?)",
            (task_id, task_name, due_time, recurrence),
        )
        await db.commit()

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


async def get_weekly_plan() -> dict:
    """获取当前周的任务列表"""
    now = datetime.now()
    # 计算本周一和本周日
    monday = now - timedelta(days=now.weekday())
    sunday = monday + timedelta(days=6)
    monday_str = monday.strftime("%Y-%m-%dT00:00:00")
    sunday_str = sunday.strftime("%Y-%m-%dT23:59:59")

    async with aiosqlite.connect(str(DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT task_id, task_name, due_time, recurrence, status
            FROM tasks
            WHERE status != 'deleted'
              AND due_time >= ? AND due_time <= ?
            ORDER BY due_time
            """,
            (monday_str, sunday_str),
        )
        rows = await cursor.fetchall()

    tasks = []
    for row in rows:
        tasks.append({
            "task_id": row["task_id"],
            "task_name": row["task_name"],
            "due_time": row["due_time"],
            "recurrence": row["recurrence"],
            "status": _translate_status(row["status"]),
        })

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
        })

    # 生成时间线摘要
    timeline = []
    for date_key in sorted(by_date.keys()):
        names = by_date[date_key]
        weekday = _date_to_weekday(date_key)
        timeline.append(f"📅 {date_key} ({weekday}) — {len(names)} 项: {', '.join(names)}")

    return {
        "status": "success",
        "total": len(raw_tasks),
        "analyzed": analyzed,
        "timeline": timeline,
        "by_date": {k: v for k, v in sorted(by_date.items())},
        "message": f"解析完成: {len(analyzed)} 项任务, 跨 {len(by_date)} 天",
    }


def _normalize_time(time_str: str) -> str:
    """
    尝试将各种时间格式转为 ISO 8601。
    支持: "3月22日" → "2026-03-22T09:00:00", "2026-03-22" → "2026-03-22T09:00:00"
    """
    if not time_str:
        return ""

    import re

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
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """获取全部任务，支持状态筛选和关键词搜索"""
    conditions = []
    params = []

    if status_filter == "active":
        conditions.append("status != 'deleted'")
    elif status_filter in ("pending", "completed", "deleted"):
        conditions.append("status = ?")
        params.append(status_filter)

    if keyword:
        conditions.append("task_name LIKE ?")
        params.append(f"%{keyword}%")

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    # 总数
    async with aiosqlite.connect(str(DB_PATH)) as db:
        cursor = await db.execute(
            f"SELECT COUNT(*) FROM tasks WHERE {where_clause}", params
        )
        total = (await cursor.fetchone())[0]

        # 分页查询
        offset = (page - 1) * page_size
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            f"""
            SELECT task_id, task_name, due_time, recurrence, status, created_at
            FROM tasks WHERE {where_clause}
            ORDER BY due_time DESC
            LIMIT ? OFFSET ?
            """,
            params + [page_size, offset],
        )
        rows = await cursor.fetchall()

    tasks = []
    for row in rows:
        tasks.append({
            "task_id": row["task_id"],
            "task_name": row["task_name"],
            "due_time": row["due_time"],
            "recurrence": row["recurrence"],
            "status": _translate_status(row["status"]),
            "created_at": row["created_at"],
        })

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
    """更新下载记录"""
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

        # 磁盘统计
        from config import DOWNLOADS_DIR
        total_size = 0
        file_count = 0
        if DOWNLOADS_DIR.exists():
            for f in DOWNLOADS_DIR.rglob("*"):
                if f.is_file():
                    total_size += f.stat().st_size
                    file_count += 1

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
            "total_size": _human_size(total_size),
            "total_size_bytes": total_size,
            "file_count": file_count,
        },
        "recent_logs": recent_logs,
        "recent_downloads": recent_downloads,
    }


def _human_size(size_bytes: int) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"
