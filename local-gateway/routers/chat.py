"""
POST /api/chat — AI 对话端点
GET  /api/chat/config — 获取 AI 配置
POST /api/chat/config — 保存 AI 配置（持久化到本地）
POST /api/chat/test — 测试 AI 连接
GET  /api/chat/models — 获取可选模型列表
"""
from fastapi import APIRouter

from config import ai_config, AI_MODEL_OPTIONS
from models.schemas import (
    AIConfigRequest,
    AIConfigResponse,
    AITestResponse,
    ChatRequest,
    ChatResponse,
)
from services.ai_service import chat, clear_conversation, test_connection

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def handle_chat(request: ChatRequest):
    """处理 AI 对话请求"""
    result = await chat(
        user_message=request.message,
        conversation_id=request.conversation_id,
    )
    return ChatResponse(**result)


@router.post("/chat/clear")
async def handle_clear_chat(request: ChatRequest):
    """清除对话历史"""
    clear_conversation(request.conversation_id)
    return {"status": "success", "message": "对话历史已清除"}


@router.get("/chat/config", response_model=AIConfigResponse)
async def get_ai_config():
    """获取当前 AI 配置"""
    return AIConfigResponse(
        status="success",
        config=ai_config.to_dict(),
    )


@router.post("/chat/config", response_model=AIConfigResponse)
async def save_ai_config(request: AIConfigRequest):
    """保存 AI 配置（持久化到本地，无需重启）"""
    if request.api_base:
        ai_config.api_base = request.api_base.rstrip("/")
    if request.api_key:
        ai_config.api_key = request.api_key
    if request.model:
        ai_config.model = request.model

    # 持久化到本地文件
    saved = ai_config.save()

    # 清除对话历史（配置变更后重新开始）
    clear_conversation()

    return AIConfigResponse(
        status="success",
        config=ai_config.to_dict(),
        message="配置已保存到本地并立即生效" if saved else "配置已生效但本地保存失败",
    )


@router.post("/chat/test", response_model=AITestResponse)
async def test_ai_connection(request: AIConfigRequest):
    """测试 AI API 连通性"""
    result = await test_connection(
        api_base=request.api_base or None,
        api_key=request.api_key or None,
        model=request.model or None,
    )
    return AITestResponse(**result)


@router.get("/chat/models")
async def get_models():
    """获取可选模型列表"""
    return {"status": "success", "models": AI_MODEL_OPTIONS}
