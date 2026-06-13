"""
任务管理服务 — SQLite CRUD + APScheduler 定时提醒 + 批量任务编排
"""
from __future__ import annotations

import asyncio
import logging
import re
import sqlite3
import uuid
from datetime import datetime, timedelta
import aiosqlite

from config import DB_PATH
from services import dashboard_query_service
from services import task_command_service
from services import task_planning_service
from services import task_query_service
from services.utils import human_size
from services.tag_service import add_task_tags, get_task_tags_batch
from services.time_service import extract_system_date, is_overdue, system_now, system_today_iso


logger = logging.getLogger(__name__)


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
    start_time    TEXT,  -- 任务执行开始时间（ISO 8601，可空）
    end_time      TEXT,  -- 任务执行结束时间（ISO 8601，可空）
    completed_at  TEXT,  -- 任务完成时间（可空）
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

CREATE TABLE IF NOT EXISTS planning_previews (
    preview_id   TEXT PRIMARY KEY,
    payload      TEXT NOT NULL,
    selected_variant TEXT,
    source       TEXT DEFAULT 'ai_planning',
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    expire_at    TEXT
);
"""


def _sync_task_module_paths() -> None:
    """Keep split task modules on same database path as compatibility facade."""
    task_command_service.DB_PATH = DB_PATH
    dashboard_query_service.DB_PATH = DB_PATH
    task_query_service.DB_PATH = DB_PATH


async def init_db():
    """初始化数据库表结构"""
    _sync_task_module_paths()
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

    # 初始化番茄钟相关表
    from services.pomodoro_service import init_pomodoro_db
    await init_pomodoro_db()

    # 初始化习惯相关表
    from services.habit_service import init_habit_db
    await init_habit_db()

    # 初始化笔记相关表
    from services.note_service import init_note_db
    await init_note_db()

    # 初始化日历相关表
    from services.calendar_sync_service import init_calendar_db
    await init_calendar_db()

    # 迁移：为已有数据库添加 start_time / end_time / completed_at 列
    async with aiosqlite.connect(str(DB_PATH)) as db:
        cursor = await db.execute("PRAGMA table_info(tasks)")
        existing_columns = {row[1] for row in await cursor.fetchall()}
        for col in ("start_time", "end_time", "completed_at"):
            if col not in existing_columns:
                await db.execute(f"ALTER TABLE tasks ADD COLUMN {col} TEXT")
        await db.commit()


# ============================================================
# CRUD 操作
# ============================================================

async def _check_conflicts(start_time: str, end_time: str, exclude_task_id: str = None) -> list[str]:
    _sync_task_module_paths()
    return await task_command_service._check_conflicts(
        start_time=start_time,
        end_time=end_time,
        exclude_task_id=exclude_task_id,
    )


async def add_task(
    task_name: str,
    due_time: str,
    recurrence: str = "once",
    priority: int = 2,
    description: str = None,
    estimated_minutes: int = None,
    tags: list[str] = None,
    start_time: str = None,
    end_time: str = None,
) -> dict:
    _sync_task_module_paths()
    return await task_command_service.add_task(
        task_name=task_name,
        due_time=due_time,
        recurrence=recurrence,
        priority=priority,
        description=description,
        estimated_minutes=estimated_minutes,
        tags=tags,
        start_time=start_time,
        end_time=end_time,
    )


async def delete_task(task_id: str) -> dict:
    _sync_task_module_paths()
    return await task_command_service.delete_task(task_id)


async def complete_task(task_id: str) -> dict:
    _sync_task_module_paths()
    return await task_command_service.complete_task(task_id)


async def get_task_by_id(task_id: str) -> dict | None:
    """按 ID 获取单个任务，附带标签"""
    _sync_task_module_paths()
    return await task_query_service.get_task_by_id(task_id)


async def update_task(
    task_id: str,
    task_name: str = None,
    due_time: str = None,
    recurrence: str = None,
    priority: int = None,
    description: str = None,
    estimated_minutes: int = None,
    start_time: str = None,
    end_time: str = None,
    tags: list[str] = None,
) -> dict:
    _sync_task_module_paths()
    return await task_command_service.update_task(
        task_id=task_id,
        task_name=task_name,
        due_time=due_time,
        recurrence=recurrence,
        priority=priority,
        description=description,
        estimated_minutes=estimated_minutes,
        start_time=start_time,
        end_time=end_time,
        tags=tags,
    )


async def batch_update_tasks(
    task_ids: list[str],
    priority: int = None,
    due_time: str = None,
    tags_add: list[str] = None,
    tags_remove: list[str] = None,
) -> dict:
    _sync_task_module_paths()
    return await task_command_service.batch_update_tasks(
        task_ids=task_ids,
        priority=priority,
        due_time=due_time,
        tags_add=tags_add,
        tags_remove=tags_remove,
    )


async def batch_complete_tasks(task_ids: list[str]) -> dict:
    _sync_task_module_paths()
    return await task_command_service.batch_complete_tasks(task_ids)


async def batch_delete_tasks(task_ids: list[str]) -> dict:
    _sync_task_module_paths()
    return await task_command_service.batch_delete_tasks(task_ids)


async def get_weekly_plan(monday_iso: str = "", sunday_iso: str = "") -> dict:
    """获取指定周的任务列表。不传参则取当前周。"""
    _sync_task_module_paths()
    return await task_query_service.get_weekly_plan(monday_iso, sunday_iso)


async def get_pending_tasks(today_only: bool = False) -> dict:
    """获取未完成任务，支持仅返回今日相关任务"""
    _sync_task_module_paths()
    return await task_query_service.get_pending_tasks(today_only=today_only)


# ============================================================
# 批量任务编排
# ============================================================

async def batch_add_tasks(tasks: list[dict]) -> dict:
    _sync_task_module_paths()
    return await task_command_service.batch_add_tasks(tasks)


async def analyze_tasks(raw_tasks: list[dict]) -> dict:
    _sync_task_module_paths()
    task_planning_service.DB_PATH = DB_PATH
    return await task_planning_service.analyze_tasks(raw_tasks)


def _generate_daily_plan(analyzed: list[dict]) -> dict[str, dict]:
    return task_planning_service.generate_daily_plan(analyzed)


def _normalize_time(time_str: str) -> str:
    return task_planning_service.normalize_time(time_str)


def _date_to_weekday(date_str: str) -> str:
    return task_planning_service.date_to_weekday(date_str)


# ============================================================
# 辅助函数
# ============================================================

def _calc_next_reminder(due_time: str, recurrence: str) -> str:
    return task_planning_service.calc_next_reminder(due_time, recurrence)


def _human_readable_time(iso_time: str) -> str:
    return task_planning_service.human_readable_time(iso_time)


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
    _sync_task_module_paths()
    return await task_query_service.get_all_tasks(
        status_filter=status_filter,
        keyword=keyword,
        tag=tag,
        priority=priority,
        page=page,
        page_size=page_size,
    )


async def get_download_history(
    category: str = "",
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """获取下载历史"""
    _sync_task_module_paths()
    return await dashboard_query_service.get_download_history(
        category=category,
        page=page,
        page_size=page_size,
    )


async def get_logs(
    page: int = 1,
    page_size: int = 50,
    operation: str = "",
) -> dict:
    """获取操作日志"""
    _sync_task_module_paths()
    return await dashboard_query_service.get_logs(
        page=page,
        page_size=page_size,
        operation=operation,
    )


async def get_task_detail(task_id: str) -> dict:
    """获取任务详情聚合信息"""
    _sync_task_module_paths()
    return await task_query_service.get_task_detail(task_id)


# ============================================================
# 仪表盘统计
# ============================================================

async def get_dashboard_stats() -> dict:
    """获取仪表盘统计信息"""
    _sync_task_module_paths()
    return await dashboard_query_service.get_dashboard_stats()


# human_size 已移至 services.utils
