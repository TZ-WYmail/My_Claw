import aiosqlite
import pytest

import services.mail_service as mail_service


@pytest.mark.asyncio
async def test_auto_handle_incoming_mail_draft_only_creates_draft_without_sending(temp_mail_db, monkeypatch):
    account = await mail_service.create_mail_account(
        display_name="Desk",
        email_address="desk@example.com",
        auto_mail_policy="draft_only",
    )
    account_id = account["account_id"]

    inbound = await mail_service.ingest_mail_message(
        account_id=account_id,
        subject="Please confirm dinner",
        text_body="Can you reply and confirm tonight?",
        from_name="Friend",
        from_email="friend@gmail.com",
        to=[{"name": "Desk", "email": "desk@example.com"}],
        direction="inbound",
        folder_kind="inbox",
        internet_message_id="friend-1@example.com",
        received_at="2026-05-16T18:00:00",
    )
    thread_id = inbound["thread_id"]

    async def fake_generate_reply(thread, messages, account_data):
        return {
            "subject": "Re: Please confirm dinner",
            "body": "Tonight works for me.",
            "source": "ai",
        }

    monkeypatch.setattr(mail_service, "_generate_ai_reply_content", fake_generate_reply)
    result = await mail_service.auto_handle_incoming_mail(thread_id)

    assert result["status"] == "success"
    assert result["auto_mail_policy"] == "draft_only"

    detail = await mail_service.get_mail_thread(thread_id)
    assert detail is not None
    assert len(detail["drafts"]) == 1
    assert len([m for m in detail["messages"] if m["direction"] == "outbound"]) == 0

    async with aiosqlite.connect(str(temp_mail_db)) as db:
        cursor = await db.execute(
            "SELECT status, result_summary FROM mail_agent_runs WHERE thread_id = ? AND action_kind = 'auto_reply'",
            (thread_id,),
        )
        row = await cursor.fetchone()
    assert row is not None
    assert row[0] == "draft_created"


@pytest.mark.asyncio
async def test_auto_handle_incoming_mail_draft_and_notify_does_not_send(temp_mail_db, monkeypatch):
    account = await mail_service.create_mail_account(
        display_name="Desk",
        email_address="desk@example.com",
        auto_mail_policy="draft_and_notify",
    )
    account_id = account["account_id"]

    inbound = await mail_service.ingest_mail_message(
        account_id=account_id,
        subject="Need your reply",
        text_body="Please reply when you can.",
        from_name="Client",
        from_email="client@gmail.com",
        to=[{"name": "Desk", "email": "desk@example.com"}],
        direction="inbound",
        folder_kind="inbox",
        internet_message_id="client-1@example.com",
        received_at="2026-05-16T19:00:00",
    )
    thread_id = inbound["thread_id"]

    async def fake_generate_reply(thread, messages, account_data):
        return {
            "subject": "Re: Need your reply",
            "body": "I have noted this and will confirm soon.",
            "source": "ai",
        }

    monkeypatch.setattr(mail_service, "_generate_ai_reply_content", fake_generate_reply)
    result = await mail_service.auto_handle_incoming_mail(thread_id)

    assert result["status"] == "success"
    assert result["auto_mail_policy"] == "draft_and_notify"

    detail = await mail_service.get_mail_thread(thread_id)
    assert detail is not None
    assert len(detail["drafts"]) == 1
    assert len([m for m in detail["messages"] if m["direction"] == "outbound"]) == 0

    async with aiosqlite.connect(str(temp_mail_db)) as db:
        cursor = await db.execute(
            "SELECT status FROM mail_agent_runs WHERE thread_id = ? AND action_kind = 'auto_reply'",
            (thread_id,),
        )
        row = await cursor.fetchone()
    assert row is not None
    assert row[0] == "user_confirmation_required"


@pytest.mark.asyncio
async def test_auto_handle_incoming_mail_skips_non_direct_mail(temp_mail_db):
    account = await mail_service.create_mail_account(
        display_name="Desk",
        email_address="desk@example.com",
    )
    account_id = account["account_id"]

    inbound = await mail_service.ingest_mail_message(
        account_id=account_id,
        subject="Weekly newsletter",
        text_body="unsubscribe from this newsletter",
        from_name="Newsletter",
        from_email="no-reply@updates.example.com",
        to=[{"name": "Desk", "email": "desk@example.com"}],
        direction="inbound",
        folder_kind="inbox",
        internet_message_id="newsletter-1@example.com",
        received_at="2026-05-16T20:00:00",
    )
    thread_id = inbound["thread_id"]

    result = await mail_service.auto_handle_incoming_mail(thread_id)
    assert result["status"] == "skipped"

    async with aiosqlite.connect(str(temp_mail_db)) as db:
        cursor = await db.execute(
            "SELECT status FROM mail_agent_runs WHERE thread_id = ? AND action_kind = 'auto_reply'",
            (thread_id,),
        )
        row = await cursor.fetchone()
    assert row is not None
    assert row[0] == "skipped_non_direct"


@pytest.mark.asyncio
async def test_auto_handle_incoming_mail_auto_send_records_sent_run(temp_mail_db, monkeypatch):
    account = await mail_service.create_mail_account(
        display_name="Desk",
        email_address="desk@example.com",
        auto_mail_policy="auto_send",
        smtp_host="smtp.example.com",
        smtp_user="desk@example.com",
        smtp_password="secret1234",
    )
    account_id = account["account_id"]

    inbound = await mail_service.ingest_mail_message(
        account_id=account_id,
        subject="Need a quick answer",
        text_body="Please reply and confirm.",
        from_name="Friend",
        from_email="friend@gmail.com",
        to=[{"name": "Desk", "email": "desk@example.com"}],
        direction="inbound",
        folder_kind="inbox",
        internet_message_id="friend-2@example.com",
        received_at="2026-05-16T21:00:00",
    )
    thread_id = inbound["thread_id"]

    async def fake_generate_reply(thread, messages, account_data):
        return {
            "subject": "Re: Need a quick answer",
            "body": "Confirmed. I will follow up shortly.",
            "source": "ai",
        }

    async def fake_to_thread(fn, *args, **kwargs):
        return fn(*args, **kwargs)

    class DummySMTP:
        def __init__(self, *args, **kwargs):
            pass

        def login(self, *args, **kwargs):
            return None

        def sendmail(self, *args, **kwargs):
            return None

        def quit(self):
            return None

    monkeypatch.setattr(mail_service, "_generate_ai_reply_content", fake_generate_reply)
    monkeypatch.setattr(mail_service.smtplib, "SMTP_SSL", DummySMTP)
    original_to_thread = mail_service.asyncio.to_thread
    mail_service.asyncio.to_thread = fake_to_thread
    try:
        result = await mail_service.auto_handle_incoming_mail(thread_id)
    finally:
        mail_service.asyncio.to_thread = original_to_thread

    assert result["status"] == "success"
    assert result["auto_mail_policy"] == "auto_send"

    detail = await mail_service.get_mail_thread(thread_id)
    assert detail is not None
    assert len([m for m in detail["messages"] if m["direction"] == "outbound"]) == 1
    assert detail["agent_runs"][0]["status"] == "sent"


@pytest.mark.asyncio
async def test_get_mail_thread_includes_recent_agent_runs(temp_mail_db, monkeypatch):
    account = await mail_service.create_mail_account(
        display_name="Desk",
        email_address="desk@example.com",
        auto_mail_policy="draft_and_notify",
    )
    account_id = account["account_id"]

    inbound = await mail_service.ingest_mail_message(
        account_id=account_id,
        subject="Need your reply",
        text_body="Please reply when you can.",
        from_name="Client",
        from_email="client@gmail.com",
        to=[{"name": "Desk", "email": "desk@example.com"}],
        direction="inbound",
        folder_kind="inbox",
        internet_message_id="client-2@example.com",
        received_at="2026-05-16T22:00:00",
    )
    thread_id = inbound["thread_id"]

    async def fake_generate_reply(thread, messages, account_data):
        return {
            "subject": "Re: Need your reply",
            "body": "I have noted this and will confirm soon.",
            "source": "ai",
        }

    monkeypatch.setattr(mail_service, "_generate_ai_reply_content", fake_generate_reply)
    await mail_service.auto_handle_incoming_mail(thread_id)

    detail = await mail_service.get_mail_thread(thread_id)
    runs = await mail_service.list_mail_agent_runs(thread_id)

    assert detail is not None
    assert detail["agent_runs"]
    assert detail["agent_runs"][0]["thread_id"] == thread_id
    assert detail["agent_runs"][0]["details"]["reason_code"] == "policy_requires_confirmation"
    assert runs
    assert runs[0]["status"] == "user_confirmation_required"
    assert runs[0]["details"]["policy"] == "draft_and_notify"
