"""
子任务管理服务
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime

import aiosqlite

from config import DB_PATH

logger = logging.getLogger(__name__)


# ============================================================
# 数据库初始化
# ============================================================

_schema = """
-- 子任务表
CREATE TABLE IF NOT EXISTS subtasks (
    subtask_id   TEXT PRIMARY KEY,
    task_id      TEXT NOT NULL,
    name         TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'pending',  -- pending/completed
    sort_order   INTEGER DEFAULT 0,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (task_id) REFERENCES tasks(task_id) ON DELETE CASCADE
);
"""


async def init_subtask_db():
    """初始化子任务数据库表结构"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(str(DB_PATH)) as db:
        await db.executescript(_schema)
        await db.commit()


# ============================================================
# 子任务管理
# ============================================================

async def create_subtask(task_id: str, name: str) -> dict:
    """创建子任务"""
    subtask_id = f"sub_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"

    async with aiosqlite.connect(str(DB_PATH)) as db:
        # 获取当前最大排序号
        cursor = await db.execute(
            "SELECT MAX(sort_order) FROM subtasks WHERE task_id = ?", (task_id,)
        )
        row = await cursor.fetchone()
        sort_order = (row[0] or 0) + 1

        await db.execute(
            "INSERT INTO subtasks (subtask_id, task_id, name, sort_order) VALUES (?, ?, ?, ?)",
            (subtask_id, task_id, name, sort_order),
        )
        await db.commit()

    return {
        "status": "success",
        "subtask_id": subtask_id,
        "task_id": task_id,
        "name": name,
        "sort_order": sort_order,
    }


async def get_subtasks(task_id: str) -> list[dict]:
    """获取任务的所有子任务"""
    async with aiosqlite.connect(str(DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT subtask_id, task_id, name, status, sort_order
               FROM subtasks WHERE task_id = ? ORDER BY sort_order""",
            (task_id,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def update_subtask(subtask_id: str, name: str = None, status: str = None) -> dict:
    """更新子任务"""
    updates = []
    params = []
    if name is not None:
        updates.append("name = ?")
        params.append(name)
    if status is not None:
        updates.append("status = ?")
        params.append(status)

    if not updates:
        return {"status": "error", "message": "没有要更新的字段"}

    params.append(subtask_id)
    async with aiosqlite.connect(str(DB_PATH)) as db:
        cursor = await db.execute(
            f"UPDATE subtasks SET {', '.join(updates)} WHERE subtask_id = ?",
            params,
        )
        await db.commit()
        if cursor.rowcount == 0:
            return {"status": "error", "message": f"子任务 {subtask_id} 不存在"}

    return {"status": "success", "message": f"子任务 {subtask_id} 已更新"}


async def delete_subtask(subtask_id: str) -> dict:
    """删除子任务"""
    async with aiosqlite.connect(str(DB_PATH)) as db:
        cursor = await db.execute(
            "DELETE FROM subtasks WHERE subtask_id = ?", (subtask_id,)
        )
        await db.commit()
        if cursor.rowcount == 0:
            return {"status": "error", "message": f"子任务 {subtask_id} 不存在"}
    return {"status": "success", "message": f"子任务 {subtask_id} 已删除"}
