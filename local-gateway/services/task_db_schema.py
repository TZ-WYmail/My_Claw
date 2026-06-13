"""
Task database schema definitions.

This module exists so bootstrap/init code does not need to import the
`task_service` compatibility facade just to access table DDL.
"""
from __future__ import annotations


TASK_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS tasks (
    task_id      TEXT PRIMARY KEY,
    task_name    TEXT NOT NULL,
    due_time     TEXT NOT NULL,
    recurrence   TEXT NOT NULL DEFAULT 'once',
    status       TEXT NOT NULL DEFAULT 'pending',
    priority     INTEGER NOT NULL DEFAULT 2,  -- 0=urgent, 1=high, 2=medium, 3=low
    description  TEXT,
    estimated_minutes INTEGER,  -- 预估时间（分钟）
    start_time    TEXT,  -- 任务执行开始时间（ISO 8601，可空）
    end_time      TEXT,  -- 任务执行结束时间（ISO 8601，可空）
    completed_at  TEXT,  -- 任务完成时间（可空）
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS download_history (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    url          TEXT NOT NULL,
    filename     TEXT,
    category     TEXT NOT NULL,
    file_path    TEXT,
    file_size    TEXT,
    security_scan TEXT DEFAULT 'pending',
    status       TEXT NOT NULL DEFAULT 'downloading',
    job_id       TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS operation_logs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    operation    TEXT NOT NULL,
    endpoint     TEXT NOT NULL,
    params       TEXT,
    result       TEXT DEFAULT 'success',
    detail       TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

-- 同步设备表
CREATE TABLE IF NOT EXISTS sync_devices (
    device_id    TEXT PRIMARY KEY,
    device_name  TEXT,
    device_type  TEXT,                    -- mobile/desktop/web
    last_seen    TEXT NOT NULL DEFAULT (datetime('now')),
    registered_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- 离线操作队列
CREATE TABLE IF NOT EXISTS sync_offline_queue (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    operation    TEXT NOT NULL,           -- create/update/delete
    table_name   TEXT,
    record_id    TEXT,
    data         TEXT,                    -- JSON
    source       TEXT DEFAULT 'unknown',
    synced       INTEGER DEFAULT 0,       -- 0=pending, 1=synced
    error        TEXT,
    queued_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

-- 推送令牌表
CREATE TABLE IF NOT EXISTS push_tokens (
    device_id    TEXT PRIMARY KEY,
    token        TEXT NOT NULL,
    platform     TEXT NOT NULL,           -- ios/android
    registered_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS planning_previews (
    preview_id   TEXT PRIMARY KEY,
    payload      TEXT NOT NULL,
    selected_variant TEXT,
    source       TEXT DEFAULT 'ai_planning',
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    expire_at    TEXT
);
"""
