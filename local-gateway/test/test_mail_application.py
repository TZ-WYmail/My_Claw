from unittest.mock import AsyncMock, patch

import pytest

from application import mail_actions


@pytest.mark.asyncio
async def test_get_mail_thread_or_error_returns_error_for_missing_thread():
    with patch("application.mail_actions.mail_service.get_mail_thread", new=AsyncMock(return_value=None)):
        result = await mail_actions.get_mail_thread_or_error("thread_missing")

    assert result["status"] == "error"
    assert "不存在" in result["message"]


@pytest.mark.asyncio
async def test_archive_thread_action_delegates_to_mail_service():
    with patch("application.mail_actions.mail_service.move_thread_to_folder", new=AsyncMock(return_value={"status": "success"})) as mocked:
        result = await mail_actions.archive_thread_action("thread_1")

    mocked.assert_awaited_once_with("thread_1", "archive")
    assert result["status"] == "success"


@pytest.mark.asyncio
async def test_portal_save_draft_action_updates_existing_draft():
    detail = {
        "thread": {"thread_id": "thread_1"},
        "drafts": [
            {"draft_id": "draft_1", "subject": "Existing subject"},
        ],
    }

    with patch("application.mail_actions.mail_service.get_mail_thread", new=AsyncMock(return_value=detail)), \
         patch("application.mail_actions.mail_service.update_mail_draft", new=AsyncMock(return_value={"status": "success"})) as mocked:
        result = await mail_actions.portal_save_draft_action(
            thread_id="thread_1",
            draft_id="draft_1",
            subject="Edited subject",
            body_html="Edited body",
        )

    mocked.assert_awaited_once_with(
        "draft_1",
        subject="Edited subject",
        body_html="Edited body",
        user_edited_after_ai=True,
    )
    assert result["status"] == "success"

