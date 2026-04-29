"""
子任务服务测试
"""
import tempfile
from pathlib import Path

import pytest

from services.subtask_service import (
    init_subtask_db,
    create_subtask,
    get_subtasks,
    update_subtask,
    delete_subtask,
)


@pytest.fixture
async def temp_db(monkeypatch):
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_db_path = Path(temp_dir) / "test_subtasks.db"
        monkeypatch.setattr('config.DB_PATH', temp_db_path)
        monkeypatch.setattr('services.subtask_service.DB_PATH', temp_db_path)
        await init_subtask_db()
        yield temp_db_path


@pytest.mark.asyncio
async def test_create_subtask(temp_db):
    """测试创建子任务"""
    task_id = "test_task_001"

    # 创建第一个子任务
    result = await create_subtask(task_id, "子任务1")
    assert result["status"] == "success"
    assert result["task_id"] == task_id
    assert result["name"] == "子任务1"
    assert result["sort_order"] == 1
    assert "subtask_id" in result

    # 创建第二个子任务，排序号应该递增
    result2 = await create_subtask(task_id, "子任务2")
    assert result2["sort_order"] == 2


@pytest.mark.asyncio
async def test_get_subtasks(temp_db):
    """测试获取子任务列表"""
    task_id = "test_task_002"

    # 创建两个子任务
    await create_subtask(task_id, "子任务A")
    await create_subtask(task_id, "子任务B")

    # 获取子任务列表
    subtasks = await get_subtasks(task_id)
    assert len(subtasks) == 2
    assert subtasks[0]["name"] == "子任务A"
    assert subtasks[0]["sort_order"] == 1
    assert subtasks[1]["name"] == "子任务B"
    assert subtasks[1]["sort_order"] == 2

    # 测试空列表
    subtasks_empty = await get_subtasks("nonexistent_task")
    assert len(subtasks_empty) == 0


@pytest.mark.asyncio
async def test_update_subtask(temp_db):
    """测试更新子任务"""
    task_id = "test_task_003"

    # 创建子任务
    create_result = await create_subtask(task_id, "原始名称")
    subtask_id = create_result["subtask_id"]

    # 更新名称
    update_result = await update_subtask(subtask_id, name="新名称")
    assert update_result["status"] == "success"

    # 验证更新
    subtasks = await get_subtasks(task_id)
    assert subtasks[0]["name"] == "新名称"
    assert subtasks[0]["status"] == "pending"

    # 更新状态
    update_result2 = await update_subtask(subtask_id, status="completed")
    assert update_result2["status"] == "success"

    # 验证更新
    subtasks2 = await get_subtasks(task_id)
    assert subtasks2[0]["status"] == "completed"

    # 同时更新名称和状态
    update_result3 = await update_subtask(subtask_id, name="最终名称", status="pending")
    assert update_result3["status"] == "success"

    # 验证更新
    subtasks3 = await get_subtasks(task_id)
    assert subtasks3[0]["name"] == "最终名称"
    assert subtasks3[0]["status"] == "pending"

    # 测试不存在的子任务
    update_result4 = await update_subtask("nonexistent_sub", name="测试")
    assert update_result4["status"] == "error"

    # 测试没有要更新的字段
    update_result5 = await update_subtask(subtask_id)
    assert update_result5["status"] == "error"


@pytest.mark.asyncio
async def test_delete_subtask(temp_db):
    """测试删除子任务"""
    task_id = "test_task_004"

    # 创建子任务
    create_result = await create_subtask(task_id, "要删除的子任务")
    subtask_id = create_result["subtask_id"]

    # 验证子任务存在
    subtasks_before = await get_subtasks(task_id)
    assert len(subtasks_before) == 1

    # 删除子任务
    delete_result = await delete_subtask(subtask_id)
    assert delete_result["status"] == "success"

    # 验证子任务已删除
    subtasks_after = await get_subtasks(task_id)
    assert len(subtasks_after) == 0

    # 测试删除不存在的子任务
    delete_result2 = await delete_subtask("nonexistent_sub")
    assert delete_result2["status"] == "error"
