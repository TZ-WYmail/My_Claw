from __future__ import annotations

import uuid
from typing import Optional

import aiosqlite

from config import DB_PATH as DEFAULT_DB_PATH
from services.mail.accounts import ensure_default_folders, get_folder_id, get_mail_account_raw
from services.mail.compat import get_runtime_db_path
from services.mail.threads import create_thread, find_existing_thread_id, get_mail_thread, refresh_thread_state
from services.mail.utils import json_dumps, normalize_message_id, now_iso


async def ingest_mail_message(
    account_id: str,
    subject: str,
    text_body: str = "",
    html_body: str = "",
    direction: str = "inbound",
    folder_kind: str = "inbox",
    thread_id: Optional[str] = None,
    from_name: str = "",
    from_email: str = "",
    to: Optional[list[dict]] = None,
    cc: Optional[list[dict]] = None,
    bcc: Optional[list[dict]] = None,
    reply_to: Optional[list[dict]] = None,
    remote_message_id: str = "",
    internet_message_id: str = "",
    in_reply_to: str = "",
    references: Optional[list[str]] = None,
    sent_at: Optional[str] = None,
    received_at: Optional[str] = None,
    is_read: bool = False,
    is_starred: bool = False,
    delivery_status: str = "sent",
    attachments: Optional[list[dict]] = None,
) -> dict:
    account = await get_mail_account_raw(account_id)
    if not account:
        return {"status": "error", "message": f"账户 {account_id} 不存在"}

    message_id = f"msg_{uuid.uuid4().hex[:12]}"
    current_time = now_iso()
    async with aiosqlite.connect(str(get_runtime_db_path(DEFAULT_DB_PATH))) as db:
        await db.executescript("PRAGMA foreign_keys = ON;")
        db.row_factory = aiosqlite.Row
        normalized_internet_message_id = normalize_message_id(internet_message_id)
        normalized_in_reply_to = normalize_message_id(in_reply_to)
        normalized_references = [
            item for item in (normalize_message_id(ref) for ref in (references or [])) if item
        ]
        folder_id = await get_folder_id(db, account_id, folder_kind)
        if not folder_id:
            await ensure_default_folders(db, account_id)
            folder_id = await get_folder_id(db, account_id, folder_kind)

        if normalized_internet_message_id:
            cursor = await db.execute(
                """
                SELECT message_id, thread_id
                FROM mail_messages
                WHERE account_id = ? AND internet_message_id = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (account_id, normalized_internet_message_id),
            )
            existing = await cursor.fetchone()
            if existing:
                detail = await get_mail_thread(existing["thread_id"])
                return {
                    "status": "success",
                    "message": "邮件已存在，跳过重复入库",
                    "message_id": existing["message_id"],
                    "thread_id": existing["thread_id"],
                    **detail,
                }

        if not thread_id:
            participants = []
            if from_email:
                participants.append({"name": from_name or from_email, "email": from_email, "role": "from"})
            for recipient in to or []:
                if recipient.get("email"):
                    participants.append({
                        "name": recipient.get("name") or recipient["email"],
                        "email": recipient["email"],
                        "role": "to",
                    })
            thread_id = await find_existing_thread_id(
                db,
                account_id,
                subject,
                participants=participants,
                internet_message_id=normalized_internet_message_id,
                in_reply_to=normalized_in_reply_to,
                references=normalized_references,
            )
        if not thread_id:
            thread_id = await create_thread(
                db,
                account_id=account_id,
                subject=subject,
                participants=participants,
                latest_folder_kind=folder_kind,
                snippet=text_body or html_body,
            )

        await db.execute(
            """
            INSERT INTO mail_messages (
                message_id, thread_id, account_id, folder_id, remote_message_id,
                internet_message_id, in_reply_to, references_json, direction, from_name, from_email,
                to_json, cc_json, bcc_json, reply_to_json, subject, html_body,
                text_body, quoted_body, sent_at, received_at, is_read,
                is_starred, is_draft, delivery_status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                message_id,
                thread_id,
                account_id,
                folder_id,
                remote_message_id,
                normalized_internet_message_id,
                normalized_in_reply_to,
                json_dumps(normalized_references),
                direction,
                from_name,
                from_email,
                json_dumps(to),
                json_dumps(cc),
                json_dumps(bcc),
                json_dumps(reply_to),
                subject,
                html_body,
                text_body,
                "",
                sent_at,
                received_at,
                1 if is_read else 0,
                1 if is_starred else 0,
                0,
                delivery_status,
                current_time,
                current_time,
            ),
        )
        for index, attachment in enumerate(attachments or []):
            attachment_id = str(attachment.get("attachment_id") or f"att_{uuid.uuid4().hex[:12]}_{index}")
            await db.execute(
                """
                INSERT INTO mail_attachments (
                    attachment_id, message_id, thread_id, account_id, filename, mime_type,
                    size_bytes, content_id, is_inline, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    attachment_id,
                    message_id,
                    thread_id,
                    account_id,
                    str(attachment.get("filename") or ""),
                    str(attachment.get("mime_type") or "application/octet-stream"),
                    int(attachment.get("size_bytes") or 0),
                    normalize_message_id(attachment.get("content_id")),
                    1 if bool(attachment.get("is_inline")) else 0,
                    current_time,
                    current_time,
                ),
            )
        await refresh_thread_state(db, thread_id)
        await db.commit()

    detail = await get_mail_thread(thread_id)
    return {"status": "success", "message_id": message_id, "thread_id": thread_id, **detail}
