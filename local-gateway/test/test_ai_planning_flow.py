"""
AI 安排任务流程测试
"""
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


with tempfile.TemporaryDirectory() as temp_dir:
    temp_db_path = Path(temp_dir) / "test_ai_planning.db"
    with patch('config.DB_PATH', temp_db_path), \
         patch('services.task_service.DB_PATH', temp_db_path), \
         patch('services.note_service.DB_PATH', temp_db_path), \
         patch('services.tag_service.DB_PATH', temp_db_path), \
         patch('services.subtask_service.DB_PATH', temp_db_path), \
         patch('services.pomodoro_service.DB_PATH', temp_db_path), \
         patch('services.calendar_sync_service.DB_PATH', temp_db_path):
        from services.task_service import init_db
        from services.ai_planning_service import preview_task_plan, confirm_task_plan, replan_tasks, replan_tasks_with_acceptance


@pytest.fixture(autouse=True)
async def setup_db():
    await init_db()
    yield


@pytest.mark.asyncio
async def test_preview_task_plan_returns_structured_result():
    result = await preview_task_plan([
        {"task_name": "写周报", "due_time": "2026-05-20", "estimated_minutes": 60},
        {"task_name": "整理邮件", "due_time": "2026-05-20", "estimated_minutes": 30},
    ])

    assert result["status"] == "success"
    assert "preview_id" in result
    assert "normalized_tasks" in result
    assert "daily_plan" in result
    assert "variants" in result
    assert "variant_plans" in result
    assert set(result["variant_plans"].keys()) >= {"balanced", "conservative", "aggressive"}
    assert result["variant_plans"]["conservative"]["summary"]["risk_level"] in {"low", "medium", "high"}


@pytest.mark.asyncio
async def test_preview_variants_have_distinct_capacity_results():
    result = await preview_task_plan([
        {"task_name": "准备汇报", "due_time": "2026-05-20", "estimated_minutes": 360},
        {"task_name": "写方案", "due_time": "2026-05-20", "estimated_minutes": 240},
    ])

    balanced_days = len(result["variant_plans"]["balanced"]["daily_plan"])
    conservative_days = len(result["variant_plans"]["conservative"]["daily_plan"])
    aggressive_days = len(result["variant_plans"]["aggressive"]["daily_plan"])

    assert conservative_days >= balanced_days
    assert aggressive_days <= conservative_days


@pytest.mark.asyncio
async def test_preview_supports_dependencies_and_earliest_start():
    result = await preview_task_plan([
        {"task_name": "收集数据", "due_time": "2026-05-19", "earliest_start": "2026-05-17"},
        {"task_name": "写周报", "due_time": "2026-05-20", "depends_on": ["收集数据"]},
    ])

    assert result["status"] == "success"
    normalized = {item["task_name"]: item for item in result["normalized_tasks"]}
    assert normalized["收集数据"]["earliest_start_valid"] is True
    assert normalized["写周报"]["depends_on"] == ["收集数据"]


@pytest.mark.asyncio
async def test_preview_generates_time_blocks():
    result = await preview_task_plan([
        {"task_name": "写周报", "due_time": "2026-05-20", "estimated_minutes": 120},
    ])

    assert result["status"] == "success"
    balanced = result["variant_plans"]["balanced"]
    first_day = next(iter(balanced["daily_plan"].values()))
    assert "time_blocks" in first_day
    assert len(first_day["time_blocks"]) >= 1
    assert first_day["tasks"][0]["time_slot"]


@pytest.mark.asyncio
async def test_preview_applies_deep_work_and_evening_protection():
    result = await preview_task_plan([
        {"task_name": "开发核心模块", "due_time": "2026-05-20", "estimated_minutes": 180, "work_domain": "engineering"},
        {"task_name": "整理邮件", "due_time": "2026-05-20", "estimated_minutes": 60, "work_domain": "admin"},
    ], constraints={
        "focus_start_hour": 9,
        "focus_end_hour": 21,
        "protect_evening_after": 19,
        "deep_work_start_hour": 9,
        "deep_work_end_hour": 11,
        "lunch_start_hour": 12,
        "lunch_end_hour": 13,
    })

    assert result["status"] == "success"
    balanced = result["variant_plans"]["balanced"]
    blocks = []
    for info in balanced["daily_plan"].values():
        blocks.extend(info.get("time_blocks", []))

    assert any(block["energy_type"] == "deep" for block in blocks)
    assert all(int(block["end_time"][11:13]) <= 19 for block in blocks)


@pytest.mark.asyncio
async def test_confirm_task_plan_requires_preview():
    result = await confirm_task_plan("missing_preview_id")
    assert result["status"] == "error"


@pytest.mark.asyncio
async def test_confirm_task_plan_uses_selected_variant():
    preview = await preview_task_plan([
        {"task_name": "准备汇报", "due_time": "2026-05-21", "estimated_minutes": 360},
    ])

    result = await confirm_task_plan(preview["preview_id"], selected_variant="conservative")

    assert result["status"] == "success"
    assert result["selected_variant"] == "conservative"
    assert result["success_count"] == 1
    created = result["created_tasks"][0]
    assert created["status"] == "success"
    assert created["start_time"]
    assert created["end_time"]
    assert "T" in created["start_time"]
    assert "T" in created["end_time"]


@pytest.mark.asyncio
async def test_replan_task_plan_returns_preview():
    result = await replan_tasks([
        {"task_name": "旧任务A", "due_time": "2026-05-20"},
        {"task_name": "旧任务B", "due_time": "2026-05-21"},
    ], interrupt_task={"task_name": "突发任务", "due_time": "2026-05-19"})

    assert result["status"] == "success"
    assert "new_plan" in result
    assert "postpone_candidates" in result
    assert isinstance(result["new_plan"].get("variant_plans"), dict)
    assert "impact_summary" in result
    assert isinstance(result["risk_changes"], list)
    assert "conflict_chain" in result
    assert "reordered_tasks" in result
    assert "suggested_plan" in result
    assert "applied_actions" in result
    if result["reordered_tasks"]:
        assert "confidence" in result["reordered_tasks"][0]
        assert "severity" in result["reordered_tasks"][0]
        assert "reason_type" in result["reordered_tasks"][0]


@pytest.mark.asyncio
async def test_replan_returns_conflict_chain_for_linked_tasks():
    result = await replan_tasks([
        {"task_name": "收集数据", "due_time": "2026-05-20"},
        {"task_name": "写初稿", "due_time": "2026-05-20", "depends_on": ["收集数据"]},
        {"task_name": "准备汇报", "due_time": "2026-05-20", "depends_on": ["写初稿"]},
    ], interrupt_task={"task_name": "突发需求", "due_time": "2026-05-19"})

    assert result["status"] == "success"
    assert isinstance(result["conflict_chain"], list)
    assert isinstance(result["reordered_tasks"], list)
    assert isinstance(result["applied_actions"], list)
    assert isinstance(result["suggested_plan"].get("variant_plans"), dict)


@pytest.mark.asyncio
async def test_replan_with_acceptance_applies_partial_suggestions():
    result = await replan_tasks_with_acceptance([
        {"task_name": "收集数据", "due_time": "2026-05-20"},
        {"task_name": "写初稿", "due_time": "2026-05-20", "depends_on": ["收集数据"]},
        {"task_name": "准备汇报", "due_time": "2026-05-20", "depends_on": ["写初稿"]},
    ], interrupt_task={"task_name": "突发需求", "due_time": "2026-05-19"}, accepted_task_names=["写初稿"])

    assert result["status"] == "success"
    assert result["accepted_task_names"] == ["写初稿"]
    assert any(item["task_name"] == "写初稿" for item in result["applied_actions"])
    assert isinstance(result["suggested_plan"].get("variant_plans"), dict)
    if result["applied_actions"]:
        assert "confidence" in result["applied_actions"][0]
        assert "severity" in result["applied_actions"][0]
        assert "reason_type" in result["applied_actions"][0]
