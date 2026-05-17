import io
import tarfile
from pathlib import Path

import pytest

from services import sandbox_service
from services.security_service import (
    parse_command_string,
    validate_local_command,
)
from services.workflow_service import WorkflowEngine


def _build_archive(filename: str, content: bytes) -> bytes:
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w") as tar:
        info = tarfile.TarInfo(name=filename)
        info.size = len(content)
        tar.addfile(info, io.BytesIO(content))
    return stream.getvalue()


class FakeContainer:
    def __init__(self, payload: bytes):
        self.payload = payload

    def get_archive(self, _path: str):
        return iter([self.payload]), {}


def test_copy_output_files_extracts_tar_payload(tmp_path, monkeypatch):
    archive = _build_archive("result.txt", b"hello sandbox")
    monkeypatch.setattr(sandbox_service, "DOWNLOADS_DIR", tmp_path)

    copied = sandbox_service._copy_output_files(FakeContainer(archive), ["/workspace/result.txt"])

    assert len(copied) == 1
    output_path = Path(copied[0])
    assert output_path.read_text(encoding="utf-8") == "hello sandbox"


def test_parse_command_string_rejects_invalid_input():
    ok, command, message = parse_command_string('echo "unterminated')
    assert ok is False
    assert command is None
    assert "解析失败" in message


def test_validate_local_command_blocks_non_whitelisted_binary():
    ok, message = validate_local_command(["curl", "https://example.com"], raw_command="curl https://example.com")
    assert ok is False
    assert "不在允许列表中" in message


def test_validate_local_command_blocks_dangerous_pattern():
    ok, message = validate_local_command(["echo", "$(cat /etc/passwd)"], raw_command="echo $(cat /etc/passwd)")
    assert ok is False
    assert "元字符" in message or "危险命令模式" in message


@pytest.mark.asyncio
async def test_workflow_exec_command_uses_shared_guard():
    engine = WorkflowEngine()
    result = await engine._execute_action("exec_command", {"command": "curl https://example.com"})
    assert result["status"] == "error"
    assert "允许列表" in result["message"]
