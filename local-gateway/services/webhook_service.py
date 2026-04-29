"""
Webhook 服务 — 接收和发送 Webhook
支持事件订阅和外部系统集成
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional

import httpx

from config import BASE_DIR
from services import task_service
from services import habit_service

logger = logging.getLogger(__name__)

# Webhook 配置存储
WEBHOOK_CONFIG_FILE = BASE_DIR / "data" / "webhooks.json"
WEBHOOK_LOG_FILE = BASE_DIR / "data" / "webhook_logs.json"


class WebhookManager:
    """Webhook 管理器"""

    def __init__(self):
        self.webhooks = {}  # webhook_id -> config
        self.subscriptions = {}  # event_type -> [webhook_ids]
        self._load()

    def _load(self):
        """加载配置"""
        try:
            if WEBHOOK_CONFIG_FILE.exists():
                with open(WEBHOOK_CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.webhooks = data.get("webhooks", {})
                self.subscriptions = data.get("subscriptions", {})
        except Exception as e:
            logger.warning(f"加载 Webhook 配置失败: {e}")

    def save(self):
        """保存配置"""
        try:
            WEBHOOK_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(WEBHOOK_CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump({
                    "webhooks": self.webhooks,
                    "subscriptions": self.subscriptions,
                }, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"保存 Webhook 配置失败: {e}")
            return False

    def register(
        self,
        url: str,
        events: list[str],
        secret: str = None,
        description: str = "",
        active: bool = True,
    ) -> dict:
        """注册 Webhook"""
        webhook_id = f"wh_{uuid.uuid4().hex[:12]}"

        webhook_config = {
            "id": webhook_id,
            "url": url,
            "events": events,
            "secret": secret,
            "description": description,
            "active": active,
            "created_at": datetime.now().isoformat(),
            "success_count": 0,
            "fail_count": 0,
            "last_triggered": None,
        }

        self.webhooks[webhook_id] = webhook_config

        # 更新订阅映射
        for event in events:
            if event not in self.subscriptions:
                self.subscriptions[event] = []
            if webhook_id not in self.subscriptions[event]:
                self.subscriptions[event].append(webhook_id)

        self.save()

        return {
            "status": "success",
            "webhook_id": webhook_id,
            "config": webhook_config,
        }

    def unregister(self, webhook_id: str) -> dict:
        """注销 Webhook"""
        if webhook_id not in self.webhooks:
            return {"status": "error", "message": f"Webhook {webhook_id} 不存在"}

        webhook = self.webhooks.pop(webhook_id)

        # 清理订阅
        for event in webhook.get("events", []):
            if event in self.subscriptions:
                if webhook_id in self.subscriptions[event]:
                    self.subscriptions[event].remove(webhook_id)

        self.save()

        return {"status": "success", "message": f"Webhook {webhook_id} 已删除"}

    def get(self, webhook_id: str = None) -> dict:
        """获取 Webhook 信息"""
        if webhook_id:
            if webhook_id not in self.webhooks:
                return {"status": "error", "message": f"Webhook {webhook_id} 不存在"}
            return {
                "status": "success",
                "webhook": self.webhooks[webhook_id],
            }

        return {
            "status": "success",
            "webhooks": list(self.webhooks.values()),
            "total": len(self.webhooks),
        }

    def toggle(self, webhook_id: str, active: bool) -> dict:
        """启用/禁用 Webhook"""
        if webhook_id not in self.webhooks:
            return {"status": "error", "message": f"Webhook {webhook_id} 不存在"}

        self.webhooks[webhook_id]["active"] = active
        self.save()

        return {
            "status": "success",
            "message": f"Webhook {webhook_id} 已{'启用' if active else '禁用'}",
        }


# 全局 Webhook 管理器
webhook_manager = WebhookManager()


# ============================================================
# 发送 Webhook
# ============================================================

async def send_webhook(webhook_id: str, event_type: str, payload: dict) -> dict:
    """发送 Webhook 事件"""
    if webhook_id not in webhook_manager.webhooks:
        return {"status": "error", "message": "Webhook 不存在"}

    webhook = webhook_manager.webhooks[webhook_id]

    if not webhook.get("active", True):
        return {"status": "skipped", "message": "Webhook 已禁用"}

    # 构建请求
    headers = {
        "Content-Type": "application/json",
        "X-Webhook-ID": webhook_id,
        "X-Event-Type": event_type,
        "X-Timestamp": datetime.now().isoformat(),
    }

    # 如果有 secret，添加签名
    if webhook.get("secret"):
        signature = _generate_signature(payload, webhook["secret"])
        headers["X-Signature"] = signature

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                webhook["url"],
                headers=headers,
                json={
                    "event": event_type,
                    "timestamp": datetime.now().isoformat(),
                    "data": payload,
                },
            )

            webhook["last_triggered"] = datetime.now().isoformat()

            if resp.status_code < 400:
                webhook["success_count"] = webhook.get("success_count", 0) + 1
                webhook_manager.save()

                # 记录日志
                await _log_webhook(webhook_id, event_type, "success", resp.status_code)

                return {
                    "status": "success",
                    "http_status": resp.status_code,
                }
            else:
                webhook["fail_count"] = webhook.get("fail_count", 0) + 1
                webhook_manager.save()

                await _log_webhook(webhook_id, event_type, "failed", resp.status_code, resp.text[:500])

                return {
                    "status": "failed",
                    "http_status": resp.status_code,
                    "response": resp.text[:500],
                }

    except Exception as e:
        webhook["fail_count"] = webhook.get("fail_count", 0) + 1
        webhook_manager.save()

        await _log_webhook(webhook_id, event_type, "error", 0, str(e))

        return {
            "status": "error",
            "message": str(e),
        }


def _generate_signature(payload: dict, secret: str) -> str:
    """生成 Webhook 签名"""
    payload_str = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    signature = hmac.new(
        secret.encode("utf-8"),
        payload_str.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"sha256={signature}"


async def broadcast_event(event_type: str, payload: dict) -> dict:
    """广播事件到所有订阅的 Webhook"""
    webhook_ids = webhook_manager.subscriptions.get(event_type, [])

    if not webhook_ids:
        return {"status": "success", "sent": 0, "message": "无订阅者"}

    results = []
    for webhook_id in webhook_ids:
        result = await send_webhook(webhook_id, event_type, payload)
        results.append({
            "webhook_id": webhook_id,
            "result": result,
        })

    success_count = sum(1 for r in results if r["result"].get("status") == "success")

    return {
        "status": "success",
        "sent": len(results),
        "success": success_count,
        "failed": len(results) - success_count,
        "results": results,
    }


# ============================================================
# 接收 Webhook
# ============================================================

async def handle_incoming_webhook(
    source: str,
    payload: dict,
    headers: dict = None,
    signature: str = None,
    secret: str = None,
) -> dict:
    """
    处理接收到的 Webhook

    支持的事件:
    - task.create: 创建任务
    - task.complete: 完成任务
    - note.create: 创建笔记
    - habit.checkin: 习惯打卡
    """
    # 验证签名（如果提供了 secret）
    if secret and signature:
        expected_sig = _generate_signature(payload, secret)
        if not hmac.compare_digest(signature, expected_sig):
            return {"status": "error", "message": "签名验证失败"}

    event_type = payload.get("event", "")
    data = payload.get("data", {})

    # 处理不同事件
    if event_type == "task.create":
        result = await task_service.add_task(
            task_name=data.get("task_name", "外部任务"),
            due_time=data.get("due_time", datetime.now().isoformat()),
            description=data.get("description"),
            priority=data.get("priority", 2),
        )

    elif event_type == "task.complete":
        task_id = data.get("task_id")
        if task_id:
            result = await task_service.complete_task(task_id)
        else:
            return {"status": "error", "message": "缺少 task_id"}

    elif event_type == "note.create":
        result = await task_service.create_note(
            title=data.get("title", "外部笔记"),
            content=data.get("content", ""),
            tags=data.get("tags", []),
        )

    elif event_type == "habit.checkin":
        habit_id = data.get("habit_id")
        if habit_id:
            result = await habit_service.checkin_habit(
                habit_id,
                count=data.get("count", 1),
                note=data.get("note", ""),
            )
        else:
            return {"status": "error", "message": "缺少 habit_id"}

    else:
        return {"status": "error", "message": f"未知事件类型: {event_type}"}

    # 记录日志
    await _log_webhook("incoming", event_type, "received", 200, source=source)

    return {
        "status": "success",
        "event": event_type,
        "result": result,
    }


# ============================================================
# 日志管理
# ============================================================

async def _log_webhook(
    webhook_id: str,
    event_type: str,
    status: str,
    http_status: int = 0,
    response: str = None,
    source: str = None,
):
    """记录 Webhook 日志"""
    try:
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "webhook_id": webhook_id,
            "event_type": event_type,
            "status": status,
            "http_status": http_status,
            "response": response,
            "source": source,
        }

        logs = []
        if WEBHOOK_LOG_FILE.exists():
            with open(WEBHOOK_LOG_FILE, "r", encoding="utf-8") as f:
                logs = json.load(f)

        logs.append(log_entry)

        # 只保留最近 1000 条
        logs = logs[-1000:]

        with open(WEBHOOK_LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(logs, f, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"记录 Webhook 日志失败: {e}")


async def get_webhook_logs(webhook_id: str = None, limit: int = 100) -> dict:
    """获取 Webhook 日志"""
    try:
        if not WEBHOOK_LOG_FILE.exists():
            return {"status": "success", "logs": [], "total": 0}

        with open(WEBHOOK_LOG_FILE, "r", encoding="utf-8") as f:
            logs = json.load(f)

        if webhook_id:
            logs = [l for l in logs if l.get("webhook_id") == webhook_id]

        logs = logs[-limit:]

        return {
            "status": "success",
            "logs": logs,
            "total": len(logs),
        }

    except Exception as e:
        return {"status": "error", "message": f"获取日志失败: {e}"}
