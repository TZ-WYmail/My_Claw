"""
LocalCommandCenter 本地网关 - 全局配置
"""
import json
import os
from pathlib import Path

# ==================== 服务配置 ====================
SERVICE_NAME = "LocalCommandCenter"
VERSION = "3.0.0"
HOST = os.getenv("GATEWAY_HOST", "0.0.0.0")
PORT = int(os.getenv("GATEWAY_PORT", "8900"))
DEBUG = os.getenv("GATEWAY_DEBUG", "false").lower() == "true"

# ==================== 目录配置 ====================
BASE_DIR = Path(__file__).parent
DOWNLOADS_DIR = Path(os.getenv("DOWNLOADS_DIR", str(BASE_DIR / "downloads")))

# 分类子目录映射
CATEGORY_DIRS = {
    "paper": DOWNLOADS_DIR / "paper",
    "video": DOWNLOADS_DIR / "video",
    "code": DOWNLOADS_DIR / "code",
    "misc": DOWNLOADS_DIR / "misc",
}

# 数据库路径
DB_PATH = BASE_DIR / "data" / "tasks.db"

# ==================== 安全配置 ====================
# 文件名危险字符（禁止出现在下载文件名中）
DANGEROUS_FILENAME_CHARS = ["..", "/", "\\", "\0", "\n", "\r"]

# 允许的 URL 协议
ALLOWED_URL_SCHEMES = ["https", "http"]

# 可执行文件扩展名（触发强制确认）
EXECUTABLE_EXTENSIONS = [
    ".exe", ".sh", ".bat", ".cmd", ".ps1", ".dll", ".so",
    ".app", ".deb", ".rpm", ".msi", ".dmg",
]

# 单文件大小上限（字节），500MB
MAX_FILE_SIZE = 500 * 1024 * 1024

# ==================== Docker 沙盒配置 ====================
DOCKER_IMAGES = {
    "python": "python:3.11-slim",
    "node": "node:20-slim",
    "ffmpeg": "linuxserver/ffmpeg:latest",
    "pandoc": "pandoc/core:latest",
}

# 沙盒超时（秒）
SANDBOX_TIMEOUT = int(os.getenv("SANDBOX_TIMEOUT", "300"))  # 5分钟

# 沙盒最大内存限制
SANDBOX_MEMORY_LIMIT = os.getenv("SANDBOX_MEMORY_LIMIT", "512m")

# 沙盒工作目录
SANDBOX_WORKDIR = "/workspace"

# ==================== 下载配置 ====================
# 下载超时（秒）
DOWNLOAD_TIMEOUT = int(os.getenv("DOWNLOAD_TIMEOUT", "120"))

# 大文件阈值（字节），超过此大小走异步下载
LARGE_FILE_THRESHOLD = 50 * 1024 * 1024  # 50MB

# 下载分块大小
DOWNLOAD_CHUNK_SIZE = 8192

# ==================== CORS 配置 ====================
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")

# ==================== Job 配置 ====================
# 异步任务结果保留时间（秒）
JOB_RESULT_TTL = 3600  # 1小时


def ensure_dirs():
    """确保所有必要目录存在"""
    DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
    for d in CATEGORY_DIRS.values():
        d.mkdir(parents=True, exist_ok=True)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)


# ==================== AI 对话配置 ====================
# AI 配置支持运行时动态修改（通过 /api/chat/config 端点）

class AIConfig:
    """AI 配置对象，支持运行时修改 + 持久化到本地文件"""
    _CONFIG_FILE = BASE_DIR / "data" / "ai_config.json"

    def __init__(self):
        self.api_base = os.getenv("AI_API_BASE", "https://open.bigmodel.cn/api/paas/v4")
        self.api_key = os.getenv("AI_API_KEY", "")
        self.model = os.getenv("AI_MODEL", "glm-4-flash")
        self.gateway_base_url = os.getenv("GATEWAY_BASE_URL", "http://localhost:8900")
        # 启动时从本地文件加载
        self._load()

    def _load(self):
        """从本地 JSON 文件加载持久化配置"""
        try:
            if self._CONFIG_FILE.exists():
                with open(self._CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if data.get("api_base"):
                    self.api_base = data["api_base"]
                if data.get("api_key"):
                    self.api_key = data["api_key"]
                if data.get("model"):
                    self.model = data["model"]
                if data.get("gateway_base_url"):
                    self.gateway_base_url = data["gateway_base_url"]
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"加载 AI 配置文件失败: {e}")

    def save(self):
        """持久化当前配置到本地 JSON 文件"""
        try:
            self._CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(self._CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump({
                    "api_base": self.api_base,
                    "api_key": self.api_key,
                    "model": self.model,
                    "gateway_base_url": self.gateway_base_url,
                }, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"保存 AI 配置失败: {e}")
            return False

    def to_dict(self) -> dict:
        return {
            "api_base": self.api_base,
            "api_key_set": bool(self.api_key),
            "api_key_masked": self._mask_key(self.api_key),
            "model": self.model,
            "gateway_base_url": self.gateway_base_url,
        }

    @staticmethod
    def _mask_key(key: str) -> str:
        if not key or len(key) < 8:
            return "***"
        return key[:4] + "***" + key[-4:]

ai_config = AIConfig()

# 兼容旧引用
AI_API_BASE = ai_config.api_base
AI_API_KEY = ai_config.api_key
AI_MODEL = ai_config.model
GATEWAY_BASE_URL = ai_config.gateway_base_url

# 支持的模型列表（常见选项）
AI_MODEL_OPTIONS = [
    {"id": "glm-4-flash", "name": "GLM-4-Flash (免费/快速)", "provider": "智谱"},
    {"id": "glm-4-air", "name": "GLM-4-Air (均衡)", "provider": "智谱"},
    {"id": "glm-4-plus", "name": "GLM-4-Plus (高精度)", "provider": "智谱"},
    {"id": "glm-4-long", "name": "GLM-4-Long (长文本)", "provider": "智谱"},
    {"id": "gpt-4o-mini", "name": "GPT-4o-mini (快速)", "provider": "OpenAI"},
    {"id": "gpt-4o", "name": "GPT-4o (高精度)", "provider": "OpenAI"},
    {"id": "gpt-3.5-turbo", "name": "GPT-3.5-Turbo (经济)", "provider": "OpenAI"},
    {"id": "deepseek-chat", "name": "DeepSeek-Chat", "provider": "DeepSeek"},
    {"id": "deepseek-reasoner", "name": "DeepSeek-Reasoner (推理)", "provider": "DeepSeek"},
]
