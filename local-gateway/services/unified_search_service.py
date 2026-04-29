"""
统一搜索服务 — 文件搜索 + 全文搜索 + 数据库搜索
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Optional

from config import CATEGORY_DIRS, DOWNLOADS_DIR
from services.utils import human_size

logger = logging.getLogger(__name__)


async def unified_search(
    keyword: str,
    scope: str = "all",
    category: str = "all",
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """统一搜索入口"""
    if not keyword or not keyword.strip():
        return {"status": "error", "message": "关键词不能为空", "total": 0, "results": {}, "scope": scope}

    tasks = []

    if scope in ("all", "files"):
        tasks.append(_search_files(keyword, category))
    else:
        tasks.append(_empty_result("files"))

    if scope in ("all", "tasks"):
        tasks.append(_search_tasks(keyword, page, page_size))
    else:
        tasks.append(_empty_result("tasks"))

    if scope in ("all", "notes"):
        tasks.append(_search_notes(keyword, page, page_size))
    else:
        tasks.append(_empty_result("notes"))

    if scope in ("all", "habits"):
        tasks.append(_search_habits(keyword))
    else:
        tasks.append(_empty_result("habits"))

    results_list = await asyncio.gather(*tasks)
    results = {
        "files": results_list[0],
        "tasks": results_list[1],
        "notes": results_list[2],
        "habits": results_list[3],
    }

    total = sum(len(v) if isinstance(v, list) else v.get("total", 0) for v in results.values())

    return {
        "status": "success",
        "results": results,
        "total": total,
        "scope": scope,
    }


async def _empty_result(scope: str) -> dict:
    return {"items": [], "total": 0}


async def _search_files(keyword: str, category: str) -> dict:
    """搜索本地文件（异步包装）"""
    return await asyncio.to_thread(_search_files_sync, keyword, category)


def _search_files_sync(keyword: str, category: str) -> dict:
    """同步文件搜索（在线程池中执行）"""
    from datetime import datetime as dt

    if category == "all":
        search_dirs = list(CATEGORY_DIRS.values())
    else:
        target = CATEGORY_DIRS.get(category)
        if not target:
            return {"items": [], "total": 0}
        search_dirs = [target]

    keyword_lower = keyword.lower()
    items = []

    for search_dir in search_dirs:
        if not search_dir.exists():
            continue
        for file_path in search_dir.rglob("*"):
            if not file_path.is_file():
                continue
            if keyword_lower and keyword_lower not in file_path.name.lower():
                continue
            stat = file_path.stat()
            items.append({
                "filename": file_path.name,
                "category": file_path.parent.name,
                "path": str(file_path),
                "size": human_size(stat.st_size),
                "downloaded_at": dt.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%dT%H:%M:%S"),
            })

    items.sort(key=lambda x: x["filename"])
    return {"items": items, "total": len(items)}


async def _search_tasks(keyword: str, page: int, page_size: int) -> dict:
    """搜索任务"""
    from services.task_service import get_all_tasks
    result = await get_all_tasks(keyword=keyword, page=page, page_size=page_size)
    return {"items": result.get("tasks", []), "total": result.get("total", 0)}


async def _search_notes(keyword: str, page: int, page_size: int) -> dict:
    """搜索笔记"""
    from services.note_service import get_all_notes
    result = await get_all_notes(keyword=keyword, page=page, page_size=page_size)
    return {"items": result.get("notes", []), "total": result.get("total", 0)}


async def _search_habits(keyword: str) -> dict:
    """搜索习惯"""
    from services.habit_service import get_all_habits
    habits = await get_all_habits()
    keyword_lower = keyword.lower()
    filtered = [h for h in habits if keyword_lower in h.get("name", "").lower()]
    return {"items": filtered, "total": len(filtered)}


# Full-text search integration (compatibility wrappers for fulltext_search_service)
async def search_fulltext(query: str, category: str = None, top_k: int = 20) -> dict:
    """全文搜索（兼容接口）"""
    try:
        from services.fulltext_search_service import search_fulltext as _ft_search
        return await _ft_search(query, category, top_k)
    except ImportError:
        return {"status": "success", "results": [], "total_results": 0, "message": "全文搜索不可用"}


async def index_all_files(category: str = None) -> dict:
    """构建全文索引（兼容接口）"""
    try:
        from services.fulltext_search_service import index_all_files as _idx
        return await _idx(category)
    except ImportError:
        return {"status": "error", "message": "全文索引不可用"}


async def get_index_stats() -> dict:
    """获取索引统计（兼容接口）"""
    try:
        from services.fulltext_search_service import get_index_stats as _stats
        return await _stats()
    except ImportError:
        return {"status": "error", "message": "全文索引不可用"}


async def rebuild_index() -> dict:
    """重建索引（兼容接口）"""
    try:
        from services.fulltext_search_service import rebuild_index as _rebuild
        return await _rebuild()
    except ImportError:
        return {"status": "error", "message": "全文索引不可用"}
