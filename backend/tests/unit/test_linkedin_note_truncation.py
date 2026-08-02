"""Sprint 6, item 3 (LinkedIn Validation): connection-note length must
never exceed LinkedIn/Unipile's provider limit, truncated safely (at a
word boundary where possible) rather than rejected or sent as-is."""
from datetime import date

from app.models.schemas import LinkedInAccount
from app.services.linkedin.service import (
    LINKEDIN_CONNECTION_NOTE_MAX_CHARS,
    LinkedInQueueService,
    truncate_connection_note,
)


def test_short_message_is_returned_unchanged():
    message = "Hi there, looking forward to connecting!"
    assert truncate_connection_note(message) == message


def test_message_at_exactly_the_limit_is_unchanged():
    message = "x" * LINKEDIN_CONNECTION_NOTE_MAX_CHARS
    assert truncate_connection_note(message) == message


def test_over_limit_message_is_truncated_to_at_most_the_limit():
    message = "This is a very long connection note. " * 20
    result = truncate_connection_note(message)
    assert len(result) <= LINKEDIN_CONNECTION_NOTE_MAX_CHARS
    assert result != message


def test_truncation_prefers_a_word_boundary_not_a_mid_word_cut():
    message = "word " * 100  # well over the limit, plenty of spaces to cut at
    result = truncate_connection_note(message, max_chars=50)
    core = result[:-1] if result.endswith("…") else result  # strip the ellipsis marker
    assert core.endswith("word") or core == ""  # never ends mid-"word"


def test_truncation_appends_an_ellipsis_marker():
    message = "x" * 500
    result = truncate_connection_note(message)
    assert result.endswith("…")


def test_none_message_passes_through_unchanged():
    assert truncate_connection_note(None) is None


def test_a_single_unbreakable_long_word_still_respects_the_limit():
    message = "a" * 500  # no spaces at all
    result = truncate_connection_note(message, max_chars=50)
    assert len(result) <= 50


async def test_send_connection_request_truncates_before_calling_the_adapter():
    captured = {}

    class _RecordingAdapter:
        async def send_connection_request(self, linkedin_url, account_id, message=None):
            captured["message"] = message
            return {"status": "sent"}

    service = LinkedInQueueService(_RecordingAdapter())
    account = LinkedInAccount(
        tenant_id="t1", account_id="acct-1", daily_send_count=0, daily_limit=20,
        daily_count_date=date.today(),
    )
    long_message = "Let's connect! " * 50

    await service.send_connection_request(account, "https://linkedin.com/in/someone", message=long_message)

    assert len(captured["message"]) <= LINKEDIN_CONNECTION_NOTE_MAX_CHARS


async def test_send_connection_request_never_exceeds_the_limit_even_at_the_boundary():
    captured = {}

    class _RecordingAdapter:
        async def send_connection_request(self, linkedin_url, account_id, message=None):
            captured["message"] = message
            return {"status": "sent"}

    service = LinkedInQueueService(_RecordingAdapter())
    account = LinkedInAccount(
        tenant_id="t1", account_id="acct-1", daily_send_count=0, daily_limit=20,
        daily_count_date=date.today(),
    )
    exact_message = "y" * LINKEDIN_CONNECTION_NOTE_MAX_CHARS

    await service.send_connection_request(account, "https://linkedin.com/in/someone", message=exact_message)

    assert captured["message"] == exact_message  # unchanged, no unnecessary truncation
