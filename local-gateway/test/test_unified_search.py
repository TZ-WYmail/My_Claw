"""
统一搜索服务测试
运行: cd local-gateway && conda run -n claude python -m pytest test/test_unified_search.py -v
"""
import pytest
from services.unified_search_service import unified_search


@pytest.fixture(autouse=True)
async def setup_db(tmp_path, monkeypatch):
    import services.task_service as ts_mod
    import services.note_service as ns_mod
    import services.habit_service as hs_mod
    import services.tag_service as tg_mod
    import services.subtask_service as st_mod
    import services.pomodoro_service as pm_mod
    import services.calendar_sync_service as cs_mod
    db_path = tmp_path / "test_unified.db"
    monkeypatch.setattr(ts_mod, "DB_PATH", db_path)
    monkeypatch.setattr(ns_mod, "DB_PATH", db_path)
    monkeypatch.setattr(hs_mod, "DB_PATH", db_path)
    monkeypatch.setattr(tg_mod, "DB_PATH", db_path)
    monkeypatch.setattr(st_mod, "DB_PATH", db_path)
    monkeypatch.setattr(pm_mod, "DB_PATH", db_path)
    monkeypatch.setattr(cs_mod, "DB_PATH", db_path)
    from services.task_service import init_db
    await init_db()


@pytest.mark.asyncio
async def test_unified_search_tasks():
    from services.task_service import add_task
    await add_task("学习Python", "2026-05-01T09:00:00")
    result = await unified_search("Python", scope="tasks")
    assert result["total"] >= 1
    assert len(result["results"]["tasks"]["items"]) >= 1


@pytest.mark.asyncio
async def test_unified_search_notes():
    from services.note_service import create_note
    await create_note("Python笔记", content="Flask教程")
    result = await unified_search("Python", scope="notes")
    assert result["total"] >= 1
    assert len(result["results"]["notes"]["items"]) >= 1


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
