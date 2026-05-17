"""
双向邮件系统基础路由
"""
import re
from html import escape
from typing import Optional
from urllib.parse import quote, urlencode

from fastapi import APIRouter, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field

from services import mail_service

router = APIRouter(prefix="/mail", tags=["mail"])


def _html_to_plain_text(value: str) -> str:
    text = (value or "").replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
    text = re.sub(r"</p\s*>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    return text.strip()


def _message_body_text(message: Optional[dict]) -> str:
    if not message:
        return ""
    return ((message.get("text_body") or "").strip() or _html_to_plain_text(message.get("html_body") or "")).strip()


def _portal_result_page(title: str, message: str, thread_id: str, token: str) -> HTMLResponse:
    portal_url = f"/api/mail/portal/{thread_id}?token={token}"
    html = f"""
    <!doctype html>
    <html lang="zh-CN">
    <head>
      <meta charset="utf-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
      <title>{title}</title>
      <style>
        body {{ margin:0; font-family:-apple-system,BlinkMacSystemFont,'PingFang SC','Segoe UI',sans-serif; background:#f7f1e8; color:#1f1b16; }}
        main {{ max-width:720px; margin:0 auto; padding:32px 18px 48px; }}
        .card {{ background:#fffaf2; border:1px solid #dfd2bf; border-radius:20px; padding:20px; box-shadow:0 14px 36px rgba(72,48,20,.08); }}
        h1 {{ font-size:24px; margin:0 0 10px; }}
        p {{ line-height:1.7; color:#5c5348; }}
        .btn {{ display:block; margin-top:14px; text-align:center; text-decoration:none; padding:14px 16px; border-radius:14px; font-weight:600; background:#2f6fed; color:#fff; }}
        .btn-secondary {{ background:#efe4d2; color:#5a4526; }}
      </style>
    </head>
    <body>
      <main>
        <section class="card">
          <h1>{title}</h1>
          <p>{message}</p>
          <a class="btn" href="{portal_url}">回到这封信的处理页</a>
          <a class="btn btn-secondary" href="javascript:history.back()">返回上一页</a>
        </section>
      </main>
    </body>
    </html>
    """
    return HTMLResponse(html)


def _portal_redirect(thread_id: str, token: str, notice: str, tone: str = "success") -> RedirectResponse:
    query = urlencode({"token": token, "notice": notice, "tone": tone})
    return RedirectResponse(url=f"/api/mail/portal/{thread_id}?{query}", status_code=303)


def _portal_quick_link(thread_id: str, token: str, action: str, **params: str) -> str:
    query = urlencode({"token": token, **params})
    return f"/api/mail/portal/{thread_id}/quick/{action}?{query}"


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


@router.get("/portal/{thread_id}", response_class=HTMLResponse)
async def mail_portal(
    thread_id: str,
    token: str = Query(..., description="门户访问令牌"),
    notice: str = "",
    tone: str = "success",
):
    if not mail_service.verify_mail_portal_token(thread_id, token):
        return HTMLResponse("<h3>链接无效或已失效</h3>", status_code=403)

    detail = await mail_service.get_mail_thread(thread_id)
    if not detail:
        return HTMLResponse("<h3>这封信不存在</h3>", status_code=404)

    thread = detail["thread"]
    latest_draft = next((draft for draft in detail.get("drafts", []) if draft.get("status") != "sent"), None)
    draft_preview = _html_to_plain_text((latest_draft or {}).get("body_html", "尚未起草回复。"))
    latest_draft_id = (latest_draft or {}).get("draft_id", "")
    actions = "".join(
        f"<span style='display:inline-block;padding:6px 10px;border-radius:999px;background:#f6efe3;color:#7a5b2f;font-size:12px;margin:4px 6px 0 0;'>{escape(str(item))}</span>"
        for item in (thread.get("action_suggestions") or [])[:4]
    )
    reply_subject = escape(thread.get("subject") or "")
    risk_level = escape(thread.get("risk_level") or "normal")
    mail_kind = escape(thread.get("mail_kind") or "info")
    needs_reply = "是" if thread.get("needs_reply") else "否"
    analysis_reason = escape(thread.get("analysis_reason") or "这封信正在等待你的下一步。")
    title = escape(thread.get("subject") or "未命名来信")
    decision_status = thread.get("decision_status") or "pending"
    draft_subject = escape((latest_draft or {}).get("subject") or (thread.get("subject") or ""))
    draft_body = escape(draft_preview)
    draft_source = "AI 起草" if (latest_draft or {}).get("ai_generated") else "手动草稿"
    draft_badge = "已修改" if (latest_draft or {}).get("user_edited_after_ai") else draft_source
    decision_label = {
        "pending": "待你决定",
        "snoozed": "稍后再问",
        "cleared": "暂时处理完",
    }.get(decision_status, "待处理")
    waiting_banner = "这封信仍在等你拍板。" if thread.get("waiting_user_decision") else "这条线程暂时安静，仍可继续编辑或寄出。"
    reply_to_list = (latest_draft or {}).get("to") or []
    latest_inbound = next((item for item in reversed(detail.get("messages", [])) if item.get("direction") == "inbound"), None)
    latest_sender = escape(
        (latest_inbound or {}).get("from_name")
        or (latest_inbound or {}).get("from_email")
        or "来信方"
    )
    latest_sender_email = escape((latest_inbound or {}).get("from_email") or "")
    latest_inbound_text = _message_body_text(latest_inbound) or "这封来信没有留下更多正文。"
    latest_inbound_body = escape(latest_inbound_text)
    latest_excerpt = escape(latest_inbound_text[:240])
    history_cards = []
    for message in reversed(detail.get("messages", [])[-6:]):
        direction_label = "对方来信" if message.get("direction") == "inbound" else "我方寄出"
        author = escape(message.get("from_name") or message.get("from_email") or "未署名")
        message_body = escape(_message_body_text(message) or "这封信没有正文。")
        history_cards.append(
            f"""
            <article class="history-card">
              <div class="meta">{direction_label} · {author}</div>
              <div class="history-body">{message_body}</div>
            </article>
            """
        )
    history_html = "".join(history_cards) or "<div class='meta'>暂时还没有更多往来记录。</div>"
    if not reply_to_list:
        reply_to_list = (latest_inbound or {}).get("reply_to") or []
        if not reply_to_list and (latest_inbound or {}).get("from_email"):
            reply_to_list = [{
                "name": (latest_inbound or {}).get("from_name") or (latest_inbound or {}).get("from_email"),
                "email": (latest_inbound or {}).get("from_email"),
            }]
    mailto_to = ",".join(
        str(item.get("email") or "").strip()
        for item in reply_to_list
        if str(item.get("email") or "").strip()
    )
    mailto_href = f"mailto:{mailto_to}?subject={quote((latest_draft or {}).get('subject') or (thread.get('subject') or ''))}"
    quick_snooze_href = _portal_quick_link(thread_id, token, "decision", decision_status="snoozed")
    quick_done_href = _portal_quick_link(thread_id, token, "decision", decision_status="cleared")
    quick_task_href = _portal_quick_link(thread_id, token, "task")
    quick_portal_href = f"/api/mail/portal/{thread_id}?token={token}"
    notice_html = ""
    if notice:
        tone_class = "notice-success" if tone != "error" else "notice-error"
        notice_html = f"<section class='notice {tone_class}'>{escape(notice)}</section>"

    html = f"""
    <!doctype html>
    <html lang="zh-CN">
    <head>
      <meta charset="utf-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
      <title>书信处理页</title>
      <style>
        body {{ margin:0; font-family:-apple-system,BlinkMacSystemFont,'PingFang SC','Segoe UI',sans-serif; background:#f7f1e8; color:#1f1b16; }}
        .sheet {{ max-width:760px; margin:0 auto; padding:24px 18px 40px; }}
        .card {{ background:#fffaf2; border:1px solid #dfd2bf; border-radius:20px; padding:18px; box-shadow:0 14px 36px rgba(72,48,20,.08); margin-bottom:16px; }}
        .notice {{ margin:0 0 14px; padding:14px 16px; border-radius:16px; font-size:14px; line-height:1.6; }}
        .notice-success {{ background:#efe7d7; border:1px solid #d9c7ab; color:#5e4725; }}
        .notice-error {{ background:#fbe5e2; border:1px solid #e6b6ab; color:#7a2f21; }}
        .kicker {{ font-size:12px; letter-spacing:.12em; text-transform:uppercase; color:#8f6b39; margin-bottom:8px; }}
        h1 {{ font-size:24px; line-height:1.3; margin:0 0 10px; }}
        p {{ line-height:1.7; margin:0 0 10px; }}
        .meta {{ color:#6b6256; font-size:13px; }}
        .btns {{ display:grid; grid-template-columns:1fr; gap:10px; margin-top:14px; }}
        .btn {{ display:block; text-align:center; text-decoration:none; padding:14px 16px; border-radius:14px; font-weight:600; }}
        .btn-primary {{ background:#2f6fed; color:#fff; }}
        .btn-secondary {{ background:#efe4d2; color:#5a4526; }}
        .draft {{ white-space:pre-wrap; line-height:1.7; font-size:14px; color:#2e2923; }}
        .label {{ display:block; font-size:12px; letter-spacing:.08em; text-transform:uppercase; color:#8f6b39; margin:14px 0 8px; }}
        .field, .textarea {{ width:100%; box-sizing:border-box; border:1px solid #d8cab4; border-radius:14px; background:#fffdf8; padding:13px 14px; font:inherit; color:#201b16; }}
        .textarea {{ min-height:220px; resize:vertical; line-height:1.7; }}
        .submeta {{ color:#7a6b58; font-size:13px; margin-top:8px; }}
        .decision-strip {{ display:flex; flex-wrap:wrap; gap:8px; margin-top:12px; }}
        .pill {{ display:inline-flex; align-items:center; padding:8px 12px; border-radius:999px; background:#f1e6d3; color:#664820; font-size:13px; }}
        .quote {{ border-left:3px solid #d5c1a1; padding-left:12px; color:#50463a; white-space:pre-wrap; }}
        .history-card {{ border:1px solid #e0d1bb; border-radius:16px; padding:14px; background:#fffdf8; margin-top:10px; }}
        .history-body {{ white-space:pre-wrap; line-height:1.7; color:#2e2923; font-size:14px; margin-top:8px; }}
        details {{ margin-top:12px; }}
        summary {{ cursor:pointer; color:#6f532c; font-weight:600; }}
        .quick-links {{ display:grid; grid-template-columns:repeat(2, minmax(0, 1fr)); gap:10px; margin-top:14px; }}
        .quick-link {{ display:block; text-align:center; text-decoration:none; padding:12px 10px; border-radius:14px; background:#f1e6d3; color:#5a4526; font-weight:600; font-size:14px; }}
      </style>
    </head>
    <body>
      <main class="sheet">
        {notice_html}
        <section class="card">
          <div class="kicker">Mail Desk / Mobile</div>
          <h1>{title}</h1>
          <p>{analysis_reason}</p>
          <div class="meta">判断：{mail_kind} · 风险：{risk_level} · 待回信：{needs_reply}</div>
          <div class="decision-strip">
            <span class="pill">{escape(decision_label)}</span>
            <span class="pill">来信人：{latest_sender}</span>
          </div>
          <div>{actions}</div>
          <div class="quick-links">
            <a class="quick-link" href="{quick_portal_href}">打开处理页</a>
            <a class="quick-link" href="{quick_task_href}">直接转成任务</a>
            <a class="quick-link" href="{quick_snooze_href}">稍后提醒我</a>
            <a class="quick-link" href="{quick_done_href}">标记已处理</a>
          </div>
        </section>

        <section class="card">
          <div class="kicker">Letter</div>
          <h2 style="font-size:20px;line-height:1.35;margin:0 0 8px;">最近一封来信</h2>
          <div class="meta">来自：{latest_sender}{f" · {latest_sender_email}" if latest_sender_email else ""}</div>
          <div class="quote" style="margin-top:12px;">{latest_inbound_body}</div>
          <details>
            <summary>展开近几次往来</summary>
            <div style="margin-top:10px;">{history_html}</div>
          </details>
        </section>

        <section class="card">
          <div class="kicker">Decision</div>
          <p>{escape(waiting_banner)}</p>
          <div class="quote">{latest_excerpt}</div>
          <div class="btns">
            <form method="post" action="/api/mail/portal/{thread_id}/decision?token={token}">
              <input type="hidden" name="decision_status" value="pending" />
              <button class="btn btn-secondary" type="submit" style="width:100%;border:none;">仍需我决定</button>
            </form>
            <form method="post" action="/api/mail/portal/{thread_id}/decision?token={token}">
              <input type="hidden" name="decision_status" value="snoozed" />
              <button class="btn btn-secondary" type="submit" style="width:100%;border:none;">稍后再问我</button>
            </form>
            <form method="post" action="/api/mail/portal/{thread_id}/decision?token={token}">
              <input type="hidden" name="decision_status" value="cleared" />
              <button class="btn btn-secondary" type="submit" style="width:100%;border:none;">这封信先处理完</button>
            </form>
          </div>
        </section>

        <section class="card">
          <div class="kicker">Counsel</div>
          <div class="meta">AI 判断理由</div>
          <div class="quote" style="margin-top:12px;">{analysis_reason}</div>
          <div class="decision-strip">{actions}</div>
        </section>

        <section class="card">
          <div class="kicker">Suggested Draft</div>
          <div class="meta">当前草稿：{escape(draft_badge)}</div>
          <form method="post" action="/api/mail/portal/{thread_id}/save-draft?token={token}">
            <input type="hidden" name="draft_id" value="{latest_draft_id}" />
            <label class="label" for="subject">邮件标题</label>
            <input class="field" id="subject" name="subject" value="{draft_subject}" placeholder="回信标题" />
            <label class="label" for="body">回信内容</label>
            <textarea class="textarea" id="body" name="body">{draft_body}</textarea>
            <div class="submeta">这是一张为手机准备的简页：先改字，再决定寄出、归档或转成任务。</div>
            <div class="btns">
              <button class="btn btn-primary" type="submit" style="width:100%;border:none;">保存这版草稿</button>
            </div>
          </form>
          <label class="label">当前预览</label>
          <div class="draft">{draft_body}</div>
          <div class="btns">
            <a class="btn btn-primary" href="{mailto_href}">在邮箱里继续回复</a>
            <form method="post" action="/api/mail/portal/{thread_id}/generate-reply-draft?token={token}">
              <button class="btn btn-secondary" type="submit" style="width:100%;border:none;">重新起草一版</button>
            </form>
            <form method="post" action="/api/mail/portal/{thread_id}/create-task?token={token}">
              <button class="btn btn-secondary" type="submit" style="width:100%;border:none;">把这封信转成任务</button>
            </form>
            <form method="post" action="/api/mail/portal/{thread_id}/archive?token={token}">
              <button class="btn btn-secondary" type="submit" style="width:100%;border:none;">归档这封信</button>
            </form>
            {f'''<form method="post" action="/api/mail/portal/{thread_id}/send-draft?token={token}">
              <input type="hidden" name="draft_id" value="{latest_draft_id}" />
              <button class="btn btn-secondary" type="submit" style="width:100%;border:none;">发送当前草稿</button>
            </form>''' if latest_draft_id else ''}
          </div>
        </section>
      </main>
    </body>
    </html>
    """
    return HTMLResponse(html)


@router.post("/portal/{thread_id}/save-draft", response_class=HTMLResponse)
async def portal_save_draft(
    thread_id: str,
    draft_id: str = Form(""),
    subject: str = Form(""),
    body: str = Form(""),
    token: str = Query(...),
):
    if not mail_service.verify_mail_portal_token(thread_id, token):
        return HTMLResponse("<h3>链接无效或已失效</h3>", status_code=403)

    detail = await mail_service.get_mail_thread(thread_id)
    if not detail:
        return HTMLResponse("<h3>这封信不存在</h3>", status_code=404)

    if not draft_id:
        latest_draft = next((draft for draft in detail.get("drafts", []) if draft.get("status") != "sent"), None)
        draft_id = (latest_draft or {}).get("draft_id", "")

    if not draft_id:
        generated = await mail_service.generate_reply_draft_for_thread(thread_id)
        if generated.get("status") != "success":
            return _portal_result_page("保存失败", generated.get("message", "未能生成可编辑草稿"), thread_id, token)
        draft_id = generated.get("draft_id", "")

    if not draft_id:
        return _portal_result_page("保存失败", "系统没有找到可保存的草稿。", thread_id, token)

    current_draft = next((draft for draft in detail.get("drafts", []) if draft.get("draft_id") == draft_id), None)
    normalized_subject = subject.strip() or ((current_draft or {}).get("subject") or thread_id)
    body_html = escape(body or "").replace("\r\n", "\n").replace("\r", "\n").replace("\n", "<br>")
    result = await mail_service.update_mail_draft(
        draft_id,
        subject=normalized_subject,
        body_html=body_html,
        user_edited_after_ai=True,
    )
    if result.get("status") != "success":
        return _portal_redirect(thread_id, token, result.get("message", "草稿保存失败"), tone="error")
    return _portal_redirect(thread_id, token, "已把你的改动收进这封回信。")


@router.post("/portal/{thread_id}/generate-reply-draft", response_class=HTMLResponse)
async def portal_generate_reply_draft(thread_id: str, token: str = Query(...)):
    if not mail_service.verify_mail_portal_token(thread_id, token):
        return HTMLResponse("<h3>链接无效或已失效</h3>", status_code=403)
    result = await mail_service.generate_reply_draft_for_thread(thread_id)
    if result.get("status") != "success":
        return _portal_redirect(thread_id, token, result.get("message", "未能生成回信草稿"), tone="error")
    source = "AI" if result.get("draft_source") == "ai" else "模板"
    return _portal_redirect(thread_id, token, f"{source} 已为你重新起草一版回复。")


@router.post("/portal/{thread_id}/create-task", response_class=HTMLResponse)
async def portal_create_task(thread_id: str, token: str = Query(...)):
    if not mail_service.verify_mail_portal_token(thread_id, token):
        return HTMLResponse("<h3>链接无效或已失效</h3>", status_code=403)
    result = await mail_service.create_task_from_mail_thread(thread_id)
    if result.get("status") != "success":
        return _portal_redirect(thread_id, token, result.get("message", "未能从邮件创建任务"), tone="error")
    return _portal_redirect(thread_id, token, f"已创建任务：{result.get('task_name', '邮件跟进任务')}")


@router.post("/portal/{thread_id}/archive", response_class=HTMLResponse)
async def portal_archive_thread(thread_id: str, token: str = Query(...)):
    if not mail_service.verify_mail_portal_token(thread_id, token):
        return HTMLResponse("<h3>链接无效或已失效</h3>", status_code=403)
    result = await mail_service.move_thread_to_folder(thread_id, "archive")
    if result.get("status") != "success":
        return _portal_redirect(thread_id, token, result.get("message", "未能归档这封信"), tone="error")
    return _portal_redirect(thread_id, token, "这封信已经安静收进归档夹。")


@router.get("/portal/{thread_id}/quick/{action}", response_class=HTMLResponse)
async def portal_quick_action(
    thread_id: str,
    action: str,
    token: str = Query(...),
    decision_status: str = Query("", description="pending/snoozed/cleared"),
):
    if not mail_service.verify_mail_portal_token(thread_id, token):
        return HTMLResponse("<h3>链接无效或已失效</h3>", status_code=403)

    if action == "task":
        result = await mail_service.create_task_from_mail_thread(thread_id)
        if result.get("status") != "success":
            return _portal_redirect(thread_id, token, result.get("message", "未能从邮件创建任务"), tone="error")
        return _portal_redirect(thread_id, token, f"已创建任务：{result.get('task_name', '邮件跟进任务')}")

    if action == "archive":
        result = await mail_service.move_thread_to_folder(thread_id, "archive")
        if result.get("status") != "success":
            return _portal_redirect(thread_id, token, result.get("message", "未能归档这封信"), tone="error")
        return _portal_redirect(thread_id, token, "这封信已经安静收进归档夹。")

    if action == "decision":
        result = await mail_service.set_thread_decision_status(thread_id, decision_status or "pending")
        if result.get("status") != "success":
            return _portal_redirect(thread_id, token, result.get("message", "未能更新处理状态"), tone="error")
        status_copy = {
            "pending": "这封信重新回到待决定列表。",
            "snoozed": "我先把它按下，稍后再提醒你。",
            "cleared": "这封信已暂时离开待决定队列。",
        }
        return _portal_redirect(thread_id, token, status_copy.get(decision_status or "pending", "处理状态已更新。"))

    return _portal_redirect(thread_id, token, f"不支持的快捷动作：{action}", tone="error")


@router.post("/portal/{thread_id}/decision", response_class=HTMLResponse)
async def portal_thread_decision(
    thread_id: str,
    decision_status: str = Form(...),
    token: str = Query(...),
):
    if not mail_service.verify_mail_portal_token(thread_id, token):
        return HTMLResponse("<h3>链接无效或已失效</h3>", status_code=403)
    result = await mail_service.set_thread_decision_status(thread_id, decision_status)
    if result.get("status") != "success":
        return _portal_redirect(thread_id, token, result.get("message", "未能更新处理状态"), tone="error")
    status_copy = {
        "pending": "这封信重新回到待决定列表。",
        "snoozed": "我先把它按下，稍后再提醒你。",
        "cleared": "这封信已暂时离开待决定队列。",
    }
    return _portal_redirect(thread_id, token, status_copy.get(decision_status, "处理状态已更新。"))


@router.post("/portal/{thread_id}/send-draft", response_class=HTMLResponse)
async def portal_send_draft(thread_id: str, draft_id: str = Form(""), token: str = Query(...)):
    if not mail_service.verify_mail_portal_token(thread_id, token):
        return HTMLResponse("<h3>链接无效或已失效</h3>", status_code=403)
    if not draft_id:
        detail = await mail_service.get_mail_thread(thread_id)
        latest_draft = next((draft for draft in (detail or {}).get("drafts", []) if draft.get("status") != "sent"), None)
        draft_id = (latest_draft or {}).get("draft_id", "")
    if not draft_id:
        return _portal_redirect(thread_id, token, "当前没有可发送的草稿。", tone="error")
    result = await mail_service.send_mail_draft(draft_id)
    if result.get("status") != "success":
        return _portal_redirect(thread_id, token, result.get("message", "草稿发送失败"), tone="error")
    return _portal_redirect(thread_id, token, "这封回信已经替你寄出。")


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
