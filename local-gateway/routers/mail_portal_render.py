"""
双向邮件系统 Portal 渲染函数
"""
import re
from html import escape
from typing import Optional
from urllib.parse import quote

from fastapi.responses import HTMLResponse


def html_to_plain_text(value: str) -> str:
    text = (value or "").replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
    text = re.sub(r"</p\s*>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    return text.strip()


def message_body_text(message: Optional[dict]) -> str:
    if not message:
        return ""
    return ((message.get("text_body") or "").strip() or html_to_plain_text(message.get("html_body") or "")).strip()


def render_portal_result_page(title: str, message: str, thread_id: str, token: str) -> HTMLResponse:
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


def render_mail_portal_page(thread_id: str, token: str, detail: dict, notice: str = "", tone: str = "success") -> HTMLResponse:
    thread = detail["thread"]
    latest_draft = next((draft for draft in detail.get("drafts", []) if draft.get("status") != "sent"), None)
    draft_preview = html_to_plain_text((latest_draft or {}).get("body_html", "尚未起草回复。"))
    latest_draft_id = (latest_draft or {}).get("draft_id", "")
    actions = "".join(
        f"<span style='display:inline-block;padding:6px 10px;border-radius:999px;background:#f6efe3;color:#7a5b2f;font-size:12px;margin:4px 6px 0 0;'>{escape(str(item))}</span>"
        for item in (thread.get("action_suggestions") or [])[:4]
    )
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
    latest_inbound_text = message_body_text(latest_inbound) or "这封来信没有留下更多正文。"
    latest_inbound_body = escape(latest_inbound_text)
    latest_excerpt = escape(latest_inbound_text[:240])
    history_cards = []
    for message in reversed(detail.get("messages", [])[-6:]):
        direction_label = "对方来信" if message.get("direction") == "inbound" else "我方寄出"
        author = escape(message.get("from_name") or message.get("from_email") or "未署名")
        body = escape(message_body_text(message) or "这封信没有正文。")
        history_cards.append(
            f"""
            <article class="history-card">
              <div class="meta">{direction_label} · {author}</div>
              <div class="history-body">{body}</div>
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
    quick_snooze_href = f"/api/mail/portal/{thread_id}/quick/decision?token={token}&decision_status=snoozed"
    quick_done_href = f"/api/mail/portal/{thread_id}/quick/decision?token={token}&decision_status=cleared"
    quick_task_href = f"/api/mail/portal/{thread_id}/quick/task?token={token}"
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
