import pytest

import services.mail_service as mail_service


@pytest.fixture()
async def temp_mail_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test_mail.db"
    monkeypatch.setattr(mail_service, "DB_PATH", db_path)
    monkeypatch.setattr(mail_service.notification_config, "smtp_user", "")
    monkeypatch.setattr(mail_service.notification_config, "smtp_host", "")
    monkeypatch.setattr(mail_service.notification_config, "smtp_password", "")
    await mail_service.init_mail_db()
    return db_path
