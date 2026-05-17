from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional

from services.mail.compat import get_runtime_mail_service
from services.mail.schema import MAIL_POLLING_CONFIG_FILE
from services.mail.utils import now_iso

logger = logging.getLogger(__name__)

_mail_polling_state = {
    "enabled": False,
    "interval_seconds": 300,
    "folder_kind": "inbox",
    "limit": 20,
    "last_started_at": "",
    "last_finished_at": "",
    "last_success_at": "",
    "last_error": "",
    "last_summary": {},
    "is_running": False,
}
_mail_polling_task: Optional[asyncio.Task] = None


def load_mail_polling_config():
    try:
        if MAIL_POLLING_CONFIG_FILE.exists():
            with open(MAIL_POLLING_CONFIG_FILE, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            _mail_polling_state["enabled"] = bool(data.get("enabled", False))
            _mail_polling_state["interval_seconds"] = max(60, int(data.get("interval_seconds", 300)))
            _mail_polling_state["folder_kind"] = str(data.get("folder_kind") or "inbox")
            _mail_polling_state["limit"] = max(1, min(int(data.get("limit", 20)), 100))
    except Exception as exc:
        logger.warning("加载邮件轮询配置失败: %s", exc)


def save_mail_polling_config():
    try:
        MAIL_POLLING_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(MAIL_POLLING_CONFIG_FILE, "w", encoding="utf-8") as handle:
            json.dump(
                {
                    "enabled": _mail_polling_state["enabled"],
                    "interval_seconds": _mail_polling_state["interval_seconds"],
                    "folder_kind": _mail_polling_state["folder_kind"],
                    "limit": _mail_polling_state["limit"],
                },
                handle,
                ensure_ascii=False,
                indent=2,
            )
    except Exception as exc:
        logger.error("保存邮件轮询配置失败: %s", exc)


def get_mail_polling_status() -> dict:
    return {
        "enabled": bool(_mail_polling_state["enabled"]),
        "interval_seconds": int(_mail_polling_state["interval_seconds"]),
        "folder_kind": _mail_polling_state["folder_kind"],
        "limit": int(_mail_polling_state["limit"]),
        "is_running": bool(_mail_polling_state["is_running"]),
        "last_started_at": _mail_polling_state["last_started_at"],
        "last_finished_at": _mail_polling_state["last_finished_at"],
        "last_success_at": _mail_polling_state["last_success_at"],
        "last_error": _mail_polling_state["last_error"],
        "last_summary": _mail_polling_state["last_summary"],
    }


async def update_mail_polling_config(
    *,
    enabled: Optional[bool] = None,
    interval_seconds: Optional[int] = None,
    folder_kind: Optional[str] = None,
    limit: Optional[int] = None,
) -> dict:
    global _mail_polling_task

    if enabled is not None:
        _mail_polling_state["enabled"] = bool(enabled)
    if interval_seconds is not None:
        _mail_polling_state["interval_seconds"] = max(60, int(interval_seconds))
    if folder_kind:
        _mail_polling_state["folder_kind"] = str(folder_kind).strip() or "inbox"
    if limit is not None:
        _mail_polling_state["limit"] = max(1, min(int(limit), 100))

    save_mail_polling_config()

    if _mail_polling_state["enabled"]:
        if not _mail_polling_task or _mail_polling_task.done():
            _mail_polling_task = asyncio.create_task(_mail_polling_loop())
    else:
        if _mail_polling_task and not _mail_polling_task.done():
            _mail_polling_task.cancel()
        _mail_polling_state["is_running"] = False

    return {"status": "success", "polling": get_mail_polling_status()}


async def start_mail_polling_scheduler():
    global _mail_polling_task
    load_mail_polling_config()
    if not _mail_polling_state["enabled"]:
        logger.info("邮件轮询未启用")
        return
    if _mail_polling_task and not _mail_polling_task.done():
        return
    _mail_polling_task = asyncio.create_task(_mail_polling_loop())
    logger.info("邮件轮询调度器已启动")


async def stop_mail_polling_scheduler():
    global _mail_polling_task
    if _mail_polling_task and not _mail_polling_task.done():
        _mail_polling_task.cancel()
        try:
            await _mail_polling_task
        except asyncio.CancelledError:
            pass
    _mail_polling_task = None
    _mail_polling_state["is_running"] = False
    logger.info("邮件轮询调度器已停止")


async def run_mail_polling_once() -> dict:
    _mail_polling_state["last_started_at"] = now_iso()
    _mail_polling_state["last_error"] = ""
    _mail_polling_state["is_running"] = True
    summary = {
        "account_count": 0,
        "success_count": 0,
        "skipped_count": 0,
        "error_count": 0,
        "new_count": 0,
        "results": [],
    }
    try:
        mail_service = get_runtime_mail_service()
        accounts = [account for account in await mail_service.list_mail_accounts() if account.get("sync_enabled")]
        summary["account_count"] = len(accounts)
        for account in accounts:
            account_id = account["account_id"]
            try:
                result = await mail_service.sync_mail_account(
                    account_id,
                    folder_kind=_mail_polling_state["folder_kind"],
                    limit=int(_mail_polling_state["limit"]),
                )
                summary["results"].append({
                    "account_id": account_id,
                    "folder_kind": result.get("folder_kind") or _mail_polling_state["folder_kind"],
                    "status": result.get("status"),
                    "message": result.get("message", ""),
                    "fetched_count": int(result.get("fetched_count") or 0),
                    "new_count": int(result.get("new_count") or 0),
                    "latest_uid": result.get("latest_uid") or "",
                    "sync": result.get("sync") or None,
                })
                if result.get("status") == "success":
                    summary["success_count"] += 1
                    summary["new_count"] += int(result.get("new_count") or 0)
                else:
                    summary["error_count"] += 1
            except Exception as exc:
                summary["error_count"] += 1
                summary["results"].append({
                    "account_id": account_id,
                    "folder_kind": _mail_polling_state["folder_kind"],
                    "status": "error",
                    "message": str(exc),
                    "fetched_count": 0,
                    "new_count": 0,
                    "latest_uid": "",
                    "sync": None,
                })
                logger.exception("邮件轮询同步失败: %s", account_id)

        if summary["account_count"] == 0:
            summary["skipped_count"] = 1
    except Exception as exc:
        _mail_polling_state["last_error"] = str(exc)
        logger.exception("邮件轮询执行失败")
        raise
    finally:
        _mail_polling_state["last_finished_at"] = now_iso()
        _mail_polling_state["is_running"] = False

    _mail_polling_state["last_summary"] = summary
    if summary["error_count"] == 0:
        _mail_polling_state["last_success_at"] = _mail_polling_state["last_finished_at"]
    return {"status": "success", "polling": get_mail_polling_status()}


async def _mail_polling_loop():
    while _mail_polling_state["enabled"]:
        try:
            await run_mail_polling_once()
        except asyncio.CancelledError:
            break
        except Exception as exc:
            _mail_polling_state["last_error"] = str(exc)
        await asyncio.sleep(max(60, int(_mail_polling_state["interval_seconds"])))
