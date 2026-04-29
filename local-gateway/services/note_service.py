"""
笔记管理服务 — SQLite CRUD
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Optional

import aiosqlite

from config import DB_PATH


# ============================================================
# 数据库初始化
# ============================================================

_schema = """
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
"""


async def init_note_db():
    """初始化笔记表结构"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(str(DB_PATH)) as db:
        await db.executescript(_schema)
        await db.commit()


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
