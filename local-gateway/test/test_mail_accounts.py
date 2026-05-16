import services.mail_service as mail_service


async def test_create_mail_account_creates_default_folders(temp_mail_db):
    result = await mail_service.create_mail_account(
        display_name="Desk",
        email_address="desk@example.com",
        smtp_host="smtp.example.com",
        smtp_user="desk@example.com",
        smtp_password="secret1234",
        imap_host="imap.example.com",
        imap_user="desk@example.com",
        imap_password="secret5678",
    )

    assert result["status"] == "success"
    account_id = result["account_id"]

    accounts = await mail_service.list_mail_accounts()
    assert len(accounts) == 1
    assert accounts[0]["account_id"] == account_id
    assert accounts[0]["smtp_password_masked"]
    assert "smtp_password" not in accounts[0]

    folders = await mail_service.list_mail_folders(account_id)
    assert {folder["kind"] for folder in folders} == {"inbox", "sent", "drafts", "archive", "trash"}


async def test_create_mail_account_normalizes_auto_policy(temp_mail_db):
    result = await mail_service.create_mail_account(
        display_name="Desk",
        email_address="desk@example.com",
        auto_mail_policy="AUTO_SEND",
    )

    assert result["status"] == "success"
    assert result["account"]["auto_mail_policy"] == "auto_send"


async def test_update_mail_account_keeps_existing_password_when_blank(temp_mail_db):
    created = await mail_service.create_mail_account(
        display_name="Ops",
        email_address="ops@example.com",
        smtp_host="smtp.example.com",
        smtp_user="ops@example.com",
        smtp_password="smtp-secret",
        imap_host="imap.example.com",
        imap_user="ops@example.com",
        imap_password="imap-secret",
    )

    account_id = created["account_id"]
    updated = await mail_service.update_mail_account(
        account_id,
        display_name="Ops Desk",
        smtp_password="",
        imap_password="",
    )

    assert updated["status"] == "success"

    raw = await mail_service._get_mail_account_raw(account_id)
    assert raw is not None
    assert raw["display_name"] == "Ops Desk"
    assert raw["smtp_password"] == "smtp-secret"
    assert raw["imap_password"] == "imap-secret"


async def test_update_mail_account_normalizes_auto_policy(temp_mail_db):
    created = await mail_service.create_mail_account(
        display_name="Ops",
        email_address="ops@example.com",
        auto_mail_policy="draft_only",
    )

    updated = await mail_service.update_mail_account(
        created["account_id"],
        auto_mail_policy="AUTO_SEND",
    )

    assert updated["status"] == "success"
    assert updated["account"]["auto_mail_policy"] == "auto_send"
