"""
本地文件检索服务 — 模糊匹配 + 分类过滤
"""
from __future__ import annotations

import asyncio
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from config import CATEGORY_DIRS, DOWNLOADS_DIR
from services.utils import human_size


async def search_files(keyword: str, category: str) -> dict:
    """
    搜索本地已归档文件（异步包装，不阻塞事件循环）。
    keyword: 模糊匹配文件名
    category: 指定分类或 all
    """
    return await asyncio.to_thread(_search_files_sync, keyword, category)


def _search_files_sync(keyword: str, category: str) -> dict:
    """同步搜索实现（在线程池中执行）"""
    # 确定搜索目录
    if category == "all":
        search_dirs = list(CATEGORY_DIRS.values())
    else:
        target = CATEGORY_DIRS.get(category)
        if not target:
            return {"status": "error", "message": f"未知分类: {category}", "total": 0, "files": []}
        search_dirs = [target]

    keyword_lower = keyword.lower()
    results = []

    for search_dir in search_dirs:
        if not search_dir.exists():
            continue

        # 确定相对分类名
        cat_name = _dir_to_category(search_dir)

        for file_path in search_dir.rglob("*"):
            if not file_path.is_file():
                continue
            # 模糊匹配
            if keyword_lower and keyword_lower not in file_path.name.lower():
                continue

            stat = file_path.stat()
            results.append({
                "filename": file_path.name,
                "category": cat_name,
                "path": str(file_path),
                "size": human_size(stat.st_size),
                "downloaded_at": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%dT%H:%M:%S"),
            })

    # 按文件名排序
    results.sort(key=lambda x: x["filename"])

    return {
        "status": "success",
        "total": len(results),
        "files": results,
    }


# ============================================================
# 辅助函数
# ============================================================

def _dir_to_category(path: Path) -> str:
    """从路径反推分类名"""
    for cat, cat_dir in CATEGORY_DIRS.items():
        if path.resolve() == cat_dir.resolve():
            return cat
    return "misc"


# human_size 已移至 services.utils
