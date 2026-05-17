"""
双向邮件系统 Portal 路由
"""
from html import escape
from urllib.parse import urlencode

from fastapi import APIRouter, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse

from routers.mail_portal_render import (
    render_mail_portal_page,
    render_portal_result_page,
)
from services import mail_service

router = APIRouter()


def _portal_redirect(thread_id: str, token: str, notice: str, tone: str = "success") -> RedirectResponse:
    query = urlencode({"token": token, "notice": notice, "tone": tone})
    return RedirectResponse(url=f"/api/mail/portal/{thread_id}?{query}", status_code=303)


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
    return render_mail_portal_page(thread_id=thread_id, token=token, detail=detail, notice=notice, tone=tone)


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
            return render_portal_result_page("保存失败", generated.get("message", "未能生成可编辑草稿"), thread_id, token)
        draft_id = generated.get("draft_id", "")

    if not draft_id:
        return render_portal_result_page("保存失败", "系统没有找到可保存的草稿。", thread_id, token)

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
