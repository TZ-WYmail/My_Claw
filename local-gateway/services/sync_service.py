"""
数据同步服务 — 多端数据同步协议
支持离线模式、冲突解决、增量同步
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Optional

import aiosqlite

from config import BASE_DIR, DB_PATH

logger = logging.getLogger(__name__)

# 同步记录文件
SYNC_STATE_FILE = BASE_DIR / "data" / "sync_state.json"

# 可同步的表
SYNC_TABLES = {
    "tasks": {"pk": "task_id", "version_field": "updated_at"},
    "tags": {"pk": "tag_id", "version_field": "created_at"},
    "task_tags": {"pk": None, "composite": ["task_id", "tag_id"], "version_field": "created_at"},
    "subtasks": {"pk": "subtask_id", "version_field": "created_at"},
    "pomodoro_sessions": {"pk": "session_id", "version_field": "start_time"},
    "calendar_events": {"pk": "event_id", "version_field": "created_at"},
    "notes": {"pk": "note_id", "version_field": "updated_at"},
    "habits": {"pk": "habit_id", "version_field": "created_at"},
    "habit_checkins": {"pk": "checkin_id", "version_field": "created_at"},
}


class SyncProtocol:
    """同步协议实现 — 基于版本向量和时间戳"""

    def __init__(self):
        self.device_id = self._get_or_create_device_id()
        self.sync_state = self._load_sync_state()

    def _get_or_create_device_id(self) -> str:
        """获取或创建设备ID"""
        import os
        device_file = BASE_DIR / "data" / ".device_id"
        if device_file.exists():
            return device_file.read_text().strip()

        device_id = f"dev_{uuid.uuid4().hex[:16]}"
        device_file.parent.mkdir(parents=True, exist_ok=True)
        device_file.write_text(device_id)
        return device_id

    def _load_sync_state(self) -> dict:
        """加载同步状态"""
        try:
            if SYNC_STATE_FILE.exists():
                with open(SYNC_STATE_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"加载同步状态失败: {e}")

        return {
            "device_id": self.device_id,
            "last_sync": None,
            "table_versions": {},
            "pending_changes": [],
        }

    def save_sync_state(self):
        """保存同步状态"""
        try:
            SYNC_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(SYNC_STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(self.sync_state, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"保存同步状态失败: {e}")
            return False

    def get_last_sync(self) -> Optional[str]:
        """获取上次同步时间"""
        return self.sync_state.get("last_sync")

    def update_last_sync(self, timestamp: str = None):
        """更新上次同步时间"""
        self.sync_state["last_sync"] = timestamp or datetime.now().isoformat()
        self.save_sync_state()


class ChangeTracker:
    """变更追踪器 — 记录数据变更"""

    def __init__(self):
        self.changes_table = "sync_changes"

    async def init_changes_table(self, db: aiosqlite.Connection):
        """初始化变更记录表"""
        await db.execute(f"""
            CREATE TABLE IF NOT EXISTS {self.changes_table} (
                change_id    INTEGER PRIMARY KEY AUTOINCREMENT,
                table_name   TEXT NOT NULL,
                record_id    TEXT NOT NULL,
                operation    TEXT NOT NULL,  -- INSERT/UPDATE/DELETE
                old_data     TEXT,           -- JSON
                new_data     TEXT,           -- JSON
                device_id    TEXT NOT NULL,
                timestamp    TEXT NOT NULL DEFAULT (datetime('now')),
                synced       INTEGER DEFAULT 0,  -- 0=未同步, 1=已同步
                version      INTEGER NOT NULL DEFAULT 1
            )
        """)
        await db.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_sync_changes_table
            ON {self.changes_table}(table_name, synced)
        """)
        await db.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_sync_changes_timestamp
            ON {self.changes_table}(timestamp)
        """)
        await db.commit()

    async def record_change(
        self,
        db: aiosqlite.Connection,
        table_name: str,
        record_id: str,
        operation: str,
        new_data: dict = None,
        old_data: dict = None,
        device_id: str = None,
    ):
        """记录数据变更"""
        try:
            await db.execute(f"""
                INSERT INTO {self.changes_table}
                (table_name, record_id, operation, old_data, new_data, device_id, version)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                table_name,
                record_id,
                operation,
                json.dumps(old_data, ensure_ascii=False) if old_data else None,
                json.dumps(new_data, ensure_ascii=False) if new_data else None,
                device_id or "local",
                1,
            ))
            await db.commit()
        except Exception as e:
            logger.error(f"记录变更失败: {e}")

    async def get_pending_changes(
        self,
        db: aiosqlite.Connection,
        since: str = None,
        limit: int = 1000,
    ) -> list[dict]:
        """获取待同步的变更"""
        if since:
            cursor = await db.execute(f"""
                SELECT * FROM {self.changes_table}
                WHERE timestamp > ? AND synced = 0
                ORDER BY timestamp ASC
                LIMIT ?
            """, (since, limit))
        else:
            cursor = await db.execute(f"""
                SELECT * FROM {self.changes_table}
                WHERE synced = 0
                ORDER BY timestamp ASC
                LIMIT ?
            """, (limit,))

        rows = await cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]

        changes = []
        for row in rows:
            change = dict(zip(columns, row))
            if change.get("old_data"):
                change["old_data"] = json.loads(change["old_data"])
            if change.get("new_data"):
                change["new_data"] = json.loads(change["new_data"])
            changes.append(change)

        return changes

    async def mark_synced(self, db: aiosqlite.Connection, change_ids: list[int]):
        """标记变更为已同步"""
        if not change_ids:
            return

        placeholders = ",".join(["?"] * len(change_ids))
        await db.execute(f"""
            UPDATE {self.changes_table}
            SET synced = 1
            WHERE change_id IN ({placeholders})
        """, change_ids)
        await db.commit()


class ConflictResolver:
    """冲突解决器 — 处理同步冲突"""

    # 冲突解决策略
    STRATEGIES = {
        "last_write_wins": "最后写入优先",
        "first_write_wins": "首次写入优先",
        "manual": "手动解决",
        "merge": "自动合并",
    }

    def __init__(self, strategy: str = "last_write_wins"):
        if strategy not in self.STRATEGIES:
            raise ValueError(f"不支持的冲突策略: {strategy}")
        self.strategy = strategy

    def resolve(
        self,
        local_data: dict,
        remote_data: dict,
        local_timestamp: str,
        remote_timestamp: str,
    ) -> tuple[dict, str]:
        """
        解决数据冲突
        返回: (resolved_data, resolution_type)
        """
        if self.strategy == "last_write_wins":
            if remote_timestamp >= local_timestamp:
                return remote_data, "remote_wins"
            else:
                return local_data, "local_wins"

        elif self.strategy == "first_write_wins":
            if local_timestamp <= remote_timestamp:
                return local_data, "local_wins"
            else:
                return remote_data, "remote_wins"

        elif self.strategy == "merge":
            merged = self._merge_data(local_data, remote_data)
            return merged, "merged"

        else:  # manual
            return None, "needs_manual_resolution"

    def _merge_data(self, local: dict, remote: dict) -> dict:
        """自动合并数据（简单实现：取非空字段）"""
        merged = dict(local)
        for key, value in remote.items():
            if value is not None and value != "":
                merged[key] = value
        return merged


class SyncEngine:
    """同步引擎 — 主控制器"""

    def __init__(self):
        self.protocol = SyncProtocol()
        self.tracker = ChangeTracker()
        self.resolver = ConflictResolver(strategy="last_write_wins")
        self._initialized = False

    async def initialize(self):
        """初始化同步引擎"""
        if self._initialized:
            return

        async with aiosqlite.connect(DB_PATH) as db:
            await self.tracker.init_changes_table(db)

        self._initialized = True
        logger.info("同步引擎初始化完成")

    async def get_sync_status(self) -> dict:
        """获取同步状态"""
        await self.initialize()

        last_sync = self.protocol.get_last_sync()
        device_id = self.protocol.device_id

        async with aiosqlite.connect(DB_PATH) as db:
            pending = await self.tracker.get_pending_changes(db)

        return {
            "status": "success",
            "device_id": device_id,
            "last_sync": last_sync,
            "pending_changes": len(pending),
            "sync_tables": list(SYNC_TABLES.keys()),
        }

    async def generate_sync_payload(self, since: str = None) -> dict:
        """生成同步数据包（用于发送到服务器）"""
        await self.initialize()

        if not since:
            since = self.protocol.get_last_sync()

        async with aiosqlite.connect(DB_PATH) as db:
            changes = await self.tracker.get_pending_changes(db, since=since)

        return {
            "device_id": self.protocol.device_id,
            "timestamp": datetime.now().isoformat(),
            "since": since,
            "changes": changes,
        }

    async def apply_sync_payload(self, payload: dict) -> dict:
        """应用同步数据包（从服务器接收）

        注意：仅在所有变更成功应用后才更新同步时间戳。
        若有任何变更失败，记录失败项并保留时间戳以便下次重试。
        """
        await self.initialize()

        remote_device_id = payload.get("device_id")
        changes = payload.get("changes", [])

        if remote_device_id == self.protocol.device_id:
            return {"status": "success", "applied": 0, "skipped": len(changes)}

        results = {
            "applied": 0,
            "conflicts": 0,
            "skipped": 0,
            "failed": 0,
            "details": [],
        }
        all_success = True

        async with aiosqlite.connect(DB_PATH) as db:
            for change in changes:
                try:
                    result = await self._apply_change(db, change)
                    results["details"].append(result)

                    if result["status"] == "applied":
                        results["applied"] += 1
                    elif result["status"] == "conflict":
                        results["conflicts"] += 1
                    elif result["status"] == "failed":
                        results["failed"] += 1
                        all_success = False
                    else:
                        results["skipped"] += 1

                except Exception as e:
                    logger.error(f"应用变更失败: {e}")
                    results["failed"] += 1
                    all_success = False
                    results["details"].append({"status": "failed", "error": str(e)})

            await db.commit()

        # 仅在全部成功时才更新同步时间，失败项留待下次重试
        if all_success:
            self.protocol.update_last_sync()

        return {
            "status": "success" if all_success else "partial_failure",
            "results": results,
        }

    def _build_where_clause(self, table_info: dict, record_id):
        """根据主键信息构建 WHERE 子句和参数"""
        pk_field = table_info.get("pk")
        composite = table_info.get("composite")

        if pk_field:
            return f"{pk_field} = ?", (record_id,)
        elif composite:
            if isinstance(record_id, dict):
                conditions = []
                params = []
                for field in composite:
                    conditions.append(f"{field} = ?")
                    params.append(record_id.get(field))
                return " AND ".join(conditions), tuple(params)
            else:
                return None, ()
        else:
            return None, ()

    async def _apply_change(self, db: aiosqlite.Connection, change: dict) -> dict:
        """应用单个变更"""
        table_name = change["table_name"]
        record_id = change["record_id"]
        operation = change["operation"]
        new_data = change.get("new_data", {})

        if table_name not in SYNC_TABLES:
            return {"status": "skipped", "reason": "unsupported_table"}

        table_info = SYNC_TABLES[table_name]
        where_clause, where_params = self._build_where_clause(table_info, record_id)

        # 检查本地是否存在
        local_row = None
        if where_clause:
            cursor = await db.execute(
                f"SELECT * FROM {table_name} WHERE {where_clause}",
                where_params
            )
            local_row = await cursor.fetchone()

        if operation == "DELETE":
            if local_row and where_clause:
                await db.execute(
                    f"DELETE FROM {table_name} WHERE {where_clause}",
                    where_params
                )
                return {"status": "applied", "operation": "delete"}
            return {"status": "skipped", "reason": "not_found"}

        elif operation in ("INSERT", "UPDATE"):
            if local_row:
                # 检查冲突
                local_data = dict(local_row)
                resolved, resolution = self.resolver.resolve(
                    local_data,
                    new_data,
                    local_data.get(table_info["version_field"], ""),
                    new_data.get(table_info["version_field"], ""),
                )

                if resolution == "remote_wins":
                    # 更新本地记录
                    columns = list(new_data.keys())
                    values = list(new_data.values())
                    set_clause = ", ".join([f"{c} = ?" for c in columns])
                    await db.execute(
                        f"UPDATE {table_name} SET {set_clause} WHERE {where_clause}",
                        values + list(where_params)
                    )
                    return {"status": "applied", "operation": "update", "resolution": resolution}

                elif resolution == "local_wins":
                    return {"status": "skipped", "reason": "local_wins"}

                else:  # merged
                    columns = list(resolved.keys())
                    values = list(resolved.values())
                    set_clause = ", ".join([f"{c} = ?" for c in columns])
                    await db.execute(
                        f"UPDATE {table_name} SET {set_clause} WHERE {where_clause}",
                        values + list(where_params)
                    )
                    return {"status": "applied", "operation": "update", "resolution": resolution}

            else:
                # 插入新记录（过滤掉目标表不存在的字段）
                if new_data:
                    # 获取目标表的实际列名
                    cursor = await db.execute(f"PRAGMA table_info({table_name})")
                    columns_info = await cursor.fetchall()
                    valid_columns = {row[1] for row in columns_info}

                    filtered_data = {k: v for k, v in new_data.items() if k in valid_columns}
                    if not filtered_data:
                        return {"status": "skipped", "reason": "no_valid_columns"}

                    columns = list(filtered_data.keys())
                    values = list(filtered_data.values())
                    placeholders = ", ".join(["?"] * len(columns))
                    await db.execute(
                        f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({placeholders})",
                        values
                    )
                    return {"status": "applied", "operation": "insert"}

        return {"status": "skipped", "reason": "unknown_operation"}

    async def full_sync(self) -> dict:
        """执行完整同步"""
        status = await self.get_sync_status()

        # 生成同步包
        payload = await self.generate_sync_payload()

        # 如果是服务端模式，返回同步包
        return {
            "status": "success",
            "mode": "p2p_sync",
            "device_id": self.protocol.device_id,
            "payload": payload,
            "pending_changes": status["pending_changes"],
        }


# 全局同步引擎
sync_engine = SyncEngine()
