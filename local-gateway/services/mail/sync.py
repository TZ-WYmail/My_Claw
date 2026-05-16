from __future__ import annotations

import logging
import uuid
from typing import Optional

import aiosqlite

from config import DB_PATH as DEFAULT_DB_PATH
from services.mail.accounts import ensure_default_folders, get_folder_row, get_mail_account_raw
from services.mail.automation import auto_handle_incoming_mail as default_auto_handle_incoming_mail
from services.mail.compat import get_runtime_asyncio, get_runtime_attr, get_runtime_db_path, get_runtime_imaplib
from services.mail.messages import ingest_mail_message as default_ingest_mail_message
from services.mail.parsing import parse_imap_message as default_parse_imap_message
from services.mail.schema import DEFAULT_FOLDERS
from services.mail.threads import get_mail_dashboard, list_mail_threads, refresh_thread_state
from services.mail.utils import now_iso

logger = logging.getLogger(__name__)


def _get_runtime_parser():
    return get_runtime_attr("_parse_imap_message", default_parse_imap_message)


def _get_runtime_ingest_message():
    return get_runtime_attr("ingest_mail_message", default_ingest_mail_message)


def _get_runtime_auto_handler():
    return get_runtime_attr("auto_handle_incoming_mail", default_auto_handle_incoming_mail)


async def create_sync_run(
    db: aiosqlite.Connection,
    account_id: str,
    folder_id: Optional[str],
    folder_kind: str,
) -> str:
    run_id = f"sync_{uuid.uuid4().hex[:12]}"
    current_time = now_iso()
    await db.execute(
        """
        INSERT INTO mail_sync_runs (
            run_id, account_id, folder_id, folder_kind, status, started_at,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (run_id, account_id, folder_id, folder_kind, "running", current_time, current_time, current_time),
    )
    return run_id


async def finish_sync_run(
    db: aiosqlite.Connection,
    run_id: str,
    *,
    status: str,
    fetched_count: int = 0,
    new_count: int = 0,
    latest_uid: Optional[str] = None,
    error_message: str = "",
):
    await db.execute(
        """
        UPDATE mail_sync_runs
        SET status = ?, finished_at = ?, fetched_count = ?, new_count = ?,
            latest_uid = ?, error_message = ?, updated_at = ?
        WHERE run_id = ?
        """,
        (
            status,
            now_iso(),
            fetched_count,
            new_count,
            latest_uid,
            error_message,
            now_iso(),
            run_id,
        ),
    )


async def reanalyze_mail_threads(account_id: Optional[str] = None) -> int:
    refreshed = 0
    async with aiosqlite.connect(str(get_runtime_db_path(DEFAULT_DB_PATH))) as db:
        await db.executescript("PRAGMA foreign_keys = ON;")
        db.row_factory = aiosqlite.Row
        if account_id:
            cursor = await db.execute(
                "SELECT thread_id FROM mail_threads WHERE account_id = ? ORDER BY updated_at DESC",
                (account_id,),
            )
        else:
            cursor = await db.execute("SELECT thread_id FROM mail_threads ORDER BY updated_at DESC")
        rows = await cursor.fetchall()
        for row in rows:
            await refresh_thread_state(db, row["thread_id"])
            refreshed += 1
        await db.commit()
    return refreshed


async def get_mail_sync_status(account_id: str) -> dict:
    async with aiosqlite.connect(str(get_runtime_db_path(DEFAULT_DB_PATH))) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT run_id, account_id, folder_id, folder_kind, status, started_at,
                   finished_at, fetched_count, new_count, latest_uid, error_message,
                   created_at, updated_at
            FROM mail_sync_runs
            WHERE account_id = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (account_id,),
        )
        run = await cursor.fetchone()

        cursor = await db.execute(
            """
            SELECT folder_id, account_id, kind, remote_name, sync_token, last_synced_at, created_at, updated_at
            FROM mail_folders
            WHERE account_id = ?
            ORDER BY updated_at DESC
            """,
            (account_id,),
        )
        folders = [dict(row) for row in await cursor.fetchall()]

    return {
        "status": "success",
        "latest_run": dict(run) if run else None,
        "folders": folders,
    }


async def sync_mail_account(account_id: str, folder_kind: str = "inbox", limit: int = 20) -> dict:
    account = await get_mail_account_raw(account_id)
    if not account:
        return {"status": "error", "message": f"账户 {account_id} 不存在"}
    if not account.get("sync_enabled", 1):
        return {"status": "error", "message": f"账户 {account_id} 未开启同步"}
    if not (account.get("imap_host") and account.get("imap_user") and account.get("imap_password")):
        return {"status": "error", "message": "当前账户缺少 IMAP 配置，无法拉取收件箱"}

    fetched_count = 0
    new_count = 0
    latest_uid: Optional[str] = None
    remote_name = DEFAULT_FOLDERS.get(folder_kind, "INBOX")
    runtime_asyncio = get_runtime_asyncio()
    runtime_imaplib = get_runtime_imaplib()
    runtime_parser = _get_runtime_parser()
    runtime_ingest_message = _get_runtime_ingest_message()
    runtime_auto_handler = _get_runtime_auto_handler()

    async with aiosqlite.connect(str(get_runtime_db_path(DEFAULT_DB_PATH))) as db:
        await db.executescript("PRAGMA foreign_keys = ON;")
        db.row_factory = aiosqlite.Row
        await ensure_default_folders(db, account_id)
        folder = await get_folder_row(db, account_id, folder_kind)
        if not folder:
            await db.rollback()
            return {"status": "error", "message": f"文件夹 {folder_kind} 不存在"}
        remote_name = folder["remote_name"] or remote_name
        run_id = await create_sync_run(db, account_id, folder["folder_id"], folder_kind)
        await db.commit()

    def _sync_imap():
        client = None
        try:
            if account.get("use_ssl", 1):
                client = runtime_imaplib.IMAP4_SSL(account["imap_host"], int(account.get("imap_port") or 993))
            else:
                client = runtime_imaplib.IMAP4(account["imap_host"], int(account.get("imap_port") or 143))
            client.login(account["imap_user"], account["imap_password"])
            status, _ = client.select(f'"{remote_name}"')
            if status != "OK":
                raise RuntimeError(f"无法选择 IMAP 文件夹: {remote_name}")

            status, data = client.uid("search", None, "ALL")
            if status != "OK":
                raise RuntimeError("IMAP 搜索失败")
            all_uids = [uid.decode().strip() for uid in (data[0] or b"").split() if uid.strip()]
            return all_uids, client
        except Exception:
            if client is not None:
                try:
                    client.logout()
                except Exception:
                    pass
            raise

    try:
        all_uids, client = await runtime_asyncio.to_thread(_sync_imap)
        async with aiosqlite.connect(str(get_runtime_db_path(DEFAULT_DB_PATH))) as db:
            db.row_factory = aiosqlite.Row
            folder = await get_folder_row(db, account_id, folder_kind)
            last_uid = (folder["sync_token"] or "").strip() if folder else ""

        uid_values = [uid for uid in all_uids if uid.isdigit()]
        if last_uid.isdigit():
            target_uids = [uid for uid in uid_values if int(uid) > int(last_uid)]
        else:
            target_uids = uid_values[-max(limit, 1):]

        if limit > 0:
            target_uids = target_uids[-limit:]

        for uid in target_uids:
            status, payload = await runtime_asyncio.to_thread(client.uid, "fetch", uid, "(RFC822 FLAGS)")
            if status != "OK" or not payload or not payload[0]:
                continue
            raw_message = payload[0][1]
            if not raw_message:
                continue

            parsed = runtime_parser(raw_message)
            flags_blob = b""
            if isinstance(payload[-1], tuple) and payload[-1]:
                flags_blob = payload[-1][0] or b""
            elif isinstance(payload[0], tuple) and payload[0]:
                flags_blob = payload[0][0] or b""
            is_read = b"\\Seen" in flags_blob
            is_starred = b"\\Flagged" in flags_blob
            fetched_count += 1

            result = await runtime_ingest_message(
                account_id=account_id,
                subject=parsed["subject"],
                text_body=parsed["text_body"],
                html_body=parsed["html_body"],
                direction="inbound",
                folder_kind=folder_kind,
                from_name=parsed["from_name"],
                from_email=parsed["from_email"],
                to=parsed["to"],
                cc=parsed["cc"],
                bcc=parsed["bcc"],
                reply_to=parsed["reply_to"],
                remote_message_id=uid,
                internet_message_id=parsed["internet_message_id"],
                in_reply_to=parsed["in_reply_to"],
                references=parsed["references"],
                sent_at=parsed["sent_at"],
                received_at=parsed["received_at"],
                is_read=is_read,
                is_starred=is_starred,
                delivery_status="received",
            )
            if result.get("message") != "邮件已存在，跳过重复入库":
                new_count += 1
                await runtime_auto_handler(result["thread_id"])
            latest_uid = uid

        await runtime_asyncio.to_thread(client.logout)

        async with aiosqlite.connect(str(get_runtime_db_path(DEFAULT_DB_PATH))) as db:
            await db.executescript("PRAGMA foreign_keys = ON;")
            if latest_uid:
                await db.execute(
                    """
                    UPDATE mail_folders
                    SET sync_token = ?, last_synced_at = ?, updated_at = ?
                    WHERE account_id = ? AND kind = ?
                    """,
                    (latest_uid, now_iso(), now_iso(), account_id, folder_kind),
                )
            else:
                await db.execute(
                    """
                    UPDATE mail_folders
                    SET last_synced_at = ?, updated_at = ?
                    WHERE account_id = ? AND kind = ?
                    """,
                    (now_iso(), now_iso(), account_id, folder_kind),
                )
            await finish_sync_run(
                db,
                run_id,
                status="success",
                fetched_count=fetched_count,
                new_count=new_count,
                latest_uid=latest_uid,
            )
            await db.commit()

        await reanalyze_mail_threads(account_id)

    except Exception as exc:  # pragma: no cover
        logger.exception("IMAP 同步失败: account=%s folder=%s", account_id, folder_kind)
        async with aiosqlite.connect(str(get_runtime_db_path(DEFAULT_DB_PATH))) as db:
            await finish_sync_run(
                db,
                run_id,
                status="error",
                fetched_count=fetched_count,
                new_count=new_count,
                latest_uid=latest_uid,
                error_message=str(exc),
            )
            await db.commit()
        return {"status": "error", "message": str(exc)}

    detail = await get_mail_sync_status(account_id)
    dashboard = await get_mail_dashboard(account_id)
    threads = await list_mail_threads(account_id=account_id, folder=folder_kind)
    return {
        "status": "success",
        "message": f"{folder_kind} 同步完成",
        "fetched_count": fetched_count,
        "new_count": new_count,
        "latest_uid": latest_uid,
        "sync": detail["latest_run"],
        "folders": detail["folders"],
        "summary": dashboard["summary"],
        "threads": threads,
    }
