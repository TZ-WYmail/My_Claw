"""
Phase 4 功能测试 — 多端统一 (数据同步、离线模式、PWA、移动端 API)
运行: cd local-gateway && python -m pytest test/test_phase4.py -v
"""
import pytest

from services.sync_service import sync_engine, SyncProtocol, ChangeTracker, ConflictResolver


class TestSyncProtocol:
    """同步协议测试"""

    def test_device_id_generation(self):
        """设备 ID 生成"""
        protocol = SyncProtocol()
        assert protocol.device_id.startswith("dev_")
        assert len(protocol.device_id) == 20  # dev_ + 16 chars

    def test_sync_state_load_save(self):
        """同步状态加载和保存"""
        protocol = SyncProtocol()

        # 初始状态
        assert protocol.sync_state["device_id"] == protocol.device_id

        # 更新同步时间
        protocol.update_last_sync("2026-04-26T10:00:00")
        assert protocol.get_last_sync() == "2026-04-26T10:00:00"


class TestConflictResolver:
    """冲突解决器测试"""

    def test_last_write_wins(self):
        """最后写入优先策略"""
        resolver = ConflictResolver(strategy="last_write_wins")

        local = {"name": "Local", "updated_at": "2026-04-26T10:00:00"}
        remote = {"name": "Remote", "updated_at": "2026-04-26T11:00:00"}

        result, resolution = resolver.resolve(
            local, remote,
            local["updated_at"], remote["updated_at"]
        )

        assert resolution == "remote_wins"
        assert result["name"] == "Remote"

    def test_first_write_wins(self):
        """首次写入优先策略"""
        resolver = ConflictResolver(strategy="first_write_wins")

        local = {"name": "Local", "updated_at": "2026-04-26T10:00:00"}
        remote = {"name": "Remote", "updated_at": "2026-04-26T11:00:00"}

        result, resolution = resolver.resolve(
            local, remote,
            local["updated_at"], remote["updated_at"]
        )

        assert resolution == "local_wins"
        assert result["name"] == "Local"

    def test_merge_strategy(self):
        """合并策略"""
        resolver = ConflictResolver(strategy="merge")

        local = {"name": "Local", "field1": "value1"}
        remote = {"name": "Remote", "field2": "value2"}

        result, resolution = resolver.resolve(local, remote, "", "")

        assert resolution == "merged"
        assert result["field1"] == "value1"
        assert result["field2"] == "value2"


class TestSyncEngine:
    """同步引擎测试"""

    @pytest.mark.asyncio
    async def test_sync_engine_init(self):
        """同步引擎初始化"""
        await sync_engine.initialize()
        assert sync_engine.protocol is not None
        assert sync_engine.tracker is not None
        assert sync_engine.resolver is not None

    @pytest.mark.asyncio
    async def test_get_sync_status(self):
        """获取同步状态"""
        await sync_engine.initialize()
        status = await sync_engine.get_sync_status()

        assert status["status"] == "success"
        assert "device_id" in status
        assert "sync_tables" in status
        assert len(status["sync_tables"]) > 0

    @pytest.mark.asyncio
    async def test_generate_sync_payload(self):
        """生成同步数据包"""
        await sync_engine.initialize()
        payload = await sync_engine.generate_sync_payload()

        assert "device_id" in payload
        assert "timestamp" in payload
        assert "changes" in payload
        assert isinstance(payload["changes"], list)


class TestMobileAPI:
    """移动端 API 测试"""

    @pytest.mark.skip(reason="需要数据库连接")
    def test_mobile_dashboard(self):
        """移动端仪表盘"""
        pass

    @pytest.mark.skip(reason="需要数据库连接")
    def test_quick_action(self):
        """快捷操作"""
        pass


class TestPWASupport:
    """PWA 支持测试"""

    def test_manifest_exists(self):
        """Manifest 文件存在"""
        from pathlib import Path
        manifest_path = Path(__file__).parent.parent / "static" / "manifest.json"
        assert manifest_path.exists(), "manifest.json 必须存在"

    def test_service_worker_exists(self):
        """Service Worker 文件存在"""
        from pathlib import Path
        sw_path = Path(__file__).parent.parent / "static" / "sw.js"
        assert sw_path.exists(), "sw.js 必须存在"

    def test_manifest_content(self):
        """Manifest 内容检查"""
        import json
        from pathlib import Path

        manifest_path = Path(__file__).parent.parent / "static" / "manifest.json"
        with open(manifest_path, "r") as f:
            manifest = json.load(f)

        assert manifest["name"] == "LocalCommandCenter"
        assert manifest["display"] == "standalone"
        assert "icons" in manifest
        assert len(manifest["icons"]) > 0


class TestOfflineMode:
    """离线模式测试"""

    @pytest.mark.skip(reason="需要服务器运行")
    def test_offline_queue(self):
        """离线队列"""
        pass

    @pytest.mark.skip(reason="需要服务器运行")
    def test_offline_sync(self):
        """离线同步"""
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
