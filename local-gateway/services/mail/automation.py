from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Optional

import aiosqlite

from config import DB_PATH as DEFAULT_DB_PATH
from services.mail.accounts import get_mail_account_raw
from services.mail.compat import get_runtime_attr, get_runtime_db_path
from services.mail.drafts import create_mail_draft, send_mail_draft, update_mail_draft
from services.mail.parsing import (
    build_mail_action_card as default_build_mail_action_card,
    extract_mail_command as default_extract_mail_command,
    generate_ai_reply_content as default_generate_ai_reply_content,
)
from services.mail.threads import agent_run_from_row, get_mail_thread, move_thread_to_folder
from services.mail.utils import build_mail_portal_links, now_iso


def _get_runtime_ai_reply_generator():
    return get_runtime_attr("_generate_ai_reply_content", default_generate_ai_reply_content)


def _get_runtime_mail_command_extractor():
    return get_runtime_attr("_extract_mail_command", default_extract_mail_command)


def _get_runtime_mail_action_card_builder():
    return get_runtime_attr("_build_mail_action_card", default_build_mail_action_card)


def normalize_auto_mail_policy(value: Optional[str]) -> str:
    policy = (value or "").strip().lower()
    if policy in {"draft_only", "draft_and_notify", "auto_send"}:
        return policy
    return "draft_and_notify"


def is_user_direct_mail_thread(thread: dict, messages: list[dict], account: dict) -> bool:
    inbound = next((item for item in reversed(messages) if item.get("direction") == "inbound"), None)
    if not inbound:
        return False
    sender = (inbound.get("from_email") or "").strip().lower()
    own = (account.get("email_address") or "").strip().lower()
    if not sender or sender == own:
        return False
    if sender.endswith("@qq.com") or sender.endswith("@gmail.com") or sender.endswith("@outlook.com"):
        return True
    if "no-reply" in sender or "noreply" in sender:
        return False
    subject = (thread.get("subject") or "").lower()
    body = ((inbound.get("text_body") or inbound.get("html_body") or "")).lower()
    conversational_hits = ["请", "能否", "可以吗", "帮我", "安排", "怎么", "是否", "reply", "confirm"]
    return any(token in subject or token in body for token in conversational_hits)


async def has_agent_run(message_id: str, action_kind: str) -> bool:
    async with aiosqlite.connect(str(get_runtime_db_path(DEFAULT_DB_PATH))) as db:
        cursor = await db.execute(
            "SELECT 1 FROM mail_agent_runs WHERE message_id = ? AND action_kind = ? LIMIT 1",
            (message_id, action_kind),
        )
        row = await cursor.fetchone()
    return row is not None


async def record_agent_run(
    message_id: str,
    thread_id: str,
    account_id: str,
    action_kind: str,
    status: str,
    result_summary: str = "",
    details: Optional[dict] = None,
):
    current_time = now_iso()
    async with aiosqlite.connect(str(get_runtime_db_path(DEFAULT_DB_PATH))) as db:
        await db.executescript("PRAGMA foreign_keys = ON;")
        await db.execute(
            """
            INSERT OR REPLACE INTO mail_agent_runs
            (run_id, message_id, thread_id, account_id, action_kind, status, result_summary, detail_json, created_at, updated_at)
            VALUES (
                COALESCE((SELECT run_id FROM mail_agent_runs WHERE message_id = ? AND action_kind = ?), ?),
                ?, ?, ?, ?, ?, ?, ?, COALESCE((SELECT created_at FROM mail_agent_runs WHERE message_id = ? AND action_kind = ?), ?), ?
            )
            """,
            (
                message_id,
                action_kind,
                f"mar_{uuid.uuid4().hex[:12]}",
                message_id,
                thread_id,
                account_id,
                action_kind,
                status,
                result_summary,
                json.dumps(details or {}, ensure_ascii=False),
                message_id,
                action_kind,
                current_time,
                current_time,
            ),
        )
        await db.commit()


async def list_mail_agent_runs(thread_id: str, limit: int = 20) -> list[dict]:
    capped_limit = max(1, min(int(limit or 20), 100))
    async with aiosqlite.connect(str(get_runtime_db_path(DEFAULT_DB_PATH))) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT run_id, message_id, thread_id, account_id, action_kind, status,
                   result_summary, detail_json, created_at, updated_at
            FROM mail_agent_runs
            WHERE thread_id = ?
            ORDER BY updated_at DESC, created_at DESC
            LIMIT ?
            """,
            (thread_id, capped_limit),
        )
        rows = await cursor.fetchall()
    return [agent_run_from_row(row) for row in rows]


def extract_due_time_from_thread(thread: dict, messages: list[dict]) -> Optional[str]:
    search_bodies = [thread.get("subject", ""), thread.get("snippet", "")]
    for message in messages[-3:]:
        search_bodies.append(message.get("text_body") or "")
        search_bodies.append(message.get("html_body") or "")
    combined = "\n".join(search_bodies)

    patterns = [
        r"(20\d{2})[-/年](\d{1,2})[-/月](\d{1,2})",
        r"(\d{1,2})月(\d{1,2})日",
    ]
    current = datetime.now()
    for index, pattern in enumerate(patterns):
        match = __import__("re").search(pattern, combined)
        if not match:
            continue
        if index == 0:
            year, month, day = [int(part) for part in match.groups()]
        else:
            year = current.year
            month, day = [int(part) for part in match.groups()]
        try:
            return datetime(year, month, day, 18, 0, 0).isoformat()
        except ValueError:
            continue
    return None


async def create_task_from_mail_thread(
    thread_id: str,
    task_name: Optional[str] = None,
    due_time: Optional[str] = None,
    description: str = "",
    priority: int = 1,
) -> dict:
    from services import task_service

    detail = await get_mail_thread(thread_id)
    if not detail:
        return {"status": "error", "message": f"线程 {thread_id} 不存在"}

    thread = detail["thread"]
    messages = detail["messages"]
    inferred_due_time = due_time or extract_due_time_from_thread(thread, messages) or (
        datetime.now().replace(hour=18, minute=0, second=0, microsecond=0).isoformat()
    )
    inferred_task_name = (task_name or thread.get("subject") or "邮件跟进").strip()
    if not inferred_task_name.startswith("邮件跟进："):
        inferred_task_name = f"邮件跟进：{inferred_task_name}"

    description_parts = [
        description.strip() if description else "",
        f"来源邮件主题：{thread.get('subject') or '未命名主题'}",
        f"参谋判断：{thread.get('analysis_reason') or '未生成'}",
        f"线程 ID：{thread_id}",
    ]
    task_description = "\n".join(part for part in description_parts if part)

    result = await task_service.add_task(
        task_name=inferred_task_name,
        due_time=inferred_due_time,
        priority=priority,
        description=task_description,
    )
    if result.get("status") != "success":
        return result

    current_time = now_iso()
    async with aiosqlite.connect(str(get_runtime_db_path(DEFAULT_DB_PATH))) as db:
        await db.executescript("PRAGMA foreign_keys = ON;")
        await db.execute(
            """
            INSERT OR IGNORE INTO mail_thread_task_links
            (link_id, thread_id, task_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (f"mtl_{uuid.uuid4().hex[:12]}", thread_id, result["task_id"], current_time, current_time),
        )
        cursor = await db.execute(
            "SELECT COUNT(*) FROM mail_thread_task_links WHERE thread_id = ?",
            (thread_id,),
        )
        linked_task_count = (await cursor.fetchone())[0]
        await db.execute(
            "UPDATE mail_threads SET linked_task_count = ?, updated_at = ? WHERE thread_id = ?",
            (linked_task_count, current_time, thread_id),
        )
        await db.commit()

    updated_detail = await get_mail_thread(thread_id)
    return {
        "status": "success",
        "task_id": result["task_id"],
        "task_name": inferred_task_name,
        "due_time": inferred_due_time,
        "message": result.get("message") or "已从邮件创建任务",
        **updated_detail,
    }


async def generate_reply_draft_for_thread(thread_id: str) -> dict:
    detail = await get_mail_thread(thread_id)
    if not detail:
        return {"status": "error", "message": f"线程 {thread_id} 不存在"}

    thread = detail["thread"]
    messages = detail["messages"]
    account = await get_mail_account_raw(thread["account_id"])
    if not account:
        return {"status": "error", "message": f"账户 {thread['account_id']} 不存在"}

    latest_inbound = next((item for item in reversed(messages) if item.get("direction") == "inbound"), None)
    if not latest_inbound:
        return {"status": "error", "message": "当前线程没有可回复的来信"}

    to_list = []
    if latest_inbound.get("reply_to"):
        to_list = latest_inbound["reply_to"]
    elif latest_inbound.get("from_email"):
        to_list = [{
            "name": latest_inbound.get("from_name") or latest_inbound["from_email"],
            "email": latest_inbound["from_email"],
        }]

    generated = await _get_runtime_ai_reply_generator()(thread, messages, account)
    draft_result = await create_mail_draft(
        account_id=thread["account_id"],
        thread_id=thread_id,
        subject=generated["subject"],
        body_html=generated["body"].replace("\n", "<br>"),
        to=to_list,
        reply_mode="reply",
        tone_mode=account.get("tone_mode") or "warm",
        signature=account.get("signature_text") or "",
        ai_generated=True,
    )
    if draft_result.get("status") != "success":
        return draft_result

    draft_result["draft_source"] = generated["source"]
    draft_result["message"] = "已生成回信草稿"
    return draft_result


async def auto_handle_incoming_mail(thread_id: str) -> dict:
    detail = await get_mail_thread(thread_id)
    if not detail:
        return {"status": "error", "message": f"线程 {thread_id} 不存在"}

    thread = detail["thread"]
    messages = detail["messages"]
    account = await get_mail_account_raw(thread["account_id"])
    if not account:
        return {"status": "error", "message": f"账户 {thread['account_id']} 不存在"}

    inbound = next((item for item in reversed(messages) if item.get("direction") == "inbound"), None)
    if not inbound:
        return {"status": "skipped", "message": "没有新的入站邮件"}

    message_id = inbound["message_id"]
    if await has_agent_run(message_id, "auto_reply"):
        return {"status": "skipped", "message": "该来信已处理过自动回信"}

    if not is_user_direct_mail_thread(thread, messages, account):
        await record_agent_run(
            message_id,
            thread_id,
            thread["account_id"],
            "auto_reply",
            "skipped_non_direct",
            "非用户直接协商邮件",
            details={
                "reason_code": "non_direct_thread",
                "policy": normalize_auto_mail_policy(account.get("auto_mail_policy")),
            },
        )
        return {"status": "skipped", "message": "该来信更像系统/订阅信，不自动回复"}

    policy = normalize_auto_mail_policy(account.get("auto_mail_policy"))
    command = _get_runtime_mail_command_extractor()(inbound.get("text_body") or inbound.get("html_body") or "")
    portal_links = build_mail_portal_links(thread_id)
    portal_url = portal_links["portal_url"]
    quick_task_url = portal_links["quick_task_url"]
    quick_snooze_url = portal_links["quick_snooze_url"]
    quick_done_url = portal_links["quick_done_url"]
    context_line = ""
    if command == "create_task":
        task_result = await create_task_from_mail_thread(thread_id)
        context_line = f"我已经先替你落下一项任务：{task_result.get('task_name', '邮件跟进任务')}。"
    elif command == "draft_reply":
        context_line = "我先替你起了一份回信草稿，等你确认细节后即可寄出。"
    elif command == "archive":
        await move_thread_to_folder(thread_id, "archive")
        context_line = "我已按你的来信，把这条邮件线程收进归档。"

    draft = await generate_reply_draft_for_thread(thread_id)
    if draft.get("status") != "success":
        await record_agent_run(
            message_id,
            thread_id,
            thread["account_id"],
            "auto_reply",
            "failed",
            draft.get("message", "起草失败"),
            details={
                "reason_code": "draft_generation_failed",
                "policy": policy,
                "command": command or "",
            },
        )
        return draft

    latest_draft = (draft.get("drafts") or [None])[0]
    action_card = _get_runtime_mail_action_card_builder()(
        thread,
        portal_url=portal_url,
        quick_task_url=quick_task_url,
        quick_snooze_url=quick_snooze_url,
        quick_done_url=quick_done_url,
    )
    draft_prefix = context_line or "我先把这封来信铺成一张可继续处理的草稿，等你决定是否发出。"
    if latest_draft:
        enhanced_body = (
            f"{draft_prefix}<br><br>"
            f"{latest_draft.get('body_html') or ''}"
            "<br><br><hr><br>"
            f"{action_card}"
        )
        await update_mail_draft(
            latest_draft["draft_id"],
            body_html=enhanced_body,
            user_edited_after_ai=False,
        )

    if policy == "draft_only":
        await record_agent_run(
            message_id,
            thread_id,
            thread["account_id"],
            "auto_reply",
            "draft_created",
            "已生成草稿，等待用户处理",
            details={
                "reason_code": "policy_draft_only",
                "policy": policy,
                "command": command or "",
                "draft_id": (latest_draft or {}).get("draft_id", ""),
            },
        )
        return {
            "status": "success",
            "message": "已生成草稿，等待用户处理",
            "auto_mail_policy": policy,
            **(await get_mail_thread(thread_id)),
        }

    if policy == "draft_and_notify":
        await record_agent_run(
            message_id,
            thread_id,
            thread["account_id"],
            "auto_reply",
            "user_confirmation_required",
            "已生成草稿并等待用户确认",
            details={
                "reason_code": "policy_requires_confirmation",
                "policy": policy,
                "command": command or "",
                "draft_id": (latest_draft or {}).get("draft_id", ""),
            },
        )
        return {
            "status": "success",
            "message": "已生成草稿并等待用户确认",
            "auto_mail_policy": policy,
            **(await get_mail_thread(thread_id)),
        }

    send_result = await send_mail_draft(draft["draft_id"])
    if send_result.get("status") == "success":
        await record_agent_run(
            message_id,
            thread_id,
            thread["account_id"],
            "auto_reply",
            "sent",
            "已自动发送协商回信",
            details={
                "reason_code": "policy_auto_send",
                "policy": policy,
                "command": command or "",
                "draft_id": draft["draft_id"],
            },
        )
        return {"status": "success", "message": "已自动发送邮件回复", "auto_mail_policy": policy, **send_result}

    await record_agent_run(
        message_id,
        thread_id,
        thread["account_id"],
        "auto_reply",
        "failed",
        send_result.get("message", "发送失败"),
        details={
            "reason_code": "send_failed",
            "policy": policy,
            "command": command or "",
            "draft_id": draft["draft_id"],
        },
    )
    return send_result
