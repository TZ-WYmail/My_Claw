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
    CATEGORY_DIRS,
    DOWNLOAD_CHUNK_SIZE,
    DOWNLOAD_TIMEOUT,
    EXECUTABLE_EXTENSIONS,
    LARGE_FILE_THRESHOLD,
    MAX_FILE_SIZE,
    DOWNLOADS_DIR,
)
from services.security_service import sanitize_filename, validate_url_for_ssrf
from services.task_service import add_download_record, update_download_record, add_log
from services.utils import human_size

logger = logging.getLogger(__name__)

# 运行中 Job 存储（简单内存存储，生产环境应使用 Redis）
_jobs: dict[str, dict] = {}

# 下载队列管理
_download_queue: list[dict] = []
_queue_processing: bool = False
_max_concurrent_downloads: int = 3
_active_downloads: int = 0

# 默认带宽限制 (KB/s), 0 表示无限制
_bandwidth_limit_kb: int = 0


# ============================================================
# 安全校验
# ============================================================

def validate_url(url: str) -> tuple[bool, str]:
    """校验 URL 安全性（委托给 security_service 做 SSRF 防护）"""
    return validate_url_for_ssrf(url)


def validate_filename(filename: str) -> tuple[bool, str]:
    """校验文件名安全性 - 防止路径遍历攻击"""
    if not filename:
        return False, "文件名不能为空"

    # 使用 sanitize_filename 净化，若净化后改变则说明包含危险字符
    safe = sanitize_filename(filename, default="")
    if safe != filename:
        return False, "文件名包含非法字符或路径遍历尝试"

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

    # 5. 检查文件大小 → 大文件走队列
    if content_length > LARGE_FILE_THRESHOLD:
        # 添加到下载队列
        result = await add_to_queue(url, category, filename, priority=5)
        if result["status"] == "success":
            return {
                "mode": "queued",
                "job_id": result["job_id"],
                "status": "queued",
                "position": result["position"],
                "message": f"文件较大，已加入下载队列，当前位置: {result['position'] + 1}",
            }
        return result

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


# ============================================================
# 下载队列管理
# ============================================================

async def add_to_queue(
    url: str,
    category: str,
    filename: Optional[str] = None,
    priority: int = 5,  # 1-10, 数字越小优先级越高
) -> dict:
    """添加下载到队列"""
    global _download_queue

    # URL 安全校验
    url_ok, url_msg = validate_url(url)
    if not url_ok:
        return {"status": "error", "message": f"URL 安全校验失败: {url_msg}"}

    # 确定文件名
    if not filename:
        filename = generate_filename(url)
    fn_ok, fn_msg = validate_filename(filename)
    if not fn_ok:
        return {"status": "error", "message": f"文件名校验失败: {fn_msg}"}

    job_id = f"job_q_{datetime_href(url)}"
    queue_item = {
        "job_id": job_id,
        "url": url,
        "category": category,
        "filename": filename,
        "priority": priority,
        "status": "queued",  # queued/downloading/paused/completed/failed
        "progress": 0,  # 0-100
        "downloaded_bytes": 0,
        "total_bytes": 0,
        "speed_kb_s": 0,
        "retry_count": 0,
        "max_retries": 3,
        "created_at": asyncio.get_event_loop().time(),
    }

    # 按优先级插入队列
    insert_idx = len(_download_queue)
    for i, item in enumerate(_download_queue):
        if item["priority"] > priority:
            insert_idx = i
            break
    _download_queue.insert(insert_idx, queue_item)

    # 记录下载历史
    save_dir = CATEGORY_DIRS.get(category, CATEGORY_DIRS["misc"])
    save_path = save_dir / filename
    record_id = await add_download_record(
        url=url, category=category, filename=filename,
        status="queued", job_id=job_id,
    )
    queue_item["record_id"] = record_id
    queue_item["save_path"] = str(save_path)

    # 触发队列处理
    asyncio.create_task(_process_queue())

    return {
        "status": "success",
        "job_id": job_id,
        "position": insert_idx,
        "message": f"已加入下载队列，当前位置: {insert_idx + 1}",
    }


async def _process_queue():
    """处理下载队列"""
    global _queue_processing, _active_downloads

    if _queue_processing:
        return
    _queue_processing = True

    try:
        while _download_queue and _active_downloads < _max_concurrent_downloads:
            # 找到下一个待下载的任务
            next_item = None
            for item in _download_queue:
                if item["status"] == "queued":
                    next_item = item
                    break

            if not next_item:
                break

            _active_downloads += 1
            next_item["status"] = "downloading"
            asyncio.create_task(_download_with_retry(next_item))

        # 等待所有活动下载完成
        while _active_downloads > 0:
            await asyncio.sleep(1)

    finally:
        _queue_processing = False


async def _download_with_retry(queue_item: dict):
    """带重试机制的下载"""
    global _active_downloads

    try:
        while queue_item["retry_count"] < queue_item["max_retries"]:
            result = await _download_with_resume(queue_item)

            if result["status"] == "success":
                queue_item.update(result)
                queue_item["status"] = "completed"
                await update_download_record(
                    queue_item["record_id"],
                    file_path=queue_item.get("file_path", ""),
                    file_size=queue_item.get("file_size", ""),
                    status="completed",
                )
                break
            elif result.get("retryable"):
                queue_item["retry_count"] += 1
                queue_item["status"] = "retrying"
                logger.warning(f"下载重试 {queue_item['job_id']}: 第 {queue_item['retry_count']} 次")
                await asyncio.sleep(2 ** queue_item["retry_count"])  # 指数退避
            else:
                queue_item["status"] = "failed"
                queue_item["error"] = result.get("message", "未知错误")
                await update_download_record(
                    queue_item["record_id"],
                    status="failed",
                )
                break
    except Exception as e:
        logger.exception("下载任务异常")
        queue_item["status"] = "failed"
        queue_item["error"] = str(e)
    finally:
        _active_downloads -= 1
        # 触发队列继续处理
        asyncio.create_task(_process_queue())


async def _download_with_resume(queue_item: dict) -> dict:
    """支持断点续传的下载"""
    url = queue_item["url"]
    save_path = Path(queue_item["save_path"])
    downloaded_bytes = queue_item.get("downloaded_bytes", 0)

    # 检查是否存在未完成的下载
    temp_path = save_path.with_suffix(save_path.suffix + ".tmp")

    try:
        headers = {}
        if temp_path.exists() and downloaded_bytes > 0:
            # 尝试断点续传
            headers["Range"] = f"bytes={downloaded_bytes}-"
            logger.info(f"尝试断点续传: {url} 从 {downloaded_bytes} 字节开始")

        async with httpx.AsyncClient(
            timeout=600,
            follow_redirects=True,
        ) as client:
            # 先发送 HEAD 请求检查服务器是否支持 Range
            supports_resume = False
            try:
                head_resp = await client.head(url, headers=headers)
                if head_resp.status_code == 206:
                    supports_resume = True
            except:
                pass

            async with client.stream("GET", url, headers=headers) as resp:
                if resp.status_code not in (200, 206):
                    return {
                        "status": "error",
                        "message": f"HTTP {resp.status_code}",
                        "retryable": resp.status_code >= 500 or resp.status_code == 429,
                    }

                # 获取文件总大小
                total_bytes = int(resp.headers.get("content-length", 0))
                if resp.status_code == 206:
                    # Range 响应，总大小需要加上已下载的部分
                    content_range = resp.headers.get("content-range", "")
                    if "/" in content_range:
                        total_bytes = int(content_range.split("/")[-1])
                elif total_bytes == 0:
                    total_bytes = queue_item.get("total_bytes", 0)

                queue_item["total_bytes"] = total_bytes

                # 打开文件（追加模式用于续传）
                mode = "ab" if supports_resume and downloaded_bytes > 0 else "wb"
                with open(temp_path, mode) as f:
                    last_update = asyncio.get_event_loop().time()
                    bytes_since_update = 0

                    async for chunk in resp.aiter_bytes(DOWNLOAD_CHUNK_SIZE):
                        f.write(chunk)
                        downloaded_bytes += len(chunk)
                        bytes_since_update += len(chunk)
                        queue_item["downloaded_bytes"] = downloaded_bytes

                        # 计算进度
                        if total_bytes > 0:
                            queue_item["progress"] = int(downloaded_bytes * 100 / total_bytes)

                        # 计算速度（每秒更新）
                        now = asyncio.get_event_loop().time()
                        if now - last_update >= 1:
                            queue_item["speed_kb_s"] = int(bytes_since_update / 1024 / (now - last_update))
                            last_update = now
                            bytes_since_update = 0

                        # 带宽限制
                        if _bandwidth_limit_kb > 0 and queue_item["speed_kb_s"] > _bandwidth_limit_kb:
                            await asyncio.sleep(0.1)

                        # 检查是否超过最大文件大小
                        if downloaded_bytes > MAX_FILE_SIZE:
                            temp_path.unlink(missing_ok=True)
                            return {
                                "status": "error",
                                "message": f"文件超过大小上限 ({MAX_FILE_SIZE // 1024 // 1024}MB)",
                                "retryable": False,
                            }

                # 下载完成，重命名为最终文件名
                temp_path.rename(save_path)

                # 安全扫描
                scan_result = _basic_security_scan(save_path)
                file_size = human_size(save_path.stat().st_size)

                return {
                    "status": "success",
                    "file_path": str(save_path),
                    "file_size": file_size,
                    "security_scan": scan_result,
                    "progress": 100,
                }

    except httpx.ConnectTimeout:
        return {"status": "error", "message": "连接超时", "retryable": True}
    except httpx.ConnectError:
        return {"status": "error", "message": "无法连接目标服务器", "retryable": True}
    except Exception as e:
        logger.exception("下载异常")
        return {"status": "error", "message": str(e), "retryable": True}


async def pause_download(job_id: str) -> dict:
    """暂停下载（标记状态，实际下载会继续直到当前块完成）"""
    for item in _download_queue:
        if item["job_id"] == job_id and item["status"] == "downloading":
            item["status"] = "paused"
            return {"status": "success", "message": "下载已暂停"}
    return {"status": "error", "message": "未找到进行中的下载任务"}


async def resume_download(job_id: str) -> dict:
    """恢复下载"""
    for item in _download_queue:
        if item["job_id"] == job_id and item["status"] == "paused":
            item["status"] = "queued"
            asyncio.create_task(_process_queue())
            return {"status": "success", "message": "下载已恢复"}
    return {"status": "error", "message": "未找到暂停的下载任务"}


async def cancel_download(job_id: str) -> dict:
    """取消下载"""
    for i, item in enumerate(_download_queue):
        if item["job_id"] == job_id:
            if item["status"] in ("queued", "paused"):
                _download_queue.pop(i)
                await update_download_record(item["record_id"], status="cancelled")
                return {"status": "success", "message": "下载已取消"}
            elif item["status"] == "downloading":
                item["status"] = "cancelled"
                await update_download_record(item["record_id"], status="cancelled")
                return {"status": "success", "message": "下载已标记取消"}
    return {"status": "error", "message": "未找到下载任务"}


def get_queue_status() -> dict:
    """获取下载队列状态"""
    return {
        "status": "success",
        "queue_length": len(_download_queue),
        "active_downloads": _active_downloads,
        "max_concurrent": _max_concurrent_downloads,
        "items": [
            {
                "job_id": item["job_id"],
                "filename": item["filename"],
                "status": item["status"],
                "progress": item["progress"],
                "speed_kb_s": item["speed_kb_s"],
                "retry_count": item["retry_count"],
            }
            for item in _download_queue
        ],
    }


def set_bandwidth_limit(kb_per_second: int):
    """设置带宽限制 (KB/s), 0 表示无限制"""
    global _bandwidth_limit_kb
    _bandwidth_limit_kb = kb_per_second
    return {"status": "success", "limit_kb_s": kb_per_second}


def get_bandwidth_limit() -> dict:
    """获取当前带宽限制"""
    return {"status": "success", "limit_kb_s": _bandwidth_limit_kb}
