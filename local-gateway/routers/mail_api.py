"""
双向邮件系统 JSON API 路由
"""
from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from services import mail_service

router = APIRouter()


class MailAccountCreateRequest(BaseModel):
    display_name: str = Field(..., description="账户显示名")
    email_address: str = Field(..., description="邮箱地址")
    provider_type: str = Field("smtp_imap", description="提供方类型")
    smtp_host: str = ""
    smtp_port: int = 465
    smtp_user: str = ""
    smtp_password: str = ""
    imap_host: str = ""
    imap_port: int = 993
    imap_user: str = ""
    imap_password: str = ""
    use_ssl: bool = True
    sync_enabled: bool = True
    signature_text: str = ""
    tone_mode: str = Field("warm", description="plain/warm/romantic")
    auto_mail_policy: str = Field("draft_and_notify", description="draft_only/draft_and_notify/auto_send")


class MailAccountUpdateRequest(BaseModel):
    display_name: Optional[str] = None
    email_address: Optional[str] = None
    provider_type: Optional[str] = None
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    imap_host: Optional[str] = None
    imap_port: Optional[int] = None
    imap_user: Optional[str] = None
    imap_password: Optional[str] = None
    use_ssl: Optional[bool] = None
    sync_enabled: Optional[bool] = None
    signature_text: Optional[str] = None
    tone_mode: Optional[str] = None
    auto_mail_policy: Optional[str] = None


class MailDraftCreateRequest(BaseModel):
    account_id: str
    subject: str
    body_html: str = ""
    to: list[dict] = Field(default_factory=list)
    cc: list[dict] = Field(default_factory=list)
    bcc: list[dict] = Field(default_factory=list)
    thread_id: Optional[str] = None
    reply_mode: str = "new"
    tone_mode: str = "warm"
    signature: str = ""
    scheduled_send_at: Optional[str] = None
    ai_generated: bool = False


class MailDraftUpdateRequest(BaseModel):
    subject: Optional[str] = None
    body_html: Optional[str] = None
    to: Optional[list[dict]] = None
    cc: Optional[list[dict]] = None
    bcc: Optional[list[dict]] = None
    tone_mode: Optional[str] = None
    signature: Optional[str] = None
    scheduled_send_at: Optional[str] = None
    user_edited_after_ai: Optional[bool] = None
    status: Optional[str] = None


class MailThreadDecisionRequest(BaseModel):
    decision_status: str = Field(..., description="pending/snoozed/cleared")


class MailThreadTaskCreateRequest(BaseModel):
    task_name: Optional[str] = None
    due_time: Optional[str] = None
    description: str = ""
    priority: int = 1


class MailMessageIngestRequest(BaseModel):
    account_id: str
    subject: str
    text_body: str = ""
    html_body: str = ""
    direction: str = "inbound"
    folder_kind: str = "inbox"
    thread_id: Optional[str] = None
    from_name: str = ""
    from_email: str = ""
    to: list[dict] = Field(default_factory=list)
    cc: list[dict] = Field(default_factory=list)
    bcc: list[dict] = Field(default_factory=list)
    reply_to: list[dict] = Field(default_factory=list)
    remote_message_id: str = ""
    internet_message_id: str = ""
    sent_at: Optional[str] = None
    received_at: Optional[str] = None
    is_read: bool = False
    is_starred: bool = False
    delivery_status: str = "sent"


class MailPollingConfigRequest(BaseModel):
    enabled: Optional[bool] = None
    interval_seconds: Optional[int] = Field(None, ge=60, le=86400)
    folder_kind: Optional[str] = None
    limit: Optional[int] = Field(None, ge=1, le=100)


@router.get("/accounts")
async def list_accounts():
    return {"status": "success", "accounts": await mail_service.list_mail_accounts()}


@router.get("/accounts/{account_id}")
async def get_account(account_id: str):
    account = await mail_service.get_mail_account(account_id)
    if not account:
        return {"status": "error", "message": f"账户 {account_id} 不存在"}
    return {"status": "success", "account": account}


@router.post("/accounts")
async def create_account(request: MailAccountCreateRequest):
    return await mail_service.create_mail_account(**request.model_dump())


@router.put("/accounts/{account_id}")
async def update_account(account_id: str, request: MailAccountUpdateRequest):
    return await mail_service.update_mail_account(account_id, **request.model_dump(exclude_unset=True))


@router.delete("/accounts/{account_id}")
async def delete_account(account_id: str):
    return await mail_service.delete_mail_account(account_id)


@router.post("/accounts/{account_id}/test")
async def test_account(account_id: str):
    return await mail_service.test_mail_account_connection(account_id)


@router.post("/accounts/{account_id}/sync")
async def sync_account(
    account_id: str,
    folder_kind: str = Query("inbox", description="要同步的信箱类型"),
    limit: int = Query(20, ge=1, le=100, description="单次最多拉取的邮件数"),
):
    return await mail_service.sync_mail_account(account_id, folder_kind=folder_kind, limit=limit)


@router.get("/accounts/{account_id}/sync-status")
async def get_sync_status(account_id: str):
    return await mail_service.get_mail_sync_status(account_id)


@router.get("/polling")
async def get_mail_polling():
    return {"status": "success", "polling": mail_service.get_mail_polling_status()}


@router.put("/polling")
async def update_mail_polling(request: MailPollingConfigRequest):
    return await mail_service.update_mail_polling_config(**request.model_dump(exclude_unset=True))


@router.post("/polling/run-once")
async def run_mail_polling_once():
    return await mail_service.run_mail_polling_once()


@router.get("/folders")
async def list_folders(account_id: str = Query("", description="可选账户 ID")):
    return {"status": "success", "folders": await mail_service.list_mail_folders(account_id or None)}


@router.get("/threads")
async def list_threads(
    account_id: str = Query("", description="可选账户 ID"),
    folder: str = Query("", description="inbox/sent/drafts/archive/trash"),
    needs_reply: Optional[bool] = Query(None),
    unread_only: bool = Query(False),
    waiting_user_decision: Optional[bool] = Query(None),
    scheduled_only: bool = Query(False),
    failed_draft_only: bool = Query(False),
    q: str = Query(""),
):
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


@router.get("/threads/{thread_id}")
async def get_thread(thread_id: str):
    detail = await mail_service.get_mail_thread(thread_id)
    if not detail:
        return {"status": "error", "message": f"线程 {thread_id} 不存在"}
    return {"status": "success", **detail}


@router.get("/threads/{thread_id}/agent-runs")
async def get_thread_agent_runs(
    thread_id: str,
    limit: int = Query(20, ge=1, le=100, description="返回最近的自动处理记录数"),
):
    detail = await mail_service.get_mail_thread(thread_id)
    if not detail:
        return {"status": "error", "message": f"线程 {thread_id} 不存在"}
    runs = await mail_service.list_mail_agent_runs(thread_id, limit=limit)
    return {"status": "success", "thread_id": thread_id, "agent_runs": runs}


@router.post("/threads/{thread_id}/mark-read")
async def mark_thread_read(thread_id: str):
    return await mail_service.mark_thread_read(thread_id, True)


@router.post("/threads/{thread_id}/archive")
async def archive_thread(thread_id: str):
    return await mail_service.move_thread_to_folder(thread_id, "archive")


@router.post("/threads/{thread_id}/decision")
async def set_thread_decision(thread_id: str, request: MailThreadDecisionRequest):
    return await mail_service.set_thread_decision_status(thread_id, request.decision_status)


@router.post("/threads/{thread_id}/create-task")
async def create_task_from_thread(thread_id: str, request: Optional[MailThreadTaskCreateRequest] = None):
    return await mail_service.create_task_from_mail_thread(thread_id, **((request.model_dump()) if request else {}))


@router.post("/threads/{thread_id}/generate-reply-draft")
async def generate_reply_draft(thread_id: str):
    return await mail_service.generate_reply_draft_for_thread(thread_id)


@router.post("/messages/ingest")
async def ingest_message(request: MailMessageIngestRequest):
    return await mail_service.ingest_mail_message(**request.model_dump())


@router.post("/drafts")
async def create_draft(request: MailDraftCreateRequest):
    return await mail_service.create_mail_draft(**request.model_dump())


@router.put("/drafts/{draft_id}")
async def update_draft(draft_id: str, request: MailDraftUpdateRequest):
    return await mail_service.update_mail_draft(draft_id, **request.model_dump(exclude_unset=True))


@router.post("/drafts/{draft_id}/send")
async def send_draft(draft_id: str):
    return await mail_service.send_mail_draft(draft_id)


@router.get("/dashboard")
async def get_dashboard(account_id: str = Query("", description="可选账户 ID")):
    return await mail_service.get_mail_dashboard(account_id or None)
