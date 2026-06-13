import aiosqlite
import pytest
from unittest.mock import AsyncMock, patch


@pytest.fixture(autouse=True)
async def setup_db(tmp_path, monkeypatch):
    import services.bootstrap_service as bootstrap_service
    import services.task_command_service as task_command_service
    import services.task_detail_service as task_detail_service
    import services.dashboard_query_service as dashboard_query_service
    import services.task_query_service as task_query_service
    import services.note_service as note_service
    import services.tag_service as tag_service
    import services.subtask_service as subtask_service
    import services.pomodoro_service as pomodoro_service
    import services.calendar_sync_service as calendar_sync_service

    db_path = tmp_path / "test_task_query.db"
    monkeypatch.setattr(bootstrap_service, "DB_PATH", db_path)
    monkeypatch.setattr(task_command_service, "DB_PATH", db_path)
    monkeypatch.setattr(task_detail_service, "DB_PATH", db_path)
    monkeypatch.setattr(task_query_service, "DB_PATH", db_path)
    monkeypatch.setattr(dashboard_query_service, "DB_PATH", db_path)
    monkeypatch.setattr(note_service, "DB_PATH", db_path)
    monkeypatch.setattr(tag_service, "DB_PATH", db_path)
    monkeypatch.setattr(subtask_service, "DB_PATH", db_path)
    monkeypatch.setattr(pomodoro_service, "DB_PATH", db_path)
    monkeypatch.setattr(calendar_sync_service, "DB_PATH", db_path)

    await bootstrap_service.init_db()
    async with aiosqlite.connect(str(db_path)) as db:
        await db.executescript(
            """
            DELETE FROM task_tags;
            DELETE FROM tags;
            DELETE FROM subtasks;
            DELETE FROM notes;
            DELETE FROM pomodoro_sessions;
            DELETE FROM download_history;
            DELETE FROM operation_logs;
            DELETE FROM tasks;
            """
        )
        await db.commit()

    return task_command_service, task_query_service


@pytest.mark.asyncio
async def test_get_pending_tasks_returns_today_related_and_tags(setup_db):
    task_service, task_query_service = setup_db
    created = await task_service.add_task(
        task_name="今天的任务",
        due_time="2026-06-13T10:00:00",
        tags=["work"],
    )

    result = await task_query_service.get_pending_tasks(today_only=False)

    assert result["status"] == "success"
    assert any(task["task_id"] == created["task_id"] for task in result["tasks"])
    matched = next(task for task in result["tasks"] if task["task_id"] == created["task_id"])
    assert "work" in matched["tags"]


@pytest.mark.asyncio
async def test_get_all_tasks_filters_by_status_and_keyword(setup_db):
    task_service, task_query_service = setup_db
    await task_service.add_task(task_name="task_query_unique_alpha", due_time="2026-06-13T10:00:00")
    other = await task_service.add_task(task_name="task_query_unique_mail_beta", due_time="2026-06-14T10:00:00")
    await task_service.complete_task(other["task_id"])

    result = await task_query_service.get_all_tasks(
        status_filter="completed",
        keyword="task_query_unique_mail_beta",
        page=1,
        page_size=20,
    )

    assert result["status"] == "success"
    assert result["total"] == 1
    assert result["tasks"][0]["task_name"] == "task_query_unique_mail_beta"


@pytest.mark.asyncio
async def test_get_task_detail_returns_neighbors_and_related_data(setup_db):
    task_service, task_query_service = setup_db
    target = await task_service.add_task(
        task_name="写周报",
        due_time="2026-06-13T10:00:00",
        start_time="2026-06-13T09:00:00",
        tags=["report"],
    )
    await task_service.add_task(
        task_name="准备汇报",
        due_time="2026-06-13T15:00:00",
        start_time="2026-06-13T14:00:00",
        tags=["meeting"],
    )

    with patch("services.task_detail_service.get_all_notes", new=AsyncMock(return_value={"notes": []})), \
         patch("services.task_detail_service.get_subtasks", new=AsyncMock(return_value=[])), \
         patch("services.task_detail_service.get_active_pomodoro", new=AsyncMock(return_value=None)):
        result = await task_query_service.get_task_detail(target["task_id"])

    assert result["status"] == "success"
    assert result["task"]["task_id"] == target["task_id"]
    assert isinstance(result["weekly_neighbors"], list)
    assert any(item["task_name"] == "准备汇报" for item in result["weekly_neighbors"])


@pytest.mark.asyncio
async def test_get_dashboard_stats_combines_counts_and_streak(setup_db):
    task_service, task_query_service = setup_db
    import services.dashboard_query_service as dashboard_query_service

    await task_service.add_task(task_name="任务A", due_time="2026-06-13T10:00:00")
    completed = await task_service.add_task(task_name="任务B", due_time="2026-06-13T12:00:00")
    await task_service.complete_task(completed["task_id"])

    with patch("services.dashboard_query_service.get_streak_info", new=AsyncMock(return_value={"current_streak": 3})):
        result = await dashboard_query_service.get_dashboard_stats()

    assert result["status"] == "success"
    assert result["tasks"]["pending"] >= 1
    assert result["tasks"]["completed"] >= 1
    assert result["streak"]["current_streak"] == 3
