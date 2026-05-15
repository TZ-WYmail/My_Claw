"""
标签管理服务 — 标签CRUD + 任务标签关联
"""
from __future__ import annotations

import aiosqlite
import logging

from config import DB_PATH

# 配置日志
logger = logging.getLogger(__name__)

# ============================================================
# 数据库初始化
# ============================================================

_schema = """
-- 标签表
CREATE TABLE IF NOT EXISTS tags (
    tag_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL UNIQUE,
    color        TEXT DEFAULT '#3498db',  -- 标签颜色
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

-- 任务标签关联表
CREATE TABLE IF NOT EXISTS task_tags (
    task_id      TEXT NOT NULL,
    tag_id       INTEGER NOT NULL,
    PRIMARY KEY (task_id, tag_id),
    FOREIGN KEY (task_id) REFERENCES tasks(task_id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES tags(tag_id) ON DELETE CASCADE
);
"""


async def init_tag_db():
    """初始化标签相关数据库表结构"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(str(DB_PATH)) as db:
        await db.executescript(_schema)
        await db.commit()


# ============================================================
# 标签管理
# ============================================================

async def create_tag(name: str, color: str = "#3498db") -> dict:
    """创建标签"""
    try:
        async with aiosqlite.connect(str(DB_PATH)) as db:
            cursor = await db.execute(
                "INSERT INTO tags (name, color) VALUES (?, ?)",
                (name, color),
            )
            await db.commit()
            return {
                "status": "success",
                "tag_id": cursor.lastrowid,
                "name": name,
                "color": color,
            }
    except Exception as e:
        logger.error(f"创建标签失败: {e}")
        return {"status": "error", "message": str(e)}


async def get_all_tags() -> list[dict]:
    """获取所有标签"""
    async with aiosqlite.connect(str(DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT tag_id, name, color FROM tags ORDER BY name")
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def delete_tag(tag_id: int) -> dict:
    """删除标签"""
    async with aiosqlite.connect(str(DB_PATH)) as db:
        await db.execute("DELETE FROM task_tags WHERE tag_id = ?", (tag_id,))
        cursor = await db.execute("DELETE FROM tags WHERE tag_id = ?", (tag_id,))
        await db.commit()
        if cursor.rowcount == 0:
            return {"status": "error", "message": f"标签 {tag_id} 不存在"}
    return {"status": "success", "message": f"标签 {tag_id} 已删除"}


async def add_task_tags(task_id: str, tag_names: list[str]) -> dict:
    """为任务添加标签（自动创建不存在的标签）"""
    async with aiosqlite.connect(str(DB_PATH)) as db:
        added = []
        for name in tag_names:
            # 获取或创建标签
            cursor = await db.execute("SELECT tag_id FROM tags WHERE name = ?", (name,))
            row = await cursor.fetchone()
            if row:
                tag_id = row[0]
            else:
                cursor = await db.execute(
                    "INSERT INTO tags (name) VALUES (?)", (name,)
                )
                tag_id = cursor.lastrowid

            # 关联任务和标签
            try:
                await db.execute(
                    "INSERT INTO task_tags (task_id, tag_id) VALUES (?, ?)",
                    (task_id, tag_id),
                )
                added.append(name)
            except Exception:
                pass  # 已存在，忽略

        await db.commit()
    return {"status": "success", "added": added}


async def get_task_tags(task_id: str) -> list[str]:
    """获取任务的标签列表"""
    async with aiosqlite.connect(str(DB_PATH)) as db:
        cursor = await db.execute(
            """SELECT t.name FROM tags t
               JOIN task_tags tt ON t.tag_id = tt.tag_id
               WHERE tt.task_id = ? ORDER BY t.name""",
            (task_id,),
        )
        rows = await cursor.fetchall()
        return [row[0] for row in rows]


async def get_task_tags_batch(task_ids: list[str]) -> dict[str, list[str]]:
    """批量获取多个任务的标签列表 - 优化N+1查询问题"""
    if not task_ids:
        return {}

    async with aiosqlite.connect(str(DB_PATH)) as db:
        # 使用单个查询获取所有任务的标签
        placeholders = ','.join(['?' for _ in task_ids])
        cursor = await db.execute(
            f"""SELECT tt.task_id, t.name
                FROM tags t
                JOIN task_tags tt ON t.tag_id = tt.tag_id
                WHERE tt.task_id IN ({placeholders})
                ORDER BY tt.task_id, t.name""",
            task_ids,
        )
        rows = await cursor.fetchall()

        # 构建任务ID到标签列表的映射
        result = {task_id: [] for task_id in task_ids}
        for task_id, tag_name in rows:
            result[task_id].append(tag_name)
        return result


async def remove_task_tags(task_id: str, tag_names: list[str]) -> dict:
    """移除任务的标签"""
    async with aiosqlite.connect(str(DB_PATH)) as db:
        for name in tag_names:
            await db.execute(
                """DELETE FROM task_tags WHERE task_id = ? AND tag_id =
                   (SELECT tag_id FROM tags WHERE name = ?)""",
                (task_id, name),
            )
        await db.commit()
    return {"status": "success"}


async def set_task_tags(task_id: str, tag_names: list[str]) -> dict:
    """覆盖设置任务标签"""
    async with aiosqlite.connect(str(DB_PATH)) as db:
        await db.execute("DELETE FROM task_tags WHERE task_id = ?", (task_id,))
        await db.commit()
    if not tag_names:
        return {"status": "success", "added": []}
    return await add_task_tags(task_id, tag_names)
