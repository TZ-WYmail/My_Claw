from __future__ import annotations

import asyncio
import logging
import smtplib
import uuid
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

import aiosqlite

from config import DB_PATH as DEFAULT_DB_PATH
from services.mail.accounts import get_folder_id, get_mail_account_raw
from services.mail.compat import get_runtime_asyncio, get_runtime_db_path, get_runtime_smtplib
from services.mail.threads import create_thread, get_mail_thread, refresh_thread_state
from services.mail.utils import (
    build_outgoing_message_id,
    json_dumps,
    json_loads,
    normalize_message_id,
    now_iso,
)

logger = logging.getLogger(__name__)


async def create_mail_draft(
    account_id: str,
    subject: str,
    body_html: str = "",
    to: Optional[list[dict]] = None,
    cc: Optional[list[dict]] = None,
    bcc: Optional[list[dict]] = None,
    thread_id: Optional[str] = None,
    reply_mode: str = "new",
    tone_mode: str = "warm",
    signature: str = "",
    scheduled_send_at: Optional[str] = None,
    ai_generated: bool = False,
) -> dict:
    account = await get_mail_account_raw(account_id)
    if not account:
        return {"status": "error", "message": f"账户 {account_id} 不存在"}

    draft_id = f"draft_{uuid.uuid4().hex[:12]}"
    current_time = now_iso()
    async with aiosqlite.connect(str(get_runtime_db_path(DEFAULT_DB_PATH))) as db:
        await db.executescript("PRAGMA foreign_keys = ON;")
        if not thread_id:
            thread_id = await create_thread(
                db,
                account_id=account_id,
                subject=subject,
                participants=[{"name": account["display_name"], "email": account["email_address"], "role": "self"}],
                latest_folder_kind="drafts",
                snippet=body_html,
            )
        await db.execute(
            """
            INSERT INTO mail_drafts (
                draft_id, thread_id, account_id, reply_mode, subject, to_json, cc_json,
                bcc_json, body_html, tone_mode, signature, scheduled_send_at, ai_generated,
                user_edited_after_ai, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                draft_id,
                thread_id,
                account_id,
                reply_mode,
                subject,
                json_dumps(to),
                json_dumps(cc),
                json_dumps(bcc),
                body_html,
                tone_mode,
                signature,
                scheduled_send_at,
                1 if ai_generated else 0,
                0,
                "draft",
                current_time,
                current_time,
            ),
        )
        await refresh_thread_state(db, thread_id)
        await db.commit()
    detail = await get_mail_thread(thread_id)
    return {"status": "success", "draft_id": draft_id, "thread_id": thread_id, **detail}


async def update_mail_draft(
    draft_id: str,
    subject: Optional[str] = None,
    body_html: Optional[str] = None,
    to: Optional[list[dict]] = None,
    cc: Optional[list[dict]] = None,
    bcc: Optional[list[dict]] = None,
    tone_mode: Optional[str] = None,
    signature: Optional[str] = None,
    scheduled_send_at: Optional[str] = None,
    user_edited_after_ai: Optional[bool] = None,
    status: Optional[str] = None,
) -> dict:
    updates: list[str] = []
    params: list = []
    for field, value in {
        "subject": subject,
        "body_html": body_html,
        "tone_mode": tone_mode,
        "signature": signature,
        "scheduled_send_at": scheduled_send_at,
        "status": status,
    }.items():
        if value is None:
            continue
        updates.append(f"{field} = ?")
        params.append(value)
    for field, value in {
        "to_json": json_dumps(to) if to is not None else None,
        "cc_json": json_dumps(cc) if cc is not None else None,
        "bcc_json": json_dumps(bcc) if bcc is not None else None,
    }.items():
        if value is None:
            continue
        updates.append(f"{field} = ?")
        params.append(value)
    if user_edited_after_ai is not None:
        updates.append("user_edited_after_ai = ?")
        params.append(1 if user_edited_after_ai else 0)
    if not updates:
        return {"status": "error", "message": "没有需要更新的字段"}

    updates.append("updated_at = ?")
    params.append(now_iso())
    params.append(draft_id)

    async with aiosqlite.connect(str(get_runtime_db_path(DEFAULT_DB_PATH))) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            f"UPDATE mail_drafts SET {', '.join(updates)} WHERE draft_id = ?",
            params,
        )
        if cursor.rowcount == 0:
            await db.rollback()
            return {"status": "error", "message": f"草稿 {draft_id} 不存在"}

        cursor = await db.execute("SELECT thread_id FROM mail_drafts WHERE draft_id = ?", (draft_id,))
        row = await cursor.fetchone()
        thread_id = row["thread_id"]
        await refresh_thread_state(db, thread_id)
        await db.commit()

    detail = await get_mail_thread(thread_id)
    return {"status": "success", "draft_id": draft_id, **detail}


async def send_mail_draft(draft_id: str) -> dict:
    async with aiosqlite.connect(str(get_runtime_db_path(DEFAULT_DB_PATH))) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT draft_id, thread_id, account_id, subject, to_json, cc_json, bcc_json,
                   body_html, signature, status
            FROM mail_drafts WHERE draft_id = ?
            """,
            (draft_id,),
        )
        draft = await cursor.fetchone()
        if not draft:
            return {"status": "error", "message": f"草稿 {draft_id} 不存在"}

        account = await get_mail_account_raw(draft["account_id"])
        if not account:
            return {"status": "error", "message": f"账户 {draft['account_id']} 不存在"}

        cursor = await db.execute(
            """
            SELECT message_id, from_name, from_email, to_json, subject, internet_message_id, in_reply_to, references_json
            FROM mail_messages
            WHERE thread_id = ?
            ORDER BY COALESCE(received_at, sent_at, created_at) DESC
            LIMIT 1
            """,
            (draft["thread_id"],),
        )
        latest_message = await cursor.fetchone()

        recipients = json_loads(draft["to_json"])
        if latest_message and latest_message["from_email"]:
            recipients = [{
                "name": latest_message["from_name"] or latest_message["from_email"],
                "email": latest_message["from_email"],
            }]
        if not recipients:
            recipients = json_loads(latest_message["to_json"]) if latest_message and latest_message["to_json"] else []

        if not recipients:
            return {"status": "error", "message": "当前草稿缺少收件人上下文，暂不能发送"}

        full_body = (draft["body_html"] or "") + (f"<br><br>{draft['signature']}" if draft["signature"] else "")
        parent_message_id = normalize_message_id((latest_message["internet_message_id"] if latest_message else "") or "")
        parent_references = json_loads((latest_message["references_json"] if latest_message else "") or "[]")
        outgoing_references = [
            item
            for item in (normalize_message_id(ref) for ref in parent_references + ([parent_message_id] if parent_message_id else []))
            if item
        ]
        outgoing_message_id = build_outgoing_message_id(account["email_address"])
        runtime_smtplib = get_runtime_smtplib()

        def _send():
            if not (account.get("smtp_host") and account.get("smtp_user") and account.get("smtp_password")):
                return {"status": "error", "message": "账户未配置 SMTP"}
            msg = MIMEMultipart("alternative")
            msg["Subject"] = draft["subject"]
            msg["From"] = account["email_address"]
            msg["To"] = ", ".join(item["email"] for item in recipients if item.get("email"))
            msg["Message-ID"] = f"<{outgoing_message_id}>"
            if parent_message_id:
                msg["In-Reply-To"] = f"<{parent_message_id}>"
            if outgoing_references:
                msg["References"] = " ".join(f"<{item}>" for item in outgoing_references)
            cc_list = json_loads(draft["cc_json"])
            bcc_list = json_loads(draft["bcc_json"])
            if cc_list:
                msg["Cc"] = ", ".join(item["email"] for item in cc_list if item.get("email"))
            msg.attach(MIMEText(full_body, "html", "utf-8"))
            try:
                if int(account.get("smtp_port") or 465) == 465:
                    server = runtime_smtplib.SMTP_SSL(account["smtp_host"], int(account["smtp_port"]), timeout=30)
                else:
                    server = runtime_smtplib.SMTP(account["smtp_host"], int(account["smtp_port"]), timeout=30)
                    server.ehlo()
                    server.starttls()
                    server.ehlo()
                server.login(account["smtp_user"], account["smtp_password"])
                envelope = [item["email"] for item in recipients if item.get("email")]
                envelope += [item["email"] for item in cc_list if item.get("email")]
                envelope += [item["email"] for item in bcc_list if item.get("email")]
                server.sendmail(account["smtp_user"], envelope, msg.as_string())
                server.quit()
                return {"status": "success"}
            except Exception as exc:  # pragma: no cover
                logger.error("邮件草稿发送失败: %s", exc)
                return {"status": "error", "message": str(exc)}

        result = await get_runtime_asyncio().to_thread(_send)
        if result["status"] != "success":
            await db.execute(
                "UPDATE mail_drafts SET status = ?, updated_at = ? WHERE draft_id = ?",
                ("failed", now_iso(), draft_id),
            )
            await db.commit()
            return result

        await db.execute(
            "UPDATE mail_drafts SET status = ?, updated_at = ? WHERE draft_id = ?",
            ("sent", now_iso(), draft_id),
        )

        folder_id = await get_folder_id(db, draft["account_id"], "sent")
        await db.execute(
            """
            INSERT INTO mail_messages (
                message_id, thread_id, account_id, folder_id, internet_message_id, in_reply_to, references_json, direction, from_name,
                from_email, to_json, cc_json, bcc_json, subject, html_body, text_body, sent_at,
                received_at, is_read, is_starred, is_draft, delivery_status,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"msg_{uuid.uuid4().hex[:12]}",
                draft["thread_id"],
                draft["account_id"],
                folder_id,
                outgoing_message_id,
                parent_message_id,
                json_dumps(outgoing_references),
                "outbound",
                account["display_name"],
                account["email_address"],
                json_dumps(recipients),
                draft["cc_json"],
                draft["bcc_json"],
                draft["subject"],
                draft["body_html"],
                "",
                now_iso(),
                None,
                1,
                0,
                0,
                "sent",
                now_iso(),
                now_iso(),
            ),
        )
        await refresh_thread_state(db, draft["thread_id"])
        await db.commit()

    detail = await get_mail_thread(draft["thread_id"])
    return {"status": "success", "draft_id": draft_id, **detail}
