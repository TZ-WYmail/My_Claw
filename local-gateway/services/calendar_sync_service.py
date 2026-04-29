"""
日历同步服务 — Google Calendar / Outlook 同步
支持双向同步、事件导入导出
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional

import aiosqlite
import httpx

from config import BASE_DIR, DB_PATH

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
                result = await create_calendar_event(
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
            for event in events:
                start_time = event.get("start", {}).get("dateTime", "")
                end_time = event.get("end", {}).get("dateTime", "")

                result = await create_calendar_event(
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
# 日历事件表 Schema
# ============================================================

_calendar_schema = """
-- 日历事件表（用于非任务类事件）
CREATE TABLE IF NOT EXISTS calendar_events (
    event_id     TEXT PRIMARY KEY,
    title        TEXT NOT NULL,
    description  TEXT,
    start_time   TEXT NOT NULL,
    end_time     TEXT NOT NULL,
    event_type   TEXT DEFAULT 'personal',  -- personal/work/meeting/deadline
    color        TEXT DEFAULT '#3498db',
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


async def init_calendar_db():
    """初始化日历相关表结构"""
    async with aiosqlite.connect(str(DB_PATH)) as db:
        await db.executescript(_calendar_schema)
        await db.commit()


# ============================================================
# 日历事件管理
# ============================================================

async def create_calendar_event(
    title: str,
    start_time: str,
    end_time: str,
    description: str = None,
    event_type: str = "personal",
    color: str = None,
) -> dict:
    """创建日历事件"""
    event_id = f"evt_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"

    # 默认颜色
    if not color:
        color_map = {
            "work": "#e74c3c",
            "meeting": "#9b59b6",
            "deadline": "#e67e22",
            "personal": "#3498db",
        }
        color = color_map.get(event_type, "#3498db")

    async with aiosqlite.connect(str(DB_PATH)) as db:
        await db.execute(
            """INSERT INTO calendar_events (event_id, title, description, start_time, end_time, event_type, color)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (event_id, title, description, start_time, end_time, event_type, color),
        )
        await db.commit()

    return {
        "status": "success",
        "event_id": event_id,
        "title": title,
        "start_time": start_time,
        "end_time": end_time,
    }


async def get_calendar_events(start_date: str, end_date: str) -> list[dict]:
    """获取日期范围内的日历事件"""
    async with aiosqlite.connect(str(DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT event_id, title, description, start_time, end_time, event_type, color
               FROM calendar_events
               WHERE date(start_time) >= date(?) AND date(start_time) <= date(?)
               ORDER BY start_time""",
            (start_date, end_date),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def delete_calendar_event(event_id: str) -> dict:
    """删除日历事件"""
    async with aiosqlite.connect(str(DB_PATH)) as db:
        cursor = await db.execute(
            "DELETE FROM calendar_events WHERE event_id = ?", (event_id,)
        )
        await db.commit()
        if cursor.rowcount == 0:
            return {"status": "error", "message": f"事件 {event_id} 不存在"}
    return {"status": "success", "message": f"事件 {event_id} 已删除"}


async def get_calendar_view(year: int, month: int) -> dict:
    """获取月度日历视图数据"""
    import calendar

    # 获取该月第一天和最后一天
    first_day = datetime(year, month, 1)
    if month == 12:
        last_day = datetime(year + 1, 1, 1) - timedelta(days=1)
    else:
        last_day = datetime(year, month + 1, 1) - timedelta(days=1)

    # 计算日历显示范围（包含前后月的日期）
    cal = calendar.Calendar(firstweekday=0)  # 周一为一周开始
    month_days = cal.monthdayscalendar(year, month)

    start_date = datetime(year, month, 1) - timedelta(days=first_day.weekday())
    end_date = datetime(year, month, last_day.day) + timedelta(days=6 - last_day.weekday())

    # 获取该范围内的所有任务
    async with aiosqlite.connect(str(DB_PATH)) as db:
        db.row_factory = aiosqlite.Row

        # 任务（包括子任务计数）
        cursor = await db.execute(
            """SELECT t.task_id, t.task_name, t.due_time, t.recurrence, t.status, t.priority,
                      COUNT(s.subtask_id) as subtask_count,
                      SUM(CASE WHEN s.status = 'completed' THEN 1 ELSE 0 END) as completed_subtasks
               FROM tasks t
               LEFT JOIN subtasks s ON t.task_id = s.task_id
               WHERE t.status != 'deleted'
                 AND date(t.due_time) >= date(?) AND date(t.due_time) <= date(?)
               GROUP BY t.task_id
               ORDER BY t.due_time""",
            (start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")),
        )
        task_rows = await cursor.fetchall()

        # 批量获取标签，避免 N+1 查询
        from services.tag_service import get_task_tags_batch
        task_ids = [row["task_id"] for row in task_rows]
        tags_map = await get_task_tags_batch(task_ids)

        tasks_by_date = {}
        for row in task_rows:
            task = dict(row)
            due_date = task["due_time"][:10]
            task["tags"] = tags_map.get(task["task_id"], [])

            if due_date not in tasks_by_date:
                tasks_by_date[due_date] = []
            tasks_by_date[due_date].append(task)

        # 日历事件
        cursor = await db.execute(
            """SELECT event_id, title, description, start_time, end_time, event_type, color
               FROM calendar_events
               WHERE date(start_time) >= date(?) AND date(start_time) <= date(?)
               ORDER BY start_time""",
            (start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")),
        )
        event_rows = await cursor.fetchall()
        events_by_date = {}
        for row in event_rows:
            event = dict(row)
            event_date = event["start_time"][:10]
            if event_date not in events_by_date:
                events_by_date[event_date] = []
            events_by_date[event_date].append(event)

        # 每日番茄钟计数
        cursor = await db.execute(
            """SELECT date(start_time) as date, COUNT(*) as count
               FROM pomodoro_sessions
               WHERE status = 'completed'
                 AND date(start_time) >= date(?) AND date(start_time) <= date(?)
               GROUP BY date(start_time)""",
            (start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")),
        )
        pomodoro_counts = {row[0]: row[1] for row in await cursor.fetchall()}

    # 构建日历天数
    days = []
    today_str = datetime.now().strftime("%Y-%m-%d")
    current_date = start_date

    while current_date <= end_date:
        date_str = current_date.strftime("%Y-%m-%d")
        is_current_month = current_date.month == month

        day_data = {
            "date": date_str,
            "weekday": current_date.weekday(),
            "is_today": date_str == today_str,
            "is_current_month": is_current_month,
            "tasks": tasks_by_date.get(date_str, []),
            "events": events_by_date.get(date_str, []),
            "pomodoro_count": pomodoro_counts.get(date_str, 0),
        }
        days.append(day_data)
        current_date += timedelta(days=1)

    return {
        "status": "success",
        "view_type": "month",
        "year": year,
        "month": month,
        "days": days,
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
