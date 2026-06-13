"""
任务管理服务 — SQLite CRUD + APScheduler 定时提醒 + 批量任务编排
"""
from __future__ import annotations

import logging
import re
import sqlite3
import uuid
from datetime import datetime, timedelta
import aiosqlite

from config import DB_PATH
from services import dashboard_query_service
from services import task_command_service
from services import task_detail_service
from services import task_planning_service
from services import task_query_service


logger = logging.getLogger(__name__)


def _sync_task_module_paths() -> None:
    """Keep split task modules on same database path as compatibility facade."""
    task_command_service.DB_PATH = DB_PATH
    dashboard_query_service.DB_PATH = DB_PATH
    task_detail_service.DB_PATH = DB_PATH
    task_query_service.DB_PATH = DB_PATH


async def init_db():
    """兼容入口：初始化数据库表结构"""
    from services import bootstrap_service

    bootstrap_service.DB_PATH = DB_PATH
    await bootstrap_service.init_db()


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
    return await task_detail_service.get_task_detail(task_id)


# ============================================================
# 仪表盘统计
# ============================================================

async def get_dashboard_stats() -> dict:
    """获取仪表盘统计信息"""
    _sync_task_module_paths()
    return await dashboard_query_service.get_dashboard_stats()


# human_size 已移至 services.utils
