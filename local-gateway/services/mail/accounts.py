from __future__ import annotations

import asyncio
import imaplib
import logging
import smtplib
import uuid
from typing import Optional

import aiosqlite

from config import DB_PATH as DEFAULT_DB_PATH
from services.mail.compat import get_runtime_asyncio, get_runtime_db_path, get_runtime_imaplib, get_runtime_smtplib
from services.mail.schema import DEFAULT_FOLDERS
from services.mail.utils import mask_secret, now_iso
from services.notification_service import notification_config

logger = logging.getLogger(__name__)


def _normalize_auto_mail_policy(value: Optional[str]) -> str:
    policy = (value or "").strip().lower()
    if policy in {"draft_only", "draft_and_notify", "auto_send"}:
        return policy
    return "draft_and_notify"


def account_from_row(row: aiosqlite.Row) -> dict:
    data = dict(row)
    data["use_ssl"] = bool(data.get("use_ssl", 1))
    data["sync_enabled"] = bool(data.get("sync_enabled", 1))
    data["smtp_password_masked"] = mask_secret(data.get("smtp_password", ""))
    data["imap_password_masked"] = mask_secret(data.get("imap_password", ""))
    data.pop("smtp_password", None)
    data.pop("imap_password", None)
    return data


async def ensure_default_folders(db: aiosqlite.Connection, account_id: str):
    now = now_iso()
    for kind, remote_name in DEFAULT_FOLDERS.items():
        await db.execute(
            """
            INSERT OR IGNORE INTO mail_folders
            (folder_id, account_id, kind, remote_name, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (f"{account_id}_{kind}", account_id, kind, remote_name, now, now),
        )


async def get_mail_account_raw(account_id: str) -> Optional[dict]:
    async with aiosqlite.connect(str(get_runtime_db_path(DEFAULT_DB_PATH))) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM mail_accounts WHERE account_id = ?", (account_id,))
        row = await cursor.fetchone()
    return dict(row) if row else None


async def get_folder_id(db: aiosqlite.Connection, account_id: str, folder_kind: str) -> Optional[str]:
    cursor = await db.execute(
        "SELECT folder_id FROM mail_folders WHERE account_id = ? AND kind = ?",
        (account_id, folder_kind),
    )
    row = await cursor.fetchone()
    return row[0] if row else None


async def get_folder_row(db: aiosqlite.Connection, account_id: str, folder_kind: str) -> Optional[aiosqlite.Row]:
    db.row_factory = aiosqlite.Row
    cursor = await db.execute(
        """
        SELECT folder_id, account_id, kind, remote_name, sync_token, last_synced_at, created_at, updated_at
        FROM mail_folders
        WHERE account_id = ? AND kind = ?
        """,
        (account_id, folder_kind),
    )
    return await cursor.fetchone()


async def ensure_mail_account_from_notification_config() -> Optional[dict]:
    if not notification_config.smtp_user:
        return None

    account_id = "mail_acc_notify_network"
    now = now_iso()
    imap_host = notification_config.smtp_host.replace("smtp.", "imap.", 1) if notification_config.smtp_host else ""

    async with aiosqlite.connect(str(get_runtime_db_path(DEFAULT_DB_PATH))) as db:
        await db.executescript("PRAGMA foreign_keys = ON;")
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT account_id FROM mail_accounts WHERE account_id = ?", (account_id,))
        existing = await cursor.fetchone()
        if existing:
            await db.execute(
                """
                UPDATE mail_accounts
                SET display_name = ?, email_address = ?, provider_type = ?,
                    smtp_host = ?, smtp_port = ?, smtp_user = ?, smtp_password = ?,
                    use_ssl = ?, sync_enabled = ?, signature_text = ?, tone_mode = ?, updated_at = ?,
                    imap_host = COALESCE(NULLIF(imap_host, ''), ?),
                    imap_port = COALESCE(imap_port, 993),
                    imap_user = COALESCE(NULLIF(imap_user, ''), ?),
                    imap_password = COALESCE(NULLIF(imap_password, ''), ?)
                WHERE account_id = ?
                """,
                (
                    "NOTIFY NETWORK",
                    notification_config.smtp_user,
                    "smtp_imap",
                    notification_config.smtp_host,
                    notification_config.smtp_port,
                    notification_config.smtp_user,
                    notification_config.smtp_password,
                    1,
                    1,
                    "来自 NOTIFY NETWORK 的默认署名",
                    "warm",
                    now,
                    imap_host,
                    notification_config.smtp_user,
                    notification_config.smtp_password,
                    account_id,
                ),
            )
        else:
            await db.execute(
                """
                INSERT INTO mail_accounts (
                    account_id, display_name, email_address, provider_type,
                    smtp_host, smtp_port, smtp_user, smtp_password,
                    imap_host, imap_port, imap_user, imap_password,
                    use_ssl, sync_enabled, signature_text, tone_mode,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    account_id,
                    "NOTIFY NETWORK",
                    notification_config.smtp_user,
                    "smtp_imap",
                    notification_config.smtp_host,
                    notification_config.smtp_port,
                    notification_config.smtp_user,
                    notification_config.smtp_password,
                    imap_host,
                    993,
                    notification_config.smtp_user,
                    notification_config.smtp_password,
                    1,
                    1,
                    "来自 NOTIFY NETWORK 的默认署名",
                    "warm",
                    now,
                    now,
                ),
            )
        await ensure_default_folders(db, account_id)
        await db.commit()

    account = await get_mail_account_raw(account_id)
    return account_from_row(account) if account else None


async def list_mail_accounts() -> list[dict]:
    await ensure_mail_account_from_notification_config()
    async with aiosqlite.connect(str(get_runtime_db_path(DEFAULT_DB_PATH))) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT account_id, display_name, email_address, provider_type,
                   smtp_host, smtp_port, smtp_user, smtp_password,
                   imap_host, imap_port, imap_user, imap_password,
                   use_ssl, sync_enabled, signature_text, tone_mode, auto_mail_policy,
                   created_at, updated_at
            FROM mail_accounts
            ORDER BY updated_at DESC
            """
        )
        rows = await cursor.fetchall()
    return [account_from_row(row) for row in rows]


async def get_mail_account(account_id: str) -> Optional[dict]:
    await ensure_mail_account_from_notification_config()
    async with aiosqlite.connect(str(get_runtime_db_path(DEFAULT_DB_PATH))) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT account_id, display_name, email_address, provider_type,
                   smtp_host, smtp_port, smtp_user, smtp_password,
                   imap_host, imap_port, imap_user, imap_password,
                   use_ssl, sync_enabled, signature_text, tone_mode, auto_mail_policy,
                   created_at, updated_at
            FROM mail_accounts
            WHERE account_id = ?
            """,
            (account_id,),
        )
        row = await cursor.fetchone()
    return account_from_row(row) if row else None


async def create_mail_account(
    display_name: str,
    email_address: str,
    provider_type: str = "smtp_imap",
    smtp_host: str = "",
    smtp_port: int = 465,
    smtp_user: str = "",
    smtp_password: str = "",
    imap_host: str = "",
    imap_port: int = 993,
    imap_user: str = "",
    imap_password: str = "",
    use_ssl: bool = True,
    sync_enabled: bool = True,
    signature_text: str = "",
    tone_mode: str = "warm",
    auto_mail_policy: str = "draft_and_notify",
) -> dict:
    account_id = f"mail_acc_{uuid.uuid4().hex[:12]}"
    now = now_iso()
    auto_mail_policy = _normalize_auto_mail_policy(auto_mail_policy)
    async with aiosqlite.connect(str(get_runtime_db_path(DEFAULT_DB_PATH))) as db:
        await db.executescript("PRAGMA foreign_keys = ON;")
        try:
            await db.execute(
                """
                INSERT INTO mail_accounts (
                    account_id, display_name, email_address, provider_type,
                    smtp_host, smtp_port, smtp_user, smtp_password,
                    imap_host, imap_port, imap_user, imap_password,
                    use_ssl, sync_enabled, signature_text, tone_mode, auto_mail_policy,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    account_id, display_name, email_address, provider_type,
                    smtp_host, smtp_port, smtp_user, smtp_password,
                    imap_host, imap_port, imap_user, imap_password,
                    1 if use_ssl else 0, 1 if sync_enabled else 0,
                    signature_text, tone_mode, auto_mail_policy, now, now,
                ),
            )
        except aiosqlite.IntegrityError:
            return {"status": "error", "message": f"邮箱账户 {email_address} 已存在"}
        await ensure_default_folders(db, account_id)
        await db.commit()
    account = await get_mail_account(account_id)
    return {"status": "success", "account_id": account_id, "account": account}


async def update_mail_account(account_id: str, **kwargs) -> dict:
    current = await get_mail_account_raw(account_id)
    if not current:
        return {"status": "error", "message": f"账户 {account_id} 不存在"}

    updatable_fields = {
        "display_name": kwargs.get("display_name"),
        "email_address": kwargs.get("email_address"),
        "provider_type": kwargs.get("provider_type"),
        "smtp_host": kwargs.get("smtp_host"),
        "smtp_port": kwargs.get("smtp_port"),
        "smtp_user": kwargs.get("smtp_user"),
        "smtp_password": kwargs.get("smtp_password"),
        "imap_host": kwargs.get("imap_host"),
        "imap_port": kwargs.get("imap_port"),
        "imap_user": kwargs.get("imap_user"),
        "imap_password": kwargs.get("imap_password"),
        "use_ssl": kwargs.get("use_ssl"),
        "sync_enabled": kwargs.get("sync_enabled"),
        "signature_text": kwargs.get("signature_text"),
        "tone_mode": kwargs.get("tone_mode"),
        "auto_mail_policy": kwargs.get("auto_mail_policy"),
    }

    updates: list[str] = []
    params: list = []
    for field, value in updatable_fields.items():
        if value is None:
            continue
        if field == "auto_mail_policy":
            value = _normalize_auto_mail_policy(value)
        if field in {"smtp_password", "imap_password"} and value == "":
            continue
        if field in {"use_ssl", "sync_enabled"}:
            value = 1 if bool(value) else 0
        updates.append(f"{field} = ?")
        params.append(value)

    if not updates:
        account = await get_mail_account(account_id)
        return {"status": "success", "account": account, "message": "没有需要更新的字段"}

    updates.append("updated_at = ?")
    params.append(now_iso())
    params.append(account_id)

    async with aiosqlite.connect(str(get_runtime_db_path(DEFAULT_DB_PATH))) as db:
        try:
            await db.execute(
                f"UPDATE mail_accounts SET {', '.join(updates)} WHERE account_id = ?",
                params,
            )
            await ensure_default_folders(db, account_id)
            await db.commit()
        except aiosqlite.IntegrityError:
            return {"status": "error", "message": "邮箱地址已被其他账户占用"}

    account = await get_mail_account(account_id)
    return {"status": "success", "account": account, "message": "邮件账户已更新"}


async def delete_mail_account(account_id: str) -> dict:
    async with aiosqlite.connect(str(get_runtime_db_path(DEFAULT_DB_PATH))) as db:
        cursor = await db.execute("DELETE FROM mail_accounts WHERE account_id = ?", (account_id,))
        await db.commit()
        if cursor.rowcount == 0:
            return {"status": "error", "message": f"账户 {account_id} 不存在"}
    return {"status": "success", "message": "邮件账户已删除"}


async def list_mail_folders(account_id: Optional[str] = None) -> list[dict]:
    query = """
        SELECT folder_id, account_id, kind, remote_name, sync_token,
               last_synced_at, created_at, updated_at
        FROM mail_folders
    """
    params: list = []
    if account_id:
        query += " WHERE account_id = ?"
        params.append(account_id)
    query += " ORDER BY account_id, kind"

    async with aiosqlite.connect(str(get_runtime_db_path(DEFAULT_DB_PATH))) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def test_mail_account_connection(account_id: str) -> dict:
    account = await get_mail_account_raw(account_id)
    if not account:
        return {"status": "error", "message": f"账户 {account_id} 不存在"}

    results = {
        "smtp": {"status": "skipped", "message": "未配置 SMTP"},
        "imap": {"status": "skipped", "message": "未配置 IMAP"},
    }

    def _test_smtp():
        if not (account.get("smtp_host") and account.get("smtp_user") and account.get("smtp_password")):
            return {"status": "skipped", "message": "未配置 SMTP"}
        try:
            runtime_smtplib = get_runtime_smtplib()
            if int(account.get("smtp_port") or 465) == 465:
                server = runtime_smtplib.SMTP_SSL(account["smtp_host"], int(account["smtp_port"]), timeout=20)
            else:
                server = runtime_smtplib.SMTP(account["smtp_host"], int(account["smtp_port"]), timeout=20)
                server.ehlo()
                server.starttls()
                server.ehlo()
            server.login(account["smtp_user"], account["smtp_password"])
            server.quit()
            return {"status": "success", "message": "SMTP 登录成功"}
        except Exception as exc:  # pragma: no cover
            return {"status": "error", "message": str(exc)}

    def _test_imap():
        if not (account.get("imap_host") and account.get("imap_user") and account.get("imap_password")):
            return {"status": "skipped", "message": "未配置 IMAP"}
        try:
            runtime_imaplib = get_runtime_imaplib()
            if account.get("use_ssl", 1):
                client = runtime_imaplib.IMAP4_SSL(account["imap_host"], int(account.get("imap_port") or 993))
            else:
                client = runtime_imaplib.IMAP4(account["imap_host"], int(account.get("imap_port") or 143))
            client.login(account["imap_user"], account["imap_password"])
            client.logout()
            return {"status": "success", "message": "IMAP 登录成功"}
        except Exception as exc:  # pragma: no cover
            return {"status": "error", "message": str(exc)}

    runtime_asyncio = get_runtime_asyncio()
    results["smtp"] = await runtime_asyncio.to_thread(_test_smtp)
    results["imap"] = await runtime_asyncio.to_thread(_test_imap)
    overall = "success" if any(item["status"] == "success" for item in results.values()) else "error"
    return {"status": overall, "results": results}
