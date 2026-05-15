"""
MVP 收尾测试

覆盖本轮新增的关键能力：
- 单任务更新
- 任务标签覆盖更新
- 任务关联笔记
"""
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


with tempfile.TemporaryDirectory() as temp_dir:
    temp_db_path = Path(temp_dir) / "test_mvp_updates.db"
    with patch('config.DB_PATH', temp_db_path), \
         patch('services.task_service.DB_PATH', temp_db_path), \
         patch('services.note_service.DB_PATH', temp_db_path), \
         patch('services.tag_service.DB_PATH', temp_db_path):
        from services.task_service import init_db, add_task, update_task, get_all_tasks
        from services.note_service import create_note, get_all_notes


@pytest.fixture(autouse=True)
async def setup_db():
    await init_db()
    yield


@pytest.mark.asyncio
async def test_update_task_fields_and_tags():
    """任务应支持更新基础字段与覆盖标签"""
    created = await add_task(
        task_name="原任务",
        due_time="2026-05-20T10:00:00",
        priority=2,
        description="old",
        tags=["old-tag"],
    )
    task_id = created["task_id"]

    updated = await update_task(
        task_id=task_id,
        task_name="新任务",
        due_time="2026-05-21T11:00:00",
        start_time="2026-05-21T09:00:00",
        end_time="2026-05-21T10:00:00",
        priority=0,
        description="new",
        estimated_minutes=45,
        tags=["work", "deep"],
    )

    assert updated["status"] == "success"

    result = await get_all_tasks(status_filter="active", keyword="新任务", page_size=20)
    assert result["status"] == "success"
    assert len(result["tasks"]) == 1

    task = result["tasks"][0]
    assert task["task_name"] == "新任务"
    assert task["priority"] == 0
    assert task["description"] == "new"
    assert task["estimated_minutes"] == 45
    assert task["start_time"] == "2026-05-21T09:00:00"
    assert task["end_time"] == "2026-05-21T10:00:00"
    assert sorted(task["tags"]) == ["deep", "work"]


@pytest.mark.asyncio
async def test_update_task_requires_any_field():
    """空更新应返回错误"""
    created = await add_task(
        task_name="空更新任务",
        due_time="2026-05-20T10:00:00",
    )

    result = await update_task(task_id=created["task_id"])
    assert result["status"] == "error"


@pytest.mark.asyncio
async def test_create_note_with_task_relation():
    """笔记应保留 task_id 关联"""
    created_task = await add_task(
        task_name="带笔记任务",
        due_time="2026-05-22T18:00:00",
    )
    task_id = created_task["task_id"]

    created_note = await create_note(
        title="带关联笔记",
        content="记录任务执行",
        tags=["log"],
        task_id=task_id,
    )

    assert created_note["status"] == "success"

    notes = await get_all_notes(keyword="带关联笔记", page_size=20)
    assert notes["status"] == "success"
    assert len(notes["notes"]) == 1
    assert notes["notes"][0]["task_id"] == task_id
