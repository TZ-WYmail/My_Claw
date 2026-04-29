# Batch 1: Architecture Foundation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split task_service into 6 domain services, unify search, and unify calendar — establishing clean architecture foundations.

**Architecture:** Extract domain logic from the monolithic task_service.py into independent service files with their own schema, CRUD, and init functions. The main task_service retains only task CRUD and delegates init_db orchestration. Search and calendar services absorb functionality from their scattered locations.

**Tech Stack:** Python 3.11, FastAPI, aiosqlite, Pydantic, pytest

---

## File Structure

### New Files (to create)
- `local-gateway/services/tag_service.py` — Tag CRUD + task-tag association
- `local-gateway/services/subtask_service.py` — Subtask CRUD
- `local-gateway/services/pomodoro_service.py` — Pomodoro session management
- `local-gateway/services/note_service.py` — Note CRUD
- `local-gateway/services/habit_service.py` — Habit CRUD + checkin
- `local-gateway/services/unified_search_service.py` — Merged file + fulltext + DB search
- `local-gateway/services/event_bus.py` — Application event bus (used by calendar + future workflow)
- `local-gateway/test/test_tag_service.py` — Tag service tests
- `local-gateway/test/test_subtask_service.py` — Subtask service tests
- `local-gateway/test/test_pomodoro_service.py` — Pomodoro service tests
- `local-gateway/test/test_note_service.py` — Note service tests
- `local-gateway/test/test_habit_service.py` — Habit service tests
- `local-gateway/test/test_unified_search.py` — Unified search tests

### Modified Files
- `local-gateway/services/task_service.py` — Remove extracted code, keep task CRUD + init_db orchestration
- `local-gateway/routers/task_manager.py` — No change (already imports from task_service)
- `local-gateway/routers/habits.py` — Change import from `task_service` to `habit_service`
- `local-gateway/routers/notes.py` — Change import from `task_service` to `note_service`
- `local-gateway/routers/file_search.py` — Rewrite to use unified_search_service
- `local-gateway/routers/fulltext_search.py` — Rewrite to delegate to unified_search_service
- `local-gateway/routers/dashboard.py` — Update imports for tag/stats
- `local-gateway/routers/calendar_sync.py` — Update to use calendar_service for local events
- `local-gateway/services/calendar_sync_service.py` — Absorb calendar_events CRUD from task_service
- `local-gateway/services/download_service.py` — Update import paths if needed
- `local-gateway/main.py` — Update router imports if needed
- `local-gateway/models/schemas.py` — Add UnifiedSearchRequest/Response schemas
- `local-gateway/test/test_api.py` — Update for new service paths

### Deleted Files
- `local-gateway/services/fulltext_search_service.py` — Merged into unified_search_service.py
- `local-gateway/services/search_service.py` — Merged into unified_search_service.py

---

## Task 1: Extract tag_service.py

**Files:**
- Create: `local-gateway/services/tag_service.py`
- Create: `local-gateway/test/test_tag_service.py`
- Modify: `local-gateway/services/task_service.py` (remove tag functions, add import)

- [ ] **Step 1: Create the tag service test file**

```python
# local-gateway/test/test_tag_service.py
import pytest
import asyncio
from services.tag_service import (
    init_tag_db,
    create_tag,
    get_all_tags,
    delete_tag,
    add_task_tags,
    get_task_tags,
    get_task_tags_batch,
    remove_task_tags,
)


@pytest.fixture(autouse=True)
async def setup_db(tmp_path, monkeypatch):
    """Use a temp database for each test."""
    import services.tag_service as mod
    db_path = tmp_path / "test_tags.db"
    monkeypatch.setattr(mod, "DB_PATH", db_path)
    await init_tag_db()


@pytest.mark.asyncio
async def test_create_tag():
    result = await create_tag("工作", "#e74c3c")
    assert result["status"] == "success"
    assert result["name"] == "工作"
    assert result["color"] == "#e74c3c"


@pytest.mark.asyncio
async def test_get_all_tags():
    await create_tag("工作")
    await create_tag("学习")
    tags = await get_all_tags()
    assert len(tags) == 2
    names = {t["name"] for t in tags}
    assert names == {"工作", "学习"}


@pytest.mark.asyncio
async def test_delete_tag():
    result = await create_tag("临时")
    tag_id = result["tag_id"]
    del_result = await delete_tag(tag_id)
    assert del_result["status"] == "success"
    tags = await get_all_tags()
    assert len(tags) == 0


@pytest.mark.asyncio
async def test_add_and_get_task_tags():
    await create_tag("重要")
    result = await add_task_tags("task_test_001", ["重要"])
    assert result["status"] == "success"
    assert "重要" in result["added"]

    tags = await get_task_tags("task_test_001")
    assert tags == ["重要"]


@pytest.mark.asyncio
async def test_get_task_tags_batch():
    await create_tag("A")
    await create_tag("B")
    await add_task_tags("task_001", ["A"])
    await add_task_tags("task_002", ["B"])

    result = await get_task_tags_batch(["task_001", "task_002", "task_003"])
    assert result["task_001"] == ["A"]
    assert result["task_002"] == ["B"]
    assert result["task_003"] == []


@pytest.mark.asyncio
async def test_remove_task_tags():
    await create_tag("临时")
    await add_task_tags("task_001", ["临时"])
    await remove_task_tags("task_001", ["临时"])
    tags = await get_task_tags("task_001")
    assert tags == []
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd /home/tanzheng/Desktop/My_Claw/local-gateway && python -m pytest test/test_tag_service.py -v 2>&1 | head -30`
Expected: FAIL — `ModuleNotFoundError: No module named 'services.tag_service'`

- [ ] **Step 3: Create tag_service.py**

```python
# local-gateway/services/tag_service.py
"""
标签管理服务 — 标签 CRUD + 任务标签关联
"""
from __future__ import annotations

import logging
from typing import Optional

import aiosqlite

from config import DB_PATH

logger = logging.getLogger(__name__)

_schema = """
CREATE TABLE IF NOT EXISTS tags (
    tag_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL UNIQUE,
    color        TEXT DEFAULT '#3498db',
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS task_tags (
    task_id      TEXT NOT NULL,
    tag_id       INTEGER NOT NULL,
    PRIMARY KEY (task_id, tag_id),
    FOREIGN KEY (task_id) REFERENCES tasks(task_id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES tags(tag_id) ON DELETE CASCADE
);
"""


async def init_tag_db():
    """初始化标签相关表"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(str(DB_PATH)) as db:
        await db.executescript(_schema)
        await db.commit()


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
            cursor = await db.execute("SELECT tag_id FROM tags WHERE name = ?", (name,))
            row = await cursor.fetchone()
            if row:
                tag_id = row[0]
            else:
                cursor = await db.execute(
                    "INSERT INTO tags (name) VALUES (?)", (name,)
                )
                tag_id = cursor.lastrowid

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
    """批量获取多个任务的标签列表"""
    if not task_ids:
        return {}

    async with aiosqlite.connect(str(DB_PATH)) as db:
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
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd /home/tanzheng/Desktop/My_Claw/local-gateway && python -m pytest test/test_tag_service.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Remove tag functions from task_service.py**

In `local-gateway/services/task_service.py`:
- Remove functions: `create_tag`, `get_all_tags`, `delete_tag`, `add_task_tags`, `get_task_tags`, `get_task_tags_batch`, `remove_task_tags`
- Remove `tags` and `task_tags` table definitions from `_schema`
- Add `from services.tag_service import add_task_tags, get_task_tags_batch` at top
- In `add_task()`, the existing `await add_task_tags(task_id, tags)` call now uses the imported version
- In `get_weekly_plan()` and `get_all_tasks()`, the existing `await get_task_tags_batch(task_ids)` calls now use the imported version
- In `init_db()`, add `from services.tag_service import init_tag_db` and `await init_tag_db()`

- [ ] **Step 6: Run existing tests to verify nothing broke**

Run: `cd /home/tanzheng/Desktop/My_Claw/local-gateway && python -m pytest test/ -v --timeout=30 2>&1 | tail -30`
Expected: All existing tests still pass (or same failures as before — no new regressions)

- [ ] **Step 7: Commit**

```bash
cd /home/tanzheng/Desktop/My_Claw
git add local-gateway/services/tag_service.py local-gateway/services/task_service.py local-gateway/test/test_tag_service.py
git commit -m "feat: extract tag_service from task_service — tag CRUD + task-tag association"
```

---

## Task 2: Extract subtask_service.py

**Files:**
- Create: `local-gateway/services/subtask_service.py`
- Create: `local-gateway/test/test_subtask_service.py`
- Modify: `local-gateway/services/task_service.py` (remove subtask functions)

- [ ] **Step 1: Create the subtask service test file**

```python
# local-gateway/test/test_subtask_service.py
import pytest
from services.subtask_service import (
    init_subtask_db,
    create_subtask,
    get_subtasks,
    update_subtask,
    delete_subtask,
)


@pytest.fixture(autouse=True)
async def setup_db(tmp_path, monkeypatch):
    import services.subtask_service as mod
    db_path = tmp_path / "test_subtasks.db"
    monkeypatch.setattr(mod, "DB_PATH", db_path)
    await init_subtask_db()


@pytest.mark.asyncio
async def test_create_subtask():
    result = await create_subtask("task_001", "写提纲")
    assert result["status"] == "success"
    assert result["name"] == "写提纲"
    assert result["sort_order"] == 1


@pytest.mark.asyncio
async def test_get_subtasks():
    await create_subtask("task_001", "步骤一")
    await create_subtask("task_001", "步骤二")
    subtasks = await get_subtasks("task_001")
    assert len(subtasks) == 2
    assert subtasks[0]["sort_order"] < subtasks[1]["sort_order"]


@pytest.mark.asyncio
async def test_update_subtask():
    r = await create_subtask("task_001", "草稿")
    result = await update_subtask(r["subtask_id"], name="定稿", status="completed")
    assert result["status"] == "success"
    subtasks = await get_subtasks("task_001")
    assert subtasks[0]["name"] == "定稿"
    assert subtasks[0]["status"] == "completed"


@pytest.mark.asyncio
async def test_delete_subtask():
    r = await create_subtask("task_001", "临时步骤")
    result = await delete_subtask(r["subtask_id"])
    assert result["status"] == "success"
    subtasks = await get_subtasks("task_001")
    assert len(subtasks) == 0
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd /home/tanzheng/Desktop/My_Claw/local-gateway && python -m pytest test/test_subtask_service.py -v 2>&1 | head -20`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Create subtask_service.py**

```python
# local-gateway/services/subtask_service.py
"""
子任务管理服务 — 子任务 CRUD + 排序
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Optional

import aiosqlite

from config import DB_PATH

logger = logging.getLogger(__name__)

_schema = """
CREATE TABLE IF NOT EXISTS subtasks (
    subtask_id   TEXT PRIMARY KEY,
    task_id      TEXT NOT NULL,
    name         TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'pending',
    sort_order   INTEGER DEFAULT 0,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (task_id) REFERENCES tasks(task_id) ON DELETE CASCADE
);
"""


async def init_subtask_db():
    """初始化子任务表"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(str(DB_PATH)) as db:
        await db.executescript(_schema)
        await db.commit()


async def create_subtask(task_id: str, name: str) -> dict:
    """创建子任务"""
    subtask_id = f"sub_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"

    async with aiosqlite.connect(str(DB_PATH)) as db:
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
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd /home/tanzheng/Desktop/My_Claw/local-gateway && python -m pytest test/test_subtask_service.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Remove subtask functions from task_service.py**

In `local-gateway/services/task_service.py`:
- Remove functions: `create_subtask`, `get_subtasks`, `update_subtask`, `delete_subtask`
- Remove `subtasks` table definition from `_schema`
- In `init_db()`, add `from services.subtask_service import init_subtask_db` and `await init_subtask_db()`

- [ ] **Step 6: Run all tests**

Run: `cd /home/tanzheng/Desktop/My_Claw/local-gateway && python -m pytest test/ -v --timeout=30 2>&1 | tail -20`
Expected: No new regressions

- [ ] **Step 7: Commit**

```bash
cd /home/tanzheng/Desktop/My_Claw
git add local-gateway/services/subtask_service.py local-gateway/services/task_service.py local-gateway/test/test_subtask_service.py
git commit -m "feat: extract subtask_service from task_service — subtask CRUD"
```

---

## Task 3: Extract pomodoro_service.py

**Files:**
- Create: `local-gateway/services/pomodoro_service.py`
- Create: `local-gateway/test/test_pomodoro_service.py`
- Modify: `local-gateway/services/task_service.py` (remove pomodoro functions)

- [ ] **Step 1: Create the pomodoro service test file**

```python
# local-gateway/test/test_pomodoro_service.py
import pytest
from services.pomodoro_service import (
    init_pomodoro_db,
    start_pomodoro,
    complete_pomodoro,
    interrupt_pomodoro,
    get_active_pomodoro,
    get_pomodoro_stats,
    get_pomodoro_history,
)


@pytest.fixture(autouse=True)
async def setup_db(tmp_path, monkeypatch):
    import services.pomodoro_service as mod
    db_path = tmp_path / "test_pomodoro.db"
    monkeypatch.setattr(mod, "DB_PATH", db_path)
    await init_pomodoro_db()
    # Reset global state
    mod._active_pomodoro = None


@pytest.mark.asyncio
async def test_start_pomodoro():
    result = await start_pomodoro(duration_minutes=25)
    assert result["status"] == "success"
    assert result["duration_minutes"] == 25


@pytest.mark.asyncio
async def test_start_pomodoro_when_active():
    await start_pomodoro(duration_minutes=25)
    result = await start_pomodoro(duration_minutes=25)
    assert result["status"] == "error"
    assert "已有进行中" in result["message"]


@pytest.mark.asyncio
async def test_complete_pomodoro():
    await start_pomodoro(duration_minutes=25)
    result = await complete_pomodoro()
    assert result["status"] == "success"
    assert result["actual_minutes"] >= 0


@pytest.mark.asyncio
async def test_complete_pomodoro_when_none():
    result = await complete_pomodoro()
    assert result["status"] == "error"


@pytest.mark.asyncio
async def test_interrupt_pomodoro():
    await start_pomodoro(duration_minutes=25)
    result = await interrupt_pomodoro(reason="电话打扰")
    assert result["status"] == "success"
    assert result["reason"] == "电话打扰"


@pytest.mark.asyncio
async def test_get_active_pomodoro():
    await start_pomodoro(duration_minutes=25)
    active = await get_active_pomodoro()
    assert active is not None
    assert active["status"] == "running"


@pytest.mark.asyncio
async def test_get_pomodoro_stats():
    await start_pomodoro(duration_minutes=1)
    await complete_pomodoro()
    stats = await get_pomodoro_stats()
    assert stats["status"] == "success"
    assert stats["today_count"] >= 1
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd /home/tanzheng/Desktop/My_Claw/local-gateway && python -m pytest test/test_pomodoro_service.py -v 2>&1 | head -20`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Create pomodoro_service.py**

Extract the full pomodoro code block from `task_service.py` (lines 1192–1399 in the original) into `local-gateway/services/pomodoro_service.py`. The file should contain:
- `_schema` with only the `pomodoro_sessions` table
- `init_pomodoro_db()`
- `_active_pomodoro` global variable
- `start_pomodoro()`, `complete_pomodoro()`, `interrupt_pomodoro()`, `get_active_pomodoro()`
- `get_pomodoro_stats()`, `get_pomodoro_history()`
- Import `from config import DB_PATH`
- In `start_pomodoro()`, the task_name lookup should call `from services.task_service import ...` to avoid circular import at module level — use a local import inside the function

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd /home/tanzheng/Desktop/My_Claw/local-gateway && python -m pytest test/test_pomodoro_service.py -v`
Expected: All 8 tests PASS

- [ ] **Step 5: Remove pomodoro functions from task_service.py**

- Remove: `_active_pomodoro`, `start_pomodoro`, `complete_pomodoro`, `interrupt_pomodoro`, `get_active_pomodoro`, `get_pomodoro_stats`, `get_pomodoro_history`
- Remove `pomodoro_sessions` from `_schema`
- In `init_db()`, add `from services.pomodoro_service import init_pomodoro_db` and `await init_pomodoro_db()`

- [ ] **Step 6: Run all tests**

Run: `cd /home/tanzheng/Desktop/My_Claw/local-gateway && python -m pytest test/ -v --timeout=30 2>&1 | tail -20`
Expected: No new regressions

- [ ] **Step 7: Commit**

```bash
cd /home/tanzheng/Desktop/My_Claw
git add local-gateway/services/pomodoro_service.py local-gateway/services/task_service.py local-gateway/test/test_pomodoro_service.py
git commit -m "feat: extract pomodoro_service from task_service — pomodoro session management"
```

---

## Task 4: Extract note_service.py

**Files:**
- Create: `local-gateway/services/note_service.py`
- Create: `local-gateway/test/test_note_service.py`
- Modify: `local-gateway/services/task_service.py` (remove note functions)
- Modify: `local-gateway/routers/notes.py` (change import)

- [ ] **Step 1: Create the note service test file**

```python
# local-gateway/test/test_note_service.py
import pytest
from services.note_service import (
    init_note_db,
    create_note,
    get_note,
    update_note,
    delete_note,
    get_all_notes,
)


@pytest.fixture(autouse=True)
async def setup_db(tmp_path, monkeypatch):
    import services.note_service as mod
    db_path = tmp_path / "test_notes.db"
    monkeypatch.setattr(mod, "DB_PATH", db_path)
    await init_note_db()


@pytest.mark.asyncio
async def test_create_note():
    result = await create_note("会议记录", content="讨论了Q2计划", tags=["工作"])
    assert result["status"] == "success"
    assert result["title"] == "会议记录"


@pytest.mark.asyncio
async def test_get_note():
    r = await create_note("测试笔记", content="内容")
    note = await get_note(r["note_id"])
    assert note is not None
    assert note["title"] == "测试笔记"
    assert note["tags"] == []


@pytest.mark.asyncio
async def test_get_note_not_found():
    note = await get_note("nonexistent")
    assert note is None


@pytest.mark.asyncio
async def test_update_note():
    r = await create_note("草稿", content="初始")
    result = await update_note(r["note_id"], title="终稿", content="更新后")
    assert result["status"] == "success"
    note = await get_note(r["note_id"])
    assert note["title"] == "终稿"


@pytest.mark.asyncio
async def test_delete_note():
    r = await create_note("临时笔记")
    result = await delete_note(r["note_id"])
    assert result["status"] == "success"
    note = await get_note(r["note_id"])
    assert note is None


@pytest.mark.asyncio
async def test_get_all_notes_keyword():
    await create_note("Python学习", content="Flask框架")
    await create_note("Go学习", content="Gin框架")
    result = await get_all_notes(keyword="Python")
    assert result["total"] >= 1
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd /home/tanzheng/Desktop/My_Claw/local-gateway && python -m pytest test/test_note_service.py -v 2>&1 | head -20`
Expected: FAIL

- [ ] **Step 3: Create note_service.py**

Extract note functions from `task_service.py` (lines 1587–1732 in the original) into `local-gateway/services/note_service.py`. The file should contain:
- `_schema` with only the `notes` table
- `init_note_db()`
- `create_note()`, `get_note()`, `update_note()`, `delete_note()`, `get_all_notes()`

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd /home/tanzheng/Desktop/My_Claw/local-gateway && python -m pytest test/test_note_service.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Remove note functions from task_service.py and update router**

In `local-gateway/services/task_service.py`:
- Remove: `create_note`, `get_note`, `update_note`, `delete_note`, `get_all_notes`
- Remove `notes` from `_schema`
- In `init_db()`, add `from services.note_service import init_note_db` and `await init_note_db()`

In `local-gateway/routers/notes.py`:
- Change `from services import task_service` to `from services import note_service`
- Change all `task_service.create_note(...)` to `note_service.create_note(...)`
- Same for `get_note`, `update_note`, `delete_note`, `get_all_notes`

- [ ] **Step 6: Run all tests**

Run: `cd /home/tanzheng/Desktop/My_Claw/local-gateway && python -m pytest test/ -v --timeout=30 2>&1 | tail -20`
Expected: No new regressions

- [ ] **Step 7: Commit**

```bash
cd /home/tanzheng/Desktop/My_Claw
git add local-gateway/services/note_service.py local-gateway/services/task_service.py local-gateway/routers/notes.py local-gateway/test/test_note_service.py
git commit -m "feat: extract note_service — note CRUD + router import update"
```

---

## Task 5: Extract habit_service.py

**Files:**
- Create: `local-gateway/services/habit_service.py`
- Create: `local-gateway/test/test_habit_service.py`
- Modify: `local-gateway/services/task_service.py` (remove habit functions)
- Modify: `local-gateway/routers/habits.py` (change import)

- [ ] **Step 1: Create the habit service test file**

```python
# local-gateway/test/test_habit_service.py
import pytest
from services.habit_service import (
    init_habit_db,
    create_habit,
    get_all_habits,
    get_habit,
    checkin_habit,
    get_habit_stats,
    delete_habit,
)


@pytest.fixture(autouse=True)
async def setup_db(tmp_path, monkeypatch):
    import services.habit_service as mod
    db_path = tmp_path / "test_habits.db"
    monkeypatch.setattr(mod, "DB_PATH", db_path)
    await init_habit_db()


@pytest.mark.asyncio
async def test_create_habit():
    result = await create_habit("跑步", frequency="daily")
    assert result["status"] == "success"
    assert result["name"] == "跑步"


@pytest.mark.asyncio
async def test_get_all_habits():
    await create_habit("跑步")
    await create_habit("阅读", frequency="daily")
    habits = await get_all_habits()
    assert len(habits) == 2


@pytest.mark.asyncio
async def test_checkin_habit():
    r = await create_habit("冥想")
    result = await checkin_habit(r["habit_id"])
    assert result["status"] == "success"
    habit = await get_habit(r["habit_id"])
    assert len(habit["checkins"]) >= 1


@pytest.mark.asyncio
async def test_get_habit_stats():
    r = await create_habit("喝水")
    await checkin_habit(r["habit_id"])
    stats = await get_habit_stats(r["habit_id"])
    assert stats["status"] == "success"
    assert stats["total_days"] >= 1


@pytest.mark.asyncio
async def test_delete_habit():
    r = await create_habit("临时习惯")
    result = await delete_habit(r["habit_id"])
    assert result["status"] == "success"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd /home/tanzheng/Desktop/My_Claw/local-gateway && python -m pytest test/test_habit_service.py -v 2>&1 | head -20`
Expected: FAIL

- [ ] **Step 3: Create habit_service.py**

Extract habit functions from `task_service.py` (lines 1737–1912 in the original) into `local-gateway/services/habit_service.py`. The file should contain:
- `_schema` with `habits` and `habit_checkins` tables
- `init_habit_db()`
- `create_habit()`, `get_all_habits()`, `get_habit()`, `_calculate_streak()`, `checkin_habit()`, `get_habit_stats()`, `delete_habit()`

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd /home/tanzheng/Desktop/My_Claw/local-gateway && python -m pytest test/test_habit_service.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Remove habit functions from task_service.py and update router**

In `local-gateway/services/task_service.py`:
- Remove: `create_habit`, `get_all_habits`, `get_habit`, `_calculate_streak`, `checkin_habit`, `get_habit_stats`, `delete_habit`
- Remove `habits` and `habit_checkins` from `_schema`
- In `init_db()`, add `from services.habit_service import init_habit_db` and `await init_habit_db()`

In `local-gateway/routers/habits.py`:
- Change `from services import task_service` to `from services import habit_service`
- Change all `task_service.create_habit(...)` to `habit_service.create_habit(...)`
- Same for all other habit functions

- [ ] **Step 6: Run all tests**

Run: `cd /home/tanzheng/Desktop/My_Claw/local-gateway && python -m pytest test/ -v --timeout=30 2>&1 | tail -20`
Expected: No new regressions

- [ ] **Step 7: Commit**

```bash
cd /home/tanzheng/Desktop/My_Claw
git add local-gateway/services/habit_service.py local-gateway/services/task_service.py local-gateway/routers/habits.py local-gateway/test/test_habit_service.py
git commit -m "feat: extract habit_service — habit CRUD + checkin + router import update"
```

---

## Task 6: Migrate calendar events to calendar_sync_service.py

**Files:**
- Modify: `local-gateway/services/calendar_sync_service.py` (absorb calendar_events CRUD)
- Modify: `local-gateway/services/task_service.py` (remove calendar event functions)
- Modify: `local-gateway/routers/calendar_sync.py` (add local event endpoints)

- [ ] **Step 1: Add calendar event functions to calendar_sync_service.py**

In `local-gateway/services/calendar_sync_service.py`:
- Add `_calendar_schema` containing the `calendar_events` table CREATE statement (copied from task_service.py)
- Add `init_calendar_db()` function
- Add `create_calendar_event()`, `get_calendar_events()`, `delete_calendar_event()`, `get_calendar_view()` functions (copied from task_service.py)
- For `get_calendar_view()`, change the `from services import task_service` local import to use `from services.task_service import get_weekly_plan, get_task_tags_batch` (or whatever task queries are needed) to query task data for the calendar view
- Add `import calendar as cal_module` (Python stdlib) at the top to avoid name collision with the `calendar` variable in existing code

- [ ] **Step 2: Remove calendar event functions from task_service.py**

In `local-gateway/services/task_service.py`:
- Remove: `create_calendar_event`, `get_calendar_events`, `delete_calendar_event`, `get_calendar_view`
- Remove `calendar_events` from `_schema`
- In `init_db()`, add `from services.calendar_sync_service import init_calendar_db` and `await init_calendar_db()`

- [ ] **Step 3: Update calendar_sync_service.py internal references**

In `local-gateway/services/calendar_sync_service.py`, the `sync_from_google_calendar()` and `sync_from_outlook_calendar()` functions currently do `from services import task_service` and call `task_service.create_calendar_event(...)`. Change these to call the local `create_calendar_event()` function directly (now in the same file).

- [ ] **Step 4: Update calendar_sync router**

In `local-gateway/routers/calendar_sync.py`, add new endpoints for local calendar event management:
- `POST /api/calendar/events` — Create local event
- `GET /api/calendar/events` — List events in date range
- `DELETE /api/calendar/events/{event_id}` — Delete event
- `GET /api/calendar/view` — Calendar month view

These should import from `services.calendar_sync_service` instead of `services.task_service`.

- [ ] **Step 5: Run all tests**

Run: `cd /home/tanzheng/Desktop/My_Claw/local-gateway && python -m pytest test/ -v --timeout=30 2>&1 | tail -20`
Expected: No new regressions

- [ ] **Step 6: Commit**

```bash
cd /home/tanzheng/Desktop/My_Claw
git add local-gateway/services/calendar_sync_service.py local-gateway/services/task_service.py local-gateway/routers/calendar_sync.py
git commit -m "feat: unify calendar — migrate calendar_events CRUD to calendar_sync_service"
```

---

## Task 7: Create unified search service

**Files:**
- Create: `local-gateway/services/unified_search_service.py`
- Create: `local-gateway/test/test_unified_search.py`
- Modify: `local-gateway/models/schemas.py` (add UnifiedSearchRequest/Response)
- Modify: `local-gateway/routers/file_search.py` (delegate to unified service)
- Modify: `local-gateway/routers/fulltext_search.py` (delegate to unified service)

- [ ] **Step 1: Add unified search schemas**

In `local-gateway/models/schemas.py`, add:

```python
class SearchScope(str, enum.Enum):
    all = "all"
    files = "files"
    tasks = "tasks"
    notes = "notes"
    habits = "habits"


class UnifiedSearchRequest(BaseModel):
    keyword: str = Field(..., min_length=1, description="搜索关键词")
    scope: SearchScope = Field(SearchScope.all, description="搜索范围")
    category: Optional[str] = Field("all", description="文件分类（仅 files scope）")
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)


class UnifiedSearchResponse(BaseModel):
    status: str
    results: dict = Field(default_factory=dict)
    total: int = 0
    scope: str = "all"
```

- [ ] **Step 2: Create the unified search test file**

```python
# local-gateway/test/test_unified_search.py
import pytest
from services.unified_search_service import unified_search


@pytest.fixture(autouse=True)
async def setup_db(tmp_path, monkeypatch):
    import services.task_service as ts_mod
    import services.note_service as ns_mod
    import services.habit_service as hs_mod
    db_path = tmp_path / "test_unified.db"
    monkeypatch.setattr(ts_mod, "DB_PATH", db_path)
    monkeypatch.setattr(ns_mod, "DB_PATH", db_path)
    monkeypatch.setattr(hs_mod, "DB_PATH", db_path)
    from services.task_service import init_db
    await init_db()


@pytest.mark.asyncio
async def test_unified_search_tasks():
    from services.task_service import add_task
    await add_task("学习Python", "2026-05-01T09:00:00")
    result = await unified_search("Python", scope="tasks")
    assert result["total"] >= 1
    assert len(result["results"]["tasks"]) >= 1


@pytest.mark.asyncio
async def test_unified_search_notes():
    from services.note_service import create_note
    await create_note("Python笔记", content="Flask教程")
    result = await unified_search("Python", scope="notes")
    assert result["total"] >= 1
    assert len(result["results"]["notes"]) >= 1


@pytest.mark.asyncio
async def test_unified_search_scope_all():
    from services.task_service import add_task
    from services.note_service import create_note
    await add_task("学习Go", "2026-05-01T09:00:00")
    await create_note("Go笔记", content="Gin框架")
    result = await unified_search("Go", scope="all")
    assert result["total"] >= 2


@pytest.mark.asyncio
async def test_unified_search_empty_keyword():
    result = await unified_search("", scope="all")
    assert result["status"] == "error"
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `cd /home/tanzheng/Desktop/My_Claw/local-gateway && python -m pytest test/test_unified_search.py -v 2>&1 | head -20`
Expected: FAIL

- [ ] **Step 4: Create unified_search_service.py**

```python
# local-gateway/services/unified_search_service.py
"""
统一搜索服务 — 文件搜索 + 全文搜索 + 数据库搜索
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Optional

from config import CATEGORY_DIRS, DOWNLOADS_DIR
from services.utils import human_size

logger = logging.getLogger(__name__)


async def unified_search(
    keyword: str,
    scope: str = "all",
    category: str = "all",
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """统一搜索入口"""
    if not keyword or not keyword.strip():
        return {"status": "error", "message": "关键词不能为空", "total": 0, "results": {}, "scope": scope}

    tasks = []

    if scope in ("all", "files"):
        tasks.append(_search_files(keyword, category))
    else:
        tasks.append(_empty_result("files"))

    if scope in ("all", "tasks"):
        tasks.append(_search_tasks(keyword, page, page_size))
    else:
        tasks.append(_empty_result("tasks"))

    if scope in ("all", "notes"):
        tasks.append(_search_notes(keyword, page, page_size))
    else:
        tasks.append(_empty_result("notes"))

    if scope in ("all", "habits"):
        tasks.append(_search_habits(keyword))
    else:
        tasks.append(_empty_result("habits"))

    results_list = await asyncio.gather(*tasks)
    results = {
        "files": results_list[0],
        "tasks": results_list[1],
        "notes": results_list[2],
        "habits": results_list[3],
    }

    total = sum(len(v) if isinstance(v, list) else v.get("total", 0) for v in results.values())

    return {
        "status": "success",
        "results": results,
        "total": total,
        "scope": scope,
    }


async def _empty_result(scope: str) -> dict:
    return {"items": [], "total": 0}


async def _search_files(keyword: str, category: str) -> dict:
    """搜索本地文件（异步包装）"""
    return await asyncio.to_thread(_search_files_sync, keyword, category)


def _search_files_sync(keyword: str, category: str) -> dict:
    """同步文件搜索（在线程池中执行）"""
    from datetime import datetime as dt

    if category == "all":
        search_dirs = list(CATEGORY_DIRS.values())
    else:
        target = CATEGORY_DIRS.get(category)
        if not target:
            return {"items": [], "total": 0}
        search_dirs = [target]

    keyword_lower = keyword.lower()
    items = []

    for search_dir in search_dirs:
        if not search_dir.exists():
            continue
        for file_path in search_dir.rglob("*"):
            if not file_path.is_file():
                continue
            if keyword_lower and keyword_lower not in file_path.name.lower():
                continue
            stat = file_path.stat()
            items.append({
                "filename": file_path.name,
                "category": file_path.parent.name,
                "path": str(file_path),
                "size": human_size(stat.st_size),
                "downloaded_at": dt.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%dT%H:%M:%S"),
            })

    items.sort(key=lambda x: x["filename"])
    return {"items": items, "total": len(items)}


async def _search_tasks(keyword: str, page: int, page_size: int) -> dict:
    """搜索任务"""
    from services.task_service import get_all_tasks
    result = await get_all_tasks(keyword=keyword, page=page, page_size=page_size)
    return {"items": result.get("tasks", []), "total": result.get("total", 0)}


async def _search_notes(keyword: str, page: int, page_size: int) -> dict:
    """搜索笔记"""
    from services.note_service import get_all_notes
    result = await get_all_notes(keyword=keyword, page=page, page_size=page_size)
    return {"items": result.get("notes", []), "total": result.get("total", 0)}


async def _search_habits(keyword: str) -> dict:
    """搜索习惯"""
    from services.habit_service import get_all_habits
    habits = await get_all_habits()
    keyword_lower = keyword.lower()
    filtered = [h for h in habits if keyword_lower in h.get("name", "").lower()]
    return {"items": filtered, "total": len(filtered)}


# Full-text search integration (from fulltext_search_service.py)
async def search_fulltext(query: str, category: str = None, top_k: int = 20) -> dict:
    """全文搜索（保留兼容接口）"""
    try:
        from services.fulltext_search_service import search_fulltext as _ft_search
        return await _ft_search(query, category, top_k)
    except ImportError:
        return {"status": "success", "results": [], "total_results": 0, "message": "全文搜索不可用"}


async def index_all_files(category: str = None) -> dict:
    """构建全文索引（保留兼容接口）"""
    try:
        from services.fulltext_search_service import index_all_files as _idx
        return await _idx(category)
    except ImportError:
        return {"status": "error", "message": "全文索引不可用"}


async def get_index_stats() -> dict:
    """获取索引统计（保留兼容接口）"""
    try:
        from services.fulltext_search_service import get_index_stats as _stats
        return await _stats()
    except ImportError:
        return {"status": "error", "message": "全文索引不可用"}


async def rebuild_index() -> dict:
    """重建索引（保留兼容接口）"""
    try:
        from services.fulltext_search_service import rebuild_index as _rebuild
        return await _rebuild()
    except ImportError:
        return {"status": "error", "message": "全文索引不可用"}
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `cd /home/tanzheng/Desktop/My_Claw/local-gateway && python -m pytest test/test_unified_search.py -v`
Expected: All 4 tests PASS

- [ ] **Step 6: Update file_search router to delegate to unified service**

In `local-gateway/routers/file_search.py`, replace the entire content with:

```python
"""
POST /api/search — 统一搜索端点（文件 + 任务 + 笔记 + 习惯）
GET  /api/search/fulltext — 全文搜索（兼容旧端点）
POST /api/search/index — 构建全文索引
GET  /api/search/index/stats — 索引统计
POST /api/search/index/rebuild — 重建索引
"""
from fastapi import APIRouter, Query

from models.schemas import FileSearchRequest, FileSearchResponse, UnifiedSearchRequest, UnifiedSearchResponse
from services.unified_search_service import unified_search, search_fulltext, index_all_files, get_index_stats, rebuild_index

router = APIRouter(prefix="/search", tags=["search"])


@router.post("", response_model=UnifiedSearchResponse)
async def handle_unified_search(request: UnifiedSearchRequest):
    """统一搜索：文件 + 任务 + 笔记 + 习惯"""
    result = await unified_search(
        keyword=request.keyword,
        scope=request.scope.value,
        category=request.category or "all",
        page=request.page,
        page_size=request.page_size,
    )
    return UnifiedSearchResponse(**result)


# 保留旧端点兼容
@router.post("/legacy", response_model=FileSearchResponse)
async def handle_legacy_search(request: FileSearchRequest):
    """旧文件搜索端点（兼容）"""
    result = await unified_search(
        keyword=request.keyword,
        scope="files",
        category=request.category.value,
    )
    files = result.get("results", {}).get("files", {})
    return FileSearchResponse(
        status="success",
        total=files.get("total", 0),
        files=files.get("items", []),
    )


@router.get("/fulltext")
async def fulltext_search_endpoint(
    q: str = Query(..., description="搜索关键词"),
    category: str = Query(None, description="分类筛选"),
    top_k: int = Query(20, ge=1, le=100),
):
    """全文搜索下载的文件内容"""
    return await search_fulltext(q, category, top_k)


@router.post("/index")
async def build_index(category: str = Query(None, description="指定分类索引")):
    """构建/更新搜索索引"""
    return await index_all_files(category)


@router.get("/index/stats")
async def index_statistics():
    """获取索引统计"""
    return await get_index_stats()


@router.post("/index/rebuild")
async def rebuild_search_index():
    """重建搜索索引"""
    return await rebuild_index()
```

- [ ] **Step 7: Update main.py router imports**

In `local-gateway/main.py`:
- Remove `from routers import fulltext_search` (the fulltext_search router endpoints are now merged into file_search router)
- Remove `app.include_router(fulltext_search.router, prefix="/api")`
- Keep `from routers import file_search` and `app.include_router(file_search.router, prefix="/api")`

- [ ] **Step 8: Run all tests**

Run: `cd /home/tanzheng/Desktop/My_Claw/local-gateway && python -m pytest test/ -v --timeout=30 2>&1 | tail -20`
Expected: No new regressions

- [ ] **Step 9: Commit**

```bash
cd /home/tanzheng/Desktop/My_Claw
git add local-gateway/services/unified_search_service.py local-gateway/test/test_unified_search.py local-gateway/models/schemas.py local-gateway/routers/file_search.py local-gateway/main.py
git rm local-gateway/routers/fulltext_search.py
git commit -m "feat: unified search service — merge file_search + fulltext_search into single endpoint"
```

---

## Task 8: Final cleanup — verify task_service.py is slim

**Files:**
- Modify: `local-gateway/services/task_service.py` (final cleanup)
- Modify: `local-gateway/routers/dashboard.py` (verify imports)

- [ ] **Step 1: Verify task_service.py only contains task-related functions**

After all extractions, `task_service.py` should contain ONLY:
- `_schema` with `tasks`, `download_history`, `operation_logs`, `sync_devices`, `sync_offline_queue`, `push_tokens` tables
- `init_db()` — orchestration entry point calling all `init_*_db()` functions
- `add_task()`, `delete_task()`, `complete_task()`, `get_weekly_plan()`, `get_all_tasks()`
- `batch_add_tasks()`, `analyze_tasks()`, `_generate_daily_plan()`, `_normalize_time()`, helper functions
- `add_download_record()`, `update_download_record()`, `get_download_history()`
- `add_log()`, `get_logs()`
- `get_dashboard_stats()`, `_calc_disk_stats()`

It should NOT contain: tag, subtask, pomodoro, note, habit, or calendar event functions.

- [ ] **Step 2: Verify dashboard router imports**

In `local-gateway/routers/dashboard.py`, the `get_all_tasks` and `get_dashboard_stats` calls should still work because they remain in `task_service.py`. Verify no broken imports.

- [ ] **Step 3: Run full test suite**

Run: `cd /home/tanzheng/Desktop/My_Claw/local-gateway && python -m pytest test/ -v --timeout=30 2>&1 | tail -30`
Expected: All tests pass, no import errors

- [ ] **Step 4: Verify application starts**

Run: `cd /home/tanzheng/Desktop/My_Claw/local-gateway && timeout 5 python -c "from main import app; print('App imported successfully')" 2>&1`
Expected: `App imported successfully`

- [ ] **Step 5: Commit**

```bash
cd /home/tanzheng/Desktop/My_Claw
git add -A
git commit -m "refactor: batch1 complete — task_service split, unified search, unified calendar"
```

---

## Self-Review Checklist

- [x] **Spec coverage**: Task 1–5 cover task_service split; Task 6 covers calendar unification; Task 7 covers search unification; Task 8 covers final verification
- [x] **Placeholder scan**: No TBD/TODO/fill-in-later — all tasks contain complete code or exact instructions
- [x] **Type consistency**: All service functions preserve their original signatures; router imports match new service names
- [x] **Missing items**: Download history/logs/dashboard functions remain in task_service as designed (they relate to operational stats, not a distinct domain)
