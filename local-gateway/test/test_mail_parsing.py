from email.message import EmailMessage

import pytest

from services.mail import parsing


def test_parse_imap_message_extracts_headers_bodies_and_attachments():
    message = EmailMessage()
    message["Subject"] = "=?utf-8?b?5rWL6K+V5L+h5Lu2?="
    message["From"] = "Alice <alice@example.com>"
    message["To"] = "Bob <bob@example.com>"
    message["Cc"] = "Carol <carol@example.com>"
    message["Reply-To"] = "Desk Reply <reply@example.com>"
    message["Message-ID"] = "<msg-1@example.com>"
    message["In-Reply-To"] = "<prev@example.com>"
    message["References"] = "<prev@example.com> <older@example.com> <prev@example.com>"
    message["Date"] = "Sun, 17 May 2026 10:00:00 +0800"
    message.set_content("Plain body")
    message.add_alternative("<p>HTML body</p>", subtype="html")
    message.add_attachment(
        b"pdf-bytes",
        maintype="application",
        subtype="pdf",
        filename="plan.pdf",
    )

    parsed = parsing.parse_imap_message(message.as_bytes())

    assert parsed["subject"] == "测试信件"
    assert parsed["from_email"] == "alice@example.com"
    assert parsed["to"][0]["email"] == "bob@example.com"
    assert parsed["cc"][0]["email"] == "carol@example.com"
    assert parsed["reply_to"][0]["email"] == "reply@example.com"
    assert parsed["text_body"] == "Plain body"
    assert "<p>HTML body</p>" in parsed["html_body"]
    assert parsed["internet_message_id"] == "msg-1@example.com"
    assert parsed["in_reply_to"] == "prev@example.com"
    assert parsed["references"] == ["prev@example.com", "older@example.com"]
    assert parsed["attachments"][0]["filename"] == "plan.pdf"
    assert parsed["attachments"][0]["mime_type"] == "application/pdf"
    assert parsed["sent_at"] == "2026-05-17T02:00:00"


def test_extract_mail_command_supports_html_and_chinese_prefix():
    assert parsing.extract_mail_command("<p>#cmd: draft_reply</p>") == "draft_reply"
    assert parsing.extract_mail_command("请处理<br>指令：create_task") == "create_task"
    assert parsing.extract_mail_command("没有明确指令") is None


@pytest.mark.asyncio
async def test_generate_ai_reply_content_uses_template_when_api_key_missing(monkeypatch):
    monkeypatch.setattr(parsing.ai_config, "api_key", "")

    result = await parsing.generate_ai_reply_content(
        thread={"subject": "Dinner Plan", "snippet": "Can we confirm tonight?"},
        messages=[
            {
                "direction": "inbound",
                "from_name": "Friend",
                "from_email": "friend@example.com",
                "text_body": "Can we confirm tonight?",
            }
        ],
        account={"display_name": "Desk", "email_address": "desk@example.com"},
    )

    assert result["subject"] == "Re: Dinner Plan"
    assert "我已经看到你关于「Dinner Plan」的来信" in result["body"]
    assert result["source"] == "template"


@pytest.mark.asyncio
async def test_generate_ai_reply_content_falls_back_to_template_on_http_error(monkeypatch):
    monkeypatch.setattr(parsing.ai_config, "api_key", "token")
    monkeypatch.setattr(parsing.ai_config, "api_base", "https://api.example.com")
    monkeypatch.setattr(parsing.ai_config, "model", "demo-model")

    class FailingClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, *args, **kwargs):
            raise RuntimeError("network down")

    monkeypatch.setattr(parsing.httpx, "AsyncClient", lambda timeout=60.0: FailingClient())

    result = await parsing.generate_ai_reply_content(
        thread={"subject": "Trip Plan", "analysis_reason": "需要确认时间"},
        messages=[
            {
                "direction": "inbound",
                "from_name": "Partner",
                "from_email": "partner@example.com",
                "text_body": "Please confirm tomorrow morning.",
            }
        ],
        account={"display_name": "Desk", "email_address": "desk@example.com"},
    )

    assert result["subject"] == "Re: Trip Plan"
    assert "我已经看到你关于「Trip Plan」的来信" in result["body"]
    assert result["source"] == "template"
