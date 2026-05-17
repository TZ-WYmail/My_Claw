"""
工作流引擎 — 自动化工作流
支持触发器-动作模式
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Callable, Optional

from config import BASE_DIR
from services.security_service import (
    execute_validated_local_command,
)

logger = logging.getLogger(__name__)

# 工作流存储
WORKFLOW_FILE = BASE_DIR / "data" / "workflows.json"
WORKFLOW_EXECUTION_FILE = BASE_DIR / "data" / "workflow_executions.json"


# 触发器类型
TRIGGER_TYPES = {
    "schedule": "定时触发",
    "task_completed": "任务完成",
    "task_created": "任务创建",
    "habit_checkin": "习惯打卡",
    "download_completed": "下载完成",
    "webhook": "Webhook 接收",
    "startup": "系统启动",
}

# 动作类型
ACTION_TYPES = {
    "create_task": "创建任务",
    "complete_task": "完成任务",
    "send_webhook": "发送 Webhook",
    "exec_command": "执行命令",
    "create_note": "创建笔记",
    "checkin_habit": "习惯打卡",
    "send_notification": "发送通知",
    "delay": "延迟等待",
}


class WorkflowEngine:
    """工作流引擎"""

    def __init__(self):
        self.workflows = {}
        self.executions = []
        self._running = False
        self._scheduler_task = None
        self._load()

    def _load(self):
        """加载工作流"""
        try:
            if WORKFLOW_FILE.exists():
                with open(WORKFLOW_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.workflows = data.get("workflows", {})

            if WORKFLOW_EXECUTION_FILE.exists():
                with open(WORKFLOW_EXECUTION_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.executions = data.get("executions", [])
        except Exception as e:
            logger.warning(f"加载工作流失败: {e}")

    def save(self):
        """保存工作流"""
        try:
            WORKFLOW_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(WORKFLOW_FILE, "w", encoding="utf-8") as f:
                json.dump({"workflows": self.workflows}, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"保存工作流失败: {e}")
            return False

    def save_executions(self):
        """保存执行记录"""
        try:
            WORKFLOW_EXECUTION_FILE.parent.mkdir(parents=True, exist_ok=True)
            # 只保留最近 500 条
            executions_to_save = self.executions[-500:]
            with open(WORKFLOW_EXECUTION_FILE, "w", encoding="utf-8") as f:
                json.dump({"executions": executions_to_save}, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"保存执行记录失败: {e}")
            return False

    def create(
        self,
        name: str,
        trigger: dict,
        actions: list[dict],
        description: str = "",
        enabled: bool = True,
    ) -> dict:
        """创建工作流"""
        workflow_id = f"wf_{uuid.uuid4().hex[:12]}"

        workflow = {
            "id": workflow_id,
            "name": name,
            "description": description,
            "trigger": trigger,
            "actions": actions,
            "enabled": enabled,
            "created_at": datetime.now().isoformat(),
            "execution_count": 0,
            "last_execution": None,
        }

        self.workflows[workflow_id] = workflow
        self.save()

        return {
            "status": "success",
            "workflow_id": workflow_id,
            "workflow": workflow,
        }

    def delete(self, workflow_id: str) -> dict:
        """删除工作流"""
        if workflow_id not in self.workflows:
            return {"status": "error", "message": f"工作流 {workflow_id} 不存在"}

        del self.workflows[workflow_id]
        self.save()

        return {"status": "success", "message": f"工作流 {workflow_id} 已删除"}

    def get(self, workflow_id: str = None) -> dict:
        """获取工作流"""
        if workflow_id:
            if workflow_id not in self.workflows:
                return {"status": "error", "message": f"工作流 {workflow_id} 不存在"}
            return {
                "status": "success",
                "workflow": self.workflows[workflow_id],
            }

        return {
            "status": "success",
            "workflows": list(self.workflows.values()),
            "total": len(self.workflows),
        }

    def toggle(self, workflow_id: str, enabled: bool) -> dict:
        """启用/禁用工作流"""
        if workflow_id not in self.workflows:
            return {"status": "error", "message": f"工作流 {workflow_id} 不存在"}

        self.workflows[workflow_id]["enabled"] = enabled
        self.save()

        return {
            "status": "success",
            "message": f"工作流 {workflow_id} 已{'启用' if enabled else '禁用'}",
        }

    async def trigger(self, trigger_type: str, context: dict = None) -> list[dict]:
        """触发工作流"""
        context = context or {}
        results = []

        for workflow_id, workflow in self.workflows.items():
            if not workflow.get("enabled", True):
                continue

            trigger = workflow.get("trigger", {})
            if trigger.get("type") != trigger_type:
                continue

            # 检查触发条件
            if not self._check_trigger_condition(trigger, context):
                continue

            # 执行工作流
            result = await self.execute(workflow_id, context)
            results.append(result)

        return results

    def _check_trigger_condition(self, trigger: dict, context: dict) -> bool:
        """检查触发条件"""
        conditions = trigger.get("conditions", {})

        for key, expected in conditions.items():
            actual = context.get(key)
            if actual != expected:
                return False

        return True

    async def execute(self, workflow_id: str, context: dict = None) -> dict:
        """执行工作流"""
        if workflow_id not in self.workflows:
            return {"status": "error", "message": f"工作流 {workflow_id} 不存在"}

        workflow = self.workflows[workflow_id]
        context = context or {}

        execution_id = f"exec_{uuid.uuid4().hex[:8]}"
        execution = {
            "id": execution_id,
            "workflow_id": workflow_id,
            "workflow_name": workflow["name"],
            "started_at": datetime.now().isoformat(),
            "status": "running",
            "results": [],
        }

        logger.info(f"开始执行工作流 {workflow_id}: {workflow['name']}")

        try:
            for i, action in enumerate(workflow.get("actions", [])):
                action_type = action.get("type")
                action_config = action.get("config", {})

                # 替换模板变量
                action_config = self._render_template(action_config, context)

                # 执行动作
                result = await self._execute_action(action_type, action_config)

                execution["results"].append({
                    "step": i + 1,
                    "action": action_type,
                    "status": result.get("status"),
                    "result": result,
                })

                if result.get("status") == "error":
                    execution["status"] = "failed"
                    break

                # 更新上下文
                context[f"step_{i+1}_result"] = result

            else:
                execution["status"] = "completed"

        except Exception as e:
            logger.exception(f"工作流执行失败 {workflow_id}")
            execution["status"] = "error"
            execution["error"] = str(e)

        execution["ended_at"] = datetime.now().isoformat()

        # 更新统计
        workflow["execution_count"] = workflow.get("execution_count", 0) + 1
        workflow["last_execution"] = execution["ended_at"]
        self.save()

        # 保存执行记录
        self.executions.append(execution)
        self.save_executions()

        return {
            "status": "success",
            "execution": execution,
        }

    def _render_template(self, config: dict, context: dict) -> dict:
        """渲染模板变量"""
        result = {}
        for key, value in config.items():
            if isinstance(value, str):
                # 替换 {{variable}} 格式
                for ctx_key, ctx_value in context.items():
                    placeholder = "{{" + ctx_key + "}}"
                    if placeholder in value:
                        value = value.replace(placeholder, str(ctx_value))
                result[key] = value
            elif isinstance(value, dict):
                result[key] = self._render_template(value, context)
            elif isinstance(value, list):
                result[key] = [
                    self._render_template(item, context) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                result[key] = value
        return result

    async def _execute_action(self, action_type: str, config: dict) -> dict:
        """执行单个动作"""
        from services import task_service
        from services import habit_service
        from services import note_service
        from services.webhook_service import send_webhook

        try:
            if action_type == "create_task":
                return await task_service.add_task(
                    task_name=config.get("task_name", "自动任务"),
                    due_time=config.get("due_time", datetime.now().isoformat()),
                    description=config.get("description"),
                    priority=config.get("priority", 2),
                    tags=config.get("tags", []),
                )

            elif action_type == "complete_task":
                return await task_service.complete_task(config.get("task_id"))

            elif action_type == "create_note":
                return await note_service.create_note(
                    title=config.get("title", "自动笔记"),
                    content=config.get("content", ""),
                    tags=config.get("tags", []),
                )

            elif action_type == "checkin_habit":
                return await habit_service.checkin_habit(
                    config.get("habit_id"),
                    count=config.get("count", 1),
                )

            elif action_type == "send_webhook":
                webhook_id = config.get("webhook_id")
                if webhook_id:
                    return await send_webhook(
                        webhook_id,
                        config.get("event_type", "workflow.trigger"),
                        config.get("payload", {}),
                    )
                return {"status": "error", "message": "缺少 webhook_id"}

            elif action_type == "delay":
                seconds = config.get("seconds", 1)
                await asyncio.sleep(seconds)
                return {"status": "success", "message": f"延迟 {seconds} 秒"}

            elif action_type == "exec_command":
                command = config.get("command", "")
                timeout = min(config.get("timeout", 60), 300)
                result = await execute_validated_local_command(command, timeout=timeout)
                if result.get("blocked"):
                    logger.warning("拒绝执行命令: %s (%s)", command[:200], result.get("stderr", "blocked"))
                return {
                    "status": result["status"],
                    "stdout": result.get("stdout", ""),
                    "stderr": result.get("stderr", ""),
                    "returncode": result.get("exit_code", 1),
                    **({"message": result["stderr"]} if result["status"] == "error" and result.get("stderr") else {}),
                }

            elif action_type == "send_notification":
                # 简单记录通知
                return {
                    "status": "success",
                    "message": config.get("message", ""),
                    "title": config.get("title", "通知"),
                }

            else:
                return {"status": "error", "message": f"未知动作类型: {action_type}"}

        except Exception as e:
            logger.exception(f"动作执行失败 {action_type}")
            return {"status": "error", "message": str(e)}

    async def start_scheduler(self):
        """启动定时调度器"""
        if self._running:
            return

        self._running = True
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())
        logger.info("工作流调度器已启动")

    async def stop_scheduler(self):
        """停止定时调度器"""
        self._running = False
        if self._scheduler_task:
            self._scheduler_task.cancel()
        logger.info("工作流调度器已停止")

    async def _scheduler_loop(self):
        """调度循环"""
        while self._running:
            try:
                now = datetime.now()

                for workflow_id, workflow in self.workflows.items():
                    if not workflow.get("enabled", True):
                        continue

                    trigger = workflow.get("trigger", {})
                    if trigger.get("type") != "schedule":
                        continue

                    # 检查是否到达执行时间
                    schedule = trigger.get("config", {})
                    cron = schedule.get("cron", "")

                    # 简单支持: 每分钟检查一次
                    # 这里可以实现完整的 cron 解析
                    if cron == "* * * * *":  # 每分钟
                        await self.execute(workflow_id)
                    elif cron.endswith("* * *"):  # 每小时
                        if now.minute == 0:
                            await self.execute(workflow_id)
                    elif cron.startswith("0 0"):  # 每天
                        if now.hour == 0 and now.minute == 0:
                            await self.execute(workflow_id)

                await asyncio.sleep(60)  # 每分钟检查一次

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"调度循环错误: {e}")
                await asyncio.sleep(60)

    def get_executions(self, workflow_id: str = None, limit: int = 50) -> dict:
        """获取执行记录"""
        executions = self.executions

        if workflow_id:
            executions = [e for e in executions if e.get("workflow_id") == workflow_id]

        executions = sorted(executions, key=lambda x: x.get("started_at", ""), reverse=True)
        executions = executions[:limit]

        return {
            "status": "success",
            "executions": executions,
            "total": len(executions),
        }


# 全局引擎实例
workflow_engine = WorkflowEngine()
