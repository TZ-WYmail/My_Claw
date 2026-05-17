import services.mail_service as mail_service
from services.mail import facade as mail_facade


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


def test_mail_facade_declares_explicit_exports():
    expected_exports = {
        "create_mail_account",
        "update_mail_account",
        "delete_mail_account",
        "list_mail_accounts",
        "get_mail_account",
        "list_mail_folders",
        "test_mail_account_connection",
        "create_mail_draft",
        "update_mail_draft",
        "send_mail_draft",
        "ingest_mail_message",
        "list_mail_threads",
        "get_mail_thread",
        "get_mail_dashboard",
        "mark_thread_read",
        "move_thread_to_folder",
        "set_thread_decision_status",
        "create_task_from_mail_thread",
        "generate_reply_draft_for_thread",
        "auto_handle_incoming_mail",
        "list_mail_agent_runs",
        "get_mail_polling_status",
        "update_mail_polling_config",
        "start_mail_polling_scheduler",
        "stop_mail_polling_scheduler",
        "run_mail_polling_once",
        "mail_polling_runtime",
        "MailPollingRuntime",
        "init_mail_db",
        "sync_mail_account",
        "get_mail_sync_status",
        "verify_mail_portal_token",
        "build_mail_portal_links",
    }

    assert expected_exports.issubset(set(mail_facade.__all__))
