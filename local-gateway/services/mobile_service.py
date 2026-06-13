"""
Mobile service.

Compatibility wrapper for legacy mobile dashboard query callers.
"""
from __future__ import annotations

from config import DB_PATH
from services import mobile_query_service


async def get_mobile_dashboard_snapshot() -> dict:
    mobile_query_service.DB_PATH = DB_PATH
    return await mobile_query_service.get_mobile_dashboard_snapshot()
