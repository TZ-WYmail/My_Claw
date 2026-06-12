"""
Sync-related request models shared across sync/mobile entrypoints.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class OfflineOperation(BaseModel):
    operation: str = "unknown"
    table_name: Optional[str] = None
    record_id: Optional[str] = None
    data: Optional[dict] = None
    source: str = "unknown"


class SyncPayload(BaseModel):
    """同步数据包"""
    device_id: str
    timestamp: str
    since: Optional[str] = None
    changes: list[dict] = Field(default_factory=list)


class SyncResponse(BaseModel):
    """同步响应"""
    status: str
    device_id: str
    results: Optional[dict] = None


class DeviceInfo(BaseModel):
    """设备信息"""
    device_id: str
    device_name: Optional[str] = None
    device_type: Optional[str] = None  # mobile/desktop/web
    last_seen: Optional[str] = None
