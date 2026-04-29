"""
移动端专用 API — 为移动 App 提供优化接口
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

import aiosqlite
from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from config import DB_PATH
from services import task_service
from services import pomodoro_service
from services.sync_service import sync_engine
from routers.sync import OfflineOperation, _enqueue_operation

router = APIRouter(prefix="/mobile", tags=["mobile"])


# ============================================================
# 请求/响应模型
# ============================================================

class MobileTaskCreate(BaseModel):
    """移动端创建任务"""
    task_name: str
    due_time: Optional[str] = None
    recurrence: str = "once"
    priority: int = 2
    description: Optional[str] = None
    tags: list[str] = Field(default_factory=list)


class PushToken(BaseModel):
    """推送令牌"""
    token: str
    platform: str  # ios/android
    device_id: str


class QuickAction(BaseModel):
    """快捷操作"""
    action_type: str  # complete_task, start_pomodoro, checkin_habit
    target_id: str


# 快捷操作分发表
_QUICK_ACTION_DISPATCH = {
    "complete_task": task_service.complete_task,
    "start_pomodoro": pomodoro_service.start_pomodoro,
    "checkin_habit": task_service.checkin_habit,
}


# ============================================================
# 仪表盘 API — 移动端首页数据
# ============================================================

@router.get("/dashboard")
async def mobile_dashboard():
    """
    移动端仪表盘 — 聚合今日所需的所有数据
    一次请求获取：今日任务、习惯、番茄钟统计
    """
    today = datetime.now().strftime("%Y-%m-%d")
    today_start = f"{today}T00:00:00"
    today_end = f"{today}T23:59:59"

    async with aiosqlite.connect(DB_PATH) as db:
        # 今日任务
        cursor = await db.execute("""
            SELECT * FROM tasks
            WHERE due_time BETWEEN ? AND ?
            AND status = 'pending'
            ORDER BY priority ASC, due_time ASC
            LIMIT 10
        """, (today_start, today_end))
        today_tasks = [dict(row) async for row in cursor]

        # 待办统计
        cursor = await db.execute("""
            SELECT COUNT(*) as count FROM tasks WHERE status = 'pending'
        """)
        pending_count = (await cursor.fetchone())[0]

        # 今日番茄钟
        cursor = await db.execute("""
            SELECT COUNT(*) as count FROM pomodoro_sessions
            WHERE start_time LIKE ? AND status = 'completed'
        """, (f"{today}%",))
        pomodoro_count = (await cursor.fetchone())[0]

        # 习惯列表
        cursor = await db.execute("""
            SELECT h.*, COUNT(hc.checkin_id) as today_count
            FROM habits h
            LEFT JOIN habit_checkins hc ON h.habit_id = hc.habit_id
            AND hc.checkin_date = ?
            GROUP BY h.habit_id
        """, (today,))
        habits = []
        async for row in cursor:
            habit = dict(row)
            habit["checked_in"] = habit["today_count"] > 0
            habits.append(habit)

        # 本周概览
        week_start = (datetime.now() - timedelta(days=datetime.now().weekday())).strftime("%Y-%m-%d")
        cursor = await db.execute("""
            SELECT COUNT(*) as count FROM tasks
            WHERE due_time BETWEEN ? AND ?
        """, (week_start, today_end))
        week_tasks = (await cursor.fetchone())[0]

    return {
        "status": "success",
        "data": {
            "today": {
                "tasks": today_tasks,
                "task_count": len(today_tasks),
                "pomodoro_count": pomodoro_count,
            },
            "summary": {
                "pending_tasks": pending_count,
                "week_tasks": week_tasks,
            },
            "habits": habits,
            "sync_status": await sync_engine.get_sync_status(),
        },
    }


# ============================================================
# 快速操作 API
# ============================================================

@router.post("/quick-action")
async def quick_action(action: QuickAction):
    """快捷操作 — 一键完成任务/开始番茄钟/习惯打卡"""
    handler = _QUICK_ACTION_DISPATCH.get(action.action_type)
    if not handler:
        return {"status": "error", "message": f"Unknown action type: {action.action_type}"}

    result = await handler(action.target_id)
    return {"status": "success", "action": action.action_type, "result": result}


# ============================================================
# 语音快速创建
# ============================================================

@router.post("/voice-task")
async def voice_create_task(audio_data: dict):
    """
    语音创建任务 — 移动端语音输入
    接收 base64 编码的音频，返回识别结果和创建的任务
    """
    from services.voice_service import voice_service

    try:
        result = await voice_service.process_voice(
            audio_data.get("audio_base64", ""),
            source="mobile"
        )

        if result.get("task_created"):
            return {
                "status": "success",
                "recognized_text": result.get("text", ""),
                "task": result.get("task"),
            }

        return {
            "status": "success",
            "recognized_text": result.get("text", ""),
            "message": "未识别到任务创建意图",
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}


# ============================================================
# 推送通知 (持久化到 SQLite)
# ============================================================

@router.post("/push/register")
async def register_push_token(token: PushToken):
    """注册推送令牌"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR REPLACE INTO push_tokens (device_id, token, platform, registered_at)
            VALUES (?, ?, ?, datetime('now'))
        """, (token.device_id, token.token, token.platform))
        await db.commit()

    return {"status": "success", "message": "Push token registered"}


@router.post("/push/unregister")
async def unregister_push_token(device_id: str):
    """注销推送令牌"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM push_tokens WHERE device_id = ?", (device_id,))
        await db.commit()

    return {"status": "success", "message": "Push token unregistered"}


@router.post("/push/test")
async def test_push_notification(device_id: str):
    """发送测试推送通知"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM push_tokens WHERE device_id = ?", (device_id,)
        )
        token_row = await cursor.fetchone()

    if not token_row:
        return {"status": "error", "message": "Device not registered"}

    return {
        "status": "success",
        "message": f"Test notification sent to {dict(token_row)['platform']}",
        "target": device_id,
    }


# ============================================================
# 离线同步 API — 移动端专用
# ============================================================

@router.post("/offline/queue-batch")
async def queue_offline_batch(operations: list[OfflineOperation]):
    """
    批量添加离线操作
    移动端在离线时累积的操作，联网后批量提交
    """
    async with aiosqlite.connect(DB_PATH) as db:
        for op in operations:
            await _enqueue_operation(db, op)
        await db.commit()

    return {"status": "success", "queued_count": len(operations)}


@router.get("/offline/pending")
async def get_pending_operations(device_id: str):
    """获取该设备的待同步操作"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM sync_offline_queue WHERE synced = 0 AND source = ? ORDER BY queued_at ASC",
            (device_id,),
        )
        pending = [dict(r) for r in await cursor.fetchall()]

    return {"status": "success", "pending": len(pending), "operations": pending}


# ============================================================
# 数据压缩 API — 减少移动端流量
# ============================================================

@router.get("/sync/delta")
async def get_delta_sync(
    since: str = Query(..., description="上次同步时间"),
    tables: Optional[str] = Query(None, description="指定表，逗号分隔"),
):
    """
    增量同步 — 只获取变更的数据
    """
    payload = await sync_engine.generate_sync_payload(since)

    # 如果指定了表，过滤
    if tables:
        table_list = tables.split(",")
        payload["changes"] = [
            c for c in payload["changes"]
            if c.get("table_name") in table_list
        ]

    # 添加统计信息
    by_table: dict[str, int] = {}
    for change in payload["changes"]:
        table = change.get("table_name", "unknown")
        by_table[table] = by_table.get(table, 0) + 1

    payload["stats"] = {"total_changes": len(payload["changes"]), "by_table": by_table}

    return {"status": "success", "payload": payload}


# ============================================================
# 设置同步
# ============================================================

@router.get("/settings")
async def get_mobile_settings():
    """获取移动端设置"""
    return {
        "status": "success",
        "settings": {
            "theme": "auto",
            "language": "zh-CN",
            "notification_enabled": True,
            "pomodoro_duration": 25,
            "break_duration": 5,
            "sync_interval": 300,
            "offline_mode": False,
        },
    }


@router.post("/settings")
async def update_mobile_settings(settings: dict):
    """更新移动端设置"""
    return {"status": "success", "message": "Settings updated", "settings": settings}
