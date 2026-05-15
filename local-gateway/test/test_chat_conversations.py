"""
对话列表与删除接口测试
"""
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


with tempfile.TemporaryDirectory() as temp_dir:
    temp_base = Path(temp_dir)
    temp_data = temp_base / "data"
    temp_data.mkdir(parents=True, exist_ok=True)
    temp_conv = temp_data / "conversations"
    temp_conv.mkdir(parents=True, exist_ok=True)

    with patch("config.BASE_DIR", temp_base):
        from services.ai_service import _list_all_conversations, _save_conversation_meta, _save_conversation_message, delete_conversation_data


@pytest.mark.asyncio
async def test_delete_conversation_removes_meta_and_messages():
    conversation_id = "conv_delete_test"

    _save_conversation_meta(conversation_id, "测试删除")
    _save_conversation_message(conversation_id, "user", "hello")

    before = _list_all_conversations()
    assert any(item["id"] == conversation_id for item in before)

    result = delete_conversation_data(conversation_id)
    assert result["status"] == "success"

    after = _list_all_conversations()
    assert not any(item["id"] == conversation_id for item in after)
