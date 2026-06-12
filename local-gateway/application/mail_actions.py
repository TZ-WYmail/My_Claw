"""
Mail application entrypoints.

This module centralizes higher-level mail actions so different entry surfaces
such as JSON API routes and portal routes can share the same internal use-case
path instead of coordinating directly against the compatibility facade.
"""
from __future__ import annotations

from typing import Optional

from services import mail_service


async def list_accounts_action() -> dict:
    return {"status": "success", "accounts": await mail_service.list_mail_accounts()}


async def get_account_action(account_id: str) -> dict:
    account = await mail_service.get_mail_account(account_id)
    if not account:
        return {"status": "error", "message": f"账户 {account_id} 不存在"}
    return {"status": "success", "account": account}


async def create_account_action(payload: dict) -> dict:
    return await mail_service.create_mail_account(**payload)


async def update_account_action(account_id: str, payload: dict) -> dict:
    return await mail_service.update_mail_account(account_id, **payload)


async def delete_account_action(account_id: str) -> dict:
    return await mail_service.delete_mail_account(account_id)


async def test_account_action(account_id: str) -> dict:
    return await mail_service.test_mail_account_connection(account_id)


async def sync_account_action(account_id: str, folder_kind: str = "inbox", limit: int = 20) -> dict:
    return await mail_service.sync_mail_account(account_id, folder_kind=folder_kind, limit=limit)


async def get_sync_status_action(account_id: str) -> dict:
    return await mail_service.get_mail_sync_status(account_id)


async def get_mail_polling_action() -> dict:
    return {"status": "success", "polling": mail_service.get_mail_polling_status()}


async def update_mail_polling_action(payload: dict) -> dict:
    return await mail_service.update_mail_polling_config(**payload)


async def run_mail_polling_once_action() -> dict:
    return await mail_service.run_mail_polling_once()


async def list_folders_action(account_id: Optional[str] = None) -> dict:
    return {"status": "success", "folders": await mail_service.list_mail_folders(account_id or None)}


async def list_threads_action(
    account_id: Optional[str] = None,
    folder: str = "",
    needs_reply: Optional[bool] = None,
    unread_only: bool = False,
    waiting_user_decision: Optional[bool] = None,
    scheduled_only: bool = False,
    failed_draft_only: bool = False,
    q: str = "",
) -> dict:
    threads = await mail_service.list_mail_threads(
        account_id=account_id or None,
        folder=folder,
        needs_reply=needs_reply,
        unread_only=unread_only,
        waiting_user_decision=waiting_user_decision,
        scheduled_only=scheduled_only,
        failed_draft_only=failed_draft_only,
        q=q,
    )
    return {"status": "success", "threads": threads}


async def get_thread_agent_runs_action(thread_id: str, limit: int = 20) -> dict:
    detail = await get_mail_thread_or_error(thread_id)
    if detail.get("status") != "success":
        return detail
    runs = await mail_service.list_mail_agent_runs(thread_id, limit=limit)
    return {"status": "success", "thread_id": thread_id, "agent_runs": runs}


async def get_mail_thread_or_error(thread_id: str) -> dict:
    detail = await mail_service.get_mail_thread(thread_id)
    if not detail:
        return {"status": "error", "message": f"线程 {thread_id} 不存在"}
    return {"status": "success", **detail}


async def create_task_from_thread_action(
    thread_id: str,
    task_name: Optional[str] = None,
    due_time: Optional[str] = None,
    description: str = "",
    priority: int = 1,
) -> dict:
    return await mail_service.create_task_from_mail_thread(
        thread_id,
        task_name=task_name,
        due_time=due_time,
        description=description,
        priority=priority,
    )


async def generate_reply_draft_action(thread_id: str) -> dict:
    return await mail_service.generate_reply_draft_for_thread(thread_id)


async def archive_thread_action(thread_id: str) -> dict:
    return await mail_service.move_thread_to_folder(thread_id, "archive")


async def set_thread_decision_action(thread_id: str, decision_status: str) -> dict:
    return await mail_service.set_thread_decision_status(thread_id, decision_status)


async def mark_thread_read_action(thread_id: str, is_read: bool = True) -> dict:
    return await mail_service.mark_thread_read(thread_id, is_read)


async def send_draft_action(draft_id: str) -> dict:
    return await mail_service.send_mail_draft(draft_id)


async def ingest_message_action(payload: dict) -> dict:
    return await mail_service.ingest_mail_message(**payload)


async def create_draft_action(payload: dict) -> dict:
    return await mail_service.create_mail_draft(**payload)


async def update_draft_action(draft_id: str, payload: dict) -> dict:
    return await mail_service.update_mail_draft(draft_id, **payload)


async def get_dashboard_action(account_id: Optional[str] = None) -> dict:
    return await mail_service.get_mail_dashboard(account_id or None)


async def portal_save_draft_action(
    thread_id: str,
    draft_id: str,
    subject: str,
    body_html: str,
) -> dict:
    detail = await mail_service.get_mail_thread(thread_id)
    if not detail:
        return {"status": "error", "message": f"线程 {thread_id} 不存在"}

    current_draft = next((draft for draft in detail.get("drafts", []) if draft.get("draft_id") == draft_id), None)
    normalized_subject = subject.strip() or ((current_draft or {}).get("subject") or thread_id)

    return await mail_service.update_mail_draft(
        draft_id,
        subject=normalized_subject,
        body_html=body_html,
        user_edited_after_ai=True,
    )
