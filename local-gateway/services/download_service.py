"""
安全下载服务 — 异步下载 + 安全扫描 + 分类归档
"""
from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import logging
import re
import uuid
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import httpx

from config import (
    ALLOWED_URL_SCHEMES,
    CATEGORY_DIRS,
    DANGEROUS_FILENAME_CHARS,
    DOWNLOAD_CHUNK_SIZE,
    DOWNLOAD_TIMEOUT,
    EXECUTABLE_EXTENSIONS,
    LARGE_FILE_THRESHOLD,
    MAX_FILE_SIZE,
    DOWNLOADS_DIR,
)
from services.task_service import add_download_record, update_download_record, add_log

logger = logging.getLogger(__name__)

# 运行中 Job 存储（简单内存存储，生产环境应使用 Redis）
_jobs: dict[str, dict] = {}


# ============================================================
# 安全校验
# ============================================================

def validate_url(url: str) -> tuple[bool, str]:
    """校验 URL 安全性"""
    try:
        parsed = urlparse(url)
    except Exception as e:
        return False, f"URL 解析失败: {e}"

    if parsed.scheme not in ALLOWED_URL_SCHEMES:
        return False, f"不允许的协议: {parsed.scheme}，仅支持 {ALLOWED_URL_SCHEMES}"

    if not parsed.hostname:
        return False, "URL 缺少主机名"

    # 检查危险域名模式
    hostname = parsed.hostname.lower()
    if hostname in ("localhost", "127.0.0.1", "0.0.0.0", "::1"):
        return False, f"不允许下载本地地址: {hostname}"

    # RFC1918 私有 IP 检查
    try:
        import socket
        resolved_ips = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
        for _, _, _, _, addr in resolved_ips:
            ip_str = addr[0]
            ip = ipaddress.ip_address(ip_str)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                return False, f"不允许下载内网地址: {hostname} -> {ip_str}"
    except (socket.gaierror, ValueError):
        pass  # DNS 解析失败时放行，后续 HTTP 请求会自然失败

    return True, "OK"


def validate_filename(filename: str) -> tuple[bool, str]:
    """校验文件名安全性"""
    for char in DANGEROUS_FILENAME_CHARS:
        if char in filename:
            return False, f"文件名包含危险字符: {repr(char)}"
    return True, "OK"


def is_executable(filename: str) -> bool:
    """检查是否为可执行文件"""
    suffix = Path(filename).suffix.lower()
    return suffix in EXECUTABLE_EXTENSIONS


def generate_filename(url: str, content_type: Optional[str] = None) -> str:
    """从 URL 或 Content-Type 自动生成文件名"""
    parsed = urlparse(url)
    path = parsed.path

    # 尝试从 URL 路径提取文件名
    if path and "/" in path:
        name = path.rsplit("/", 1)[-1]
        if name and "." in name:
            return _sanitize_filename(name)

    # 基于 Content-Type 生成
    ext_map = {
        "application/pdf": ".pdf",
        "video/mp4": ".mp4",
        "video/webm": ".webm",
        "audio/mpeg": ".mp3",
        "application/zip": ".zip",
        "application/octet-stream": ".bin",
    }
    ext = ext_map.get(content_type or "", ".bin")
    return f"download_{uuid.uuid4().hex[:8]}{ext}"


def _sanitize_filename(name: str) -> str:
    """清理文件名中的特殊字符"""
    return re.sub(r'[<>:"|?*]', '_', name)


# ============================================================
# 下载执行
# ============================================================

async def safe_download(
    url: str,
    category: str,
    filename: Optional[str] = None,
) -> dict:
    """
    执行安全下载。
    大文件返回异步 job_id，小文件直接返回结果。
    """
    # 1. URL 安全校验
    url_ok, url_msg = validate_url(url)
    if not url_ok:
        return {"status": "error", "message": f"URL 安全校验失败: {url_msg}"}

    # 2. 确保分类目录存在
    save_dir = CATEGORY_DIRS.get(category, CATEGORY_DIRS["misc"])
    save_dir.mkdir(parents=True, exist_ok=True)

    # 3. 先 HEAD 请求获取元信息
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            head_resp = await client.head(url)
            content_length = int(head_resp.headers.get("content-length", 0))
            content_type = head_resp.headers.get("content-type", "")
    except httpx.HTTPError as e:
        # HEAD 失败不阻断，用默认值
        content_length = 0
        content_type = ""

    # 4. 确定文件名
    if not filename:
        filename = generate_filename(url, content_type)
    fn_ok, fn_msg = validate_filename(filename)
    if not fn_ok:
        return {"status": "error", "message": f"文件名校验失败: {fn_msg}"}

    save_path = save_dir / filename

    # 5. 检查文件大小 → 大文件走异步
    if content_length > LARGE_FILE_THRESHOLD:
        job_id = f"job_dl_{datetime_href(url)}"
        _jobs[job_id] = {
            "url": url,
            "category": category,
            "filename": filename,
            "save_path": str(save_path),
            "status": "downloading",
            "estimated_seconds": max(30, content_length // 1024 // 1024 * 3),
        }
        # 记录下载历史
        record_id = await add_download_record(
            url=url, category=category, filename=filename,
            status="downloading", job_id=job_id,
        )
        # 启动后台下载
        asyncio.create_task(_async_download_with_record(job_id, url, save_path, record_id))
        return {
            "mode": "async",
            "job_id": job_id,
            "status": "downloading",
            "estimated_seconds": _jobs[job_id]["estimated_seconds"],
            "message": "文件较大，正在后台下载中",
        }

    # 6. 同步下载小文件
    return await _sync_download(url, save_path, category)


async def _sync_download(url: str, save_path: Path, category: str) -> dict:
    """同步下载文件"""
    try:
        async with httpx.AsyncClient(
            timeout=DOWNLOAD_TIMEOUT,
            follow_redirects=True,
        ) as client:
            async with client.stream("GET", url) as resp:
                if resp.status_code >= 400:
                    return {
                        "status": "error",
                        "message": f"下载失败，HTTP {resp.status_code}",
                    }

                total = 0
                with open(save_path, "wb") as f:
                    async for chunk in resp.aiter_bytes(DOWNLOAD_CHUNK_SIZE):
                        f.write(chunk)
                        total += len(chunk)
                        if total > MAX_FILE_SIZE:
                            # 超限删除
                            save_path.unlink(missing_ok=True)
                            return {
                                "status": "error",
                                "message": f"文件超过大小上限 ({MAX_FILE_SIZE // 1024 // 1024}MB)",
                            }

        # 安全扫描（基本实现）
        scan_result = _basic_security_scan(save_path)

        from services.utils import human_size
        file_size = human_size(save_path.stat().st_size)

        # 记录下载历史
        await add_download_record(
            url=url, category=category, filename=save_path.name,
            file_path=str(save_path), file_size=file_size,
            security_scan=scan_result, status="completed",
        )
        await add_log("download", "/api/download", url, "success", f"{save_path.name} ({file_size})")

        return {
            "status": "success",
            "file_path": str(save_path),
            "file_size": file_size,
            "security_scan": scan_result,
            "message": "文件已安全下载并归档",
        }

    except httpx.ConnectTimeout:
        return {"status": "error", "message": "连接超时，请检查 URL 是否可访问"}
    except httpx.ConnectError:
        return {"status": "error", "message": "无法连接目标服务器"}
    except Exception as e:
        logger.exception("下载异常")
        return {"status": "error", "message": f"下载异常: {e}"}


async def _async_download_with_record(job_id: str, url: str, save_path: Path, record_id: int):
    """异步下载大文件（带历史记录更新）"""
    await _async_download(job_id, url, save_path)
    # 更新下载历史
    job = _jobs.get(job_id, {})
    if job.get("status") == "completed":
        await update_download_record(record_id,
            file_path=job.get("file_path", ""),
            file_size=job.get("file_size", ""),
            security_scan=job.get("security_scan", ""),
            status="completed",
        )
        await add_log("download_async", "/api/download", url, "success", f"完成 {job.get('file_size', '')}")


async def _async_download(job_id: str, url: str, save_path: Path):
    """异步下载大文件"""
    try:
        async with httpx.AsyncClient(
            timeout=600,
            follow_redirects=True,
        ) as client:
            async with client.stream("GET", url) as resp:
                if resp.status_code >= 400:
                    _jobs[job_id].update({
                        "status": "failed",
                        "message": f"HTTP {resp.status_code}",
                    })
                    return

                total = 0
                with open(save_path, "wb") as f:
                    async for chunk in resp.aiter_bytes(DOWNLOAD_CHUNK_SIZE):
                        f.write(chunk)
                        total += len(chunk)

        scan_result = _basic_security_scan(save_path)
        _jobs[job_id].update({
            "status": "completed",
            "file_path": str(save_path),
            "file_size": human_size(save_path.stat().st_size),
            "security_scan": scan_result,
            "duration_seconds": 0,  # 由调用者补充
            "message": "下载完成",
        })

    except Exception as e:
        logger.exception("异步下载异常")
        _jobs[job_id].update({
            "status": "failed",
            "message": str(e),
        })


# ============================================================
# 任务状态查询
# ============================================================

def get_job_status(job_id: str) -> Optional[dict]:
    """查询异步任务状态"""
    return _jobs.get(job_id)


# ============================================================
# 安全扫描
# ============================================================

def _basic_security_scan(file_path: Path) -> str:
    """基础安全扫描（生产环境应接入 ClamAV 等）"""
    # 检查可执行文件头
    try:
        with open(file_path, "rb") as f:
            header = f.read(4)
            # ELF
            if header[:4] == b'\x7fELF':
                return "failed"
            # MZ (PE/EXE)
            if header[:2] == b'MZ':
                return "failed"
    except Exception:
        pass

    return "passed"


# ============================================================
# 辅助函数
# ============================================================

# human_size 已移至 services.utils


def datetime_href(url: str) -> str:
    """URL → 简短时间戳 ID"""
    from datetime import datetime
    return f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:4]}"
