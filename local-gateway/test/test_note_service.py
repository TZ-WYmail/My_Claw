"""
笔记服务测试
"""
import tempfile
from pathlib import Path

import pytest
from unittest.mock import patch

# 需要在导入 note_service 前 patch DB_PATH
with tempfile.TemporaryDirectory() as temp_dir:
    temp_db_path = Path(temp_dir) / "test_notes.db"
    # 先 patch config 和 services.note_service 中的 DB_PATH
    with patch('config.DB_PATH', temp_db_path), \
         patch('services.note_service.DB_PATH', temp_db_path):
        from services.note_service import (
            init_note_db,
            create_note,
            get_note,
            update_note,
            delete_note,
            get_all_notes,
        )


@pytest.fixture(autouse=True)
async def setup_db():
    """每个测试前初始化数据库"""
    await init_note_db()
    yield


@pytest.mark.asyncio
async def test_create_note():
    """测试创建笔记"""
    result = await create_note(
        title="测试笔记",
        content="这是测试内容",
        tags=["测试", "笔记"],
    )
    assert result["status"] == "success"
    assert "note_id" in result
    assert result["title"] == "测试笔记"


@pytest.mark.asyncio
async def test_get_note():
    """测试获取笔记"""
    # 先创建笔记
    create_result = await create_note(
        title="获取测试",
        content="获取测试内容",
        tags=["tag1", "tag2"],
    )
    note_id = create_result["note_id"]

    # 获取笔记
    note = await get_note(note_id)
    assert note is not None
    assert note["title"] == "获取测试"
    assert note["content"] == "获取测试内容"
    assert note["tags"] == ["tag1", "tag2"]


@pytest.mark.asyncio
async def test_get_note_not_found():
    """测试获取不存在的笔记"""
    note = await get_note("nonexistent_id")
    assert note is None


@pytest.mark.asyncio
async def test_update_note():
    """测试更新笔记"""
    # 先创建笔记
    create_result = await create_note(
        title="原始标题",
        content="原始内容",
        tags=["old"],
    )
    note_id = create_result["note_id"]

    # 更新笔记
    update_result = await update_note(
        note_id=note_id,
        title="新标题",
        content="新内容",
        tags=["new1", "new2"],
    )
    assert update_result["status"] == "success"

    # 验证更新
    note = await get_note(note_id)
    assert note["title"] == "新标题"
    assert note["content"] == "新内容"
    assert note["tags"] == ["new1", "new2"]


@pytest.mark.asyncio
async def test_delete_note():
    """测试删除笔记"""
    # 先创建笔记
    create_result = await create_note(title="要删除的笔记")
    note_id = create_result["note_id"]

    # 删除笔记
    delete_result = await delete_note(note_id)
    assert delete_result["status"] == "success"

    # 验证已删除
    note = await get_note(note_id)
    assert note is None


@pytest.mark.asyncio
async def test_get_all_notes_keyword():
    """测试关键词搜索笔记"""
    # 创建多个笔记
    await create_note(title="苹果笔记", content="关于苹果的内容", tags=["fruit"])
    await create_note(title="香蕉笔记", content="关于香蕉的内容", tags=["fruit"])
    await create_note(title="汽车笔记", content="关于汽车的内容", tags=["vehicle"])

    # 搜索关键词
    result = await get_all_notes(keyword="苹果", page_size=10)
    assert result["status"] == "success"
    assert len(result["notes"]) == 1
    assert result["notes"][0]["title"] == "苹果笔记"
