"""
双向邮件系统基础服务

第一阶段先落地账户、文件夹、线程、消息、草稿和基础仪表盘。
后续的 IMAP 增量同步、发送队列和 AI 桥接都在这层之上扩展。
"""
from __future__ import annotations

import asyncio
import imaplib
import smtplib

from config import DB_PATH
from services.mail.facade import *  # noqa: F401,F403
from services.mail.parsing import (
    build_mail_action_card,
    extract_mail_command,
    generate_ai_reply_content,
    parse_imap_message,
)
from services.mail.accounts import (
    account_from_row,
    ensure_default_folders,
    get_folder_id,
    get_folder_row,
    get_mail_account_raw,
)
from services.mail.threads import (
    agent_run_from_row,
    attach_portal_links_to_thread,
    create_thread,
    draft_from_row,
    find_existing_thread_id,
    message_from_row,
    refresh_thread_state,
    thread_from_row,
    infer_mail_analysis,
    attachment_from_row,
)
from services.mail.automation import (
    has_agent_run,
    is_user_direct_mail_thread,
    normalize_auto_mail_policy,
    record_agent_run,
)
from services.mail.sync import (
    create_sync_run,
    finish_sync_run,
)
from services.notification_service import notification_config
from services.mail.schema import init_mail_db, ensure_mail_schema_migrations, SCHEMA_SQL
from services.mail.utils import build_outgoing_message_id

_build_outgoing_message_id = build_outgoing_message_id
_generate_ai_reply_content = generate_ai_reply_content
_parse_imap_message = parse_imap_message
_extract_mail_command = extract_mail_command
_build_mail_action_card = build_mail_action_card
_account_from_row = account_from_row
_get_mail_account_raw = get_mail_account_raw
_ensure_default_folders = ensure_default_folders
_get_folder_id = get_folder_id
_get_folder_row = get_folder_row
_thread_from_row = thread_from_row
_message_from_row = message_from_row
_draft_from_row = draft_from_row
_attachment_from_row = attachment_from_row
_agent_run_from_row = agent_run_from_row
_attach_portal_links_to_thread = attach_portal_links_to_thread
_find_existing_thread_id = find_existing_thread_id
_create_thread = create_thread
_refresh_thread_state = refresh_thread_state
_infer_mail_analysis = infer_mail_analysis
_has_agent_run = has_agent_run
_record_agent_run = record_agent_run
_normalize_auto_mail_policy = normalize_auto_mail_policy
_is_user_direct_mail_thread = is_user_direct_mail_thread
_create_sync_run = create_sync_run
_finish_sync_run = finish_sync_run
