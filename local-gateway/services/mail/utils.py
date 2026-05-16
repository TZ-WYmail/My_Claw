from __future__ import annotations

import hashlib
import hmac
import json
import socket
import uuid
from datetime import datetime
from typing import Optional

from config import ai_config

MAIL_PORTAL_SECRET = "local_mail_portal_secret_v1"


def now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat()


def normalize_subject(subject: str) -> str:
    cleaned = (subject or "").strip()
    lowered = cleaned.lower()
    prefixes = ("re:", "fw:", "fwd:")
    changed = True
    while changed:
        changed = False
        for prefix in prefixes:
            if lowered.startswith(prefix):
                cleaned = cleaned[len(prefix):].strip()
                lowered = cleaned.lower()
                changed = True
    return cleaned or "(no subject)"


def json_dumps(value) -> str:
    return json.dumps(value or [], ensure_ascii=False)


def json_loads(value: Optional[str]) -> list:
    if not value:
        return []
    try:
        loaded = json.loads(value)
        return loaded if isinstance(loaded, list) else []
    except json.JSONDecodeError:
        return []


def mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) < 8:
        return "***"
    return value[:2] + "***" + value[-2:]


def clean_snippet(text: str) -> str:
    compact = " ".join((text or "").replace("\n", " ").split())
    return compact[:180]


def normalize_message_id(value: Optional[str]) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    if raw.startswith("<") and raw.endswith(">"):
        raw = raw[1:-1].strip()
    return raw


def extract_reference_ids(value: Optional[str]) -> list[str]:
    import re

    raw = (value or "").strip()
    if not raw:
        return []
    matched = re.findall(r"<([^>]+)>", raw)
    items = matched or re.split(r"\s+", raw)
    ordered: list[str] = []
    seen: set[str] = set()
    for item in items:
        normalized = normalize_message_id(item)
        if normalized and normalized not in seen:
            seen.add(normalized)
            ordered.append(normalized)
    return ordered


def build_outgoing_message_id(email_address: str) -> str:
    domain = (email_address.split("@", 1)[1].strip() if "@" in (email_address or "") else "") or "local-mail"
    return f"mail-{uuid.uuid4().hex}@{domain}"


def build_mail_portal_token(thread_id: str) -> str:
    digest = hmac.new(
        MAIL_PORTAL_SECRET.encode("utf-8"),
        thread_id.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return digest[:24]


def verify_mail_portal_token(thread_id: str, token: str) -> bool:
    expected = build_mail_portal_token(thread_id)
    return hmac.compare_digest(expected, (token or "").strip())


def detect_lan_ipv4() -> Optional[str]:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        ip = sock.getsockname()[0]
        return ip or None
    except OSError:
        return None
    finally:
        sock.close()


def resolve_mail_gateway_base_url() -> str:
    raw = (ai_config.gateway_base_url or "").strip() or "http://localhost:8900"
    return raw.rstrip("/")


def build_mail_portal_links(thread_id: str) -> dict[str, str]:
    token = build_mail_portal_token(thread_id)
    base_url = resolve_mail_gateway_base_url().rstrip("/")
    return {
        "base_url": base_url,
        "token": token,
        "portal_url": f"{base_url}/api/mail/portal/{thread_id}?token={token}",
        "quick_task_url": f"{base_url}/api/mail/portal/{thread_id}/quick/task?token={token}",
        "quick_snooze_url": f"{base_url}/api/mail/portal/{thread_id}/quick/decision?token={token}&decision_status=snoozed",
        "quick_done_url": f"{base_url}/api/mail/portal/{thread_id}/quick/decision?token={token}&decision_status=cleared",
    }

