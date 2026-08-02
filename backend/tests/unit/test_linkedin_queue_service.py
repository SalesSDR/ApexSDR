from datetime import UTC, date, datetime, timedelta

import pytest

from app.models.schemas import LinkedInAccount
from app.services.linkedin.base import LinkedInRateLimitError
from app.services.linkedin.service import LinkedInQueueService


def _account(**overrides) -> LinkedInAccount:
    defaults = dict(
        tenant_id="test-tenant",
        account_id="acc_1",
        daily_send_count=0,
        daily_count_date=date.today(),
        daily_limit=20,
        is_paused=False,
    )
    defaults.update(overrides)
    return LinkedInAccount(**defaults)


class _RecordingAdapter:
    def __init__(self):
        self.connection_calls = []
        self.message_calls = []

    async def send_connection_request(self, linkedin_url, account_id, message=None):
        self.connection_calls.append((linkedin_url, account_id, message))
        return {"status": "sent"}

    async def send_message(self, account_id, provider_id, text):
        self.message_calls.append((account_id, provider_id, text))
        return {"status": "sent"}


class _RateLimitedAdapter:
    async def send_connection_request(self, linkedin_url, account_id, message=None):
        raise LinkedInRateLimitError("429 from Unipile")

    async def send_message(self, account_id, provider_id, text):
        raise LinkedInRateLimitError("429 from Unipile")


# --- can_send() ---

def test_can_send_allows_fresh_account():
    service = LinkedInQueueService(_RecordingAdapter())
    account = _account()
    allowed, reason = service.can_send(account)
    assert allowed is True
    assert reason is None


def test_can_send_blocks_when_daily_limit_reached():
    service = LinkedInQueueService(_RecordingAdapter())
    account = _account(daily_send_count=20, daily_limit=20)
    allowed, reason = service.can_send(account)
    assert allowed is False
    assert reason == "daily_limit_reached"


def test_can_send_resets_count_on_a_new_day():
    service = LinkedInQueueService(_RecordingAdapter())
    account = _account(daily_send_count=20, daily_limit=20, daily_count_date=date.today() - timedelta(days=1))
    allowed, reason = service.can_send(account)
    assert allowed is True
    assert account.daily_send_count == 0
    assert account.daily_count_date == date.today()


def test_can_send_blocks_while_paused():
    service = LinkedInQueueService(_RecordingAdapter())
    account = _account(is_paused=True, paused_until=datetime.now(UTC) + timedelta(hours=1))
    allowed, reason = service.can_send(account)
    assert allowed is False
    assert reason == "account_paused"


def test_can_send_lifts_pause_once_expired():
    service = LinkedInQueueService(_RecordingAdapter())
    account = _account(is_paused=True, paused_reason="rate_limited", paused_until=datetime.now(UTC) - timedelta(minutes=1))
    allowed, reason = service.can_send(account)
    assert allowed is True
    assert account.is_paused is False
    assert account.paused_reason is None
    assert account.paused_until is None


# --- send_connection_request() / send_message() ---

async def test_send_connection_request_increments_daily_count_on_success():
    service = LinkedInQueueService(_RecordingAdapter())
    account = _account()

    await service.send_connection_request(account, "https://linkedin.com/in/x", message="hi")

    assert account.daily_send_count == 1


async def test_send_message_increments_daily_count_on_success():
    service = LinkedInQueueService(_RecordingAdapter())
    account = _account()

    await service.send_message(account, provider_id="p1", text="hello")

    assert account.daily_send_count == 1


async def test_send_connection_request_pauses_account_on_rate_limit_and_reraises():
    service = LinkedInQueueService(_RateLimitedAdapter())
    account = _account()

    with pytest.raises(LinkedInRateLimitError):
        await service.send_connection_request(account, "https://linkedin.com/in/x")

    assert account.is_paused is True
    assert account.paused_reason == "rate_limited"
    assert account.paused_until is not None
    assert account.daily_send_count == 0  # a failed send never counts against the daily cap


async def test_send_message_pauses_account_on_rate_limit_and_reraises():
    service = LinkedInQueueService(_RateLimitedAdapter())
    account = _account()

    with pytest.raises(LinkedInRateLimitError):
        await service.send_message(account, provider_id="p1", text="hello")

    assert account.is_paused is True
    assert account.paused_reason == "rate_limited"
