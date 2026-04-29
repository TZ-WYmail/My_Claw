"""
AI 智能规划服务 — 任务拆解、智能建议、时间估算
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Optional

import httpx

from config import ai_config
from services import task_service

logger = logging.getLogger(__name__)


async def decompose_task(task_name: str, description: str = None) -> dict:
    """
    使用 AI 将复杂任务拆解为子任务
    """
    if not ai_config.api_key:
        return {
            "status": "error",
            "message": "AI API Key 未配置",
        }

    prompt = f"""请将以下任务拆解为具体的子任务列表。

任务名称: {task_name}
任务描述: {description or "无"}

要求:
1. 将任务拆解为 3-8 个可执行的子任务
2. 每个子任务应有明确的名称和预估完成时间（分钟）
3. 子任务之间有逻辑顺序，标明依赖关系
4. 返回 JSON 格式

返回格式:
{{
    "subtasks": [
        {{
            "name": "子任务名称",
            "estimated_minutes": 30,
            "description": "子任务描述",
            "depends_on": []  // 依赖的子任务索引（空表示无依赖）
        }}
    ],
    "total_estimated_minutes": 120,
    "difficulty": "easy|medium|hard",
    "tips": ["执行建议1", "执行建议2"]
}}
"""

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
                    "messages": [
                        {"role": "system", "content": "你是一个任务规划专家，擅长将复杂任务拆解为可执行的子任务。"},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.3,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]

            # 提取 JSON
            try:
                # 尝试直接解析
                result = json.loads(content)
            except json.JSONDecodeError:
                # 尝试从 markdown 代码块中提取
                import re
                json_match = re.search(r'```json\n(.*?)\n```', content, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group(1))
                else:
                    # 尝试从文本中提取 JSON
                    json_match = re.search(r'\{.*\}', content, re.DOTALL)
                    if json_match:
                        result = json.loads(json_match.group())
                    else:
                        raise ValueError("无法解析 AI 响应")

            return {
                "status": "success",
                "decomposition": result,
            }

    except Exception as e:
        logger.exception("AI 任务拆解失败")
        return {
            "status": "error",
            "message": f"AI 任务拆解失败: {e}",
        }


async def generate_task_plan(tasks: list[dict], constraints: dict = None) -> dict:
    """
    基于任务列表和约束条件生成优化的时间安排
    """
    if not ai_config.api_key:
        return {
            "status": "error",
            "message": "AI API Key 未配置",
        }

    tasks_str = json.dumps(tasks, ensure_ascii=False, indent=2)
    constraints_str = json.dumps(constraints or {}, ensure_ascii=False, indent=2)

    prompt = f"""作为时间管理专家，请为以下任务制定最优执行计划。

待规划任务:
{tasks_str}

约束条件:
{constraints_str}

要求:
1. 考虑任务优先级和截止日期
2. 合理安排每日工作量（不超过6小时/天）
3. 为高优先级任务预留缓冲时间
4. 识别可以并行处理的任务
5. 返回详细的每日计划

返回 JSON 格式:
{{
    "daily_plans": [
        {{
            "date": "2026-04-22",
            "total_hours": 5.5,
            "tasks": [
                {{
                    "task_name": "任务名",
                    "allocated_hours": 2,
                    "time_slot": "09:00-11:00",
                    "notes": "执行建议"
                }}
            ]
        }}
    ],
    "parallel_groups": [["任务1", "任务2"]],  // 可并行任务
    "risk_warnings": ["风险提示"],
    "optimization_tips": ["优化建议"]
}}
"""

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
                    "messages": [
                        {"role": "system", "content": "你是时间管理专家，擅长制定高效的任务执行计划。"},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.3,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]

            # 提取 JSON
            try:
                result = json.loads(content)
            except json.JSONDecodeError:
                import re
                json_match = re.search(r'```json\n(.*?)\n```', content, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group(1))
                else:
                    json_match = re.search(r'\{.*\}', content, re.DOTALL)
                    if json_match:
                        result = json.loads(json_match.group())
                    else:
                        raise ValueError("无法解析 AI 响应")

            return {
                "status": "success",
                "plan": result,
            }

    except Exception as e:
        logger.exception("AI 计划生成失败")
        return {
            "status": "error",
            "message": f"AI 计划生成失败: {e}",
        }


async def estimate_task_time(task_name: str, description: str = None, category: str = None) -> dict:
    """
    基于历史数据和AI分析估算任务完成时间
    """
    # 先查询历史相似任务
    historical_data = await _get_historical_task_data(task_name, category)

    if not ai_config.api_key:
        # 使用历史数据估算
        if historical_data:
            avg_time = sum(h["estimated_minutes"] for h in historical_data) / len(historical_data)
            return {
                "status": "success",
                "estimated_minutes": int(avg_time),
                "source": "historical",
                "confidence": "medium",
                "based_on": len(historical_data),
            }
        return {
            "status": "success",
            "estimated_minutes": 60,
            "source": "default",
            "confidence": "low",
        }

    historical_str = json.dumps(historical_data, ensure_ascii=False, indent=2)

    prompt = f"""请估算以下任务的完成时间。

任务名称: {task_name}
任务描述: {description or "无"}
任务类别: {category or "未分类"}

历史相似任务数据:
{historical_str}

要求:
1. 综合考虑任务复杂度、历史数据和常见工作模式
2. 给出乐观、正常、悲观三种估算
3. 返回 JSON 格式

返回格式:
{{
    "estimated_minutes": 120,
    "optimistic": 90,
    "pessimistic": 180,
    "confidence": "high|medium|low",
    "reasoning": "估算理由...",
    "factors": ["影响因素1", "影响因素2"]
}}
"""

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{ai_config.api_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {ai_config.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": ai_config.model,
                    "messages": [
                        {"role": "system", "content": "你是项目管理专家，擅长估算任务完成时间。"},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.2,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]

            try:
                result = json.loads(content)
            except json.JSONDecodeError:
                import re
                json_match = re.search(r'```json\n(.*?)\n```', content, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group(1))
                else:
                    json_match = re.search(r'\{.*\}', content, re.DOTALL)
                    if json_match:
                        result = json.loads(json_match.group())
                    else:
                        raise ValueError("无法解析 AI 响应")

            result["source"] = "ai"
            return {
                "status": "success",
                "estimation": result,
            }

    except Exception as e:
        logger.exception("AI 时间估算失败")
        # 回退到历史数据
        if historical_data:
            avg_time = sum(h["estimated_minutes"] for h in historical_data) / len(historical_data)
            return {
                "status": "success",
                "estimated_minutes": int(avg_time),
                "source": "historical_fallback",
                "confidence": "medium",
            }
        return {
            "status": "error",
            "message": f"AI 时间估算失败: {e}",
        }


async def _get_historical_task_data(task_name: str, category: str = None) -> list[dict]:
    """获取历史相似任务数据"""
    # 从数据库查询已完成的任务
    result = await task_service.get_all_tasks(
        status_filter="completed",
        keyword=task_name.split()[0] if task_name else "",
        page=1,
        page_size=10,
    )

    historical = []
    for task in result.get("tasks", []):
        if task.get("estimated_minutes"):
            historical.append({
                "task_name": task["task_name"],
                "estimated_minutes": task["estimated_minutes"],
                "created_at": task.get("created_at"),
            })

    return historical


async def get_smart_suggestions(user_context: dict = None) -> dict:
    """
    基于当前任务状态提供智能建议
    """
    # 获取当前任务状态
    weekly_plan = await task_service.get_weekly_plan()
    pending_tasks = [t for t in weekly_plan.get("tasks", []) if t["status"] == "待执行"]

    # 获取番茄钟统计
    pomodoro_stats = await task_service.get_pomodoro_stats()

    suggestions = []

    # 分析任务优先级分布
    urgent_count = sum(1 for t in pending_tasks if t.get("priority", 2) == 0)
    high_count = sum(1 for t in pending_tasks if t.get("priority", 2) == 1)

    if urgent_count > 0:
        suggestions.append({
            "type": "urgent",
            "priority": "high",
            "message": f"有 {urgent_count} 个紧急任务需要立即处理",
            "action": "查看紧急任务",
        })

    if high_count > 3:
        suggestions.append({
            "type": "warning",
            "priority": "medium",
            "message": "高优先级任务较多，建议重新评估优先级",
            "action": "调整优先级",
        })

    # 番茄钟专注度分析
    today_minutes = pomodoro_stats.get("today_minutes", 0)
    if today_minutes < 60:
        suggestions.append({
            "type": "tip",
            "priority": "low",
            "message": "今日专注时间较短，建议开启番茄钟提升效率",
            "action": "开始番茄钟",
        })

    # 截止日期提醒
    now = datetime.now()
    for task in pending_tasks:
        try:
            due = datetime.fromisoformat(task["due_time"].replace("Z", "+00:00"))
            if (due - now).days <= 1:
                suggestions.append({
                    "type": "deadline",
                    "priority": "high",
                    "message": f"任务 '{task['task_name']}' 即将到期",
                    "action": "立即处理",
                    "task_id": task["task_id"],
                })
        except:
            pass

    # 工作负载平衡建议
    if len(pending_tasks) > 10:
        suggestions.append({
            "type": "workload",
            "priority": "medium",
            "message": f"本周有 {len(pending_tasks)} 个待办任务，建议拆分或推迟部分任务",
            "action": "重新规划",
        })

    return {
        "status": "success",
        "suggestions": suggestions,
        "stats": {
            "pending_count": len(pending_tasks),
            "urgent_count": urgent_count,
            "high_count": high_count,
            "today_focus_minutes": today_minutes,
        },
    }


async def analyze_task_patterns() -> dict:
    """
    分析用户任务完成模式，提供效率洞察
    """
    # 获取所有任务
    all_tasks = await task_service.get_all_tasks(
        status_filter="completed",
        page=1,
        page_size=100,
    )

    completed_tasks = all_tasks.get("tasks", [])

    if len(completed_tasks) < 5:
        return {
            "status": "success",
            "message": "数据不足，请继续使用以生成分析报告",
            "insights": [],
        }

    # 分析完成时间分布
    weekday_counts = {i: 0 for i in range(7)}
    hour_counts = {i: 0 for i in range(24)}

    for task in completed_tasks:
        try:
            created = datetime.fromisoformat(task.get("created_at", "").replace("Z", "+00:00"))
            weekday_counts[created.weekday()] += 1
            hour_counts[created.hour] += 1
        except:
            pass

    # 找出最高效的时间段
    best_weekday = max(weekday_counts, key=weekday_counts.get)
    best_hour = max(hour_counts, key=hour_counts.get)

    weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

    insights = [
        {
            "type": "pattern",
            "title": "高效时间段",
            "description": f"你在 {weekdays[best_weekday]} {best_hour}:00 左右完成任务最多",
            "recommendation": "建议将重要任务安排在这个时间段",
        },
        {
            "type": "stats",
            "title": "任务完成统计",
            "description": f"已完成 {len(completed_tasks)} 个任务",
            "details": {
                "avg_per_day": round(len(completed_tasks) / 7, 1),
                "most_productive_day": weekdays[best_weekday],
            },
        },
    ]

    return {
        "status": "success",
        "insights": insights,
        "weekday_distribution": weekday_counts,
        "hour_distribution": hour_counts,
    }
