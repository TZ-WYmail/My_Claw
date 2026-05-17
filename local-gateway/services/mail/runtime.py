from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional

from services.mail.compat import get_runtime_mail_service
from services.mail.schema import MAIL_POLLING_CONFIG_FILE
from services.mail.utils import now_iso

logger = logging.getLogger(__name__)


class MailPollingRuntime:
    def __init__(self):
        self.state = {
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
        self.task: Optional[asyncio.Task] = None

    def load_config(self):
        try:
            if MAIL_POLLING_CONFIG_FILE.exists():
                with open(MAIL_POLLING_CONFIG_FILE, "r", encoding="utf-8") as handle:
                    data = json.load(handle)
                self.state["enabled"] = bool(data.get("enabled", False))
                self.state["interval_seconds"] = max(60, int(data.get("interval_seconds", 300)))
                self.state["folder_kind"] = str(data.get("folder_kind") or "inbox")
                self.state["limit"] = max(1, min(int(data.get("limit", 20)), 100))
        except Exception as exc:
            logger.warning("加载邮件轮询配置失败: %s", exc)

    def save_config(self):
        try:
            MAIL_POLLING_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(MAIL_POLLING_CONFIG_FILE, "w", encoding="utf-8") as handle:
                json.dump(
                    {
                        "enabled": self.state["enabled"],
                        "interval_seconds": self.state["interval_seconds"],
                        "folder_kind": self.state["folder_kind"],
                        "limit": self.state["limit"],
                    },
                    handle,
                    ensure_ascii=False,
                    indent=2,
                )
        except Exception as exc:
            logger.error("保存邮件轮询配置失败: %s", exc)

    def snapshot(self) -> dict:
        return {
            "enabled": bool(self.state["enabled"]),
            "interval_seconds": int(self.state["interval_seconds"]),
            "folder_kind": self.state["folder_kind"],
            "limit": int(self.state["limit"]),
            "is_running": bool(self.state["is_running"]),
            "last_started_at": self.state["last_started_at"],
            "last_finished_at": self.state["last_finished_at"],
            "last_success_at": self.state["last_success_at"],
            "last_error": self.state["last_error"],
            "last_summary": self.state["last_summary"],
        }

    async def update_config(
        self,
        *,
        enabled: Optional[bool] = None,
        interval_seconds: Optional[int] = None,
        folder_kind: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> dict:
        if enabled is not None:
            self.state["enabled"] = bool(enabled)
        if interval_seconds is not None:
            self.state["interval_seconds"] = max(60, int(interval_seconds))
        if folder_kind:
            self.state["folder_kind"] = str(folder_kind).strip() or "inbox"
        if limit is not None:
            self.state["limit"] = max(1, min(int(limit), 100))

        self.save_config()

        if self.state["enabled"]:
            if not self.task or self.task.done():
                self.task = asyncio.create_task(self._loop())
        else:
            if self.task and not self.task.done():
                self.task.cancel()
            self.state["is_running"] = False

        return {"status": "success", "polling": self.snapshot()}

    async def start_scheduler(self):
        self.load_config()
        if not self.state["enabled"]:
            logger.info("邮件轮询未启用")
            return
        if self.task and not self.task.done():
            return
        self.task = asyncio.create_task(self._loop())
        logger.info("邮件轮询调度器已启动")

    async def stop_scheduler(self):
        if self.task and not self.task.done():
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        self.task = None
        self.state["is_running"] = False
        logger.info("邮件轮询调度器已停止")

    async def run_once(self) -> dict:
        self.state["last_started_at"] = now_iso()
        self.state["last_error"] = ""
        self.state["is_running"] = True
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
                        folder_kind=self.state["folder_kind"],
                        limit=int(self.state["limit"]),
                    )
                    summary["results"].append({
                        "account_id": account_id,
                        "folder_kind": result.get("folder_kind") or self.state["folder_kind"],
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
                        "folder_kind": self.state["folder_kind"],
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
            self.state["last_error"] = str(exc)
            logger.exception("邮件轮询执行失败")
            raise
        finally:
            self.state["last_finished_at"] = now_iso()
            self.state["is_running"] = False

        self.state["last_summary"] = summary
        if summary["error_count"] == 0:
            self.state["last_success_at"] = self.state["last_finished_at"]
        return {"status": "success", "polling": self.snapshot()}

    async def _loop(self):
        while self.state["enabled"]:
            try:
                await self.run_once()
            except asyncio.CancelledError:
                logger.info("邮件轮询循环收到取消信号")
                break
            except Exception as exc:
                self.state["last_error"] = str(exc)
                logger.exception("邮件轮询循环异常")
            await asyncio.sleep(max(60, int(self.state["interval_seconds"])))


mail_polling_runtime = MailPollingRuntime()


def load_mail_polling_config():
    mail_polling_runtime.load_config()


def save_mail_polling_config():
    mail_polling_runtime.save_config()


def get_mail_polling_status() -> dict:
    return mail_polling_runtime.snapshot()


async def update_mail_polling_config(
    *,
    enabled: Optional[bool] = None,
    interval_seconds: Optional[int] = None,
    folder_kind: Optional[str] = None,
    limit: Optional[int] = None,
) -> dict:
    return await mail_polling_runtime.update_config(
        enabled=enabled,
        interval_seconds=interval_seconds,
        folder_kind=folder_kind,
        limit=limit,
    )


async def start_mail_polling_scheduler():
    await mail_polling_runtime.start_scheduler()


async def stop_mail_polling_scheduler():
    await mail_polling_runtime.stop_scheduler()


async def run_mail_polling_once() -> dict:
    return await mail_polling_runtime.run_once()
