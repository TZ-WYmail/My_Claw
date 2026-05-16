import services.mail_service as mail_service


def test_mail_service_exposes_compatibility_surface():
    expected_symbols = [
        "DB_PATH",
        "notification_config",
        "asyncio",
        "smtplib",
        "imaplib",
        "init_mail_db",
        "SCHEMA_SQL",
        "_generate_ai_reply_content",
        "_parse_imap_message",
        "_extract_mail_command",
        "_build_mail_action_card",
        "_get_mail_account_raw",
        "_ensure_default_folders",
        "_get_folder_id",
        "_get_folder_row",
        "_thread_from_row",
        "_message_from_row",
        "_draft_from_row",
        "_attachment_from_row",
        "_agent_run_from_row",
        "_attach_portal_links_to_thread",
        "_find_existing_thread_id",
        "_create_thread",
        "_refresh_thread_state",
        "_infer_mail_analysis",
        "_has_agent_run",
        "_record_agent_run",
        "_normalize_auto_mail_policy",
        "_is_user_direct_mail_thread",
        "_create_sync_run",
        "_finish_sync_run",
        "_build_outgoing_message_id",
    ]

    for symbol in expected_symbols:
        assert hasattr(mail_service, symbol), symbol
