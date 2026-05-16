from __future__ import annotations

import json
import uuid
from typing import Optional

import aiosqlite

from config import DB_PATH as DEFAULT_DB_PATH
from services.mail.accounts import ensure_default_folders, get_folder_id
from services.mail.compat import get_runtime_db_path
from services.mail.utils import (
    build_mail_portal_links,
    clean_snippet,
    json_dumps,
    json_loads,
    normalize_message_id,
    normalize_subject,
    now_iso,
)


def infer_mail_analysis(
    *,
    subject: str,
    snippet: str,
    participants: list[dict],
    unread_count: int,
    has_new_inbound: bool,
    has_pending_draft: bool,
    last_actor: str,
    latest_folder_kind: str,
) -> dict:
    lowered = f"{subject or ''}\n{snippet or ''}".lower()
    sender = (participants[0].get("email", "") if participants else "").lower()

    marketing_hits = [
        "unsubscribe", "退订", "促销", "优惠", "newsletter", "精选", "每周", "欢迎注册", "验证码", "verification code",
    ]
    planning_hits = [
        "deadline", "due", "meeting", "interview", "schedule", "appointment", "confirm", "payment",
        "截止", "会议", "面试", "安排", "预约", "确认", "出行", "付款", "材料", "提交", "签约", "体检",
    ]
    explicit_reply_hits = [
        "please reply", "reply", "respond", "confirm", "let me know", "请回复", "请确认", "是否可以", "能否", "烦请",
    ]

    mail_kind = "info"
    reply_level = "none"
    risk_level = "normal"
    analysis_reason = "这封信目前更像供阅读与存档的信息。"
    action_suggestions = ["归档留存", "稍后再读"]

    is_marketing = any(token in lowered for token in marketing_hits) or sender.startswith("no-reply")
    is_planning_related = any(token in lowered for token in planning_hits)
    has_explicit_reply_signal = any(token in lowered for token in explicit_reply_hits)

    if latest_folder_kind == "sent":
        mail_kind = "outbound"
        analysis_reason = "这是你已经发出的信，当前更适合留痕与追踪。"
        action_suggestions = ["查看往返", "继续跟进"]
    elif is_marketing:
        mail_kind = "marketing"
        risk_level = "low"
        analysis_reason = "这封信带有明显的订阅或营销特征，通常不需要投入回应。"
        action_suggestions = ["归档留存", "忽略这封信"]
    elif has_new_inbound and (has_explicit_reply_signal or is_planning_related):
        mail_kind = "planning" if is_planning_related else "reply"
        reply_level = "must_reply" if (unread_count > 0 or is_planning_related) else "suggest_reply"
        risk_level = "high" if is_planning_related else "normal"
        analysis_reason = "来信里含有确认、时间、安排或明确提问，适合尽快由你决定下一步。"
        action_suggestions = ["起草回复", "转成任务", "和 AI 商量"]
    elif has_new_inbound or last_actor == "counterparty":
        mail_kind = "reply"
        reply_level = "suggest_reply"
        risk_level = "normal"
        analysis_reason = "往返链条停在对方一侧，系统建议你看一眼是否需要回信。"
        action_suggestions = ["起草回复", "稍后再问", "归档留存"]
    elif is_planning_related:
        mail_kind = "planning"
        risk_level = "high"
        analysis_reason = "这封信与后续时间安排或执行节点相关，即使未必立刻回信，也值得纳入计划。"
        action_suggestions = ["转成任务", "和 AI 商量", "稍后再问"]

    if has_pending_draft:
        action_suggestions = ["继续编辑草稿", "和 AI 商量", "寄出回复"]
        if reply_level == "none":
            reply_level = "suggest_reply"
        if not analysis_reason:
            analysis_reason = "你已经起了草稿，这封信正在等待完成。"

    needs_reply = 1 if (has_new_inbound or last_actor == "counterparty") and latest_folder_kind != "archive" else 0
    waiting_user_decision = 1 if reply_level in {"must_reply", "suggest_reply"} or mail_kind == "planning" else 0
    if latest_folder_kind == "archive":
        waiting_user_decision = 0

    return {
        "needs_reply": needs_reply,
        "mail_kind": mail_kind,
        "reply_level": reply_level,
        "decision_status": "pending" if waiting_user_decision else "cleared",
        "waiting_user_decision": waiting_user_decision,
        "analysis_reason": analysis_reason,
        "action_suggestions_json": json_dumps(action_suggestions),
        "risk_level": risk_level,
        "last_analyzed_at": now_iso(),
    }


def thread_from_row(row: aiosqlite.Row) -> dict:
    data = dict(row)
    data["participants"] = json_loads(data.pop("participants_json", "[]"))
    data["action_suggestions"] = json_loads(data.pop("action_suggestions_json", "[]"))
    data["has_new_inbound"] = bool(data.get("has_new_inbound", 0))
    data["has_pending_draft"] = bool(data.get("has_pending_draft", 0))
    data["is_archived"] = bool(data.get("is_archived", 0))
    data["needs_reply"] = bool(data.get("needs_reply", 0))
    data["has_draft"] = bool(data.get("has_draft", 0))
    data["waiting_user_decision"] = bool(data.get("waiting_user_decision", 0))
    return data


def message_from_row(row: aiosqlite.Row) -> dict:
    data = dict(row)
    data["to"] = json_loads(data.pop("to_json", "[]"))
    data["cc"] = json_loads(data.pop("cc_json", "[]"))
    data["bcc"] = json_loads(data.pop("bcc_json", "[]"))
    data["reply_to"] = json_loads(data.pop("reply_to_json", "[]"))
    data["references"] = json_loads(data.pop("references_json", "[]"))
    data["is_read"] = bool(data.get("is_read", 0))
    data["is_starred"] = bool(data.get("is_starred", 0))
    data["is_draft"] = bool(data.get("is_draft", 0))
    return data


def draft_from_row(row: aiosqlite.Row) -> dict:
    data = dict(row)
    data["to"] = json_loads(data.pop("to_json", "[]"))
    data["cc"] = json_loads(data.pop("cc_json", "[]"))
    data["bcc"] = json_loads(data.pop("bcc_json", "[]"))
    data["ai_generated"] = bool(data.get("ai_generated", 0))
    data["user_edited_after_ai"] = bool(data.get("user_edited_after_ai", 0))
    return data


def attachment_from_row(row: aiosqlite.Row) -> dict:
    data = dict(row)
    data["is_inline"] = bool(data.get("is_inline", 0))
    return data


def agent_run_from_row(row: aiosqlite.Row) -> dict:
    data = dict(row)
    detail_raw = data.pop("detail_json", "{}")
    try:
        parsed = json.loads(detail_raw or "{}")
        data["details"] = parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        data["details"] = {}
    return data


def attach_portal_links_to_thread(thread: Optional[dict]) -> Optional[dict]:
    if not thread or not thread.get("thread_id"):
        return thread
    links = build_mail_portal_links(thread["thread_id"])
    thread["portal_url"] = links["portal_url"]
    thread["quick_task_url"] = links["quick_task_url"]
    thread["quick_snooze_url"] = links["quick_snooze_url"]
    thread["quick_done_url"] = links["quick_done_url"]
    return thread


async def find_existing_thread_id(
    db: aiosqlite.Connection,
    account_id: str,
    subject: str,
    participants: Optional[list[dict]] = None,
    internet_message_id: str = "",
    in_reply_to: str = "",
    references: Optional[list[str]] = None,
) -> Optional[str]:
    references = references or []

    cursor = await db.execute(
        "SELECT email_address FROM mail_accounts WHERE account_id = ?",
        (account_id,),
    )
    account_row = await cursor.fetchone()
    own_email = ((account_row[0] if account_row else "") or "").strip().lower()

    def _counterparty_emails(items: Optional[list[dict]]) -> set[str]:
        values: set[str] = set()
        for item in items or []:
            email_value = str((item or {}).get("email") or "").strip().lower()
            if not email_value or email_value == own_email:
                continue
            values.add(email_value)
        return values

    async def _lookup_thread_by_message_ids(message_ids: list[str]) -> Optional[str]:
        normalized_ids = [item for item in (normalize_message_id(mid) for mid in message_ids) if item]
        if not normalized_ids:
            return None
        placeholders = ", ".join("?" for _ in normalized_ids)
        cursor_local = await db.execute(
            f"""
            SELECT thread_id
            FROM mail_messages
            WHERE account_id = ? AND internet_message_id IN ({placeholders})
            ORDER BY created_at DESC
            LIMIT 1
            """,
            [account_id, *normalized_ids],
        )
        row_local = await cursor_local.fetchone()
        return row_local[0] if row_local else None

    reply_chain_thread_id = await _lookup_thread_by_message_ids([in_reply_to, *references])
    if reply_chain_thread_id:
        return reply_chain_thread_id

    if internet_message_id:
        cursor = await db.execute(
            """
            SELECT thread_id
            FROM mail_messages
            WHERE account_id = ? AND internet_message_id = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (account_id, internet_message_id),
        )
        row = await cursor.fetchone()
        if row:
            return row[0]

    cursor = await db.execute(
        """
        SELECT thread_id, participants_json
        FROM mail_threads
        WHERE account_id = ? AND subject_normalized = ?
        ORDER BY COALESCE(latest_message_at, updated_at) DESC
        """,
        (account_id, normalize_subject(subject)),
    )
    rows = await cursor.fetchall()
    if not rows:
        return None

    target_counterparts = _counterparty_emails(participants or [])
    if not target_counterparts:
        return rows[0][0]

    for row in rows:
        if _counterparty_emails(json_loads(row[1])) & target_counterparts:
            return row[0]
    return None


async def create_thread(
    db: aiosqlite.Connection,
    account_id: str,
    subject: str,
    participants: Optional[list[dict]] = None,
    latest_folder_kind: str = "inbox",
    snippet: str = "",
) -> str:
    thread_id = f"thread_{uuid.uuid4().hex[:12]}"
    current_time = now_iso()
    normalized = normalize_subject(subject)
    await db.execute(
        """
        INSERT INTO mail_threads (
            thread_id, account_id, subject, subject_normalized, participants_json,
            snippet, latest_message_at, latest_folder_kind, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            thread_id,
            account_id,
            subject or normalized,
            normalized,
            json_dumps(participants or []),
            clean_snippet(snippet),
            current_time,
            latest_folder_kind,
            current_time,
            current_time,
        ),
    )
    return thread_id


async def refresh_thread_state(db: aiosqlite.Connection, thread_id: str):
    db.row_factory = aiosqlite.Row
    cursor = await db.execute(
        """
        SELECT message_id, subject, text_body, html_body, from_name, from_email,
               to_json, sent_at, received_at, is_read, direction
        FROM mail_messages
        WHERE thread_id = ?
        ORDER BY COALESCE(received_at, sent_at, created_at) DESC, created_at DESC
        LIMIT 1
        """,
        (thread_id,),
    )
    latest_message = await cursor.fetchone()

    cursor = await db.execute(
        "SELECT COUNT(*) FROM mail_messages WHERE thread_id = ? AND direction = 'inbound' AND is_read = 0",
        (thread_id,),
    )
    unread_count = (await cursor.fetchone())[0]

    cursor = await db.execute(
        "SELECT COUNT(*) FROM mail_drafts WHERE thread_id = ? AND status IN ('draft', 'queued')",
        (thread_id,),
    )
    has_pending_draft = 1 if (await cursor.fetchone())[0] > 0 else 0

    cursor = await db.execute(
        """
        SELECT message_id, COALESCE(received_at, sent_at, created_at) AS event_at
        FROM mail_messages
        WHERE thread_id = ? AND direction = 'inbound'
        ORDER BY COALESCE(received_at, sent_at, created_at) DESC, created_at DESC
        LIMIT 1
        """,
        (thread_id,),
    )
    latest_inbound = await cursor.fetchone()

    cursor = await db.execute(
        """
        SELECT message_id, COALESCE(sent_at, received_at, created_at) AS event_at
        FROM mail_messages
        WHERE thread_id = ? AND direction = 'outbound'
        ORDER BY COALESCE(sent_at, created_at) DESC
        LIMIT 1
        """,
        (thread_id,),
    )
    latest_outbound = await cursor.fetchone()

    latest_inbound_at = (latest_inbound["event_at"] if latest_inbound else "") or ""
    latest_outbound_at = (latest_outbound["event_at"] if latest_outbound else "") or ""
    has_new_inbound = 1 if latest_inbound and (not latest_outbound_at or latest_inbound_at > latest_outbound_at) else 0
    last_actor = "counterparty" if has_new_inbound else ("self" if latest_outbound else "none")
    latest_message_at = now_iso()
    subject = None
    snippet = ""
    participants: list[dict] = []
    latest_folder_kind = "inbox"

    if latest_message:
        subject = latest_message["subject"]
        latest_message_at = latest_message["received_at"] or latest_message["sent_at"] or now_iso()
        snippet = clean_snippet(latest_message["text_body"] or latest_message["html_body"])
        if latest_message["from_email"]:
            participants.append({
                "name": latest_message["from_name"] or latest_message["from_email"],
                "email": latest_message["from_email"],
                "role": "from",
            })
        for recipient in json_loads(latest_message["to_json"]):
            if isinstance(recipient, dict) and recipient.get("email"):
                participants.append({
                    "name": recipient.get("name") or recipient["email"],
                    "email": recipient["email"],
                    "role": "to",
                })

    cursor = await db.execute(
        """
        SELECT f.kind
        FROM mail_messages m
        LEFT JOIN mail_folders f ON f.folder_id = m.folder_id
        WHERE m.thread_id = ?
        ORDER BY COALESCE(m.received_at, m.sent_at, m.created_at) DESC, m.created_at DESC
        LIMIT 1
        """,
        (thread_id,),
    )
    folder_row = await cursor.fetchone()
    if folder_row and folder_row["kind"]:
        latest_folder_kind = folder_row["kind"]
    is_archived = 1 if latest_folder_kind == "archive" else 0

    analysis = infer_mail_analysis(
        subject=subject or "",
        snippet=snippet,
        participants=participants,
        unread_count=unread_count,
        has_new_inbound=bool(has_new_inbound),
        has_pending_draft=bool(has_pending_draft),
        last_actor=last_actor,
        latest_folder_kind=latest_folder_kind,
    )

    await db.execute(
        """
        UPDATE mail_threads
        SET subject = COALESCE(?, subject),
            subject_normalized = COALESCE(?, subject_normalized),
            participants_json = ?,
            snippet = ?,
            latest_message_at = ?,
            latest_folder_kind = ?,
            unread_count = ?,
            has_new_inbound = ?,
            has_pending_draft = ?,
            is_archived = ?,
            last_actor = ?,
            needs_reply = ?,
            has_draft = ?,
            mail_kind = ?,
            reply_level = ?,
            decision_status = ?,
            waiting_user_decision = ?,
            analysis_reason = ?,
            action_suggestions_json = ?,
            last_analyzed_at = ?,
            risk_level = ?,
            updated_at = ?
        WHERE thread_id = ?
        """,
        (
            subject,
            normalize_subject(subject) if subject else None,
            json_dumps(participants),
            snippet,
            latest_message_at,
            latest_folder_kind,
            unread_count,
            has_new_inbound,
            has_pending_draft,
            is_archived,
            last_actor,
            analysis["needs_reply"],
            has_pending_draft,
            analysis["mail_kind"],
            analysis["reply_level"],
            analysis["decision_status"],
            analysis["waiting_user_decision"],
            analysis["analysis_reason"],
            analysis["action_suggestions_json"],
            analysis["last_analyzed_at"],
            analysis["risk_level"],
            now_iso(),
            thread_id,
        ),
    )


async def list_mail_threads(
    account_id: Optional[str] = None,
    folder: str = "",
    needs_reply: Optional[bool] = None,
    unread_only: bool = False,
    q: str = "",
    waiting_user_decision: Optional[bool] = None,
) -> list[dict]:
    conditions = ["1=1"]
    params: list = []
    if account_id:
        conditions.append("account_id = ?")
        params.append(account_id)
    if folder:
        conditions.append("latest_folder_kind = ?")
        params.append(folder)
    else:
        conditions.append("latest_folder_kind != 'archive'")
    if needs_reply is not None:
        conditions.append("needs_reply = ?")
        params.append(1 if needs_reply else 0)
    if unread_only:
        conditions.append("unread_count > 0")
    if waiting_user_decision is not None:
        conditions.append("waiting_user_decision = ?")
        params.append(1 if waiting_user_decision else 0)
    if q:
        conditions.append("(subject LIKE ? OR snippet LIKE ? OR participants_json LIKE ?)")
        params.extend([f"%{q}%", f"%{q}%", f"%{q}%"])

    query = f"""
        SELECT thread_id, account_id, subject, subject_normalized, participants_json,
               snippet, latest_message_at, latest_folder_kind, unread_count,
               has_new_inbound, has_pending_draft, is_archived, last_actor,
               needs_reply, has_draft, mail_kind, reply_level, decision_status,
               waiting_user_decision, analysis_reason, action_suggestions_json,
               last_analyzed_at, linked_task_count, linked_note_count,
               linked_event_count, risk_level, created_at, updated_at
        FROM mail_threads
        WHERE {' AND '.join(conditions)}
        ORDER BY COALESCE(latest_message_at, updated_at) DESC
    """

    async with aiosqlite.connect(str(get_runtime_db_path(DEFAULT_DB_PATH))) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()
    return [attach_portal_links_to_thread(thread_from_row(row)) for row in rows]


async def get_mail_thread(thread_id: str) -> Optional[dict]:
    async with aiosqlite.connect(str(get_runtime_db_path(DEFAULT_DB_PATH))) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT thread_id, account_id, subject, subject_normalized, participants_json,
                   snippet, latest_message_at, latest_folder_kind, unread_count,
                   has_new_inbound, has_pending_draft, is_archived, last_actor,
                   needs_reply, has_draft, mail_kind, reply_level, decision_status,
                   waiting_user_decision, analysis_reason, action_suggestions_json,
                   last_analyzed_at, linked_task_count, linked_note_count,
                   linked_event_count, risk_level, created_at, updated_at
            FROM mail_threads
            WHERE thread_id = ?
            """,
            (thread_id,),
        )
        thread_row = await cursor.fetchone()
        if not thread_row:
            return None

        cursor = await db.execute(
            """
            SELECT message_id, thread_id, account_id, folder_id, remote_message_id,
                   internet_message_id, in_reply_to, references_json, direction, from_name, from_email,
                   to_json, cc_json, bcc_json, reply_to_json, subject, html_body,
                   text_body, quoted_body, sent_at, received_at, is_read,
                   is_starred, is_draft, delivery_status, created_at, updated_at
            FROM mail_messages
            WHERE thread_id = ?
            ORDER BY COALESCE(received_at, sent_at, created_at) ASC, created_at ASC
            """,
            (thread_id,),
        )
        messages = [message_from_row(row) for row in await cursor.fetchall()]

        cursor = await db.execute(
            """
            SELECT attachment_id, message_id, thread_id, account_id, filename, mime_type,
                   size_bytes, content_id, is_inline, created_at, updated_at
            FROM mail_attachments
            WHERE thread_id = ?
            ORDER BY created_at ASC
            """,
            (thread_id,),
        )
        attachment_rows = [attachment_from_row(row) for row in await cursor.fetchall()]
        attachments_by_message: dict[str, list[dict]] = {}
        for attachment in attachment_rows:
            attachments_by_message.setdefault(attachment["message_id"], []).append(attachment)
        for message in messages:
            message["attachments"] = attachments_by_message.get(message["message_id"], [])

        cursor = await db.execute(
            """
            SELECT draft_id, thread_id, account_id, reply_mode, subject, to_json, cc_json,
                   bcc_json, body_html, tone_mode, signature, scheduled_send_at, ai_generated,
                   user_edited_after_ai, status, created_at, updated_at
            FROM mail_drafts
            WHERE thread_id = ?
            ORDER BY updated_at DESC
            """,
            (thread_id,),
        )
        drafts = [draft_from_row(row) for row in await cursor.fetchall()]

        cursor = await db.execute(
            """
            SELECT link_id, thread_id, task_id, created_at, updated_at
            FROM mail_thread_task_links
            WHERE thread_id = ?
            ORDER BY created_at DESC
            """,
            (thread_id,),
        )
        task_links = [dict(row) for row in await cursor.fetchall()]

        cursor = await db.execute(
            """
            SELECT run_id, message_id, thread_id, account_id, action_kind, status,
                   result_summary, detail_json, created_at, updated_at
            FROM mail_agent_runs
            WHERE thread_id = ?
            ORDER BY updated_at DESC, created_at DESC
            LIMIT 12
            """,
            (thread_id,),
        )
        agent_runs = [agent_run_from_row(row) for row in await cursor.fetchall()]

    return {
        "thread": attach_portal_links_to_thread(thread_from_row(thread_row)),
        "messages": messages,
        "drafts": drafts,
        "task_links": task_links,
        "agent_runs": agent_runs,
    }


async def get_mail_dashboard(account_id: Optional[str] = None) -> dict:
    conditions = ["1=1"]
    params: list = []
    if account_id:
        conditions.append("account_id = ?")
        params.append(account_id)
    where = " AND ".join(conditions)
    active_where = f"{where} AND latest_folder_kind != 'archive'"

    async with aiosqlite.connect(str(get_runtime_db_path(DEFAULT_DB_PATH))) as db:
        cursor = await db.execute(f"SELECT COUNT(*) FROM mail_threads WHERE {active_where}", params)
        total_threads = (await cursor.fetchone())[0]

        cursor = await db.execute(f"SELECT COUNT(*) FROM mail_threads WHERE {active_where} AND unread_count > 0", params)
        unread_threads = (await cursor.fetchone())[0]

        cursor = await db.execute(f"SELECT COUNT(*) FROM mail_threads WHERE {active_where} AND needs_reply = 1", params)
        needs_reply_threads = (await cursor.fetchone())[0]

        cursor = await db.execute(f"SELECT COUNT(*) FROM mail_threads WHERE {active_where} AND waiting_user_decision = 1", params)
        waiting_decision_threads = (await cursor.fetchone())[0]

        cursor = await db.execute(
            f"SELECT COUNT(*) FROM mail_drafts WHERE account_id IN (SELECT account_id FROM mail_accounts WHERE {where}) AND status IN ('draft', 'queued')",
            params,
        )
        draft_count = (await cursor.fetchone())[0]

        cursor = await db.execute(
            f"""
            SELECT COUNT(*)
            FROM mail_messages
            WHERE account_id IN (SELECT account_id FROM mail_accounts WHERE {where})
              AND direction = 'inbound'
              AND substr(COALESCE(received_at, created_at), 1, 10) = ?
            """,
            params + [now_iso()[:10]],
        )
        inbound_today = (await cursor.fetchone())[0]

    return {
        "status": "success",
        "summary": {
            "total_threads": total_threads,
            "unread_threads": unread_threads,
            "needs_reply_threads": needs_reply_threads,
            "waiting_decision_threads": waiting_decision_threads,
            "draft_count": draft_count,
            "inbound_today": inbound_today,
        },
    }


async def mark_thread_read(thread_id: str, is_read: bool = True) -> dict:
    async with aiosqlite.connect(str(get_runtime_db_path(DEFAULT_DB_PATH))) as db:
        await db.executescript("PRAGMA foreign_keys = ON;")
        cursor = await db.execute(
            "UPDATE mail_messages SET is_read = ?, updated_at = ? WHERE thread_id = ? AND direction = 'inbound'",
            (1 if is_read else 0, now_iso(), thread_id),
        )
        if cursor.rowcount == 0:
            cursor = await db.execute("SELECT 1 FROM mail_threads WHERE thread_id = ?", (thread_id,))
            if not await cursor.fetchone():
                await db.rollback()
                return {"status": "error", "message": f"线程 {thread_id} 不存在"}
        await refresh_thread_state(db, thread_id)
        await db.commit()
    detail = await get_mail_thread(thread_id)
    return {"status": "success", **detail}


async def move_thread_to_folder(thread_id: str, folder_kind: str) -> dict:
    async with aiosqlite.connect(str(get_runtime_db_path(DEFAULT_DB_PATH))) as db:
        await db.executescript("PRAGMA foreign_keys = ON;")
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT account_id FROM mail_threads WHERE thread_id = ?", (thread_id,))
        thread_row = await cursor.fetchone()
        if not thread_row:
            return {"status": "error", "message": f"线程 {thread_id} 不存在"}
        folder_id = await get_folder_id(db, thread_row["account_id"], folder_kind)
        if not folder_id:
            await ensure_default_folders(db, thread_row["account_id"])
            folder_id = await get_folder_id(db, thread_row["account_id"], folder_kind)
        await db.execute(
            "UPDATE mail_messages SET folder_id = ?, updated_at = ? WHERE thread_id = ?",
            (folder_id, now_iso(), thread_id),
        )
        await refresh_thread_state(db, thread_id)
        await db.commit()
    detail = await get_mail_thread(thread_id)
    return {"status": "success", **detail}


async def set_thread_decision_status(thread_id: str, decision_status: str) -> dict:
    valid_statuses = {"pending", "snoozed", "cleared"}
    if decision_status not in valid_statuses:
        return {"status": "error", "message": f"不支持的决策状态: {decision_status}"}

    waiting_user_decision = 1 if decision_status in {"pending", "snoozed"} else 0
    async with aiosqlite.connect(str(get_runtime_db_path(DEFAULT_DB_PATH))) as db:
        await db.executescript("PRAGMA foreign_keys = ON;")
        cursor = await db.execute(
            """
            UPDATE mail_threads
            SET decision_status = ?, waiting_user_decision = ?, updated_at = ?
            WHERE thread_id = ?
            """,
            (decision_status, waiting_user_decision, now_iso(), thread_id),
        )
        if cursor.rowcount == 0:
            await db.rollback()
            return {"status": "error", "message": f"线程 {thread_id} 不存在"}
        await db.commit()

    detail = await get_mail_thread(thread_id)
    return {"status": "success", **detail}
