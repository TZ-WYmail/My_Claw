import pytest

import services.mail_service as mail_service


@pytest.mark.asyncio
async def test_create_draft_creates_thread(temp_mail_db):
    account = await mail_service.create_mail_account(
        display_name="Writer",
        email_address="writer@example.com",
    )
    account_id = account["account_id"]

    result = await mail_service.create_mail_draft(
        account_id=account_id,
        subject="A letter before evening",
        body_html="<p>Hello</p>",
        to=[{"name": "Reader", "email": "reader@example.com"}],
        tone_mode="romantic",
    )

    assert result["status"] == "success"
    assert result["thread_id"]
    assert result["draft_id"]
    assert result["thread"]["has_draft"] is True
    assert result["drafts"][0]["tone_mode"] == "romantic"
    assert result["drafts"][0]["to"][0]["email"] == "reader@example.com"


@pytest.mark.asyncio
async def test_update_mail_draft_marks_user_edit_after_ai(temp_mail_db, monkeypatch):
    account = await mail_service.create_mail_account(
        display_name="Letter Desk",
        email_address="desk@example.com",
        signature_text="Regards",
    )
    account_id = account["account_id"]

    inbound = await mail_service.ingest_mail_message(
        account_id=account_id,
        subject="Mobile reply needed",
        text_body="Can you confirm tomorrow?",
        from_name="Client C",
        from_email="clientc@example.com",
        to=[{"name": "Desk", "email": "desk@example.com"}],
        direction="inbound",
        folder_kind="inbox",
        received_at="2026-05-16T12:00:00",
    )
    thread_id = inbound["thread_id"]

    async def fake_ai_reply(thread, messages, account_data):
        return {
            "subject": "Re: Mobile reply needed",
            "body": "Confirmed.\nSee you tomorrow.",
            "source": "ai",
        }

    monkeypatch.setattr(mail_service, "_generate_ai_reply_content", fake_ai_reply)
    draft_result = await mail_service.generate_reply_draft_for_thread(thread_id)

    assert draft_result["status"] == "success"
    draft_id = draft_result["draft_id"]

    updated = await mail_service.update_mail_draft(
        draft_id,
        subject="Re: Mobile reply needed (edited)",
        body_html="Confirmed by phone.<br>See you tomorrow.",
        user_edited_after_ai=True,
    )

    assert updated["status"] == "success"
    assert updated["drafts"][0]["subject"] == "Re: Mobile reply needed (edited)"
    assert updated["drafts"][0]["user_edited_after_ai"] is True


@pytest.mark.asyncio
async def test_set_thread_decision_status_updates_waiting_flag(temp_mail_db):
    account = await mail_service.create_mail_account(
        display_name="Decision Desk",
        email_address="decision@example.com",
    )
    account_id = account["account_id"]

    inbound = await mail_service.ingest_mail_message(
        account_id=account_id,
        subject="Please confirm schedule",
        text_body="Need your confirmation for next week.",
        from_name="Client D",
        from_email="clientd@example.com",
        to=[{"name": "Desk", "email": "decision@example.com"}],
        direction="inbound",
        folder_kind="inbox",
        received_at="2026-05-16T13:00:00",
    )
    thread_id = inbound["thread_id"]

    snoozed = await mail_service.set_thread_decision_status(thread_id, "snoozed")
    assert snoozed["status"] == "success"
    assert snoozed["thread"]["decision_status"] == "snoozed"
    assert snoozed["thread"]["waiting_user_decision"] is True

    cleared = await mail_service.set_thread_decision_status(thread_id, "cleared")
    assert cleared["status"] == "success"
    assert cleared["thread"]["decision_status"] == "cleared"
    assert cleared["thread"]["waiting_user_decision"] is False


@pytest.mark.asyncio
async def test_thread_factual_state_transitions_across_inbound_draft_and_outbound(temp_mail_db, monkeypatch):
    account = await mail_service.create_mail_account(
        display_name="Desk",
        email_address="desk@example.com",
        signature_text="Regards",
        smtp_host="smtp.example.com",
        smtp_user="desk@example.com",
        smtp_password="secret1234",
    )
    account_id = account["account_id"]

    inbound = await mail_service.ingest_mail_message(
        account_id=account_id,
        subject="Schedule check",
        text_body="Please confirm the time.",
        from_name="Client E",
        from_email="cliente@example.com",
        to=[{"name": "Desk", "email": "desk@example.com"}],
        direction="inbound",
        folder_kind="inbox",
        internet_message_id="cliente-1@example.com",
        received_at="2026-05-16T15:00:00",
    )
    thread_id = inbound["thread_id"]
    assert inbound["thread"]["has_new_inbound"] is True
    assert inbound["thread"]["last_actor"] == "counterparty"
    assert inbound["thread"]["has_pending_draft"] is False
    assert inbound["thread"]["needs_reply"] is True

    draft = await mail_service.create_mail_draft(
        account_id=account_id,
        thread_id=thread_id,
        subject="Re: Schedule check",
        body_html="I can confirm shortly.",
        to=[{"name": "Client E", "email": "cliente@example.com"}],
        reply_mode="reply",
    )
    assert draft["thread"]["has_pending_draft"] is True
    assert draft["thread"]["has_draft"] is True
    assert draft["thread"]["has_new_inbound"] is True

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

    original_to_thread = mail_service.asyncio.to_thread
    monkeypatch.setattr(mail_service.smtplib, "SMTP_SSL", DummySMTP)
    mail_service.asyncio.to_thread = fake_to_thread
    try:
        sent = await mail_service.send_mail_draft(draft["draft_id"])
    finally:
        mail_service.asyncio.to_thread = original_to_thread

    assert sent["status"] == "success"
    assert sent["thread"]["has_new_inbound"] is False
    assert sent["thread"]["has_pending_draft"] is False
    assert sent["thread"]["last_actor"] == "self"
    assert sent["thread"]["needs_reply"] is False
