"""
移动端专用 API — 为移动 App 提供优化接口
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from application.mobile_actions import (
    get_delta_sync_action,
    get_mobile_dashboard_action,
    get_mobile_settings_action,
    get_pending_operations_action,
    queue_offline_batch_action,
    quick_action_action,
    register_push_token_action,
    test_push_notification_action,
    unregister_push_token_action,
    update_mobile_settings_action,
    voice_create_task_action,
)
from models.sync_models import OfflineOperation

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

# ============================================================
# 仪表盘 API — 移动端首页数据
# ============================================================

@router.get("/dashboard")
async def mobile_dashboard():
    """
    移动端仪表盘 — 聚合今日所需的所有数据
    一次请求获取：今日任务、习惯、番茄钟统计
    """
    return await get_mobile_dashboard_action()


# ============================================================
# 快速操作 API
# ============================================================

@router.post("/quick-action")
async def quick_action(action: QuickAction):
    """快捷操作 — 一键完成任务/开始番茄钟/习惯打卡"""
    return await quick_action_action(action.action_type, action.target_id)


# ============================================================
# 语音快速创建
# ============================================================

@router.post("/voice-task")
async def voice_create_task(audio_data: dict):
    """
    语音创建任务 — 移动端语音输入
    接收 base64 编码的音频，返回识别结果和创建的任务
    """
    return await voice_create_task_action(audio_data.get("audio_base64", ""))


# ============================================================
# 推送通知 (持久化到 SQLite)
# ============================================================

@router.post("/push/register")
async def register_push_token(token: PushToken):
    """注册推送令牌"""
    return await register_push_token_action(token.device_id, token.token, token.platform)


@router.post("/push/unregister")
async def unregister_push_token(device_id: str):
    """注销推送令牌"""
    return await unregister_push_token_action(device_id)


@router.post("/push/test")
async def test_push_notification(device_id: str):
    """发送测试推送通知"""
    return await test_push_notification_action(device_id)


# ============================================================
# 离线同步 API — 移动端专用
# ============================================================

@router.post("/offline/queue-batch")
async def queue_offline_batch(operations: list[OfflineOperation]):
    """
    批量添加离线操作
    移动端在离线时累积的操作，联网后批量提交
    """
    return await queue_offline_batch_action([operation.model_dump() for operation in operations])


@router.get("/offline/pending")
async def get_pending_operations(device_id: str):
    """获取该设备的待同步操作"""
    return await get_pending_operations_action(device_id)


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
    return await get_delta_sync_action(since, tables)


# ============================================================
# 设置同步
# ============================================================

@router.get("/settings")
async def get_mobile_settings():
    """获取移动端设置"""
    return await get_mobile_settings_action()


@router.post("/settings")
async def update_mobile_settings(settings: dict):
    """更新移动端设置"""
    return await update_mobile_settings_action(settings)
