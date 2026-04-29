"""
Webhook 路由 — 发送和接收 Webhook
"""
from fastapi import APIRouter, Header, Query, Request

from models.schemas import BaseModel, Field
from services.webhook_service import (
    broadcast_event,
    get_webhook_logs,
    handle_incoming_webhook,
    send_webhook,
    webhook_manager,
)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


class WebhookRegisterRequest(BaseModel):
    url: str = Field(..., description="Webhook URL")
    events: list[str] = Field(..., description="订阅的事件列表")
    secret: str = Field(None, description="签名密钥")
    description: str = Field("", description="描述")


class WebhookTriggerRequest(BaseModel):
    event_type: str = Field(..., description="事件类型")
    payload: dict = Field({}, description="事件数据")


class IncomingWebhookRequest(BaseModel):
    event: str = Field(..., description="事件类型")
    data: dict = Field({}, description="事件数据")


# 管理端点
@router.get("/")
async def list_webhooks():
    """获取所有 Webhook"""
    return webhook_manager.get()


@router.post("/")
async def register_webhook(request: WebhookRegisterRequest):
    """注册 Webhook"""
    return webhook_manager.register(
        url=request.url,
        events=request.events,
        secret=request.secret,
        description=request.description,
    )


@router.get("/{webhook_id}")
async def get_webhook_detail(webhook_id: str):
    """获取 Webhook 详情"""
    return webhook_manager.get(webhook_id)


@router.delete("/{webhook_id}")
async def delete_webhook(webhook_id: str):
    """删除 Webhook"""
    return webhook_manager.unregister(webhook_id)


@router.post("/{webhook_id}/toggle")
async def toggle_webhook(
    webhook_id: str,
    active: bool = Query(..., description="启用/禁用"),
):
    """启用/禁用 Webhook"""
    return webhook_manager.toggle(webhook_id, active)


# 触发端点
@router.post("/{webhook_id}/trigger")
async def trigger_webhook(webhook_id: str, request: WebhookTriggerRequest):
    """手动触发 Webhook"""
    return await send_webhook(webhook_id, request.event_type, request.payload)


@router.post("/broadcast")
async def broadcast_webhook_event(request: WebhookTriggerRequest):
    """广播事件到所有订阅的 Webhook"""
    return await broadcast_event(request.event_type, request.payload)


# 接收端点
@router.post("/incoming/{source}")
async def receive_webhook(
    source: str,
    request: IncomingWebhookRequest,
    x_signature: str = Header(None, alias="X-Signature"),
    x_secret: str = Header(None, alias="X-Secret"),
):
    """
    接收外部 Webhook

    source: 来源标识 (如: notion, github, zapier)
    """
    return await handle_incoming_webhook(
        source=source,
        payload=request.dict(),
        signature=x_signature,
        secret=x_secret,
    )


# 日志端点
@router.get("/logs")
async def get_logs(
    webhook_id: str = Query(None, description="Webhook ID 筛选"),
    limit: int = Query(100, ge=1, le=1000),
):
    """获取 Webhook 日志"""
    return await get_webhook_logs(webhook_id, limit)
