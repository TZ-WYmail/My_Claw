from __future__ import annotations

import asyncio
import imaplib
import smtplib
import sys
from pathlib import Path
from typing import Any, Optional


MAIL_SERVICE_MODULE_NAME = "services.mail_service"


def get_runtime_mail_service() -> Optional[object]:
    return sys.modules.get(MAIL_SERVICE_MODULE_NAME)


def get_runtime_attr(name: str, default: Any = None) -> Any:
    module = get_runtime_mail_service()
    if module is not None:
        return getattr(module, name, default)
    return default


def get_runtime_db_path(default_db_path: Path) -> Path:
    return Path(get_runtime_attr("DB_PATH", default_db_path))


def get_runtime_asyncio():
    return get_runtime_attr("asyncio", asyncio)


def get_runtime_smtplib():
    return get_runtime_attr("smtplib", smtplib)


def get_runtime_imaplib():
    return get_runtime_attr("imaplib", imaplib)
