import pytest

import services.mail_service as mail_service


class DummyIMAPDuplicate:
    def __init__(self, host, port):
        self.host = host
        self.port = port

    def login(self, user, password):
        return "OK", []

    def select(self, folder):
        return "OK", [b"1"]

    def uid(self, command, *args):
        if command == "search":
            return "OK", [b"101"]
        if command == "fetch":
            return "OK", [(b"1 (FLAGS (\\Seen))", b"raw-message")]
        raise AssertionError(command)

    def logout(self):
        return "BYE", []


class DummyIMAPSearchFailure:
    def __init__(self, host, port):
        self.host = host
        self.port = port

    def login(self, user, password):
        return "OK", []

    def select(self, folder):
        return "OK", [b"1"]

    def uid(self, command, *args):
        if command == "search":
            return "NO", []
        raise AssertionError(command)

    def logout(self):
        return "BYE", []


@pytest.mark.asyncio
async def test_sync_mail_account_skips_duplicate_messages_without_auto_handle(temp_mail_db, monkeypatch):
    account = await mail_service.create_mail_account(
        display_name="Desk",
        email_address="desk@example.com",
        imap_host="imap.example.com",
        imap_port=993,
        imap_user="desk@example.com",
        imap_password="secret1234",
        sync_enabled=True,
    )
    account_id = account["account_id"]

    async def fake_to_thread(fn, *args, **kwargs):
        return fn(*args, **kwargs)

    def fake_parser(raw_message):
        return {
            "subject": "Existing thread",
            "from_name": "Friend",
            "from_email": "friend@example.com",
            "to": [{"name": "Desk", "email": "desk@example.com"}],
            "cc": [],
            "bcc": [],
            "reply_to": [],
            "text_body": "Already seen",
            "html_body": "",
            "internet_message_id": "msg-dup@example.com",
            "in_reply_to": "",
            "references": [],
            "attachments": [],
            "sent_at": "2026-05-17T10:00:00",
            "received_at": "2026-05-17T10:00:00",
        }

    seen_thread_ids: list[str] = []

    async def fake_ingest(**kwargs):
        return {
            "status": "success",
            "message": "邮件已存在，跳过重复入库",
            "thread_id": "thread_dup",
        }

    async def fake_auto_handle(thread_id):
        seen_thread_ids.append(thread_id)
        return {"status": "success"}

    monkeypatch.setattr(mail_service.smtplib, "SMTP_SSL", object)
    monkeypatch.setattr(mail_service.asyncio, "to_thread", fake_to_thread)
    monkeypatch.setattr(mail_service.imaplib, "IMAP4_SSL", DummyIMAPDuplicate)
    monkeypatch.setattr(mail_service, "_parse_imap_message", fake_parser)
    monkeypatch.setattr(mail_service, "ingest_mail_message", fake_ingest)
    monkeypatch.setattr(mail_service, "auto_handle_incoming_mail", fake_auto_handle)

    result = await mail_service.sync_mail_account(account_id, limit=10)

    assert result["status"] == "success"
    assert result["fetched_count"] == 1
    assert result["new_count"] == 0
    assert result["latest_uid"] == "101"
    assert seen_thread_ids == []

    status = await mail_service.get_mail_sync_status(account_id)
    assert status["latest_run"]["status"] == "success"
    assert status["latest_run"]["latest_uid"] == "101"


@pytest.mark.asyncio
async def test_sync_mail_account_records_error_when_imap_search_fails(temp_mail_db, monkeypatch):
    account = await mail_service.create_mail_account(
        display_name="Desk",
        email_address="desk@example.com",
        imap_host="imap.example.com",
        imap_port=993,
        imap_user="desk@example.com",
        imap_password="secret1234",
        sync_enabled=True,
    )
    account_id = account["account_id"]

    async def fake_to_thread(fn, *args, **kwargs):
        return fn(*args, **kwargs)

    monkeypatch.setattr(mail_service.asyncio, "to_thread", fake_to_thread)
    monkeypatch.setattr(mail_service.imaplib, "IMAP4_SSL", DummyIMAPSearchFailure)

    result = await mail_service.sync_mail_account(account_id, limit=10)

    assert result["status"] == "error"
    assert "IMAP 搜索失败" in result["message"]

    status = await mail_service.get_mail_sync_status(account_id)
    assert status["latest_run"]["status"] == "error"
    assert "IMAP 搜索失败" in status["latest_run"]["error_message"]
