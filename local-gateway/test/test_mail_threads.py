import aiosqlite
import pytest

import services.mail_service as mail_service


@pytest.mark.asyncio
async def test_ingest_message_updates_dashboard_and_thread_state(temp_mail_db):
    account = await mail_service.create_mail_account(
        display_name="Inbox",
        email_address="inbox@example.com",
    )
    account_id = account["account_id"]

    inbound = await mail_service.ingest_mail_message(
        account_id=account_id,
        subject="Need your reply",
        text_body="Please confirm the delivery time.",
        from_name="Client A",
        from_email="client@example.com",
        to=[{"name": "Inbox", "email": "inbox@example.com"}],
        direction="inbound",
        folder_kind="inbox",
        received_at="2026-05-16T10:00:00",
    )

    assert inbound["status"] == "success"
    thread_id = inbound["thread_id"]
    assert inbound["thread"]["unread_count"] == 1
    assert inbound["thread"]["has_new_inbound"] is True
    assert inbound["thread"]["last_actor"] == "counterparty"
    assert inbound["thread"]["has_pending_draft"] is False
    assert inbound["thread"]["needs_reply"] is True

    dashboard = await mail_service.get_mail_dashboard(account_id)
    assert dashboard["summary"]["total_threads"] == 1
    assert dashboard["summary"]["unread_threads"] == 1
    assert dashboard["summary"]["needs_reply_threads"] == 1

    detail = await mail_service.get_mail_thread(thread_id)
    assert detail is not None
    assert detail["messages"][0]["from_email"] == "client@example.com"


@pytest.mark.asyncio
async def test_ingest_message_persists_attachment_metadata(temp_mail_db):
    account = await mail_service.create_mail_account(
        display_name="Inbox",
        email_address="inbox@example.com",
    )
    account_id = account["account_id"]

    inbound = await mail_service.ingest_mail_message(
        account_id=account_id,
        subject="Files enclosed",
        text_body="See attachment.",
        from_name="Client A",
        from_email="client@example.com",
        to=[{"name": "Inbox", "email": "inbox@example.com"}],
        direction="inbound",
        folder_kind="inbox",
        received_at="2026-05-16T10:05:00",
        attachments=[
            {
                "attachment_id": "att_manual_1",
                "filename": "brief.pdf",
                "mime_type": "application/pdf",
                "size_bytes": 2048,
                "content_id": "",
                "is_inline": False,
            },
        ],
    )

    detail = await mail_service.get_mail_thread(inbound["thread_id"])
    assert detail is not None
    assert len(detail["messages"]) == 1
    assert len(detail["messages"][0]["attachments"]) == 1
    attachment = detail["messages"][0]["attachments"][0]
    assert attachment["filename"] == "brief.pdf"
    assert attachment["mime_type"] == "application/pdf"
    assert attachment["size_bytes"] == 2048


@pytest.mark.asyncio
async def test_mark_thread_read_and_archive(temp_mail_db):
    account = await mail_service.create_mail_account(
        display_name="Inbox",
        email_address="inbox2@example.com",
    )
    account_id = account["account_id"]

    inbound = await mail_service.ingest_mail_message(
        account_id=account_id,
        subject="Archive me",
        text_body="A quiet letter",
        from_name="Client B",
        from_email="clientb@example.com",
        to=[{"name": "Inbox", "email": "inbox2@example.com"}],
        direction="inbound",
        folder_kind="inbox",
        received_at="2026-05-16T11:00:00",
    )
    thread_id = inbound["thread_id"]

    read_result = await mail_service.mark_thread_read(thread_id)
    assert read_result["status"] == "success"
    assert read_result["thread"]["unread_count"] == 0

    archived = await mail_service.move_thread_to_folder(thread_id, "archive")
    assert archived["status"] == "success"
    assert archived["thread"]["latest_folder_kind"] == "archive"


@pytest.mark.asyncio
async def test_init_mail_db_creates_sync_runs_table(temp_mail_db):
    async with aiosqlite.connect(str(temp_mail_db)) as db:
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'mail_sync_runs'"
        )
        row = await cursor.fetchone()

    assert row is not None


@pytest.mark.asyncio
async def test_ingest_message_prefers_reply_chain_over_subject(temp_mail_db):
    account = await mail_service.create_mail_account(
        display_name="Desk",
        email_address="desk@example.com",
    )
    account_id = account["account_id"]

    first = await mail_service.ingest_mail_message(
        account_id=account_id,
        subject="Quarterly planning",
        text_body="Let's review this quarter.",
        from_name="Partner A",
        from_email="partnera@example.com",
        to=[{"name": "Desk", "email": "desk@example.com"}],
        direction="inbound",
        folder_kind="inbox",
        internet_message_id="msg-root@example.com",
        received_at="2026-05-16T09:00:00",
    )

    reply = await mail_service.ingest_mail_message(
        account_id=account_id,
        subject="Re: Planning follow-up changed title",
        text_body="Following up on the same thread.",
        from_name="Partner A",
        from_email="partnera@example.com",
        to=[{"name": "Desk", "email": "desk@example.com"}],
        direction="inbound",
        folder_kind="inbox",
        internet_message_id="msg-reply@example.com",
        in_reply_to="msg-root@example.com",
        references=["msg-root@example.com"],
        received_at="2026-05-16T10:00:00",
    )

    assert reply["status"] == "success"
    assert reply["thread_id"] == first["thread_id"]

    detail = await mail_service.get_mail_thread(first["thread_id"])
    assert detail is not None
    assert len(detail["messages"]) == 2
    assert detail["messages"][1]["in_reply_to"] == "msg-root@example.com"
    assert detail["messages"][1]["references"] == ["msg-root@example.com"]


@pytest.mark.asyncio
async def test_same_subject_different_counterparty_does_not_merge(temp_mail_db):
    account = await mail_service.create_mail_account(
        display_name="Desk",
        email_address="desk@example.com",
    )
    account_id = account["account_id"]

    first = await mail_service.ingest_mail_message(
        account_id=account_id,
        subject="Project update",
        text_body="Alpha status update.",
        from_name="Alice",
        from_email="alice@example.com",
        to=[{"name": "Desk", "email": "desk@example.com"}],
        direction="inbound",
        folder_kind="inbox",
        internet_message_id="alice-1@example.com",
        received_at="2026-05-16T09:00:00",
    )

    second = await mail_service.ingest_mail_message(
        account_id=account_id,
        subject="Project update",
        text_body="Beta status update.",
        from_name="Bob",
        from_email="bob@example.com",
        to=[{"name": "Desk", "email": "desk@example.com"}],
        direction="inbound",
        folder_kind="inbox",
        internet_message_id="bob-1@example.com",
        received_at="2026-05-16T09:05:00",
    )

    assert second["status"] == "success"
    assert second["thread_id"] != first["thread_id"]

    threads = await mail_service.list_mail_threads(account_id=account_id)
    assert len(threads) == 2
