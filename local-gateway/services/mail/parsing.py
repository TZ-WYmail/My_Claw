from __future__ import annotations

import email
import json
import logging
import re
from datetime import timezone
from email.header import decode_header, make_header
from email.utils import getaddresses, parsedate_to_datetime
from typing import Optional

import httpx

from config import ai_config
from services.mail.utils import extract_reference_ids, normalize_message_id

logger = logging.getLogger(__name__)


def decode_mime_header(value: Optional[str]) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return value


def extract_address_list(value: Optional[str]) -> list[dict]:
    if not value:
        return []
    results: list[dict] = []
    for name, address in getaddresses([value]):
        address = (address or "").strip()
        if not address:
            continue
        results.append({
            "name": decode_mime_header(name).strip() or address,
            "email": address,
        })
    return results


def parse_email_datetime(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed.replace(microsecond=0).isoformat()
    except Exception:
        return None


def extract_mail_bodies(message: email.message.Message) -> tuple[str, str]:
    text_parts: list[str] = []
    html_parts: list[str] = []

    if message.is_multipart():
        for part in message.walk():
            if part.is_multipart():
                continue
            disposition = (part.get("Content-Disposition") or "").lower()
            if "attachment" in disposition:
                continue
            content_type = (part.get_content_type() or "").lower()
            charset = part.get_content_charset() or "utf-8"
            try:
                payload = part.get_payload(decode=True)
                body = payload.decode(charset, errors="replace") if payload else ""
            except Exception:
                try:
                    body = part.get_payload(decode=False) or ""
                except Exception:
                    body = ""
            if content_type == "text/plain":
                text_parts.append(body)
            elif content_type == "text/html":
                html_parts.append(body)
    else:
        charset = message.get_content_charset() or "utf-8"
        try:
            payload = message.get_payload(decode=True)
            body = payload.decode(charset, errors="replace") if payload else ""
        except Exception:
            try:
                body = message.get_payload(decode=False) or ""
            except Exception:
                body = ""
        if message.get_content_type() == "text/html":
            html_parts.append(body)
        else:
            text_parts.append(body)

    text_body = "\n\n".join(part.strip() for part in text_parts if part and part.strip())
    html_body = "\n".join(part.strip() for part in html_parts if part and part.strip())
    return text_body, html_body


def extract_mail_attachments(message: email.message.Message) -> list[dict]:
    attachments: list[dict] = []
    part_index = 0

    for part in message.walk():
        if part.is_multipart():
            continue

        disposition = (part.get("Content-Disposition") or "").lower()
        filename = decode_mime_header(part.get_filename()).strip()
        content_id = normalize_message_id(part.get("Content-ID"))
        content_type = (part.get_content_type() or "application/octet-stream").lower()
        is_attachment_like = "attachment" in disposition or "inline" in disposition or bool(filename) or bool(content_id)
        if not is_attachment_like:
            continue

        try:
            payload = part.get_payload(decode=True)
            size_bytes = len(payload or b"")
        except Exception:
            size_bytes = 0

        attachments.append({
            "attachment_id": f"att_part_{part_index}",
            "filename": filename,
            "mime_type": content_type,
            "size_bytes": size_bytes,
            "content_id": content_id,
            "is_inline": ("inline" in disposition) or (content_type.startswith("image/") and bool(content_id)),
        })
        part_index += 1

    return attachments


def parse_imap_message(raw_message: bytes) -> dict:
    message = email.message_from_bytes(raw_message)
    subject = decode_mime_header(message.get("Subject")) or "(no subject)"
    from_list = extract_address_list(message.get("From"))
    to_list = extract_address_list(message.get("To"))
    cc_list = extract_address_list(message.get("Cc"))
    reply_to_list = extract_address_list(message.get("Reply-To"))
    text_body, html_body = extract_mail_bodies(message)
    attachments = extract_mail_attachments(message)
    return {
        "subject": subject,
        "from_name": from_list[0]["name"] if from_list else "",
        "from_email": from_list[0]["email"] if from_list else "",
        "to": to_list,
        "cc": cc_list,
        "bcc": [],
        "reply_to": reply_to_list,
        "text_body": text_body,
        "html_body": html_body,
        "internet_message_id": normalize_message_id(message.get("Message-ID")),
        "in_reply_to": normalize_message_id(message.get("In-Reply-To")),
        "references": extract_reference_ids(message.get("References")),
        "attachments": attachments,
        "sent_at": parse_email_datetime(message.get("Date")),
        "received_at": parse_email_datetime(message.get("Date")),
        "is_read": False,
        "is_starred": False,
    }


def extract_mail_command(body: str) -> Optional[str]:
    if not body:
        return None
    text = re.sub(r"<[^>]+>", " ", body)
    text = re.sub(r"\s+", " ", text).strip()
    patterns = [
        r"(?i)#cmd\s*:\s*([a-z_]+)",
        r"(?i)指令[:：]\s*([a-z_]+)",
    ]
    for pattern in patterns:
        matched = re.search(pattern, text)
        if matched:
            return matched.group(1).strip().lower()
    return None


def build_mail_action_card(thread: dict, portal_url: str, quick_task_url: str, quick_snooze_url: str, quick_done_url: str) -> str:
    mail_kind = thread.get("mail_kind") or "info"
    headline = "这封信已经替你铺开。"
    subcopy = "你可以直接读原信、看我的判断、修改回信，或把它变成下一步。"
    primary_label = "打开这封信的处理页"
    secondary_links = [
        f"<a href=\"{quick_task_url}\">转成任务</a>",
        f"<a href=\"{quick_snooze_url}\">稍后提醒我</a>",
        f"<a href=\"{quick_done_url}\">标记已处理</a>",
    ]

    if mail_kind == "planning":
        headline = "这封信和你的安排有关。"
        subcopy = "我把它整理成一张可在手机上直接处理的小页，你可以先确认安排，再决定是否回信。"
        secondary_links = [
            f"<a href=\"{quick_task_url}\">先落成任务</a>",
            f"<a href=\"{quick_snooze_url}\">今晚再提醒我</a>",
            f"<a href=\"{portal_url}\">查看完整上下文</a>",
        ]
    elif mail_kind == "reply":
        headline = "这封信更像在等你的回声。"
        subcopy = "若你此刻只在邮箱里，也可以直接点开微页面改回信，不必折返完整网页。"
        secondary_links = [
            f"<a href=\"{portal_url}\">直接继续回信</a>",
            f"<a href=\"{quick_snooze_url}\">稍后提醒我</a>",
            f"<a href=\"{quick_done_url}\">这次先处理完</a>",
        ]
    elif mail_kind == "marketing":
        headline = "这封信大概率不值得你耗神。"
        subcopy = "如果你只想顺手清掉它，可以直接归档；若仍想看，我也把原文留在处理页里。"
        secondary_links = [
            f"<a href=\"{portal_url}\">打开处理页</a>",
            f"<a href=\"{quick_done_url}\">标记已处理</a>",
            f"<a href=\"{quick_snooze_url}\">稍后再看</a>",
        ]

    return (
        f"{headline}<br>"
        f"{subcopy}<br><br>"
        f"<a href=\"{portal_url}\">{primary_label}</a><br>"
        + " · ".join(secondary_links)
    )


async def generate_ai_reply_content(thread: dict, messages: list[dict], account: dict) -> dict:
    latest_inbound = next((item for item in reversed(messages) if item.get("direction") == "inbound"), None)
    inbound_body = (
        (latest_inbound or {}).get("text_body")
        or (latest_inbound or {}).get("html_body")
        or thread.get("snippet")
        or ""
    )
    sender = (latest_inbound or {}).get("from_name") or (latest_inbound or {}).get("from_email") or "对方"
    subject = thread.get("subject") or "未命名来信"
    target_subject = subject if subject.lower().startswith("re:") else f"Re: {subject}"

    if not ai_config.api_key:
        body = (
            f"{sender}，你好：\n\n"
            f"我已经看到你关于「{subject}」的来信。\n"
            "我会先确认其中涉及的事项与时间安排，并尽快给你一个明确回复。\n\n"
            "此致\n"
            f"{account.get('display_name') or account.get('email_address')}"
        )
        return {"subject": target_subject, "body": body, "source": "template"}

    prompt = (
        "你是书信参谋。请根据来信内容起草一封中文回复草稿。\n"
        "要求：\n"
        "1. 先判断是否必须回复，但这里无论如何都要输出一份可编辑草稿\n"
        "2. 语气清晰、克制、有人味，不要油腻\n"
        "3. 如邮件涉及安排，请给出明确下一步\n"
        "4. 只输出 JSON，格式为 {\"subject\":\"...\",\"body\":\"...\"}\n\n"
        f"我的身份：{account.get('display_name') or account.get('email_address')}\n"
        f"来信主题：{subject}\n"
        f"来信判断：{thread.get('analysis_reason') or '暂无'}\n"
        f"来信正文摘要：{inbound_body[:4000]}"
    )
    payload = {
        "model": ai_config.model,
        "messages": [
            {"role": "system", "content": "你负责起草邮件回复，只返回 JSON。"},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.6,
    }
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{ai_config.api_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {ai_config.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            return {
                "subject": parsed.get("subject") or target_subject,
                "body": parsed.get("body") or "",
                "source": "ai",
            }
    except Exception as exc:
        logger.warning("AI 回信草稿生成失败，退回模板草稿: %s", exc)
        body = (
            f"{sender}，你好：\n\n"
            f"我已经看到你关于「{subject}」的来信。\n"
            "我会先确认其中涉及的事项与时间安排，并尽快给你一个明确回复。\n\n"
            "此致\n"
            f"{account.get('display_name') or account.get('email_address')}"
        )
        return {"subject": target_subject, "body": body, "source": "template"}

