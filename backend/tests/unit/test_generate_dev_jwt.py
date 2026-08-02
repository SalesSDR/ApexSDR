import importlib.util
import os
import sys

import pytest
from jose import jwt as jose_jwt

from app.config import settings

_SCRIPT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "scripts",
    "generate_dev_jwt.py",
)
_spec = importlib.util.spec_from_file_location("generate_dev_jwt", _SCRIPT_PATH)
generate_dev_jwt_module = importlib.util.module_from_spec(_spec)
sys.modules["generate_dev_jwt"] = generate_dev_jwt_module
_spec.loader.exec_module(generate_dev_jwt_module)

generate_dev_jwt = generate_dev_jwt_module.generate_dev_jwt
DevAuthUnavailableError = generate_dev_jwt_module.DevAuthUnavailableError


def test_generated_token_verifies_against_the_real_jwt_provider(monkeypatch):
    """The whole point of this tool: a token it mints must be accepted by
    the actual JWTAuthProvider used in production, not just decodable in
    isolation."""
    from app.core.security import JWTAuthProvider

    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    monkeypatch.setattr(settings, "SECRET_KEY", "dev-jwt-test-secret")

    token = generate_dev_jwt("acme_corp")

    identity = JWTAuthProvider(settings.SECRET_KEY).authenticate(token)
    assert identity.tenant_id == "acme_corp"
    assert identity.auth_method == "jwt"


def test_generated_token_carries_tenant_id_and_expiration_claims(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    monkeypatch.setattr(settings, "SECRET_KEY", "dev-jwt-test-secret")

    token = generate_dev_jwt("acme_corp", expires_in_hours=2, subject="dev-user")
    payload = jose_jwt.decode(token, "dev-jwt-test-secret", algorithms=["HS256"])

    assert payload["tenant_id"] == "acme_corp"
    assert payload["sub"] == "dev-user"
    assert "exp" in payload
    assert "iat" in payload
    assert payload["exp"] - payload["iat"] == 2 * 3600


def test_refuses_to_run_when_environment_is_production(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "SECRET_KEY", "dev-jwt-test-secret")

    with pytest.raises(DevAuthUnavailableError, match="production"):
        generate_dev_jwt("acme_corp")


def test_refuses_to_run_when_secret_key_is_unset(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    monkeypatch.setattr(settings, "SECRET_KEY", None)

    with pytest.raises(DevAuthUnavailableError, match="SECRET_KEY"):
        generate_dev_jwt("acme_corp")


def test_default_expiry_is_24_hours(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "test")
    monkeypatch.setattr(settings, "SECRET_KEY", "dev-jwt-test-secret")

    token = generate_dev_jwt("acme_corp")
    payload = jose_jwt.decode(token, "dev-jwt-test-secret", algorithms=["HS256"])
    assert payload["exp"] - payload["iat"] == 24 * 3600
