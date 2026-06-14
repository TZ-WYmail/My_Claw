from unittest.mock import AsyncMock, patch

import pytest

from application import ai_tools
from services import ai_service


@pytest.mark.asyncio
async def test_execute_local_job_status_returns_not_found():
    result = await ai_tools.execute_local_job_status({"job_id": "missing_job"})

    assert result["job_id"] == "missing_job"
    assert result["status"] == "not_found"
    assert "不存在" in result["message"]


@pytest.mark.asyncio
async def test_execute_local_sandbox_executor_delegates_to_service():
    payload = {
        "tool_name": "python",
        "execution_command": "python -V",
        "setup_commands": ["echo setup"],
        "dynamic_files": {"main.py": "print('ok')"},
        "input_files": ["/tmp/input.txt"],
    }

    with patch("application.ai_tools.execute_in_sandbox", new=AsyncMock(return_value={
        "status": "success",
        "exit_code": 0,
        "stdout": "ok",
        "stderr": "",
        "output_files": [],
        "copied_to": [],
        "duration_seconds": 0.1,
        "message": "沙盒执行完成",
    })) as mocked:
        result = await ai_tools.execute_local_sandbox_executor(payload)

    mocked.assert_awaited_once_with(
        tool_name="python",
        execution_command="python -V",
        setup_commands=["echo setup"],
        dynamic_files={"main.py": "print('ok')"},
        input_files=["/tmp/input.txt"],
    )
    assert result["status"] == "success"
    assert result["exit_code"] == 0


@pytest.mark.asyncio
async def test_execute_tool_uses_internal_application_entrypoint():
    with patch("services.ai_service.execute_ai_tool", new=AsyncMock(return_value={"status": "success", "message": "internal"})) as mocked:
        result = await ai_service._execute_tool("local_job_status", {"job_id": "abc"})

    mocked.assert_awaited_once_with("local_job_status", {"job_id": "abc"})
    assert result == {"status": "success", "message": "internal"}



@pytest.mark.asyncio
async def test_execute_local_unified_search_delegates_to_service():
    payload = {
        "keyword": "周报",
        "scope": "all",
        "category": "all",
        "page": 1,
        "page_size": 20,
    }

    with patch("application.ai_tools.unified_search", new=AsyncMock(return_value={
        "status": "success",
        "results": {
            "files": {"items": [], "total": 0},
            "tasks": {"items": [{"task_id": "task_1"}], "total": 1},
            "notes": {"items": [], "total": 0},
            "habits": {"items": [], "total": 0},
        },
        "total": 1,
        "scope": "all",
    })) as mocked:
        result = await ai_tools.execute_local_unified_search(payload)

    mocked.assert_awaited_once_with(
        keyword="周报",
        scope="all",
        category="all",
        page=1,
        page_size=20,
    )
    assert result["status"] == "success"
    assert result["tasks"] == [{"task_id": "task_1"}]


@pytest.mark.asyncio
async def test_execute_ai_tool_accepts_legacy_search_tool_name_with_warning():
    payload = {
        "keyword": "周报",
        "scope": "all",
        "category": "all",
        "page": 1,
        "page_size": 20,
    }

    with patch("application.ai_tools.execute_local_unified_search", new=AsyncMock(return_value={
        "status": "success",
        "files": [],
        "tasks": [],
        "notes": [],
        "habits": [],
        "results": {
            "files": {"items": [], "total": 0},
            "tasks": {"items": [], "total": 0},
            "notes": {"items": [], "total": 0},
            "habits": {"items": [], "total": 0},
        },
        "total": 0,
        "scope": "all",
    })) as mocked:
        with pytest.warns(DeprecationWarning, match=r"local_unified_search"):
            result = await ai_tools.execute_ai_tool("local_file_search", payload)

    mocked.assert_awaited_once_with(payload)
    assert result["status"] == "success"
