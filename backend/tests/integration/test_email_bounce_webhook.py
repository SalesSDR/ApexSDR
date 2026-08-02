"""Sprint 3, item 1 (bounce suppression): Resend's delivery-status webhook
(email.bounced/email.complained) must add the recipient to the permanent
suppression list. Calls handle_email_delivery_event directly with a fake
Request (matching the pattern in test_webhook_transitions.py) rather than
going through the full HTTP client, with verify_resend_signature
monkeypatched to a no-op so this file tests the event-handling logic, not
signature verification (covered separately in test_webhook_signatures.py)."""
import json

import app.api.v1.webhooks as webhooks
from app.services.email_verification.service import is_bounce_suppressed


class _FakeRequest:
    def __init__(self, json_body: dict):
        self._json_body = json_body

    async def body(self):
        return json.dumps(self._json_body).encode("utf-8")


async def test_bounce_event_suppresses_the_recipient(db_session, monkeypatch):
    monkeypatch.setattr(webhooks, "verify_resend_signature", lambda request, raw_body: None)

    request = _FakeRequest({"type": "email.bounced", "data": {"to": ["bounced-prospect@example.com"]}})
    result = await webhooks.handle_email_delivery_event(request, db=db_session)

    assert result == {"status": "received"}
    assert await is_bounce_suppressed(db_session, "bounced-prospect@example.com") is True


async def test_complaint_event_also_suppresses_the_recipient(db_session, monkeypatch):
    monkeypatch.setattr(webhooks, "verify_resend_signature", lambda request, raw_body: None)

    request = _FakeRequest({"type": "email.complained", "data": {"to": "complained@example.com"}})
    result = await webhooks.handle_email_delivery_event(request, db=db_session)

    assert result == {"status": "received"}
    assert await is_bounce_suppressed(db_session, "complained@example.com") is True


async def test_unrelated_event_types_are_ignored_and_do_not_suppress(db_session, monkeypatch):
    monkeypatch.setattr(webhooks, "verify_resend_signature", lambda request, raw_body: None)

    request = _FakeRequest({"type": "email.delivered", "data": {"to": ["fine@example.com"]}})
    result = await webhooks.handle_email_delivery_event(request, db=db_session)

    assert result == {"status": "ignored", "reason": "not_a_bounce_event"}
    assert await is_bounce_suppressed(db_session, "fine@example.com") is False


async def test_missing_recipient_is_ignored_without_error(db_session, monkeypatch):
    monkeypatch.setattr(webhooks, "verify_resend_signature", lambda request, raw_body: None)

    request = _FakeRequest({"type": "email.bounced", "data": {}})
    result = await webhooks.handle_email_delivery_event(request, db=db_session)

    assert result == {"status": "ignored", "reason": "no_recipient"}
