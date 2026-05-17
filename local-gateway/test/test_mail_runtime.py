import pytest

import services.mail_service as mail_service
from services.mail import runtime as mail_runtime


@pytest.fixture(autouse=True)
async def reset_mail_polling_runtime():
    await mail_runtime.stop_mail_polling_scheduler()
    mail_runtime.mail_polling_runtime.state.update({
        "enabled": False,
        "interval_seconds": 300,
        "folder_kind": "inbox",
        "limit": 20,
        "last_started_at": "",
        "last_finished_at": "",
        "last_success_at": "",
        "last_error": "",
        "last_summary": {},
        "is_running": False,
    })
    mail_runtime.mail_polling_runtime.task = None
    yield
    await mail_runtime.stop_mail_polling_scheduler()


@pytest.mark.asyncio
async def test_update_mail_polling_config_persists_runtime_state(temp_mail_db):
    result = await mail_service.update_mail_polling_config(
        enabled=True,
        interval_seconds=180,
        folder_kind="inbox",
        limit=12,
    )

    assert result["status"] == "success"
    polling = result["polling"]
    assert polling["enabled"] is True
    assert polling["interval_seconds"] == 180
    assert polling["folder_kind"] == "inbox"
    assert polling["limit"] == 12

    await mail_service.update_mail_polling_config(enabled=False)


@pytest.mark.asyncio
async def test_run_mail_polling_once_aggregates_sync_results(temp_mail_db, monkeypatch):
    first = await mail_service.create_mail_account(
        display_name="Desk A",
        email_address="a@example.com",
        sync_enabled=True,
    )
    await mail_service.create_mail_account(
        display_name="Desk B",
        email_address="b@example.com",
        sync_enabled=False,
    )

    async def fake_sync(account_id, folder_kind="inbox", limit=20):
        return {
            "status": "success",
            "account_id": account_id,
            "folder_kind": folder_kind,
            "new_count": 2 if account_id == first["account_id"] else 0,
            "message": "ok",
        }

    monkeypatch.setattr(mail_service, "sync_mail_account", fake_sync)
    await mail_service.update_mail_polling_config(
        enabled=False,
        interval_seconds=120,
        folder_kind="inbox",
        limit=9,
    )

    result = await mail_service.run_mail_polling_once()

    assert result["status"] == "success"
    summary = result["polling"]["last_summary"]
    assert summary["account_count"] >= 1
    assert summary["success_count"] == 1
    assert summary["new_count"] == 2
    assert summary["results"][0]["account_id"] == first["account_id"]
    assert summary["results"][0]["folder_kind"] == "inbox"
    assert summary["results"][0]["fetched_count"] == 0
    assert summary["results"][0]["new_count"] == 2
    assert summary["results"][0]["latest_uid"] == ""
    assert summary["results"][0]["sync"] is None


@pytest.mark.asyncio
async def test_mail_polling_runtime_stop_clears_task_state():
    runtime = mail_runtime.mail_polling_runtime
    runtime.state["enabled"] = True

    async def idle_loop():
        await asyncio.sleep(3600)

    import asyncio
    runtime.task = asyncio.create_task(idle_loop())
    await runtime.stop_scheduler()

    assert runtime.task is None
    assert runtime.state["is_running"] is False


@pytest.mark.asyncio
async def test_run_mail_polling_once_records_top_level_failure(monkeypatch):
    runtime = mail_runtime.mail_polling_runtime
    runtime.state["folder_kind"] = "inbox"
    runtime.state["limit"] = 5

    class BrokenService:
        async def list_mail_accounts(self):
            raise RuntimeError("boom")

    monkeypatch.setattr(mail_runtime, "get_runtime_mail_service", lambda: BrokenService())

    with pytest.raises(RuntimeError, match="boom"):
        await runtime.run_once()

    assert runtime.state["last_error"] == "boom"
    assert runtime.state["is_running"] is False
    assert runtime.state["last_finished_at"]
