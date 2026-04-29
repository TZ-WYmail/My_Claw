"""
日历同步服务 — Google Calendar / Outlook 同步
支持双向同步、事件导入导出
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Optional

import httpx

from config import BASE_DIR

logger = logging.getLogger(__name__)

# 同步配置存储
SYNC_CONFIG_FILE = BASE_DIR / "data" / "calendar_sync.json"


class CalendarSyncConfig:
    """日历同步配置管理"""

    def __init__(self):
        self.google_token = None
        self.google_refresh_token = None
        self.outlook_token = None
        self.outlook_refresh_token = None
        self.sync_enabled = {
            "google": False,
            "outlook": False,
        }
        self.last_sync = {
            "google": None,
            "outlook": None,
        }
        self._load()

    def _load(self):
        """加载配置"""
        try:
            if SYNC_CONFIG_FILE.exists():
                with open(SYNC_CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.google_token = data.get("google_token")
                self.google_refresh_token = data.get("google_refresh_token")
                self.outlook_token = data.get("outlook_token")
                self.outlook_refresh_token = data.get("outlook_refresh_token")
                self.sync_enabled = data.get("sync_enabled", self.sync_enabled)
                self.last_sync = data.get("last_sync", self.last_sync)
        except Exception as e:
            logger.warning(f"加载日历同步配置失败: {e}")

    def save(self):
        """保存配置"""
        try:
            SYNC_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(SYNC_CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump({
                    "google_token": self.google_token,
                    "google_refresh_token": self.google_refresh_token,
                    "outlook_token": self.outlook_token,
                    "outlook_refresh_token": self.outlook_refresh_token,
                    "sync_enabled": self.sync_enabled,
                    "last_sync": self.last_sync,
                }, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"保存日历同步配置失败: {e}")
            return False


# 全局配置实例
sync_config = CalendarSyncConfig()


# ============================================================
# Google Calendar
# ============================================================

GOOGLE_CALENDAR_API = "https://www.googleapis.com/calendar/v3"


async def get_google_auth_url(redirect_uri: str) -> dict:
    """获取 Google OAuth 授权 URL"""
    # 注意：需要配置 Google Cloud Console 获取 client_id
    client_id = "YOUR_GOOGLE_CLIENT_ID"  # 用户需配置

    auth_url = (
        "https://accounts.google.com/o/oauth2/v2/auth"
        f"?client_id={client_id}"
        "&redirect_uri={redirect_uri}"
        "&response_type=code"
        "&scope=https://www.googleapis.com/auth/calendar.readonly"
        "+https://www.googleapis.com/auth/calendar.events"
        "&access_type=offline"
        "&prompt=consent"
    )

    return {
        "status": "success",
        "auth_url": auth_url,
        "instructions": "请访问上述URL授权，然后将返回的code传入 /api/calendar/google/callback",
    }


async def google_oauth_callback(code: str, redirect_uri: str, client_id: str, client_secret: str) -> dict:
    """处理 Google OAuth 回调"""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": code,
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            resp.raise_for_status()
            data = resp.json()

            sync_config.google_token = data.get("access_token")
            sync_config.google_refresh_token = data.get("refresh_token")
            sync_config.sync_enabled["google"] = True
            sync_config.save()

            return {
                "status": "success",
                "message": "Google Calendar 授权成功",
            }

    except Exception as e:
        logger.exception("Google OAuth 失败")
        return {
            "status": "error",
            "message": f"授权失败: {e}",
        }


async def refresh_google_token(client_id: str, client_secret: str) -> bool:
    """刷新 Google access token"""
    if not sync_config.google_refresh_token:
        return False

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "refresh_token": sync_config.google_refresh_token,
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "grant_type": "refresh_token",
                },
            )
            resp.raise_for_status()
            data = resp.json()

            sync_config.google_token = data.get("access_token")
            sync_config.save()
            return True

    except Exception as e:
        logger.error(f"刷新 Google token 失败: {e}")
        return False


async def sync_from_google_calendar(client_id: str = None, client_secret: str = None) -> dict:
    """从 Google Calendar 同步事件到本地"""
    if not sync_config.google_token:
        return {"status": "error", "message": "未授权 Google Calendar"}

    if not sync_config.sync_enabled["google"]:
        return {"status": "error", "message": "Google Calendar 同步未启用"}

    try:
        # 获取时间范围（未来30天）
        time_min = datetime.utcnow().isoformat() + "Z"
        time_max = (datetime.utcnow() + timedelta(days=30)).isoformat() + "Z"

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{GOOGLE_CALENDAR_API}/calendars/primary/events",
                headers={"Authorization": f"Bearer {sync_config.google_token}"},
                params={
                    "timeMin": time_min,
                    "timeMax": time_max,
                    "singleEvents": "true",
                    "orderBy": "startTime",
                },
            )

            if resp.status_code == 401 and client_id and client_secret:
                # Token 过期，尝试刷新
                if await refresh_google_token(client_id, client_secret):
                    # 重试
                    return await sync_from_google_calendar(client_id, client_secret)
                else:
                    return {"status": "error", "message": "Token 已过期，请重新授权"}

            resp.raise_for_status()
            data = resp.json()

            events = data.get("items", [])
            imported = []

            # 导入到本地日历
            from services import task_service

            for event in events:
                start = event.get("start", {})
                end = event.get("end", {})

                # 处理全天事件和定时事件
                if "dateTime" in start:
                    start_time = start["dateTime"]
                    end_time = end["dateTime"]
                else:
                    start_time = start.get("date", "") + "T00:00:00"
                    end_time = end.get("date", "") + "T23:59:59"

                # 创建本地事件
                result = await task_service.create_calendar_event(
                    title=event.get("summary", "无标题"),
                    description=event.get("description", ""),
                    start_time=start_time,
                    end_time=end_time,
                    event_type="external",
                    color="#9b59b6",
                )

                if result.get("status") == "success":
                    imported.append({
                        "external_id": event.get("id"),
                        "local_id": result.get("event_id"),
                        "title": event.get("summary"),
                    })

            sync_config.last_sync["google"] = datetime.now().isoformat()
            sync_config.save()

            return {
                "status": "success",
                "imported_count": len(imported),
                "events": imported,
            }

    except Exception as e:
        logger.exception("同步 Google Calendar 失败")
        return {
            "status": "error",
            "message": f"同步失败: {e}",
        }


# ============================================================
# Outlook Calendar
# ============================================================

OUTLOOK_API = "https://graph.microsoft.com/v1.0"


async def get_outlook_auth_url(redirect_uri: str, client_id: str) -> dict:
    """获取 Outlook OAuth 授权 URL"""
    auth_url = (
        "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
        f"?client_id={client_id}"
        f"&redirect_uri={redirect_uri}"
        "&response_type=code"
        "&scope=Calendars.ReadWrite offline_access"
        "&response_mode=query"
    )

    return {
        "status": "success",
        "auth_url": auth_url,
        "instructions": "请访问上述URL授权，然后将返回的code传入 /api/calendar/outlook/callback",
    }


async def outlook_oauth_callback(code: str, redirect_uri: str, client_id: str, client_secret: str) -> dict:
    """处理 Outlook OAuth 回调"""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://login.microsoftonline.com/common/oauth2/v2.0/token",
                data={
                    "code": code,
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            resp.raise_for_status()
            data = resp.json()

            sync_config.outlook_token = data.get("access_token")
            sync_config.outlook_refresh_token = data.get("refresh_token")
            sync_config.sync_enabled["outlook"] = True
            sync_config.save()

            return {
                "status": "success",
                "message": "Outlook Calendar 授权成功",
            }

    except Exception as e:
        logger.exception("Outlook OAuth 失败")
        return {
            "status": "error",
            "message": f"授权失败: {e}",
        }


async def sync_from_outlook_calendar(client_id: str = None, client_secret: str = None) -> dict:
    """从 Outlook Calendar 同步事件"""
    if not sync_config.outlook_token:
        return {"status": "error", "message": "未授权 Outlook Calendar"}

    if not sync_config.sync_enabled["outlook"]:
        return {"status": "error", "message": "Outlook Calendar 同步未启用"}

    try:
        # 获取未来30天的事件
        start = datetime.utcnow().isoformat()
        end = (datetime.utcnow() + timedelta(days=30)).isoformat()

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{OUTLOOK_API}/me/calendarview",
                headers={"Authorization": f"Bearer {sync_config.outlook_token}"},
                params={
                    "startDateTime": start,
                    "endDateTime": end,
                    "$select": "subject,start,end,body",
                    "$orderby": "start/dateTime",
                },
            )

            if resp.status_code == 401:
                return {"status": "error", "message": "Token 已过期，请重新授权"}

            resp.raise_for_status()
            data = resp.json()

            events = data.get("value", [])
            imported = []

            # 导入到本地
            from services import task_service

            for event in events:
                start_time = event.get("start", {}).get("dateTime", "")
                end_time = event.get("end", {}).get("dateTime", "")

                result = await task_service.create_calendar_event(
                    title=event.get("subject", "无标题"),
                    description=event.get("body", {}).get("content", ""),
                    start_time=start_time,
                    end_time=end_time,
                    event_type="external",
                    color="#3498db",
                )

                if result.get("status") == "success":
                    imported.append({
                        "external_id": event.get("id"),
                        "local_id": result.get("event_id"),
                        "title": event.get("subject"),
                    })

            sync_config.last_sync["outlook"] = datetime.now().isoformat()
            sync_config.save()

            return {
                "status": "success",
                "imported_count": len(imported),
                "events": imported,
            }

    except Exception as e:
        logger.exception("同步 Outlook Calendar 失败")
        return {
            "status": "error",
            "message": f"同步失败: {e}",
        }


# ============================================================
# 同步管理
# ============================================================

async def get_sync_status() -> dict:
    """获取同步状态"""
    return {
        "status": "success",
        "providers": {
            "google": {
                "enabled": sync_config.sync_enabled["google"],
                "authorized": sync_config.google_token is not None,
                "last_sync": sync_config.last_sync["google"],
            },
            "outlook": {
                "enabled": sync_config.sync_enabled["outlook"],
                "authorized": sync_config.outlook_token is not None,
                "last_sync": sync_config.last_sync["outlook"],
            },
        },
    }


async def toggle_sync(provider: str, enabled: bool) -> dict:
    """启用/禁用同步"""
    if provider not in ("google", "outlook"):
        return {"status": "error", "message": f"不支持的提供商: {provider}"}

    sync_config.sync_enabled[provider] = enabled
    sync_config.save()

    return {
        "status": "success",
        "message": f"{provider} 同步已{'启用' if enabled else '禁用'}",
    }


async def disconnect_provider(provider: str) -> dict:
    """断开提供商连接"""
    if provider == "google":
        sync_config.google_token = None
        sync_config.google_refresh_token = None
        sync_config.sync_enabled["google"] = False
        sync_config.last_sync["google"] = None
    elif provider == "outlook":
        sync_config.outlook_token = None
        sync_config.outlook_refresh_token = None
        sync_config.sync_enabled["outlook"] = False
        sync_config.last_sync["outlook"] = None
    else:
        return {"status": "error", "message": f"不支持的提供商: {provider}"}

    sync_config.save()

    return {
        "status": "success",
        "message": f"已断开 {provider} 连接",
    }
