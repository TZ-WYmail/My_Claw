"""
全局快捷键路由 — 快捷键配置和管理
POST /api/shortcuts — 注册快捷键
GET  /api/shortcuts — 获取所有快捷键
PUT  /api/shortcuts/{key_combo} — 更新快捷键
DELETE /api/shortcuts/{key_combo} — 删除快捷键
POST /api/shortcuts/trigger — 触发快捷键
POST /api/shortcuts/reset — 重置为默认
"""
from fastapi import APIRouter, Query

from models.schemas import BaseModel, Field
from services.shortcut_service import (
    check_conflict,
    delete_shortcut,
    export_shortcuts,
    get_all_shortcuts,
    get_shortcut_suggestions,
    import_shortcuts,
    register_shortcut,
    reset_to_defaults,
    trigger_shortcut,
    update_shortcut,
    validate_key_combo,
)

router = APIRouter(prefix="/shortcuts", tags=["shortcuts"])


class ShortcutRegisterRequest(BaseModel):
    key_combo: str = Field(..., description="快捷键组合，如 'ctrl+k'")
    shortcut_id: str = Field(..., description="快捷键唯一标识")
    name: str = Field(..., description="快捷键名称")
    action: str = Field(..., description="触发的动作")
    description: str = Field("", description="快捷键描述")
    enabled: bool = Field(True, description="是否启用")


class ShortcutUpdateRequest(BaseModel):
    name: str = None
    action: str = None
    description: str = None
    enabled: bool = None


class ShortcutTriggerRequest(BaseModel):
    key_combo: str = Field(..., description="快捷键组合")
    context: dict = Field({}, description="上下文信息")


class ImportShortcutsRequest(BaseModel):
    data: dict
    merge: bool = Field(False, description="是否合并而非覆盖")


@router.get("/")
async def list_shortcuts():
    """获取所有快捷键配置"""
    return get_all_shortcuts()


@router.post("/")
async def create_shortcut(request: ShortcutRegisterRequest):
    """注册新快捷键"""
    # 验证格式
    valid, msg = validate_key_combo(request.key_combo)
    if not valid:
        return {"status": "error", "message": msg}

    # 检查冲突
    conflict = check_conflict(request.key_combo)
    if conflict:
        return {
            "status": "error",
            "message": f"快捷键 {request.key_combo} 已被占用",
            "conflict_with": conflict["existing"],
        }

    return register_shortcut(
        key_combo=request.key_combo,
        shortcut_id=request.shortcut_id,
        name=request.name,
        action=request.action,
        description=request.description,
        enabled=request.enabled,
    )


@router.put("/{key_combo}")
async def modify_shortcut(key_combo: str, request: ShortcutUpdateRequest):
    """更新快捷键配置"""
    return update_shortcut(
        key_combo=key_combo,
        name=request.name,
        action=request.action,
        description=request.description,
        enabled=request.enabled,
    )


@router.delete("/{key_combo}")
async def remove_shortcut(key_combo: str):
    """删除快捷键"""
    return delete_shortcut(key_combo)


@router.post("/trigger")
async def trigger(request: ShortcutTriggerRequest):
    """触发快捷键动作"""
    return trigger_shortcut(request.key_combo, request.context)


@router.post("/reset")
async def reset_shortcuts():
    """重置为默认快捷键"""
    return reset_to_defaults()


@router.get("/suggestions")
async def get_suggestions(
    action_type: str = Query(None, description="动作类型过滤"),
):
    """获取快捷键建议"""
    return {
        "status": "success",
        "suggestions": get_shortcut_suggestions(action_type),
    }


@router.get("/validate")
async def validate_shortcut(key_combo: str = Query(..., description="快捷键组合")):
    """验证快捷键格式"""
    valid, msg = validate_key_combo(key_combo)

    # 检查是否已被占用
    conflict = check_conflict(key_combo)

    return {
        "status": "success" if valid else "error",
        "valid": valid,
        "message": msg,
        "conflict": conflict,
    }


@router.get("/export")
async def export_all_shortcuts():
    """导出快捷键配置"""
    return export_shortcuts()


@router.post("/import")
async def import_shortcuts_config(request: ImportShortcutsRequest):
    """导入快捷键配置"""
    return import_shortcuts(request.data, request.merge)
