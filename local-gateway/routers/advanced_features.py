"""
高级功能兼容路由。

历史 `/api/advanced/*` 入口保留一段兼容期，但实现不再在此重复维护。
该模块通过复用正式域 router，把 advanced 路径显式降级为 compatibility
alias，而不是继续作为主实现容器。
"""

from fastapi import APIRouter

from routers import calendar, pomodoro, subtasks, tags, task_detail

router = APIRouter(prefix="/advanced", tags=["advanced_compat"])
router.include_router(tags.router)
router.include_router(subtasks.router)
router.include_router(pomodoro.router)
router.include_router(calendar.router)
router.include_router(task_detail.router)
