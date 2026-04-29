"""
标签服务测试模块
"""
import pytest
import aiosqlite
import tempfile
import os
from pathlib import Path

# 导入被测试的服务
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

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


@pytest.fixture
async def temp_db(monkeypatch):
    """创建临时数据库用于测试"""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_db_path = Path(temp_dir) / "test_tasks.db"

        # 修改配置中的数据库路径
        monkeypatch.setattr('config.DB_PATH', temp_db_path)

        # 初始化数据库
        await init_tag_db()

        yield temp_db_path


@pytest.fixture
def sample_task_id():
    """提供示例任务ID"""
    return "task_test_001"


@pytest.fixture
def another_task_id():
    """提供另一个示例任务ID"""
    return "task_test_002"


@pytest.mark.asyncio
async def test_create_tag(temp_db):
    """测试创建标签"""
    result = await create_tag("工作", "#ff0000")

    assert result["status"] == "success"
    assert result["name"] == "工作"
    assert result["color"] == "#ff0000"
    assert "tag_id" in result


@pytest.mark.asyncio
async def test_get_all_tags(temp_db):
    """测试获取所有标签"""
    # 先创建两个标签
    await create_tag("工作", "#ff0000")
    await create_tag("个人", "#00ff00")

    tags = await get_all_tags()

    assert len(tags) == 2
    tag_names = {tag["name"] for tag in tags}
    assert "工作" in tag_names
    assert "个人" in tag_names


@pytest.mark.asyncio
async def test_delete_tag(temp_db):
    """测试删除标签"""
    # 创建标签
    create_result = await create_tag("测试标签", "#0000ff")
    tag_id = create_result["tag_id"]

    # 确认标签存在
    tags_before = await get_all_tags()
    assert len(tags_before) == 1

    # 删除标签
    delete_result = await delete_tag(tag_id)
    assert delete_result["status"] == "success"

    # 确认标签已删除
    tags_after = await get_all_tags()
    assert len(tags_after) == 0


@pytest.mark.asyncio
async def test_add_and_get_task_tags(temp_db, sample_task_id):
    """测试添加和获取任务标签"""
    # 为任务添加标签
    add_result = await add_task_tags(sample_task_id, ["重要", "紧急"])
    assert add_result["status"] == "success"
    assert len(add_result["added"]) == 2

    # 获取任务标签
    tags = await get_task_tags(sample_task_id)
    assert set(tags) == {"重要", "紧急"}


@pytest.mark.asyncio
async def test_get_task_tags_batch(temp_db, sample_task_id, another_task_id):
    """测试批量获取任务标签"""
    # 为两个任务添加标签
    await add_task_tags(sample_task_id, ["重要", "紧急"])
    await add_task_tags(another_task_id, ["个人", "学习"])

    # 批量获取标签
    task_ids = [sample_task_id, another_task_id]
    tags_map = await get_task_tags_batch(task_ids)

    assert sample_task_id in tags_map
    assert another_task_id in tags_map
    assert set(tags_map[sample_task_id]) == {"重要", "紧急"}
    assert set(tags_map[another_task_id]) == {"个人", "学习"}


@pytest.mark.asyncio
async def test_remove_task_tags(temp_db, sample_task_id):
    """测试移除任务标签"""
    # 先添加标签
    await add_task_tags(sample_task_id, ["重要", "紧急", "待办"])

    # 移除部分标签
    remove_result = await remove_task_tags(sample_task_id, ["重要", "紧急"])
    assert remove_result["status"] == "success"

    # 验证剩余标签
    remaining_tags = await get_task_tags(sample_task_id)
    assert set(remaining_tags) == {"待办"}
