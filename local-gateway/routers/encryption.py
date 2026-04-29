"""
端到端加密路由 — 密钥管理、加密/解密、加密同步
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from services.e2e_encryption import e2e

router = APIRouter(prefix="/encryption", tags=["encryption"])


class EncryptRequest(BaseModel):
    plaintext: str


class DecryptRequest(BaseModel):
    token: str


class EncryptObjectRequest(BaseModel):
    data: dict
    fields: Optional[list[str]] = None


class DecryptObjectRequest(BaseModel):
    data: dict
    fields: Optional[list[str]] = None


class EncryptPayloadRequest(BaseModel):
    payload: dict


class DecryptPayloadRequest(BaseModel):
    payload: dict


class RotateKeyRequest(BaseModel):
    new_password: Optional[str] = None


# ── 密钥管理 ──────────────────────────────────────────

@router.get("/key-info")
async def get_key_info():
    """获取当前加密密钥信息"""
    return {"status": "success", "info": e2e.get_key_info()}


@router.post("/rotate-key")
async def rotate_key(req: RotateKeyRequest):
    """密钥轮换 — 生成新密钥（旧密钥失效）"""
    result = e2e.rotate_key(req.new_password)
    return {"status": "success", "result": result}


# ── 文本加密/解密 ─────────────────────────────────────

@router.post("/encrypt")
async def encrypt_text(req: EncryptRequest):
    """加密文本"""
    token = e2e.encrypt(req.plaintext)
    return {"status": "success", "token": token}


@router.post("/decrypt")
async def decrypt_text(req: DecryptRequest):
    """解密文本"""
    try:
        plaintext = e2e.decrypt(req.token)
        return {"status": "success", "plaintext": plaintext}
    except Exception as e:
        return {"status": "error", "message": f"解密失败: {e}"}


# ── 对象加密/解密 ─────────────────────────────────────

@router.post("/encrypt-object")
async def encrypt_object(req: EncryptObjectRequest):
    """加密对象中的敏感字段"""
    fields = set(req.fields) if req.fields else None
    encrypted = e2e.encrypt_object(req.data, fields)
    return {"status": "success", "data": encrypted}


@router.post("/decrypt-object")
async def decrypt_object(req: DecryptObjectRequest):
    """解密对象中的加密字段"""
    fields = set(req.fields) if req.fields else None
    decrypted = e2e.decrypt_object(req.data, fields)
    return {"status": "success", "data": decrypted}


# ── 同步负载加密/解密 ─────────────────────────────────

@router.post("/encrypt-payload")
async def encrypt_payload(req: EncryptPayloadRequest):
    """加密同步数据包"""
    encrypted = e2e.encrypt_sync_payload(req.payload)
    return {"status": "success", "payload": encrypted}


@router.post("/decrypt-payload")
async def decrypt_payload(req: DecryptPayloadRequest):
    """解密同步数据包"""
    decrypted = e2e.decrypt_sync_payload(req.payload)
    return {"status": "success", "payload": decrypted}
