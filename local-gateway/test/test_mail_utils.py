from services.mail import utils


def test_normalize_subject_strips_nested_reply_prefixes():
    assert utils.normalize_subject("  Re: FWD: fw: Project Update ") == "Project Update"
    assert utils.normalize_subject("") == "(no subject)"


def test_json_loads_rejects_non_list_and_invalid_json():
    assert utils.json_loads('["a", "b"]') == ["a", "b"]
    assert utils.json_loads('{"a": 1}') == []
    assert utils.json_loads("not-json") == []


def test_extract_reference_ids_normalizes_deduplicates_and_preserves_order():
    raw = "<first@example.com> second@example.com <first@example.com> <third@example.com>"

    assert utils.extract_reference_ids(raw) == [
        "first@example.com",
        "second@example.com",
        "third@example.com",
    ]


def test_build_outgoing_message_id_uses_address_domain_or_local_fallback():
    assert utils.build_outgoing_message_id("desk@example.com").endswith("@example.com")
    assert utils.build_outgoing_message_id("desk").endswith("@local-mail")


def test_portal_token_and_links_follow_gateway_base_url(monkeypatch):
    monkeypatch.setattr(utils.ai_config, "gateway_base_url", "http://127.0.0.1:8900/")

    links = utils.build_mail_portal_links("thread_123")

    assert links["base_url"] == "http://127.0.0.1:8900"
    assert links["portal_url"].startswith("http://127.0.0.1:8900/api/mail/portal/thread_123?token=")
    assert utils.verify_mail_portal_token("thread_123", links["token"]) is True
    assert utils.verify_mail_portal_token("thread_123", "bad-token") is False
