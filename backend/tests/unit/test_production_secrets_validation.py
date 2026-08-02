"""Sprint 6.1: Settings must fail fast at startup when ENVIRONMENT=production
and a required secret is missing, but never block development/mock-mode
work regardless of which secrets are configured."""

import pytest

from app.config import _REQUIRED_PRODUCTION_SECRETS, Settings

_ALL_SECRETS_PRESENT = {name: f"value-for-{name}" for name in _REQUIRED_PRODUCTION_SECRETS}


def _settings(**overrides):
    values = {**_ALL_SECRETS_PRESENT, **overrides}
    return Settings(ENVIRONMENT="production", _env_file=None, **values)


def test_production_boots_when_every_required_secret_is_present():
    settings = _settings()
    assert settings.ENVIRONMENT == "production"


@pytest.mark.parametrize("missing_secret", _REQUIRED_PRODUCTION_SECRETS)
def test_production_fails_fast_when_a_required_secret_is_missing(missing_secret):
    with pytest.raises(RuntimeError, match=missing_secret):
        _settings(**{missing_secret: None})


def test_production_error_lists_every_missing_secret_at_once():
    with pytest.raises(RuntimeError) as exc_info:
        Settings(
            ENVIRONMENT="production",
            _env_file=None,
            SECRET_KEY=None,
            UNIPILE_WEBHOOK_SECRET=None,
            RESEND_WEBHOOK_SECRET="present",
            TWILIO_AUTH_TOKEN="present",
            GOOGLE_CLIENT_SECRET="present",
            HUBSPOT_API_KEY="present",
        )
    assert "SECRET_KEY" in str(exc_info.value)
    assert "UNIPILE_WEBHOOK_SECRET" in str(exc_info.value)


def test_development_boots_with_no_secrets_configured_at_all():
    settings = Settings(ENVIRONMENT="development", _env_file=None)
    assert settings.ENVIRONMENT == "development"


def test_test_environment_boots_with_no_secrets_configured_at_all():
    settings = Settings(ENVIRONMENT="test", _env_file=None)
    assert settings.ENVIRONMENT == "test"
