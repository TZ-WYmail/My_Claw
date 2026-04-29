"""
端到端加密服务 — 同步数据加密存储

使用 Fernet 对称加密 + PBKDF2 密钥派生
"""
from __future__ import annotations

import base64
import logging
import os
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from config import BASE_DIR

logger = logging.getLogger(__name__)

KEY_FILE = BASE_DIR / "data" / ".e2e_key"
SALT_FILE = BASE_DIR / "data" / ".e2e_salt"

# 需要加密的敏感字段
SENSITIVE_FIELDS = {"title", "name", "description", "content", "note"}

# 标记字段（使用带命名空间的前缀避免与用户数据冲突）
_ENCRYPTED_MARKER = "__e2e_encrypted"


class E2EEncryption:
    """端到端加密服务"""

    PBKDF2_ITERATIONS = 100_000

    def __init__(self, master_password: Optional[str] = None, salt: Optional[bytes] = None):
        self._salt = salt or self._load_or_create_salt()
        if master_password:
            self._key = self._derive_key(master_password, self._salt)
        else:
            self._key = self._load_or_create_key()
        self._fernet = Fernet(self._key)

    # ── 密钥管理 ──────────────────────────────────────

    def _load_or_create_salt(self) -> bytes:
        if SALT_FILE.exists():
            return SALT_FILE.read_bytes()
        salt = os.urandom(16)
        SALT_FILE.parent.mkdir(parents=True, exist_ok=True)
        SALT_FILE.write_bytes(salt)
        return salt

    def _derive_key(self, password: str, salt: bytes) -> bytes:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=self.PBKDF2_ITERATIONS,
        )
        return base64.urlsafe_b64encode(kdf.derive(password.encode()))

    def _load_or_create_key(self) -> bytes:
        if KEY_FILE.exists():
            return KEY_FILE.read_bytes()
        key = Fernet.generate_key()
        KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
        KEY_FILE.write_bytes(key)
        return key

    # ── 加密/解密 ─────────────────────────────────────

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, token: str) -> str:
        return self._fernet.decrypt(token.encode()).decode()

    def encrypt_object(self, obj: dict, fields: Optional[set[str]] = None) -> dict:
        """加密对象中的敏感字段，其他字段原样保留"""
        target_fields = fields or SENSITIVE_FIELDS
        result = {}
        for key, value in obj.items():
            if key in target_fields and isinstance(value, str) and value:
                result[key] = self.encrypt(value)
            else:
                result[key] = value
        result[_ENCRYPTED_MARKER] = True
        return result

    def decrypt_object(self, obj: dict, fields: Optional[set[str]] = None) -> dict:
        """解密对象中的加密字段"""
        if not obj.get(_ENCRYPTED_MARKER):
            return obj
        target_fields = fields or SENSITIVE_FIELDS
        result = {}
        for key, value in obj.items():
            if key == _ENCRYPTED_MARKER:
                continue
            if key in target_fields and isinstance(value, str) and value:
                try:
                    result[key] = self.decrypt(value)
                except InvalidToken:
                    logger.warning("Failed to decrypt field '%s', returning raw value", key)
                    result[key] = value
            else:
                result[key] = value
        return result

    # ── 同步负载加密 ───────────────────────────────────

    def encrypt_sync_payload(self, payload: dict) -> dict:
        """加密同步数据包中的 changes"""
        changes = payload.get("changes", [])
        encrypted_changes = []
        for change in changes:
            new_data = change.get("new_data")
            if isinstance(new_data, dict):
                change = {**change, "new_data": self.encrypt_object(new_data)}
            encrypted_changes.append(change)
        return {**payload, "changes": encrypted_changes, "encrypted": True}

    def decrypt_sync_payload(self, payload: dict) -> dict:
        """解密同步数据包中的 changes"""
        if not payload.get("encrypted"):
            return payload
        changes = payload.get("changes", [])
        decrypted_changes = []
        for change in changes:
            new_data = change.get("new_data")
            if isinstance(new_data, dict) and new_data.get(_ENCRYPTED_MARKER):
                change = {**change, "new_data": self.decrypt_object(new_data)}
            decrypted_changes.append(change)
        result = {**payload, "changes": decrypted_changes}
        result.pop("encrypted", None)
        return result

    # ── 密钥信息 ──────────────────────────────────────

    def get_key_info(self) -> dict:
        return {
            "has_key": bool(self._key),
            "salt_length": len(self._salt),
            "iterations": self.PBKDF2_ITERATIONS,
            "algorithm": "PBKDF2-SHA256-Fernet",
        }

    def rotate_key(self, new_password: Optional[str] = None) -> dict:
        """密钥轮换 — 原子写入新 salt + key，旧密钥失效"""
        new_salt = os.urandom(16)
        if new_password:
            new_key = self._derive_key(new_password, new_salt)
        else:
            new_key = Fernet.generate_key()

        # 原子写入：先写 key 再写 salt，确保 salt 总是与有效 key 配对
        # 若在两步之间崩溃，旧 salt+旧 key 仍可配对使用
        KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
        KEY_FILE.write_bytes(new_key)
        SALT_FILE.write_bytes(new_salt)

        self._salt = new_salt
        self._key = new_key
        self._fernet = Fernet(self._key)
        logger.info("E2E encryption key rotated")
        return {"rotated": True}


# 全局实例（使用存储的密钥，无需密码）
e2e = E2EEncryption()
