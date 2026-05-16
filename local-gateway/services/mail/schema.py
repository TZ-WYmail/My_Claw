from __future__ import annotations

import aiosqlite

from config import BASE_DIR, DB_PATH as DEFAULT_DB_PATH
from services.mail.compat import get_runtime_db_path

DEFAULT_FOLDERS = {
    "inbox": "INBOX",
    "sent": "Sent",
    "drafts": "Drafts",
    "archive": "Archive",
    "trash": "Trash",
}

MAIL_POLLING_CONFIG_FILE = BASE_DIR / "data" / "mail_polling_config.json"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS mail_accounts (
    account_id        TEXT PRIMARY KEY,
    display_name      TEXT NOT NULL,
    email_address     TEXT NOT NULL UNIQUE,
    provider_type     TEXT NOT NULL DEFAULT 'smtp_imap',
    smtp_host         TEXT,
    smtp_port         INTEGER DEFAULT 465,
    smtp_user         TEXT,
    smtp_password     TEXT,
    imap_host         TEXT,
    imap_port         INTEGER DEFAULT 993,
    imap_user         TEXT,
    imap_password     TEXT,
    use_ssl           INTEGER NOT NULL DEFAULT 1,
    sync_enabled      INTEGER NOT NULL DEFAULT 1,
    signature_text    TEXT DEFAULT '',
    tone_mode         TEXT NOT NULL DEFAULT 'warm',
    auto_mail_policy  TEXT NOT NULL DEFAULT 'draft_and_notify',
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS mail_folders (
    folder_id         TEXT PRIMARY KEY,
    account_id        TEXT NOT NULL,
    kind              TEXT NOT NULL,
    remote_name       TEXT NOT NULL,
    sync_token        TEXT,
    last_synced_at    TEXT,
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL,
    UNIQUE(account_id, kind),
    FOREIGN KEY (account_id) REFERENCES mail_accounts(account_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS mail_threads (
    thread_id             TEXT PRIMARY KEY,
    account_id            TEXT NOT NULL,
    subject               TEXT NOT NULL,
    subject_normalized    TEXT NOT NULL,
    participants_json     TEXT NOT NULL DEFAULT '[]',
    snippet               TEXT DEFAULT '',
    latest_message_at     TEXT,
    latest_folder_kind    TEXT DEFAULT 'inbox',
    unread_count          INTEGER NOT NULL DEFAULT 0,
    has_new_inbound       INTEGER NOT NULL DEFAULT 0,
    has_pending_draft     INTEGER NOT NULL DEFAULT 0,
    is_archived           INTEGER NOT NULL DEFAULT 0,
    last_actor            TEXT NOT NULL DEFAULT 'none',
    needs_reply           INTEGER NOT NULL DEFAULT 0,
    has_draft             INTEGER NOT NULL DEFAULT 0,
    mail_kind             TEXT NOT NULL DEFAULT 'info',
    reply_level           TEXT NOT NULL DEFAULT 'none',
    decision_status       TEXT NOT NULL DEFAULT 'pending',
    waiting_user_decision INTEGER NOT NULL DEFAULT 0,
    analysis_reason       TEXT DEFAULT '',
    action_suggestions_json TEXT NOT NULL DEFAULT '[]',
    last_analyzed_at      TEXT,
    linked_task_count     INTEGER NOT NULL DEFAULT 0,
    linked_note_count     INTEGER NOT NULL DEFAULT 0,
    linked_event_count    INTEGER NOT NULL DEFAULT 0,
    risk_level            TEXT NOT NULL DEFAULT 'normal',
    created_at            TEXT NOT NULL,
    updated_at            TEXT NOT NULL,
    FOREIGN KEY (account_id) REFERENCES mail_accounts(account_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS mail_messages (
    message_id            TEXT PRIMARY KEY,
    thread_id             TEXT NOT NULL,
    account_id            TEXT NOT NULL,
    folder_id             TEXT,
    remote_message_id     TEXT,
    internet_message_id   TEXT,
    in_reply_to           TEXT DEFAULT '',
    references_json       TEXT NOT NULL DEFAULT '[]',
    direction             TEXT NOT NULL,
    from_name             TEXT DEFAULT '',
    from_email            TEXT DEFAULT '',
    to_json               TEXT NOT NULL DEFAULT '[]',
    cc_json               TEXT NOT NULL DEFAULT '[]',
    bcc_json              TEXT NOT NULL DEFAULT '[]',
    reply_to_json         TEXT NOT NULL DEFAULT '[]',
    subject               TEXT NOT NULL,
    html_body             TEXT DEFAULT '',
    text_body             TEXT DEFAULT '',
    quoted_body           TEXT DEFAULT '',
    sent_at               TEXT,
    received_at           TEXT,
    is_read               INTEGER NOT NULL DEFAULT 0,
    is_starred            INTEGER NOT NULL DEFAULT 0,
    is_draft              INTEGER NOT NULL DEFAULT 0,
    delivery_status       TEXT NOT NULL DEFAULT 'sent',
    created_at            TEXT NOT NULL,
    updated_at            TEXT NOT NULL,
    FOREIGN KEY (thread_id) REFERENCES mail_threads(thread_id) ON DELETE CASCADE,
    FOREIGN KEY (account_id) REFERENCES mail_accounts(account_id) ON DELETE CASCADE,
    FOREIGN KEY (folder_id) REFERENCES mail_folders(folder_id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS mail_attachments (
    attachment_id         TEXT PRIMARY KEY,
    message_id            TEXT NOT NULL,
    thread_id             TEXT NOT NULL,
    account_id            TEXT NOT NULL,
    filename              TEXT DEFAULT '',
    mime_type             TEXT NOT NULL DEFAULT 'application/octet-stream',
    size_bytes            INTEGER NOT NULL DEFAULT 0,
    content_id            TEXT DEFAULT '',
    is_inline             INTEGER NOT NULL DEFAULT 0,
    created_at            TEXT NOT NULL,
    updated_at            TEXT NOT NULL,
    FOREIGN KEY (message_id) REFERENCES mail_messages(message_id) ON DELETE CASCADE,
    FOREIGN KEY (thread_id) REFERENCES mail_threads(thread_id) ON DELETE CASCADE,
    FOREIGN KEY (account_id) REFERENCES mail_accounts(account_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS mail_drafts (
    draft_id                 TEXT PRIMARY KEY,
    thread_id                TEXT NOT NULL,
    account_id               TEXT NOT NULL,
    reply_mode               TEXT NOT NULL DEFAULT 'new',
    subject                  TEXT NOT NULL,
    to_json                  TEXT NOT NULL DEFAULT '[]',
    cc_json                  TEXT NOT NULL DEFAULT '[]',
    bcc_json                 TEXT NOT NULL DEFAULT '[]',
    body_html                TEXT DEFAULT '',
    tone_mode                TEXT NOT NULL DEFAULT 'warm',
    signature                TEXT DEFAULT '',
    scheduled_send_at        TEXT,
    ai_generated             INTEGER NOT NULL DEFAULT 0,
    user_edited_after_ai     INTEGER NOT NULL DEFAULT 0,
    status                   TEXT NOT NULL DEFAULT 'draft',
    created_at               TEXT NOT NULL,
    updated_at               TEXT NOT NULL,
    FOREIGN KEY (thread_id) REFERENCES mail_threads(thread_id) ON DELETE CASCADE,
    FOREIGN KEY (account_id) REFERENCES mail_accounts(account_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS mail_sync_runs (
    run_id              TEXT PRIMARY KEY,
    account_id          TEXT NOT NULL,
    folder_id           TEXT,
    folder_kind         TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'running',
    started_at          TEXT NOT NULL,
    finished_at         TEXT,
    fetched_count       INTEGER NOT NULL DEFAULT 0,
    new_count           INTEGER NOT NULL DEFAULT 0,
    latest_uid          TEXT,
    error_message       TEXT DEFAULT '',
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL,
    FOREIGN KEY (account_id) REFERENCES mail_accounts(account_id) ON DELETE CASCADE,
    FOREIGN KEY (folder_id) REFERENCES mail_folders(folder_id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS mail_thread_task_links (
    link_id              TEXT PRIMARY KEY,
    thread_id            TEXT NOT NULL,
    task_id              TEXT NOT NULL,
    created_at           TEXT NOT NULL,
    updated_at           TEXT NOT NULL,
    UNIQUE(thread_id, task_id),
    FOREIGN KEY (thread_id) REFERENCES mail_threads(thread_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS mail_agent_runs (
    run_id               TEXT PRIMARY KEY,
    message_id           TEXT NOT NULL,
    thread_id            TEXT NOT NULL,
    account_id           TEXT NOT NULL,
    action_kind          TEXT NOT NULL,
    status               TEXT NOT NULL DEFAULT 'pending',
    result_summary       TEXT DEFAULT '',
    detail_json          TEXT NOT NULL DEFAULT '{}',
    created_at           TEXT NOT NULL,
    updated_at           TEXT NOT NULL,
    UNIQUE(message_id, action_kind)
);
"""


async def ensure_mail_schema_migrations(db: aiosqlite.Connection):
    cursor = await db.execute("PRAGMA table_info(mail_drafts)")
    columns = {row[1] for row in await cursor.fetchall()}
    if "to_json" not in columns:
        await db.execute("ALTER TABLE mail_drafts ADD COLUMN to_json TEXT NOT NULL DEFAULT '[]'")
    if "cc_json" not in columns:
        await db.execute("ALTER TABLE mail_drafts ADD COLUMN cc_json TEXT NOT NULL DEFAULT '[]'")
    if "bcc_json" not in columns:
        await db.execute("ALTER TABLE mail_drafts ADD COLUMN bcc_json TEXT NOT NULL DEFAULT '[]'")

    cursor = await db.execute("PRAGMA table_info(mail_messages)")
    message_columns = {row[1] for row in await cursor.fetchall()}
    if "in_reply_to" not in message_columns:
        await db.execute("ALTER TABLE mail_messages ADD COLUMN in_reply_to TEXT DEFAULT ''")
    if "references_json" not in message_columns:
        await db.execute("ALTER TABLE mail_messages ADD COLUMN references_json TEXT NOT NULL DEFAULT '[]'")

    cursor = await db.execute("PRAGMA table_info(mail_agent_runs)")
    agent_run_columns = {row[1] for row in await cursor.fetchall()}
    if "detail_json" not in agent_run_columns:
        await db.execute("ALTER TABLE mail_agent_runs ADD COLUMN detail_json TEXT NOT NULL DEFAULT '{}'")

    cursor = await db.execute("PRAGMA table_info(mail_accounts)")
    account_columns = {row[1] for row in await cursor.fetchall()}
    if "auto_mail_policy" not in account_columns:
        await db.execute("ALTER TABLE mail_accounts ADD COLUMN auto_mail_policy TEXT NOT NULL DEFAULT 'draft_and_notify'")

    cursor = await db.execute("PRAGMA table_info(mail_threads)")
    thread_columns = {row[1] for row in await cursor.fetchall()}
    thread_additions = {
        "has_new_inbound": "INTEGER NOT NULL DEFAULT 0",
        "has_pending_draft": "INTEGER NOT NULL DEFAULT 0",
        "is_archived": "INTEGER NOT NULL DEFAULT 0",
        "last_actor": "TEXT NOT NULL DEFAULT 'none'",
        "mail_kind": "TEXT NOT NULL DEFAULT 'info'",
        "reply_level": "TEXT NOT NULL DEFAULT 'none'",
        "decision_status": "TEXT NOT NULL DEFAULT 'pending'",
        "waiting_user_decision": "INTEGER NOT NULL DEFAULT 0",
        "analysis_reason": "TEXT DEFAULT ''",
        "action_suggestions_json": "TEXT NOT NULL DEFAULT '[]'",
        "last_analyzed_at": "TEXT",
    }
    for column, ddl in thread_additions.items():
        if column not in thread_columns:
            await db.execute(f"ALTER TABLE mail_threads ADD COLUMN {column} {ddl}")


async def init_mail_db():
    db_path = get_runtime_db_path(DEFAULT_DB_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    from services.mail.runtime import load_mail_polling_config

    load_mail_polling_config()
    async with aiosqlite.connect(str(db_path)) as db:
        await db.executescript("PRAGMA foreign_keys = ON;")
        await db.executescript(SCHEMA_SQL)
        await ensure_mail_schema_migrations(db)
        await db.commit()
