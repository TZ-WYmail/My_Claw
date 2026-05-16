import pytest

import services.mail_service as mail_service


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
