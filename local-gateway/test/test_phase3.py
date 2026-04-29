"""
Phase 3 功能测试 — 日历同步、全文检索、Webhook、工作流
运行: cd local-gateway && python -m pytest test/test_phase3.py -v
"""
import pytest

from services.calendar_sync_service import sync_config, get_sync_status
from services.fulltext_search_service import fulltext_index, get_index_stats
from services.webhook_service import webhook_manager
from services.workflow_service import workflow_engine, TRIGGER_TYPES, ACTION_TYPES


class TestCalendarSync:
    """日历同步测试"""

    @pytest.mark.asyncio
    async def test_sync_status(self):
        """获取同步状态"""
        result = await get_sync_status()
        assert result["status"] == "success"
        assert "providers" in result

    def test_sync_config(self):
        """同步配置"""
        assert sync_config is not None


class TestFullTextSearch:
    """全文检索测试"""

    @pytest.mark.asyncio
    async def test_index_stats(self):
        """获取索引统计"""
        result = await get_index_stats()
        assert result["status"] == "success"

    def test_index_exists(self):
        """索引实例存在"""
        assert fulltext_index is not None


class TestWebhooks:
    """Webhook 测试"""

    def test_webhook_manager(self):
        """Webhook 管理器"""
        assert webhook_manager is not None

    def test_register_webhook(self):
        """注册 Webhook"""
        result = webhook_manager.register(
            url="https://example.com/webhook",
            events=["task.completed"],
            description="测试 Webhook"
        )
        assert result["status"] == "success"
        webhook_id = result["webhook_id"]

        # 清理
        webhook_manager.unregister(webhook_id)


class TestWorkflows:
    """工作流测试"""

    def test_workflow_engine(self):
        """工作流引擎"""
        assert workflow_engine is not None

    def test_trigger_types(self):
        """触发器类型定义"""
        assert "schedule" in TRIGGER_TYPES
        assert "task_completed" in TRIGGER_TYPES

    def test_action_types(self):
        """动作类型定义"""
        assert "create_task" in ACTION_TYPES
        assert "send_webhook" in ACTION_TYPES

    def test_create_workflow(self):
        """创建工作流"""
        result = workflow_engine.create(
            name="测试工作流",
            trigger={
                "type": "task_completed",
                "conditions": {}
            },
            actions=[
                {
                    "type": "create_note",
                    "config": {"title": "任务完成", "content": "{{task_name}}"}
                }
            ]
        )
        assert result["status"] == "success"
        workflow_id = result["workflow_id"]

        # 清理
        workflow_engine.delete(workflow_id)

    @pytest.mark.asyncio
    async def test_execute_workflow(self):
        """执行工作流"""
        # 创建工作流
        result = workflow_engine.create(
            name="执行测试",
            trigger={"type": "manual"},
            actions=[
                {"type": "delay", "config": {"seconds": 0.1}},
                {"type": "send_notification", "config": {"title": "测试", "message": "Hello"}}
            ]
        )
        workflow_id = result["workflow_id"]

        # 执行
        exec_result = await workflow_engine.execute(workflow_id, {})
        assert exec_result["status"] == "success"
        assert "execution" in exec_result

        # 清理
        workflow_engine.delete(workflow_id)


class TestPhase3API:
    """Phase 3 API 端点测试 (需要运行服务器)"""

    @pytest.mark.skip(reason="需要服务器运行")
    def test_calendar_sync_api(self):
        """日历同步 API"""
        pass

    @pytest.mark.skip(reason="需要服务器运行")
    def test_fulltext_search_api(self):
        """全文搜索 API"""
        pass

    @pytest.mark.skip(reason="需要服务器运行")
    def test_webhook_api(self):
        """Webhook API"""
        pass

    @pytest.mark.skip(reason="需要服务器运行")
    def test_workflow_api(self):
        """工作流 API"""
        pass
