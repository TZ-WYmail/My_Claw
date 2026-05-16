"""
POST /api/chat — AI 对话端点
POST /api/chat/stream — AI 流式对话端点 (SSE)
GET  /api/chat/config — 获取 AI 配置
POST /api/chat/config — 保存 AI 配置（持久化到本地）
POST /api/chat/test — 测试 AI 连接
GET  /api/chat/models — 获取可选模型列表
"""
import uuid

from fastapi import APIRouter
from starlette.responses import StreamingResponse

from config import ai_config, AI_MODEL_OPTIONS
from models.schemas import (
    AIConfigRequest,
    AIConfigResponse,
    AITestResponse,
    ChatRequest,
    ChatResponse,
)
from services.ai_service import (
    chat,
    chat_stream,
    clear_conversation,
    delete_conversation_data,
    _list_all_conversations,
    _save_conversation_meta,
    test_connection,
)

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def handle_chat(request: ChatRequest):
    """处理 AI 对话请求"""
    result = await chat(
        user_message=request.message,
        conversation_id=request.conversation_id,
    )
    return ChatResponse(**result)


@router.post("/chat/stream")
async def handle_chat_stream(request: ChatRequest):
    """流式 AI 对话 — 返回 SSE 事件流"""
    return StreamingResponse(
        chat_stream(
            user_message=request.message,
            conversation_id=request.conversation_id,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


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
    if request.gateway_base_url:
        ai_config.gateway_base_url = request.gateway_base_url.rstrip("/")

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


@router.get("/chat/history/{conversation_id}")
async def get_chat_history(conversation_id: str):
    """获取对话历史记录"""
    from config import BASE_DIR
    import json

    conv_file = BASE_DIR / "data" / "conversations" / f"{conversation_id}.jsonl"
    if not conv_file.exists():
        return {"status": "success", "messages": []}

    messages = []
    with open(conv_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    messages.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    return {"status": "success", "messages": messages}


@router.get("/chat/conversations")
async def list_conversations():
    """列出所有对话"""
    conversations = _list_all_conversations()
    return {"status": "success", "conversations": conversations}


@router.post("/chat/conversations")
async def create_conversation():
    """创建新对话"""
    conversation_id = str(uuid.uuid4())[:8]
    _save_conversation_meta(conversation_id)
    return {"status": "success", "conversation_id": conversation_id}


@router.delete("/chat/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """删除对话"""
    return delete_conversation_data(conversation_id)
