"""
语音服务 — 语音转文字、语音备忘录
支持多种语音识别提供商
"""
from __future__ import annotations

import base64
import logging
import tempfile
from pathlib import Path
from typing import Optional

from config import BASE_DIR
from services.security_service import sanitize_filename

logger = logging.getLogger(__name__)

# 语音文件存储目录
VOICE_DIR = BASE_DIR / "data" / "voice"
VOICE_DIR.mkdir(parents=True, exist_ok=True)


async def save_voice_memo(
    audio_data: bytes,
    filename: str = None,
    transcribe: bool = False,
) -> dict:
    """
    保存语音备忘录

    Args:
        audio_data: 音频文件二进制数据
        filename: 文件名（可选）
        transcribe: 是否同时进行语音识别
    """
    import uuid
    from datetime import datetime

    if not filename:
        filename = f"memo_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.webm"

    # 净化文件名，防止路径遍历
    safe_filename = sanitize_filename(filename, default=f"memo_{uuid.uuid4().hex[:8]}.webm")
    file_path = VOICE_DIR / safe_filename

    try:
        with open(file_path, "wb") as f:
            f.write(audio_data)

        result = {
            "status": "success",
            "file_path": str(file_path),
            "filename": filename,
            "size_bytes": len(audio_data),
        }

        # 如果需要语音识别
        if transcribe:
            transcription = await transcribe_audio(str(file_path))
            result["transcription"] = transcription

        return result

    except Exception as e:
        logger.exception("保存语音备忘录失败")
        return {
            "status": "error",
            "message": f"保存失败: {e}",
        }


async def transcribe_audio(
    audio_path: str,
    provider: str = "whisper",
    language: str = "zh",
) -> dict:
    """
    语音转文字

    Args:
        audio_path: 音频文件路径
        provider: 识别服务提供商 (whisper/openai/local)
        language: 语言代码
    """
    try:
        if provider == "whisper":
            return await _transcribe_with_whisper(audio_path, language)
        elif provider == "openai":
            return await _transcribe_with_openai(audio_path, language)
        else:
            return await _transcribe_local(audio_path, language)
    except Exception as e:
        logger.exception("语音识别失败")
        return {
            "status": "error",
            "message": f"识别失败: {e}",
        }


async def _transcribe_with_whisper(audio_path: str, language: str) -> dict:
    """使用 Whisper 本地模型进行识别"""
    try:
        import whisper

        # 加载模型（如果可用）
        model = whisper.load_model("base")
        result = model.transcribe(audio_path, language=language)

        return {
            "status": "success",
            "text": result["text"],
            "language": result.get("language", language),
            "segments": result.get("segments", []),
            "provider": "whisper",
        }
    except ImportError:
        return {
            "status": "error",
            "message": "Whisper 未安装，请运行: pip install openai-whisper",
        }


async def _transcribe_with_openai(audio_path: str, language: str) -> dict:
    """使用 OpenAI API 进行识别"""
    import httpx
    from config import ai_config

    if not ai_config.api_key:
        return {
            "status": "error",
            "message": "未配置 AI API Key",
        }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            with open(audio_path, "rb") as f:
                resp = await client.post(
                    f"{ai_config.api_base}/audio/transcriptions",
                    headers={"Authorization": f"Bearer {ai_config.api_key}"},
                    files={"file": ("audio.webm", f, "audio/webm")},
                    data={
                        "model": "whisper-1",
                        "language": language,
                        "response_format": "json",
                    },
                )
                resp.raise_for_status()
                data = resp.json()

                return {
                    "status": "success",
                    "text": data.get("text", ""),
                    "provider": "openai",
                }
    except Exception as e:
        logger.exception("OpenAI 语音识别失败")
        return {
            "status": "error",
            "message": f"识别失败: {e}",
        }


async def _transcribe_local(audio_path: str, language: str) -> dict:
    """本地简单识别（使用 speech_recognition 库）"""
    try:
        import speech_recognition as sr

        recognizer = sr.Recognizer()

        # 转换音频格式为 WAV（如果需要）
        wav_path = await _convert_to_wav(audio_path)

        with sr.AudioFile(wav_path) as source:
            audio = recognizer.record(source)

        # 尝试使用 Google 语音识别
        try:
            text = recognizer.recognize_google(audio, language=language)
            return {
                "status": "success",
                "text": text,
                "provider": "google_sr",
            }
        except sr.UnknownValueError:
            return {
                "status": "error",
                "message": "无法识别音频内容",
            }
        except sr.RequestError as e:
            return {
                "status": "error",
                "message": f"语音识别服务不可用: {e}",
            }

    except ImportError:
        return {
            "status": "error",
            "message": "speech_recognition 未安装，请运行: pip install SpeechRecognition",
        }


async def _convert_to_wav(audio_path: str) -> str:
    """将音频转换为 WAV 格式"""
    from pydub import AudioSegment

    path = Path(audio_path)
    wav_path = path.with_suffix(".wav")

    if path.suffix.lower() == ".wav":
        return str(path)

    # 加载并转换
    audio = AudioSegment.from_file(str(path))
    audio.export(str(wav_path), format="wav")

    return str(wav_path)


async def create_task_from_voice(transcription: str) -> dict:
    """
    从语音转文字创建任务
    使用 AI 解析语音内容提取任务信息
    """
    import httpx
    import json
    from config import ai_config

    if not ai_config.api_key:
        return {
            "status": "error",
            "message": "未配置 AI API Key",
        }

    prompt = f"""从以下语音转文字内容中提取任务信息，返回JSON格式：

语音内容："{transcription}"

返回格式：
{{
    "task_name": "任务名称",
    "due_time": "截止时间（ISO 8601格式，如没有则返回null）",
    "priority": "优先级 (0=紧急, 1=高, 2=中, 3=低)",
    "tags": ["标签1", "标签2"],
    "description": "详细描述"
}}
"""

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{ai_config.api_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {ai_config.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": ai_config.model,
                    "messages": [
                        {"role": "system", "content": "你是一个任务提取助手。"},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.3,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]

            # 解析 JSON
            try:
                task_info = json.loads(content)
            except json.JSONDecodeError:
                # 尝试从代码块中提取
                import re
                json_match = re.search(r'```json\n(.*?)\n```', content, re.DOTALL)
                if json_match:
                    task_info = json.loads(json_match.group(1))
                else:
                    raise

            return {
                "status": "success",
                "task_info": task_info,
                "raw_transcription": transcription,
            }

    except Exception as e:
        logger.exception("语音任务提取失败")
        return {
            "status": "error",
            "message": f"任务提取失败: {e}",
            "raw_transcription": transcription,
        }


async def get_voice_memos(page: int = 1, page_size: int = 20) -> dict:
    """获取语音备忘录列表"""
    files = sorted(VOICE_DIR.glob("*.webm"), key=lambda x: x.stat().st_mtime, reverse=True)

    total = len(files)
    start = (page - 1) * page_size
    end = start + page_size

    memos = []
    for f in files[start:end]:
        stat = f.stat()
        from datetime import datetime
        memos.append({
            "filename": f.name,
            "path": str(f),
            "size_bytes": stat.st_size,
            "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        })

    return {
        "status": "success",
        "memos": memos,
        "total": total,
        "page": page,
        "page_size": page_size,
    }
