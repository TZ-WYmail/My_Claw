"""
共享工具函数
"""
from __future__ import annotations


def human_size(size_bytes: int) -> str:
    """将字节数转换为人类可读格式"""
    if size_bytes < 0:
        return "0 B"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"
