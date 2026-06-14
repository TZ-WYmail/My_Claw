import pytest
import httpx

import services.mail_service as mail_service
from services.mail import runtime_env as mail_runtime_env


@pytest.fixture()
async def temp_mail_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test_mail.db"
    monkeypatch.setattr(mail_service, "DB_PATH", db_path)
    monkeypatch.setattr(mail_runtime_env, "get_runtime_db_path", lambda default_db_path: db_path)
    monkeypatch.setattr(mail_service.notification_config, "smtp_user", "")
    monkeypatch.setattr(mail_service.notification_config, "smtp_host", "")
    monkeypatch.setattr(mail_service.notification_config, "smtp_password", "")
    await mail_service.init_mail_db()
    return db_path


@pytest.fixture
def live_server():
    base_url = "http://localhost:8900"
    try:
        response = httpx.get(f"{base_url}/health", timeout=2.0)
        response.raise_for_status()
    except Exception as exc:
        pytest.skip(f"需要本地服务运行在 {base_url}: {exc}")
    with httpx.Client(base_url=base_url, timeout=10.0) as client:
        yield client
