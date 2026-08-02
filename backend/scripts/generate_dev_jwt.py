#!/usr/bin/env python3
"""
Generates a correctly signed JWT for local development against Apex SDR's
authentication (see app.core.security.JWTAuthProvider / app.api.v1.auth.verify_tenant).

This is the ONE supported way to get a bearer credential for local API
testing - there is no user-management system, login endpoint, or session
store; a token minted here has exactly the shape and claims the real
verifier requires (a `tenant_id` claim and an `exp` claim), signed with the
same SECRET_KEY the running app verifies against.

Refuses to run when ENVIRONMENT=production - this is a developer-only tool,
not an auth backend, and is never imported by application/route code.

Usage:
    python scripts/generate_dev_jwt.py --tenant-id acme_corp
    python scripts/generate_dev_jwt.py --tenant-id acme_corp --expires-in-hours 2 --sub dev-user

Then use the printed value:
    curl -H "Authorization: Bearer <token>" http://localhost:8000/api/v1/prospects
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from jose import jwt  # noqa: E402

from app.config import settings  # noqa: E402


class DevAuthUnavailableError(RuntimeError):
    """Raised when this tool is invoked outside a development environment."""


def _ensure_development_environment() -> None:
    if settings.ENVIRONMENT == "production":
        raise DevAuthUnavailableError(
            "generate_dev_jwt is disabled when ENVIRONMENT=production. "
            "This tool mints tokens signed with SECRET_KEY and must never run "
            "against a production configuration."
        )
    if not settings.SECRET_KEY:
        raise DevAuthUnavailableError(
            "SECRET_KEY is not configured - set it in your local .env before "
            "generating development tokens (it must match what the running "
            "app verifies against)."
        )


def generate_dev_jwt(tenant_id: str, expires_in_hours: float = 24, subject: str = None) -> str:
    """Mints a JWT with the exact claim shape JWTAuthProvider requires:
    a `tenant_id` claim and a mandatory `exp` claim, HS256-signed with the
    app's own SECRET_KEY."""
    _ensure_development_environment()

    now = int(time.time())
    payload = {
        "tenant_id": tenant_id,
        "iat": now,
        "exp": now + int(expires_in_hours * 3600),
    }
    if subject:
        payload["sub"] = subject

    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tenant-id", required=True, help="Tenant ID to embed in the token's tenant_id claim.")
    parser.add_argument("--expires-in-hours", type=float, default=24, help="Token lifetime in hours (default: 24).")
    parser.add_argument("--sub", default=None, help="Optional subject claim (e.g. a developer's name/email).")
    args = parser.parse_args()

    try:
        token = generate_dev_jwt(args.tenant_id, args.expires_in_hours, args.sub)
    except DevAuthUnavailableError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    print(token)
    print(f"\nAuthorization: Bearer {token}", file=sys.stderr)


if __name__ == "__main__":
    main()
