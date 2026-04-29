"""
日历同步路由 — Google/Outlook 日历集成
"""
from fastapi import APIRouter, Query

from models.schemas import BaseModel, Field
from services.calendar_sync_service import (
    disconnect_provider,
    get_google_auth_url,
    get_outlook_auth_url,
    get_sync_status,
    google_oauth_callback,
    outlook_oauth_callback,
    sync_from_google_calendar,
    sync_from_outlook_calendar,
    toggle_sync,
)

router = APIRouter(prefix="/calendar/sync", tags=["calendar_sync"])


class GoogleCallbackRequest(BaseModel):
    code: str = Field(..., description="授权码")
    redirect_uri: str = Field(..., description="回调URL")
    client_id: str = Field(..., description="Google Client ID")
    client_secret: str = Field(..., description="Google Client Secret")


class OutlookCallbackRequest(BaseModel):
    code: str = Field(..., description="授权码")
    redirect_uri: str = Field(..., description="回调URL")
    client_id: str = Field(..., description="Azure Client ID")
    client_secret: str = Field(..., description="Azure Client Secret")


@router.get("/status")
async def calendar_sync_status():
    """获取日历同步状态"""
    return await get_sync_status()


# Google Calendar
@router.get("/google/auth")
async def google_auth_url(redirect_uri: str = Query(..., description="回调URL")):
    """获取 Google 授权 URL"""
    return await get_google_auth_url(redirect_uri)


@router.post("/google/callback")
async def google_callback(request: GoogleCallbackRequest):
    """Google OAuth 回调"""
    return await google_oauth_callback(
        request.code,
        request.redirect_uri,
        request.client_id,
        request.client_secret,
    )


@router.post("/google/sync")
async def sync_google(
    client_id: str = Query(None, description="Google Client ID (可选)"),
    client_secret: str = Query(None, description="Google Client Secret (可选)"),
):
    """从 Google Calendar 同步事件"""
    return await sync_from_google_calendar(client_id, client_secret)


# Outlook Calendar
@router.get("/outlook/auth")
async def outlook_auth_url(
    redirect_uri: str = Query(..., description="回调URL"),
    client_id: str = Query(..., description="Azure Client ID"),
):
    """获取 Outlook 授权 URL"""
    return await get_outlook_auth_url(redirect_uri, client_id)


@router.post("/outlook/callback")
async def outlook_callback(request: OutlookCallbackRequest):
    """Outlook OAuth 回调"""
    return await outlook_oauth_callback(
        request.code,
        request.redirect_uri,
        request.client_id,
        request.client_secret,
    )


@router.post("/outlook/sync")
async def sync_outlook(
    client_id: str = Query(None, description="Azure Client ID (可选)"),
    client_secret: str = Query(None, description="Azure Client Secret (可选)"),
):
    """从 Outlook Calendar 同步事件"""
    return await sync_from_outlook_calendar(client_id, client_secret)


# 通用管理
@router.post("/{provider}/toggle")
async def toggle_calendar_sync(
    provider: str,
    enabled: bool = Query(..., description="启用/禁用"),
):
    """启用/禁用同步"""
    return await toggle_sync(provider, enabled)


@router.post("/{provider}/disconnect")
async def disconnect_calendar(provider: str):
    """断开日历连接"""
    return await disconnect_provider(provider)
