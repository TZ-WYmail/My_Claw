"""
AI 对话服务 — Agentic Loop + Code Interpreter + Shell
将用户消息转发给 AI API，AI 通过 function calling 操控本地网关工具。
支持多轮 tool calling 循环，LLM 自主规划并解决问题。
"""
from __future__ import annotations

import asyncio
import json
import logging
import subprocess
import tempfile
from typing import Any, Optional

import httpx

from config import AI_API_BASE, AI_API_KEY, AI_MODEL, GATEWAY_BASE_URL
from config import ai_config

logger = logging.getLogger(__name__)

# Code Interpreter 最大执行时间（秒）
CODE_INTERPRETER_TIMEOUT = 120

# Shell 命令安全配置
SHELL_DANGEROUS_PATTERNS = [
    "rm -rf /", "rm -rf ~", "sudo rm", "mkfs", "dd if=", "> /dev/sd",
    "chmod 777 /", ":(){:|:&};:", "fork bomb",
    "curl", "wget", "nc ", "ncat", "/dev/tcp", "/dev/udp",
    "ssh ", "scp ", "rsync", "passwd", "shadow",
    "crontab", "systemctl", "service ", "insmod", "modprobe",
    "> /etc/", "echo root", "chown root",
]

# Python 危险模块黑名单（code_interpreter 用）
PYTHON_DANGEROUS_IMPORTS = {
    "os.system", "os.exec", "os.spawn", "os.remove", "os.rmdir",
    "os.unlink", "os.kill", "os.chmod", "os.chown",
    "shutil.rmtree", "shutil.move",
    "subprocess", "ctypes", "multiprocessing",
    "socket.socket", "http.server", "xmlrpc",
    "pty", "fcntl", "resource",
    "importlib", "__import__", "eval(", "exec(",
    "compile(", "open('/etc", "open('/root",
}

# ============================================================
# 5 个工具的 Schema 定义（给 AI function calling 用）
# ============================================================

TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "local_task_manager",
            "description": "管理日常任务与周计划，支持添加、删除、查询、完成任务。所有时间参数必须使用 ISO 8601 格式。",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["add_task", "delete_task", "get_weekly_plan", "complete_task"],
                        "description": "操作类型",
                    },
                    "task_name": {"type": "string", "description": "任务名称，add_task 时必填"},
                    "task_id": {"type": "string", "description": "任务 ID，delete_task / complete_task 时必填"},
                    "due_time": {"type": "string", "description": "ISO 8601 时间，add_task 时必填"},
                    "recurrence": {
                        "type": "string",
                        "enum": ["once", "daily", "weekly", "monthly"],
                        "description": "重复周期",
                    },
                },
                "required": ["action"],
            },
        },
    },
    # ==================== 新增：批量任务编排 ====================
    {
        "type": "function",
        "function": {
            "name": "batch_task_manager",
            "description": (
                "批量创建多个任务。当用户一次给出多项任务时使用此工具，而非逐个调用 local_task_manager。"
                "此工具会自动将用户的自然语言任务列表解析为结构化数据，并生成每日工作分布计划。"
                "preview 返回的数据包含 daily_plan（每日任务分布+预估工时）和 daily_timeline（日历摘要），"
                "你必须在回复中展示这些数据，让用户看到任务如何分配到每天。"
                "先预览确认，再批量创建。支持中文日期格式如'3月22日'。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["preview", "create"],
                        "description": "preview=预览分析（不写入），create=批量创建",
                    },
                    "tasks": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "task_name": {"type": "string", "description": "任务名称"},
                                "due_time": {"type": "string", "description": "截止时间，支持'3月22日'/'2026-03-22'等格式"},
                                "recurrence": {"type": "string", "description": "重复周期", "enum": ["once", "daily", "weekly", "monthly"]},
                            },
                            "required": ["task_name", "due_time"],
                        },
                        "description": "任务列表",
                    },
                },
                "required": ["action", "tasks"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "local_safe_downloader",
            "description": "从 URL 下载文件，经过安全扫描后按分类归档到本地。大文件会异步下载。",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "下载 URL"},
                    "category": {
                        "type": "string",
                        "enum": ["paper", "video", "code", "misc"],
                        "description": "归档分类",
                    },
                    "filename": {"type": "string", "description": "保存文件名（可选）"},
                },
                "required": ["url", "category"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "local_file_search",
            "description": "搜索本地已归档的文件，支持按文件名关键词和分类筛选。",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {"type": "string", "description": "搜索关键词"},
                    "category": {
                        "type": "string",
                        "enum": ["paper", "video", "code", "misc", "all"],
                        "description": "分类筛选",
                    },
                },
                "required": ["keyword", "category"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "local_sandbox_executor",
            "description": "在 Docker 沙盒中执行代码或命令。支持 Python/Node/FFmpeg/Pandoc。",
            "parameters": {
                "type": "object",
                "properties": {
                    "tool_name": {
                        "type": "string",
                        "enum": ["python", "node", "ffmpeg", "pandoc"],
                        "description": "运行环境",
                    },
                    "execution_command": {"type": "string", "description": "执行命令"},
                    "setup_commands": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "前置准备命令（可选）",
                    },
                    "dynamic_files": {
                        "type": "object",
                        "description": "动态写入文件 {文件名: 内容}（可选）",
                        "additionalProperties": {"type": "string"},
                    },
                    "input_files": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "宿主机文件路径列表（可选）",
                    },
                },
                "required": ["tool_name", "execution_command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "local_job_status",
            "description": "查询异步任务的执行状态与结果。",
            "parameters": {
                "type": "object",
                "properties": {
                    "job_id": {"type": "string", "description": "异步任务 ID"},
                },
                "required": ["job_id"],
            },
        },
    },
    # ==================== 新增：Code Interpreter ====================
    {
        "type": "function",
        "function": {
            "name": "code_interpreter",
            "description": (
                "执行任意代码来解决用户问题。这是你的万能工具——当其他工具无法满足需求时，"
                "你可以自己编写 Python 代码来解决。支持：数据处理、文件格式转换、图片处理、"
                "数学计算、文本处理、网络请求等。代码在隔离环境中执行。"
                "注意：可用的 pip 包包括 numpy, pandas, requests, Pillow, matplotlib 等。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "language": {
                        "type": "string",
                        "enum": ["python", "javascript", "bash"],
                        "description": "代码语言",
                    },
                    "code": {
                        "type": "string",
                        "description": "要执行的代码。Python 代码应有明确的 print() 输出结果。",
                    },
                    "description": {
                        "type": "string",
                        "description": "用一句话描述这段代码要做什么（帮助调试）",
                    },
                },
                "required": ["language", "code"],
            },
        },
    },
    # ==================== 新增：Shell 执行 ====================
    {
        "type": "function",
        "function": {
            "name": "shell_exec",
            "description": (
                "在本地系统执行 shell 命令。用于需要直接操作系统能力的场景："
                "安装软件、系统管理、文件批量操作、调用本地程序等。"
                "危险操作（rm/sudo/mv 系统目录）会被自动拦截。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "要执行的 shell 命令",
                    },
                    "description": {
                        "type": "string",
                        "description": "用一句话描述这个命令要做什么",
                    },
                },
                "required": ["command"],
            },
        },
    },
]

# System prompt
SYSTEM_PROMPT = """你是 LocalCommandCenter 助手，一个强大的本地系统 Agent。

## 核心能力（8 个工具）

### 基础工具（高频操作，直接调用）
1. **local_task_manager** — 任务管理：添加/删除/完成/查询单个任务
2. **batch_task_manager** — 批量任务编排：用户一次给多项任务时使用
   - **重要流程**：先 action=preview → 展示讨论结果 → 用户确认 → action=create
   - 支持自然语言日期：用户说"3月22日"，你转为 "3月22日" 即可（后端自动解析）
3. **local_safe_downloader** — 安全下载：URL → 本地文件，自动分类归档
4. **local_file_search** — 文件检索：搜索本地已下载文件
5. **local_sandbox_executor** — Docker 沙盒：在容器中运行 python/node/ffmpeg/pandoc
6. **local_job_status** — 异步任务状态查询

### 高级工具（万能能力）
7. **code_interpreter** — 代码执行器：你可以自己编写 Python/JS/Bash 代码来解决任何问题。
   - 数据处理、格式转换、数学计算、图片处理、文本分析、网络爬虫……
   - 当用户的需求无法用其他工具满足时，自己写代码解决
   - 代码中用 print() 输出关键结果
   - 安装包用 subprocess: `subprocess.run(["pip","install","xxx"], capture_output=True)`

8. **shell_exec** — 本地 Shell：直接在宿主机执行命令
   - 用于系统管理、软件安装、文件操作等需要本地环境的场景
   - 危险命令（rm -rf /、sudo）会被自动拦截

## 🎭 双角色讨论机制（任务编排专用）

当用户给你一堆任务时，你必须分饰两角进行**内部讨论**，然后把讨论结果呈现给用户确认。

### 角色 A：规划者 🎯
- 分析任务清单，识别任务类型、依赖关系、优先级
- 按时间线排列，发现日期冲突和过载问题
- **关键：使用 `batch_task_manager(action=preview)` 返回的 `daily_plan` 和 `daily_timeline` 数据**
- `daily_plan` 已按截止日反推起始日，将每个任务拆分到多个工作日
- 每个工作日有预估工时，超过 6h 标记为 overload
- 基于这些数据给出执行建议：哪些可以并行、哪些需要调整

### 角色 B：反思者 🤔
- 以用户视角审视规划者的方案
- 指出问题：某天工作量过重、没有休息日、任务间是否可以合并
- 关注**时间延续性**：任务不是截止日那天才做的，需要多天推进
- 提出改进：哪些任务可以提前开始、哪些需要更多天数
- 模拟用户可能担心的问题

### 输出格式（一次性完成，不要分多轮）

```
## 📋 任务规划分析

### 📅 每日工作分布（由系统自动计算）
[直接展示 daily_timeline 数据——每天的工时和任务]

### 🎯 规划者视角
[分析时间线、依赖关系、哪些天过载]

### 🤔 反思者质疑
[指出3-5个关键问题：工作量大、缺缓冲时间等]

### ✅ 优化后的方案
[经过讨论调整后的每日计划]

---
请确认是否按优化方案创建任务？如有调整请告诉我。
```

**重要**：
- 讨论要在**一次回复**中完成（用 `batch_task_manager(action=preview)` 获取解析结果后，在回复中完成讨论）
- 不要急着创建任务！先 preview → 讨论分析 → **等用户确认**
- 如果用户很忙只说了"直接加"或"确认"，才跳过讨论直接 create
- 讨论要真诚有用，不是走过场。真的要帮用户思考

## 工作原则

1. **先思考，再行动**：分析用户意图，选择最合适的工具
2. **批量任务编排流程**（非常重要！）：
   - 用户粘贴任务列表 → `batch_task_manager(action=preview)` 预览
   - 🎭 启动双角色讨论 → 在回复中展示分析和优化方案
   - **等用户说"确认"/"创建"** → `batch_task_manager(action=create)` 批量写入
3. **链式调用**：你可以连续多次调用不同工具来完成复杂任务。例如：
   - 用户说"下载论文并提取摘要" → download → code_interpreter(解析PDF)
   - 用户说"把这个 Excel 转成图表" → code_interpreter(pandas+matplotlib)
4. **自力更生**：当没有现成工具时，用 code_interpreter 自己写代码解决
5. **安全优先**：不执行危险操作，不泄露敏感信息
6. **简洁回复**：用中文，直击要点（但任务编排时要充分讨论）

## 时间格式
所有时间参数使用 ISO 8601 格式，如 2026-04-22T15:00:00+08:00
"""

# ============================================================
# 核心对话逻辑
# ============================================================

# 对话历史（内存存储，限制 TTL）
_conversations: dict[str, list[dict]] = {}
_conversation_timestamps: dict[str, float] = {}
_MAX_CONVERSATIONS = 50
_CONVERSATION_TTL = 7200  # 2小时无活动自动清理


def _cleanup_old_conversations():
    """清理过期或超量对话历史"""
    import time as _time
    now = _time.time()
    # 清理过期
    expired = [k for k, v in _conversation_timestamps.items() if now - v > _CONVERSATION_TTL]
    for k in expired:
        _conversations.pop(k, None)
        del _conversation_timestamps[k]
    # LRU: 如果仍然过多，删除最早的
    if len(_conversations) > _MAX_CONVERSATIONS:
        sorted_keys = sorted(_conversation_timestamps, key=_conversation_timestamps.get)
        for k in sorted_keys[: len(_conversations) - _MAX_CONVERSATIONS]:
            _conversations.pop(k, None)
            del _conversation_timestamps[k]


async def chat(user_message: str, conversation_id: str = "default") -> dict:
    """
    处理用户消息：
    1. 添加到对话历史
    2. 调用 AI API
    3. 如果 AI 返回 tool_call，执行对应工具
    4. 将工具结果返回给 AI 继续对话
    5. 返回最终回复
    """
    if not ai_config.api_key:
        return {
            "status": "error",
            "message": "AI API Key 未配置。请在 AI 助手中点击⚙️配置。",
            "reply": "⚠️ AI 功能未启用。请点击右下角 🤖 打开 AI 助手，然后点击 ⚙️ 按钮配置 API Key。",
        }

    # 初始化对话历史
    if conversation_id not in _conversations:
        _conversations[conversation_id] = [
            {"role": "system", "content": SYSTEM_PROMPT},
        ]
    
    import time as _time
    _conversation_timestamps[conversation_id] = _time.time()
    _cleanup_old_conversations()

    history = _conversations[conversation_id]
    history.append({"role": "user", "content": user_message})

    # 限制历史长度（保留最近 20 轮）
    if len(history) > 42:
        history[:] = [history[0]] + history[-40:]

    # 保存用户消息到本地
    _save_conversation_message(conversation_id, "user", user_message)

    try:
        # Agentic Loop: LLM 自主规划 → 调用工具 → 观察结果 → 继续或回答
        # 最多 15 轮 tool calling（支持复杂多步任务）
        for step in range(15):
            ai_response = await _call_ai(history)

            if not ai_response:
                return {"status": "error", "reply": "AI 服务无响应，请稍后重试。"}

            choice = ai_response.get("choices", [{}])[0]
            message = choice.get("message", {})

            # 如果没有 tool_calls，直接返回
            if not message.get("tool_calls"):
                reply = message.get("content", "")
                history.append({"role": "assistant", "content": reply})
                _save_conversation_message(conversation_id, "assistant", reply, model=ai_config.model)
                return {
                    "status": "success",
                    "reply": reply,
                }

            # 处理 tool calls
            # 确保message有role字段且tool_calls格式正确
            # API要求tool_calls必须包含type="function"
            tool_calls_fixed = []
            for i, tc in enumerate(message.get("tool_calls", [])):
                # 严格验证和修复每个字段
                tc_id = tc.get("id", "")
                if not tc_id or not isinstance(tc_id, str):
                    tc_id = f"call_{step}_{i}"

                # type 必须明确为 "function"，不能是空字符串或其他值
                tc_type = tc.get("type", "")
                if tc_type != "function":
                    tc_type = "function"

                # 确保function对象存在且有name和arguments
                fn = tc.get("function", {}) or {}
                fn_name = fn.get("name", "") if isinstance(fn, dict) else ""
                fn_args = fn.get("arguments", "") if isinstance(fn, dict) else "{}"

                if not fn_name:
                    logger.warning(f"Skipping tool_call without name: {tc}")
                    continue

                tool_calls_fixed.append({
                    "id": tc_id,
                    "type": tc_type,  # 必须是 "function"
                    "function": {
                        "name": fn_name,
                        "arguments": fn_args if fn_args else "{}"
                    }
                })

            if not tool_calls_fixed:
                logger.error("No valid tool_calls found in message")
                break

            tool_message = {
                "role": "assistant",
                "content": message.get("content") if message.get("content") else "",
                "tool_calls": tool_calls_fixed
            }
            history.append(tool_message)

            logger.debug(f"Added assistant message with {len(tool_calls_fixed)} tool_calls")

            for tool_call in tool_message["tool_calls"]:
                fn_name = tool_call["function"]["name"]
                fn_args_str = tool_call["function"]["arguments"]

                try:
                    fn_args = json.loads(fn_args_str)
                except json.JSONDecodeError:
                    fn_args = {}

                # 审计日志：记录所有高危操作
                if fn_name in ("code_interpreter", "shell_exec"):
                    logger.warning(
                        f"AUDIT: conv={conversation_id} step={step+1} "
                        f"tool={fn_name} args_preview={str(fn_args)[:200]}"
                    )

                # 执行工具
                tool_result = await _execute_tool(fn_name, fn_args)

                # 将结果加入历史
                history.append({
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": json.dumps(tool_result, ensure_ascii=False),
                })

        # 超过循环次数 — 汇总已完成的步骤
        return {"status": "success", "reply": "已完成多步操作的主要部分。如需继续，请告诉我下一步。"}

    except httpx.ConnectError:
        return {"status": "error", "reply": "无法连接 AI 服务，请检查网络。"}
    except Exception as e:
        logger.exception("AI 对话异常")
        return {"status": "error", "reply": f"AI 服务异常: {e}"}




def _validate_messages(messages: list[dict]) -> list[dict]:
    """验证并修复消息格式，确保 tool_calls 符合 API 要求"""
    validated = []
    for idx, msg in enumerate(messages):
        msg = dict(msg)  # Copy to avoid modifying original

        # Validate role field
        role = msg.get("role", "")
        if not role:
            msg["role"] = "assistant"

        # Fix tool_calls if present (only for assistant role)
        if role == "assistant" and msg.get("tool_calls"):
            fixed_tool_calls = []
            for i, tc in enumerate(msg["tool_calls"]):
                if not tc:
                    continue

                tc = dict(tc) if tc else {}

                # Ensure id exists and is valid string
                tc_id = tc.get("id", "")
                if not tc_id or not isinstance(tc_id, str) or not tc_id.strip():
                    tc_id = f"call_val_{idx}_{i}"
                tc["id"] = tc_id

                # Ensure type is EXACTLY "function" - CRITICAL!
                tc_type = tc.get("type")
                if tc_type != "function":
                    tc["type"] = "function"

                # Ensure function object exists with required fields
                fn = tc.get("function") or {}
                if not isinstance(fn, dict):
                    fn = {}
                tc["function"] = {
                    "name": fn.get("name") if isinstance(fn.get("name"), str) else "unknown",
                    "arguments": fn.get("arguments") if isinstance(fn.get("arguments"), str) else "{}"
                }

                fixed_tool_calls.append(tc)

            msg["tool_calls"] = fixed_tool_calls

        validated.append(msg)

    # Final pass: ensure ALL tool_calls have type="function"
    for msg in validated:
        if msg.get("role") == "assistant" and msg.get("tool_calls"):
            for tc in msg["tool_calls"]:
                if tc.get("type") != "function":
                    tc["type"] = "function"

    return validated


async def _call_ai(messages: list[dict]) -> Optional[dict]:
    """调用 AI API（OpenAI 兼容格式）"""
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{ai_config.api_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {ai_config.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": ai_config.model,
                    "messages": _validate_messages(messages),
                    "tools": TOOLS_SCHEMA,
                    "tool_choice": "auto",
                },
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as e:
        logger.error(f"AI API HTTP 错误: {e.response.status_code} {e.response.text[:500]}")
        return None
    except Exception as e:
        logger.error(f"AI API 调用失败: {e}")
        return None


async def _execute_tool(name: str, args: dict) -> dict:
    """通过 HTTP 调用本地网关的工具端点，或执行 code_interpreter/shell"""
    # Code Interpreter: 直接在本地 Python 子进程中执行
    if name == "code_interpreter":
        return await _execute_code_interpreter(args)

    # Shell Exec: 直接在本地 shell 中执行
    if name == "shell_exec":
        return await _execute_shell(args)

    tool_endpoint_map = {
        "local_task_manager": ("/api/task", "POST"),
        "batch_task_manager": ("/api/task/batch", "POST"),
        "local_safe_downloader": ("/api/download", "POST"),
        "local_file_search": ("/api/search", "POST"),
        "local_sandbox_executor": ("/api/sandbox", "POST"),
        "local_job_status": ("/api/job/status", "POST"),
    }

    if name not in tool_endpoint_map:
        return {"status": "error", "message": f"未知工具: {name}"}

    endpoint, method = tool_endpoint_map[name]
    url = f"{ai_config.gateway_base_url}{endpoint}"

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(url, json=args)
            return resp.json()
    except Exception as e:
        return {"status": "error", "message": f"工具调用失败: {e}"}


def clear_conversation(conversation_id: str = "default"):
    """清除对话历史"""
    if conversation_id in _conversations:
        del _conversations[conversation_id]


# ============================================================
# Code Interpreter — 本地子进程执行代码
# ============================================================

async def _execute_code_interpreter(args: dict) -> dict:
    """
    在子进程中执行 AI 生成的代码。
    Python 用本地 Python，JS/Node 用 node，bash 用 /bin/bash。
    工作目录为临时目录，超时保护。
    """
    language = args.get("language", "python")
    code = args.get("code", "")
    description = args.get("description", "")

    logger.info(f"Code Interpreter [{language}]: {description or code[:80]}...")

    if not code.strip():
        return {"status": "error", "stdout": "", "stderr": "代码为空", "exit_code": 1}

    # ⚠️ 安全扫描：检测危险代码模式（多层防护）
    if language == "python":
        code_lower = code.lower()

        # 1. 基础黑名单检查
        for dangerous in PYTHON_DANGEROUS_IMPORTS:
            if dangerous.lower() in code_lower:
                return {
                    "status": "error",
                    "stdout": "",
                    "stderr": f"⚠️ 安全拦截：代码包含受限操作 '{dangerous}'。不允许系统级操作。",
                    "exit_code": -1,
                    "blocked": True,
                }

        # 2. 高级绕过检测：检测字符串拼接导入
        import re
        # 检测 __import__('o'+'s') 或 __import__("os") 等形式
        if re.search(r"__import__\s*\([\"']", code_lower) or re.search(r"__import__\s*\([^)]+\+", code_lower):
            return {
                "status": "error",
                "stdout": "",
                "stderr": "⚠️ 安全拦截：检测到动态导入尝试。",
                "exit_code": -1,
                "blocked": True,
            }

        # 3. 检测 getattr 绕过
        if re.search(r"getattr\s*\([^)]+builtins", code_lower) or re.search(r"getattr\s*\([^)]+eval|exec", code_lower):
            return {
                "status": "error",
                "stdout": "",
                "stderr": "⚠️ 安全拦截：检测到 getattr 动态调用。",
                "exit_code": -1,
                "blocked": True,
            }

        # 4. 检测编码绕过（base64, hex等）
        if re.search(r"(base64|decode|encode).*exec|eval", code_lower):
            return {
                "status": "error",
                "stdout": "",
                "stderr": "⚠️ 安全拦截：检测到编码绕过尝试。",
                "exit_code": -1,
                "blocked": True,
            }

        # 5. 代码长度限制（防止内存攻击）
        if len(code) > 100000:  # 100KB限制
            return {
                "status": "error",
                "stdout": "",
                "stderr": "⚠️ 代码超过最大长度限制（100KB）。",
                "exit_code": -1,
                "blocked": True,
            }

    # 选择执行器
    exec_map = {
        "python": ("python3", ".py"),
        "javascript": ("node", ".js"),
        "bash": ("/bin/bash", ".sh"),
    }
    executor, suffix = exec_map.get(language, ("python3", ".py"))

    try:
        # 在临时目录中执行
        with tempfile.TemporaryDirectory(prefix="lcc_code_") as tmpdir:
            script_path = Path(tmpdir) / f"script{suffix}"
            script_path.write_text(code, encoding="utf-8")

            proc = await asyncio.create_subprocess_exec(
                executor, str(script_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=tmpdir,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=CODE_INTERPRETER_TIMEOUT
                )
            except asyncio.TimeoutError:
                proc.kill()
                return {
                    "status": "error",
                    "stdout": "",
                    "stderr": f"执行超时（{CODE_INTERPRETER_TIMEOUT}秒）",
                    "exit_code": -1,
                }

            stdout_str = stdout.decode("utf-8", errors="replace")
            stderr_str = stderr.decode("utf-8", errors="replace")

            # 截断过长输出
            max_len = 8000
            if len(stdout_str) > max_len:
                stdout_str = stdout_str[:max_len] + f"\n... (输出截断，共 {len(stdout_str)} 字符)"
            if len(stderr_str) > max_len:
                stderr_str = stderr_str[:max_len] + f"\n... (输出截断，共 {len(stderr_str)} 字符)"

            return {
                "status": "success" if proc.returncode == 0 else "error",
                "stdout": stdout_str,
                "stderr": stderr_str,
                "exit_code": proc.returncode,
                "language": language,
            }

    except FileNotFoundError:
        return {"status": "error", "stdout": "", "stderr": f"找不到 {executor}，请确保已安装", "exit_code": 127}
    except Exception as e:
        logger.exception("Code Interpreter 执行异常")
        return {"status": "error", "stdout": "", "stderr": str(e), "exit_code": 1}


# ============================================================
# Shell Exec — 本地 Shell 命令执行
# ============================================================

async def _execute_shell(args: dict) -> dict:
    """
    在本地执行命令，带严格安全检查。
    使用白名单机制，只允许特定安全命令。
    """
    import shlex
    command = args.get("command", "")
    description = args.get("description", "")

    logger.info(f"Shell Exec: {description or command[:80]}...")

    if not command or not command.strip():
        return {"status": "error", "stdout": "", "stderr": "命令为空", "exit_code": 1}

    # 解析命令为参数列表，避免shell注入
    try:
        cmd_list = shlex.split(command)
    except ValueError as e:
        return {"status": "error", "stdout": "", "stderr": f"命令解析失败: {e}", "exit_code": 1}

    if not cmd_list:
        return {"status": "error", "stdout": "", "stderr": "命令为空", "exit_code": 1}

    # 严格白名单：只允许这些命令
    # 安全原则：禁止任何可修改系统、提权、或访问敏感资源的命令
    ALLOWED_SHELL_COMMANDS = {
        # 文件查看（只读）
        'cat', 'head', 'tail', 'less', 'more', 'nl', 'wc', 'sort', 'uniq',
        # 目录列表（只读）
        'ls', 'll', 'dir', 'pwd', 'tree', 'find',
        # 系统信息（只读）
        'date', 'uptime', 'whoami', 'uname', 'hostname', 'env', 'printenv',
        # 文本处理
        'echo', 'grep', 'awk', 'sed', 'cut', 'tr', 'rev',
        # 压缩（只读解压）
        'tar', 'gzip', 'gunzip', 'zip', 'unzip', 'bzip2', 'xz',
        # 开发工具
        'git', 'python3', 'python', 'pip3', 'pip', 'node', 'npm',
        # 网络诊断（只读）
        'ping', 'dig', 'nslookup', 'netstat', 'ss',
        # 其他安全命令
        'which', 'whereis', 'file', 'stat', 'du', 'df', 'free', 'top', 'ps',
        'make', 'cmake', 'gcc', 'g++', 'javac', 'java', 'go', 'rustc',
    }

    base_cmd = cmd_list[0].split('/')[-1]  # 处理 /usr/bin/python3 这样的情况

    if base_cmd not in ALLOWED_SHELL_COMMANDS:
        logger.warning(f"Shell blocked non-whitelisted command: {base_cmd}")
        return {
            "status": "error",
            "stdout": "",
            "stderr": f"⚠️ 命令 '{base_cmd}' 不在允许列表中。如需执行其他命令，请使用 Docker 沙盒工具。",
            "exit_code": -1,
            "blocked": True,
        }

    # 黑名单二次检查（防止常见危险操作）
    cmd_lower = command.lower()
    DANGEROUS_PATTERNS = [
        'rm -rf /', 'rm -rf ~', 'rm -rf /*', 'mkfs', 'dd if=/dev/zero',
        ':(){:|:&};:', 'fork bomb',
        '> /etc/passwd', '> /etc/shadow',
        'chmod 777 /', 'chmod -R 777 /',
        'wget .*| *bash', 'curl .*| *sh', 'curl .*| *bash',
        r'\$\(', '`',  # 命令替换 $() 和反引号
    ]
    for pattern in DANGEROUS_PATTERNS:
        import re
        if re.search(pattern.replace('.*', '.*'), cmd_lower):
            logger.warning(f"Shell blocked dangerous pattern: {command[:100]}")
            return {
                "status": "error",
                "stdout": "",
                "stderr": "⚠️ 检测到危险命令模式，已拦截。",
                "exit_code": -1,
                "blocked": True,
            }

    logger.warning(f"Shell executing: {command[:200]}")

    try:
        # 使用 create_subprocess_exec 而不是 shell，更安全
        proc = await asyncio.create_subprocess_exec(
            *cmd_list,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=CODE_INTERPRETER_TIMEOUT
            )
        except asyncio.TimeoutError:
            proc.kill()
            return {
                "status": "error",
                "stdout": "",
                "stderr": f"执行超时（{CODE_INTERPRETER_TIMEOUT}秒）",
                "exit_code": -1,
            }

        stdout_str = stdout.decode("utf-8", errors="replace")
        stderr_str = stderr.decode("utf-8", errors="replace")

        # 截断过长输出
        max_len = 8000
        if len(stdout_str) > max_len:
            stdout_str = stdout_str[:max_len] + f"\n... (输出截断，共 {len(stdout_str)} 字符)"
        if len(stderr_str) > max_len:
            stderr_str = stderr_str[:max_len] + f"\n... (输出截断，共 {len(stderr_str)} 字符)"

        return {
            "status": "success" if proc.returncode == 0 else "error",
            "stdout": stdout_str,
            "stderr": stderr_str,
            "exit_code": proc.returncode,
        }

    except Exception as e:
        logger.exception("Shell 执行异常")
        return {"status": "error", "stdout": "", "stderr": str(e), "exit_code": 1}


async def test_connection(api_base: str = None, api_key: str = None, model: str = None) -> dict:
    """
    测试 AI API 连通性。
    使用传入的参数或当前动态配置。
    """
    base = api_base or ai_config.api_base
    key = api_key or ai_config.api_key
    mdl = model or ai_config.model

    if not key:
        return {"status": "error", "message": "API Key 为空", "reply": "❌ 请先填写 API Key"}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{base.rstrip('/')}/chat/completions",
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": mdl,
                    "messages": [{"role": "user", "content": "你好，请用一句话回复"}],
                    "max_tokens": 50,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            reply = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            return {
                "status": "success",
                "message": f"连接成功，模型: {mdl}",
                "reply": f"✅ 连接成功！\n模型: {mdl}\n回复: {reply[:100]}",
                "test_reply": reply,
            }
    except httpx.ConnectError:
        return {"status": "error", "message": "无法连接 API 地址", "reply": f"❌ 无法连接 {base}，请检查地址和网络"}
    except httpx.HTTPStatusError as e:
        detail = ""
        try:
            detail = e.response.json().get("error", {}).get("message", e.response.text[:200])
        except Exception:
            detail = e.response.text[:200]
        return {"status": "error", "message": f"HTTP {e.response.status_code}", "reply": f"❌ API 返回错误 ({e.response.status_code}): {detail}"}
    except Exception as e:
        return {"status": "error", "message": str(e), "reply": f"❌ 测试失败: {e}"}


# ============================================================
# 流式对话 — SSE + thinking/reasoning_content 支持
# ============================================================

import json as _json
from starlette.responses import StreamingResponse as _StreamingResponse


async def chat_stream(user_message: str, conversation_id: str = "default"):
    """
    流式 AI 对话，以 SSE 格式推送事件：
      - event: model       → 当前使用的模型
      - event: thinking    → 推理/思考内容 (DeepSeek reasoning_content)
      - event: content     → 正式回复内容
      - event: tool_call   → 工具调用
      - event: tool_result → 工具执行结果
      - event: done        → 完成
      - event: error       → 错误
    """
    def sse(event: str, data: dict):
        return f"event: {event}\ndata: {_json.dumps(data, ensure_ascii=False)}\n\n"

    if not ai_config.api_key:
        yield sse("error", {"message": "AI API Key 未配置"})
        return

    # 初始化对话历史
    if conversation_id not in _conversations:
        _conversations[conversation_id] = [
            {"role": "system", "content": SYSTEM_PROMPT},
        ]

    import time as _time
    _conversation_timestamps[conversation_id] = _time.time()
    _cleanup_old_conversations()

    history = _conversations[conversation_id]
    history.append({"role": "user", "content": user_message})

    if len(history) > 42:
        history[:] = [history[0]] + history[-40:]

    # 保存用户消息到本地
    _save_conversation_message(conversation_id, "user", user_message)

    # 发送模型信息
    yield sse("model", {"model": ai_config.model, "provider": "DeepSeek" if "deepseek" in ai_config.api_base else "Other"})

    try:
        for step in range(15):
            # 流式调用 AI
            thinking_text = ""
            content_text = ""
            tool_calls_list = []
            current_tool_calls = {}  # id -> {id, function: {name, arguments}}

            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream(
                    "POST",
                    f"{ai_config.api_base}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {ai_config.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": ai_config.model,
                        "messages": _validate_messages(history),
                        "tools": TOOLS_SCHEMA,
                        "tool_choice": "auto",
                        "stream": True,
                    },
                ) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        line = line.strip()
                        if not line or not line.startswith("data:"):
                            continue
                        payload = line[5:].strip()
                        if payload == "[DONE]":
                            break

                        try:
                            chunk = _json.loads(payload)
                        except _json.JSONDecodeError:
                            continue

                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        if not delta:
                            continue

                        # 处理 reasoning_content (DeepSeek thinking)
                        rc = delta.get("reasoning_content")
                        if rc:
                            thinking_text += rc
                            yield sse("thinking", {"content": rc})

                        # 处理正式 content
                        c = delta.get("content")
                        if c:
                            content_text += c
                            yield sse("content", {"content": c})

                        # 处理 tool_calls (流式增量)
                        tcs = delta.get("tool_calls")
                        if tcs:
                            for tc in tcs:
                                tc_id = tc.get("id", "")
                                tc_idx = tc.get("index", len(current_tool_calls))

                                if tc_id:
                                    # 新 tool call 开始
                                    current_tool_calls[tc_idx] = {
                                        "id": tc_id,
                                        "type": "function",
                                        "function": {
                                            "name": tc.get("function", {}).get("name", ""),
                                            "arguments": tc.get("function", {}).get("arguments", ""),
                                        },
                                    }
                                elif tc_idx in current_tool_calls:
                                    # 增量 arguments
                                    fn_delta = tc.get("function", {})
                                    if fn_delta.get("arguments"):
                                        current_tool_calls[tc_idx]["function"]["arguments"] += fn_delta["arguments"]
                                    if fn_delta.get("name"):
                                        current_tool_calls[tc_idx]["function"]["name"] += fn_delta["name"]

            # 整理 tool_calls
            tool_calls_list = list(current_tool_calls.values())

            if not tool_calls_list:
                # 无工具调用，直接返回
                reply = content_text
                history.append({"role": "assistant", "content": reply})

                # 保存到对话记录
                _save_conversation_message(conversation_id, "assistant", reply, thinking=thinking_text)

                yield sse("done", {"reply": reply, "thinking": thinking_text})
                return

            # 有工具调用
            tool_message = {
                "role": "assistant",
                "content": content_text if content_text else "",
                "tool_calls": tool_calls_list,
            }
            history.append(tool_message)

            # 执行工具
            for tc in tool_calls_list:
                fn_name = tc["function"]["name"]
                fn_args_str = tc["function"]["arguments"]

                yield sse("tool_call", {
                    "name": fn_name,
                    "arguments": fn_args_str,
                    "id": tc["id"],
                })

                try:
                    fn_args = _json.loads(fn_args_str)
                except _json.JSONDecodeError:
                    fn_args = {}

                tool_result = await _execute_tool(fn_name, fn_args)

                yield sse("tool_result", {
                    "name": fn_name,
                    "result": tool_result,
                })

                history.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": _json.dumps(tool_result, ensure_ascii=False),
                })

            # 继续循环让 AI 处理工具结果

        # 超出循环
        yield sse("done", {"reply": content_text or "已完成多步操作。", "thinking": thinking_text})

    except httpx.ConnectError:
        yield sse("error", {"message": "无法连接 AI 服务"})
    except Exception as e:
        logger.exception("流式 AI 对话异常")
        yield sse("error", {"message": str(e)})


def _save_conversation_message(conversation_id: str, role: str, content: str, thinking: str = "", model: str = ""):
    """保存对话消息到本地文件"""
    import time
    from config import BASE_DIR

    conv_dir = BASE_DIR / "data" / "conversations"
    conv_dir.mkdir(parents=True, exist_ok=True)

    msg = {
        "id": str(int(time.time() * 1000)),
        "role": role,
        "content": content,
        "thinking": thinking,
        "model": model or ai_config.model,
        "timestamp": time.time(),
    }

    conv_file = conv_dir / f"{conversation_id}.jsonl"
    with open(conv_file, "a", encoding="utf-8") as f:
        f.write(_json.dumps(msg, ensure_ascii=False) + "\n")
