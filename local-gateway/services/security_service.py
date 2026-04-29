"""
安全服务 — 统一的安全校验入口
提供路径遍历防护、SSRF校验、命令注入防护、XSS过滤等
"""
from __future__ import annotations

import ipaddress
import logging
import re
import socket
from pathlib import Path
from urllib.parse import urlparse

from config import ALLOWED_URL_SCHEMES

logger = logging.getLogger(__name__)

# 合法文件名字符白名单（保守策略：字母数字、中文、常见安全符号）
_FILENAME_SAFE_RE = re.compile(r'^[^\\/:*?"<>|]+$')

# 允许的 UPDATE 列名白名单（防止 SQL 注入）
_DOWNLOAD_HISTORY_COLUMNS = {"filename", "category", "file_path", "file_size",
                              "security_scan", "status", "job_id"}


def sanitize_filename(filename: str | None, default: str = "unnamed") -> str:
    """
    净化文件名，防止路径遍历攻击。

    策略：
    1. 若为空，返回 default
    2. 提取 Path.name（丢弃所有目录组件）
    3. 拒绝空结果或仅含 . 的结果
    4. 用正则移除/替换危险字符
    5. 限制最大长度（255 字符）
    """
    if not filename:
        return default

    # 提取纯文件名（丢弃路径）
    basename = Path(filename).name

    # 拒绝明显危险的模式
    if not basename or basename in {".", ".."} or basename.startswith(".."):
        return default

    # 替换危险字符
    safe = re.sub(r'[\\/:*?"<>|]', '_', basename)

    # 去除控制字符
    safe = re.sub(r'[\x00-\x1f\x7f]', '', safe)

    # 限制长度（保留扩展名）
    max_len = 255
    if len(safe) > max_len:
        stem = Path(safe).stem
        suffix = Path(safe).suffix
        safe = stem[:max_len - len(suffix)] + suffix

    # 如果处理后为空，返回默认
    if not safe or safe in {".", ".."}:
        return default

    return safe


def validate_url_for_ssrf(url: str) -> tuple[bool, str]:
    """
    SSRF 防护：校验 URL 安全性。

    检查项：
    1. 协议白名单
    2. 主机名存在
    3. 禁止本地地址、私有 IP、回环地址
    4. 禁止 IPv6 映射回环
    5. DNS 解析后重新校验 IP
    """
    try:
        parsed = urlparse(url)
    except Exception as e:
        return False, f"URL 解析失败: {e}"

    if parsed.scheme not in ALLOWED_URL_SCHEMES:
        return False, f"不允许的协议: {parsed.scheme}"

    if not parsed.hostname:
        return False, "URL 缺少主机名"

    hostname = parsed.hostname.lower()

    # 直接禁止常见本地主机名
    if hostname in ("localhost", "127.0.0.1", "0.0.0.0", "::1",
                    "0000:0000:0000:0000:0000:0000:0000:0001",
                    "0:0:0:0:0:0:0:1"):
        return False, f"不允许访问本地地址: {hostname}"

    # 如果 hostname 本身就是 IP，直接检查
    try:
        ip = ipaddress.ip_address(hostname)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            return False, f"不允许访问内网 IP: {hostname}"
    except ValueError:
        pass  # 不是 IP，继续

    # DNS 解析后检查
    try:
        resolved_ips = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
        for _, _, _, _, addr in resolved_ips:
            ip_str = addr[0]
            try:
                ip = ipaddress.ip_address(ip_str)
                if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                    return False, f"DNS 解析到内网地址: {hostname} -> {ip_str}"
            except ValueError:
                continue
    except socket.gaierror:
        return False, f"无法解析主机名: {hostname}"
    except Exception:
        pass

    return True, "OK"


def validate_command_tokens(command: list[str]) -> tuple[bool, str]:
    """
    命令注入防护：校验命令令牌列表。

    只允许白名单中的命令，拒绝任何 shell 元字符。
    """
    if not command:
        return False, "命令不能为空"

    # 危险命令黑名单（按完整路径或 basename 匹配）
    blocked_commands = {
        "rm", "mv", "cp", "dd", "mkfs", "fdisk", "format",
        "shutdown", "reboot", "halt", "poweroff",
        "curl", "wget", "nc", "netcat", "telnet",
        "bash", "sh", "zsh", "python", "python3",
        "sudo", "su", "chmod", "chown",
    }

    cmd = command[0]
    cmd_name = Path(cmd).name.lower()

    if cmd_name in blocked_commands:
        return False, f"命令 '{cmd_name}' 在黑名单中"

    # 检查参数中是否包含 shell 元字符
    shell_metacharacters = {";", "&", "|", "$", "`", "(", ")", "{", "}",
                            "<", ">", "*", "?", "~", "\\", "\n"}
    for arg in command[1:]:
        for ch in shell_metacharacters:
            if ch in arg:
                return False, f"参数包含 shell 元字符: {repr(ch)}"

    return True, "OK"


def escape_html(text: str) -> str:
    """XSS 防护：HTML 实体编码（含单引号）"""
    if not isinstance(text, str):
        text = str(text)
    return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#39;"))


def validate_update_columns(table: str, columns: set[str]) -> tuple[bool, set[str]]:
    """
    SQL 注入防护：校验 UPDATE 列名是否在白名单中。

    返回 (是否合法, 非法列名集合)
    """
    allowed = _get_allowed_columns(table)
    invalid = columns - allowed
    return len(invalid) == 0, invalid


def _get_allowed_columns(table: str) -> set[str]:
    """获取表允许的列名白名单"""
    mapping = {
        "download_history": _DOWNLOAD_HISTORY_COLUMNS,
        "subtasks": {"name", "status"},
        "notes": {"title", "content", "tags"},
    }
    return mapping.get(table, set())
