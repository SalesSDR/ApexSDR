import time

import pytest
from jose import jwt as jose_jwt

from app.core.security import (
    APIKeyAuthProvider,
    AuthenticationError,
    JWTAuthProvider,
    TenantAuthenticator,
)

SECRET = "unit-test-secret"


def _make_token(secret=SECRET, tenant_id="tenant_a", exp_delta=3600, include_exp=True, **extra):
    payload = {"tenant_id": tenant_id, **extra}
    if include_exp:
        payload["exp"] = int(time.time()) + exp_delta
    return jose_jwt.encode(payload, secret, algorithm="HS256")


# --- JWTAuthProvider ---

def test_valid_jwt_resolves_tenant_id():
    provider = JWTAuthProvider(SECRET)
    identity = provider.authenticate(_make_token(tenant_id="tenant_a"))
    assert identity.tenant_id == "tenant_a"
    assert identity.auth_method == "jwt"


def test_expired_jwt_is_rejected():
    provider = JWTAuthProvider(SECRET)
    token = _make_token(exp_delta=-10)  # expired 10s ago
    with pytest.raises(AuthenticationError, match="expired"):
        provider.authenticate(token)


def test_jwt_missing_exp_claim_is_rejected():
    provider = JWTAuthProvider(SECRET)
    token = _make_token(include_exp=False)
    with pytest.raises(AuthenticationError, match="expiration"):
        provider.authenticate(token)


def test_jwt_with_wrong_signature_is_rejected():
    provider = JWTAuthProvider(SECRET)
    token = _make_token(secret="a-completely-different-secret")
    with pytest.raises(AuthenticationError, match="Invalid token"):
        provider.authenticate(token)


def test_jwt_missing_tenant_id_claim_is_rejected():
    provider = JWTAuthProvider(SECRET)
    payload = {"exp": int(time.time()) + 3600}
    token = jose_jwt.encode(payload, SECRET, algorithm="HS256")
    with pytest.raises(AuthenticationError, match="tenant_id"):
        provider.authenticate(token)


def test_jwt_provider_rejects_everything_when_unconfigured():
    provider = JWTAuthProvider(secret_key=None)
    with pytest.raises(AuthenticationError, match="not configured"):
        provider.authenticate(_make_token())


def test_tampered_jwt_payload_is_rejected():
    provider = JWTAuthProvider(SECRET)
    token = _make_token(tenant_id="tenant_a")
    header, payload, signature = token.split(".")
    # Flip a character in the payload segment without re-signing.
    tampered_payload = payload[:-1] + ("A" if payload[-1] != "A" else "B")
    tampered = f"{header}.{tampered_payload}.{signature}"
    with pytest.raises(AuthenticationError):
        provider.authenticate(tampered)


# --- APIKeyAuthProvider ---

def test_valid_api_key_resolves_tenant_id():
    provider = APIKeyAuthProvider({"sk_live_abc123": "tenant_b"})
    identity = provider.authenticate("sk_live_abc123")
    assert identity.tenant_id == "tenant_b"
    assert identity.auth_method == "api_key"


def test_unknown_api_key_is_rejected():
    provider = APIKeyAuthProvider({"sk_live_abc123": "tenant_b"})
    with pytest.raises(AuthenticationError, match="Unrecognized"):
        provider.authenticate("sk_live_does_not_exist")


def test_empty_registry_rejects_every_key():
    provider = APIKeyAuthProvider({})
    with pytest.raises(AuthenticationError):
        provider.authenticate("anything")


# --- TenantAuthenticator (routing between providers) ---

def test_authenticator_routes_jwt_shaped_credential_to_jwt_provider():
    authenticator = TenantAuthenticator(
        [JWTAuthProvider(SECRET), APIKeyAuthProvider({"raw-key": "tenant_c"})]
    )
    identity = authenticator.authenticate(_make_token(tenant_id="tenant_a"))
    assert identity.tenant_id == "tenant_a"
    assert identity.auth_method == "jwt"


def test_authenticator_routes_opaque_credential_to_api_key_provider():
    authenticator = TenantAuthenticator(
        [JWTAuthProvider(SECRET), APIKeyAuthProvider({"raw-key": "tenant_c"})]
    )
    identity = authenticator.authenticate("raw-key")
    assert identity.tenant_id == "tenant_c"
    assert identity.auth_method == "api_key"


def test_authenticator_rejects_missing_credential():
    authenticator = TenantAuthenticator([JWTAuthProvider(SECRET)])
    with pytest.raises(AuthenticationError, match="Missing"):
        authenticator.authenticate("")


def test_authenticator_never_falls_back_to_a_default_tenant():
    """A JWT-shaped credential that fails verification must be rejected
    outright - it must never be reinterpreted as an API key, and there is
    no default tenant to fall back to."""
    authenticator = TenantAuthenticator(
        [JWTAuthProvider(SECRET), APIKeyAuthProvider({"raw-key": "tenant_c"})]
    )
    bad_token = _make_token(secret="wrong-secret")
    with pytest.raises(AuthenticationError):
        authenticator.authenticate(bad_token)
