"""
语音路由 — 语音转文字、语音备忘录
POST /api/voice/upload — 上传语音文件
POST /api/voice/transcribe — 语音识别
POST /api/voice/task — 语音创建任务
GET  /api/voice/memos — 语音备忘录列表
"""
from fastapi import APIRouter, File, Query, UploadFile

from models.schemas import BaseModel, Field
from services.voice_service import (
    create_task_from_voice,
    get_voice_memos,
    save_voice_memo,
    transcribe_audio,
)

router = APIRouter(prefix="/voice", tags=["voice"])


class TranscribeRequest(BaseModel):
    audio_path: str = Field(..., description="音频文件路径")
    provider: str = Field("whisper", description="识别服务: whisper/openai/local")
    language: str = Field("zh", description="语言代码")


class VoiceTaskRequest(BaseModel):
    transcription: str = Field(..., description="语音转文字内容")


@router.post("/upload")
async def upload_voice(
    file: UploadFile = File(...),
    transcribe: bool = False,
):
    """上传语音文件"""
    audio_data = await file.read()
    result = await save_voice_memo(
        audio_data=audio_data,
        filename=file.filename,
        transcribe=transcribe,
    )
    return result


@router.post("/transcribe")
async def voice_transcribe(request: TranscribeRequest):
    """语音识别转文字"""
    result = await transcribe_audio(
        audio_path=request.audio_path,
        provider=request.provider,
        language=request.language,
    )
    return result


@router.post("/task")
async def voice_create_task(request: VoiceTaskRequest):
    """从语音文字创建任务"""
    result = await create_task_from_voice(request.transcription)
    return result


@router.get("/memos")
async def list_voice_memos(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """获取语音备忘录列表"""
    result = await get_voice_memos(page, page_size)
    return result
