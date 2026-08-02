import hmac
from abc import ABC, abstractmethod
from contextvars import ContextVar
from dataclasses import dataclass

from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError

# Global context tracking for multi-tenant isolation
tenant_context: ContextVar[str | None] = ContextVar("tenant_id", default=None)


def get_current_tenant() -> str | None:
    """
    Get the currently active tenant ID from context.
    """
    return tenant_context.get()


def set_current_tenant(tenant_id: str):
    """
    Set the currently active tenant ID in context.
    """
    return tenant_context.set(tenant_id)


# ---------------------------------------------------------------------------
# Authentication adapter architecture
#
# verify_tenant() (app.api.v1.auth) never talks to jose/JWT or an API-key
# store directly - only through the AuthProvider interface below - so a
# future provider (OAuth introspection, mTLS client certs, etc.) plugs in
# without touching the FastAPI dependency or any route.
# ---------------------------------------------------------------------------


class AuthenticationError(Exception):
    """Raised by an AuthProvider for any missing, malformed, unsigned,
    expired, or otherwise unverifiable credential. Always maps to HTTP 401 -
    callers must never distinguish these into a more permissive outcome."""


@dataclass(frozen=True)
class AuthenticatedIdentity:
    tenant_id: str
    subject: str
    auth_method: str


class AuthProvider(ABC):
    """One concrete way to turn a raw bearer credential into a verified
    tenant identity."""

    @abstractmethod
    def can_handle(self, credential: str) -> bool:
        """Whether this provider's credential shape matches. Used only to
        pick which provider attempts verification - a False result here
        never grants access; only a successful authenticate() does."""

    @abstractmethod
    def authenticate(self, credential: str) -> AuthenticatedIdentity:
        """Verify the credential. Must raise AuthenticationError on any
        failure - never return a partial/guessed identity."""


class JWTAuthProvider(AuthProvider):
    """Verifies signed, unexpired JWTs. Tenant identity comes only from the
    verified `tenant_id` claim inside a cryptographically valid token -
    never from anything the caller can set without a valid signature."""

    ALGORITHM = "HS256"

    def __init__(self, secret_key: str | None):
        self._secret_key = secret_key

    def can_handle(self, credential: str) -> bool:
        # Structural check only (three dot-separated segments) - a JWT
        # shape that fails to decode is rejected outright by authenticate(),
        # it is never reinterpreted as an API key.
        return credential.count(".") == 2

    def authenticate(self, credential: str) -> AuthenticatedIdentity:
        if not self._secret_key:
            raise AuthenticationError("JWT authentication is not configured.")

        try:
            payload = jwt.decode(credential, self._secret_key, algorithms=[self.ALGORITHM])
        except ExpiredSignatureError:
            raise AuthenticationError("Token has expired.")
        except JWTError:
            raise AuthenticationError("Invalid token signature or format.")

        # python-jose treats `exp` as an OPTIONAL claim (a token that omits
        # it decodes successfully with no error) - expiration must be
        # required explicitly, not merely validated when present.
        if "exp" not in payload:
            raise AuthenticationError("Token does not carry an expiration claim.")

        tenant_id = payload.get("tenant_id")
        if not tenant_id or not isinstance(tenant_id, str):
            raise AuthenticationError("Token is missing a valid tenant_id claim.")

        return AuthenticatedIdentity(
            tenant_id=tenant_id,
            subject=str(payload.get("sub") or tenant_id),
            auth_method="jwt",
        )


class APIKeyAuthProvider(AuthProvider):
    """Verifies opaque, pre-provisioned API keys against a configured
    registry (api_key -> tenant_id). Comparison is constant-time to avoid
    timing side-channels. An unrecognized key is rejected - there is no
    default/wildcard entry."""

    def __init__(self, key_registry: dict | None = None):
        self._key_registry = key_registry or {}

    def can_handle(self, credential: str) -> bool:
        return credential.count(".") != 2

    def authenticate(self, credential: str) -> AuthenticatedIdentity:
        for known_key, tenant_id in self._key_registry.items():
            if hmac.compare_digest(known_key, credential):
                return AuthenticatedIdentity(tenant_id=tenant_id, subject=tenant_id, auth_method="api_key")
        raise AuthenticationError("Unrecognized API key.")


class TenantAuthenticator:
    """Tries each configured AuthProvider in order, using the first one
    whose can_handle() matches the credential's shape. Exactly one failure
    path (AuthenticationError) - the caller maps this to HTTP 401."""

    def __init__(self, providers: list):
        self._providers = providers

    def authenticate(self, credential: str) -> AuthenticatedIdentity:
        if not credential or not credential.strip():
            raise AuthenticationError("Missing credential.")
        for provider in self._providers:
            if provider.can_handle(credential):
                return provider.authenticate(credential)
        raise AuthenticationError("No authentication provider could handle this credential.")


def build_default_authenticator() -> TenantAuthenticator:
    """Builds the authenticator from current settings on every call (cheap:
    no I/O) rather than caching it at import time, so config changes -
    including ones made mid-test-run via monkeypatch - take effect
    immediately instead of being frozen at process startup."""
    from app.config import settings  # local import: avoids a config<->security import cycle

    return TenantAuthenticator(
        [
            JWTAuthProvider(settings.SECRET_KEY),
            APIKeyAuthProvider(settings.tenant_api_key_registry),
        ]
    )
