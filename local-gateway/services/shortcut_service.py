"""
全局快捷键服务 — 快捷键注册、触发和处理
注意：实际的全局快捷键需要前端或桌面客户端配合
这里提供后端API支持
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Optional, Callable

from config import BASE_DIR

# 快捷键存储文件
_SHORTCUTS_FILE = BASE_DIR / "data" / "shortcuts.json"

# 内存中的快捷键映射
_shortcuts: dict[str, dict] = {}

# 快捷键处理器注册表
_handlers: dict[str, Callable] = {}


# 默认快捷键配置
DEFAULT_SHORTCUTS = {
    "ctrl+k": {
        "id": "global_search",
        "name": "全局搜索",
        "action": "open_search",
        "description": "打开全局搜索框",
        "enabled": True,
    },
    "ctrl+n": {
        "id": "new_task",
        "name": "新建任务",
        "action": "open_new_task",
        "description": "快速创建新任务",
        "enabled": True,
    },
    "ctrl+j": {
        "id": "ai_assistant",
        "name": "AI助手",
        "action": "open_ai_chat",
        "description": "打开AI对话窗口",
        "enabled": True,
    },
    "ctrl+shift+p": {
        "id": "pomodoro_toggle",
        "name": "番茄钟",
        "action": "toggle_pomodoro",
        "description": "开始/停止番茄钟",
        "enabled": True,
    },
    "ctrl+d": {
        "id": "new_download",
        "name": "新建下载",
        "action": "open_new_download",
        "description": "快速添加下载",
        "enabled": True,
    },
    "ctrl+t": {
        "id": "focus_today",
        "name": "今日任务",
        "action": "show_today_tasks",
        "description": "显示今日任务列表",
        "enabled": True,
    },
    "ctrl+shift+c": {
        "id": "calendar_view",
        "name": "日历视图",
        "action": "open_calendar",
        "description": "打开日历视图",
        "enabled": True,
    },
}


def _load_shortcuts():
    """从文件加载快捷键配置"""
    global _shortcuts
    try:
        if _SHORTCUTS_FILE.exists():
            with open(_SHORTCUTS_FILE, "r", encoding="utf-8") as f:
                _shortcuts = json.load(f)
        else:
            _shortcuts = DEFAULT_SHORTCUTS.copy()
            _save_shortcuts()
    except Exception as e:
        print(f"加载快捷键配置失败: {e}")
        _shortcuts = DEFAULT_SHORTCUTS.copy()


def _save_shortcuts():
    """保存快捷键配置到文件"""
    try:
        _SHORTCUTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(_SHORTCUTS_FILE, "w", encoding="utf-8") as f:
            json.dump(_shortcuts, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"保存快捷键配置失败: {e}")
        return False


# 初始化加载
_load_shortcuts()


def get_all_shortcuts() -> dict:
    """获取所有快捷键配置"""
    return {
        "status": "success",
        "shortcuts": _shortcuts,
    }


def get_shortcut(key_combo: str) -> Optional[dict]:
    """获取指定快捷键的配置"""
    key_combo = key_combo.lower().replace(" ", "")
    return _shortcuts.get(key_combo)


def register_shortcut(
    key_combo: str,
    shortcut_id: str,
    name: str,
    action: str,
    description: str = "",
    enabled: bool = True,
) -> dict:
    """注册新快捷键"""
    key_combo = key_combo.lower().replace(" ", "")

    # 检查是否已被占用
    if key_combo in _shortcuts and _shortcuts[key_combo].get("id") != shortcut_id:
        return {
            "status": "error",
            "message": f"快捷键 {key_combo} 已被占用",
        }

    _shortcuts[key_combo] = {
        "id": shortcut_id,
        "name": name,
        "action": action,
        "description": description,
        "enabled": enabled,
        "created_at": datetime.now().isoformat(),
    }

    _save_shortcuts()

    return {
        "status": "success",
        "shortcut": _shortcuts[key_combo],
    }


def update_shortcut(key_combo: str, **kwargs) -> dict:
    """更新快捷键配置"""
    key_combo = key_combo.lower().replace(" ", "")

    if key_combo not in _shortcuts:
        return {"status": "error", "message": f"快捷键 {key_combo} 不存在"}

    for key, value in kwargs.items():
        if value is not None:
            _shortcuts[key_combo][key] = value

    _shortcuts[key_combo]["updated_at"] = datetime.now().isoformat()
    _save_shortcuts()

    return {
        "status": "success",
        "shortcut": _shortcuts[key_combo],
    }


def delete_shortcut(key_combo: str) -> dict:
    """删除快捷键"""
    key_combo = key_combo.lower().replace(" ", "")

    if key_combo not in _shortcuts:
        return {"status": "error", "message": f"快捷键 {key_combo} 不存在"}

    deleted = _shortcuts.pop(key_combo)
    _save_shortcuts()

    return {
        "status": "success",
        "message": f"快捷键 {key_combo} 已删除",
        "deleted": deleted,
    }


def reset_to_defaults() -> dict:
    """重置为默认快捷键"""
    global _shortcuts
    _shortcuts = DEFAULT_SHORTCUTS.copy()
    _save_shortcuts()

    return {
        "status": "success",
        "message": "已重置为默认快捷键",
        "shortcuts": _shortcuts,
    }


def trigger_shortcut(key_combo: str, context: dict = None) -> dict:
    """
    触发快捷键动作
    注意：实际触发需要前端配合，后端只记录和返回动作
    """
    key_combo = key_combo.lower().replace(" ", "")

    shortcut = _shortcuts.get(key_combo)
    if not shortcut:
        return {"status": "error", "message": f"未定义的快捷键: {key_combo}"}

    if not shortcut.get("enabled", True):
        return {"status": "error", "message": f"快捷键 {key_combo} 已禁用"}

    action = shortcut.get("action")

    # 记录触发日志
    from services.task_service import add_log
    asyncio.create_task(add_log(
        "shortcut_triggered",
        "/api/shortcuts/trigger",
        json.dumps({"key": key_combo, "action": action}),
        "success",
        f"快捷键触发: {shortcut.get('name')}"
    ))

    return {
        "status": "success",
        "action": action,
        "shortcut": shortcut,
        "context": context or {},
    }


def validate_key_combo(key_combo: str) -> tuple[bool, str]:
    """验证快捷键格式是否有效"""
    key_combo = key_combo.lower().replace(" ", "")

    if not key_combo:
        return False, "快捷键不能为空"

    # 支持的修饰键
    modifiers = {"ctrl", "alt", "shift", "meta", "cmd", "win"}

    parts = key_combo.split("+")

    # 检查是否有重复
    if len(parts) != len(set(parts)):
        return False, "快捷键包含重复键"

    # 检查是否至少包含一个修饰键或功能键
    has_modifier = any(p in modifiers for p in parts)
    is_function_key = any(p.startswith("f") and p[1:].isdigit() for p in parts)

    if not has_modifier and not is_function_key:
        return False, "快捷键必须包含修饰键(Ctrl/Alt/Shift)或功能键(F1-F12)"

    # 检查主键
    main_key = parts[-1]
    valid_keys = set("abcdefghijklmnopqrstuvwxyz0123456789") | modifiers | {
        "f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8", "f9", "f10", "f11", "f12",
        "space", "enter", "return", "tab", "escape", "esc", "backspace",
        "delete", "del", "insert", "ins", "home", "end", "pageup", "pagedown",
        "up", "down", "left", "right",
    }

    if main_key not in valid_keys:
        return False, f"不支持的按键: {main_key}"

    return True, "OK"


def check_conflict(key_combo: str) -> Optional[dict]:
    """检查快捷键是否与其他快捷键冲突"""
    key_combo = key_combo.lower().replace(" ", "")

    if key_combo in _shortcuts:
        return {
            "conflict": True,
            "existing": _shortcuts[key_combo],
        }

    return None


def get_shortcut_suggestions(action_type: str = None) -> list[dict]:
    """获取快捷键建议"""
    suggestions = [
        {"key": "ctrl+k", "action": "search", "description": "搜索"},
        {"key": "ctrl+n", "action": "new", "description": "新建"},
        {"key": "ctrl+s", "action": "save", "description": "保存"},
        {"key": "ctrl+o", "action": "open", "description": "打开"},
        {"key": "ctrl+p", "action": "print", "description": "打印"},
        {"key": "ctrl+z", "action": "undo", "description": "撤销"},
        {"key": "ctrl+shift+z", "action": "redo", "description": "重做"},
        {"key": "ctrl+f", "action": "find", "description": "查找"},
        {"key": "ctrl+h", "action": "replace", "description": "替换"},
        {"key": "ctrl+1~9", "action": "switch_tab", "description": "切换标签页"},
    ]

    if action_type:
        suggestions = [s for s in suggestions if action_type in s["action"]]

    return suggestions


def export_shortcuts() -> dict:
    """导出快捷键配置"""
    return {
        "status": "success",
        "version": "1.0",
        "exported_at": datetime.now().isoformat(),
        "shortcuts": _shortcuts,
    }


def import_shortcuts(data: dict, merge: bool = False) -> dict:
    """导入快捷键配置"""
    global _shortcuts

    imported = data.get("shortcuts", {})

    if merge:
        # 合并模式：保留现有，导入新的
        for key, value in imported.items():
            if key not in _shortcuts:
                _shortcuts[key] = value
    else:
        # 覆盖模式
        _shortcuts = imported

    _save_shortcuts()

    return {
        "status": "success",
        "imported_count": len(imported),
        "total_count": len(_shortcuts),
    }
