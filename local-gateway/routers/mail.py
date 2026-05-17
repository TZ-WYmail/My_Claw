"""
双向邮件系统聚合路由
"""
from fastapi import APIRouter

from routers.mail_api import router as mail_api_router
from routers.mail_portal import router as mail_portal_router

router = APIRouter(prefix="/mail", tags=["mail"])
router.include_router(mail_api_router)
router.include_router(mail_portal_router)
