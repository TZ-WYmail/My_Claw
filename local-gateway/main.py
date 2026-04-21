"""
LocalCommandCenter 本地网关 — FastAPI 应用入口

启动：python main.py
"""
import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from config import (
    CORS_ORIGINS,
    DEBUG,
    HOST,
    PORT,
    SERVICE_NAME,
    VERSION,
    ensure_dirs,
)
from models.schemas import HealthResponse
from routers import (
    chat as chat_router,
    dashboard,
    file_search,
    job_status,
    safe_downloader,
    sandbox_executor,
    task_manager,
)
from services import task_service

# ============================================================
# 日志配置
# ============================================================

logging.basicConfig(
    level=logging.DEBUG if DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ============================================================
# 应用生命周期
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动和关闭时的操作"""
    logger.info(f"🚀 {SERVICE_NAME} v{VERSION} 启动中...")
    # 确保目录存在
    ensure_dirs()
    # 初始化数据库
    await task_service.init_db()
    logger.info(f"✅ 数据库初始化完成: tasks.db")
    logger.info(f"📡 服务监听: http://{HOST}:{PORT}")
    yield
    logger.info(f"🛑 {SERVICE_NAME} 正在关闭...")


# ============================================================
# FastAPI 应用
# ============================================================

app = FastAPI(
    title=SERVICE_NAME,
    version=VERSION,
    description="本地指挥中心网关 — 接收 GLM 智能体的 Tool Call 请求并操作本地系统",
    lifespan=lifespan,
)

# CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# 注册路由
# ============================================================

app.include_router(task_manager.router, prefix="/api")
app.include_router(safe_downloader.router, prefix="/api")
app.include_router(file_search.router, prefix="/api")
app.include_router(job_status.router, prefix="/api")
app.include_router(sandbox_executor.router, prefix="/api")
app.include_router(chat_router.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")


# ============================================================
# 健康检查
# ============================================================

@app.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(
        status="healthy",
        service=SERVICE_NAME,
        version=VERSION,
    )


# 静态文件
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def root():
    """返回图形化界面"""
    return FileResponse("static/index.html")


@app.get("/api-info")
async def api_info():
    """API 信息（旧根路径功能保留）"""
    return {
        "service": SERVICE_NAME,
        "version": VERSION,
        "docs": f"http://{HOST}:{PORT}/docs",
        "ui": f"http://{HOST}:{PORT}/",
        "endpoints": {
            "task_manager": "/api/task",
            "safe_downloader": "/api/download",
            "file_search": "/api/search",
            "job_status": "/api/job/status",
            "sandbox_executor": "/api/sandbox",
            "health": "/health",
        },
    }


# ============================================================
# 直接运行
# ============================================================

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=HOST,
        port=PORT,
        reload=DEBUG,
        log_level="debug" if DEBUG else "info",
    )
