import os

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Secrets that must be present for the app to boot with ENVIRONMENT=production.
# Checked by name against the Settings instance in validate_production_secrets()
# below - missing any of these in production means the corresponding
# integration would silently no-op or fail-closed at request time instead of
# at startup, which is worse: better to crash the boot than serve traffic
# with, e.g., signed-webhook verification impossible to satisfy.
_REQUIRED_PRODUCTION_SECRETS = (
    "SECRET_KEY",
    "UNIPILE_WEBHOOK_SECRET",
    "RESEND_WEBHOOK_SECRET",
    "TWILIO_AUTH_TOKEN",
    "GOOGLE_CLIENT_SECRET",
    "HUBSPOT_API_KEY",
)


class Settings(BaseSettings):
    ENVIRONMENT: str = Field("production", validation_alias="ENVIRONMENT")
    DATABASE_URL: str | None = Field(None, validation_alias="DATABASE_URL")
    DATABASE_ASYNC_URL: str = Field(
        "postgresql+asyncpg://sdr_admin:SECURE_VAULT_PW@localhost:5432/apex_sdr_prod",
        validation_alias="DATABASE_ASYNC_URL"
    )

    @model_validator(mode='after')
    def parse_database_url(self) -> 'Settings':
        if self.DATABASE_URL:
            url = self.DATABASE_URL
            if url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql+asyncpg://", 1)
            elif url.startswith("postgresql://"):
                url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
            self.DATABASE_ASYNC_URL = url
        return self
    REDIS_URL: str = Field("redis://localhost:6379/0", validation_alias="REDIS_URL")

    # Unipile Integration
    UNIPILE_API_KEY: str = Field("unip_live_stub", validation_alias="UNIPILE_API_KEY")
    UNIPILE_BASE_URL: str = Field("https://api.unipile.com/api/v1", validation_alias="UNIPILE_BASE_URL")
    UNIPILE_ACCOUNT_ID: str | None = Field(None, validation_alias="UNIPILE_ACCOUNT_ID")

    # Apollo Integration
    APOLLO_API_KEY: str | None = Field(None, validation_alias="APOLLO_API_KEY")

    # Twilio Integration
    TWILIO_ACCOUNT_SID: str | None = Field(None, validation_alias="TWILIO_ACCOUNT_SID")
    TWILIO_AUTH_TOKEN: str | None = Field(None, validation_alias="TWILIO_AUTH_TOKEN")
    TWILIO_FROM_NUMBER: str | None = Field(None, validation_alias="TWILIO_FROM_NUMBER")

    # Public base URL the backend is reachable at, used for Twilio status callbacks.
    # Historically this reused the frontend's NEXT_PUBLIC_API_URL var name; kept as
    # the alias so no deployment env vars need to change.
    PUBLIC_BASE_URL: str = Field("https://api.apexsdr.com", validation_alias="NEXT_PUBLIC_API_URL")

    # Voice AI (Sprint 7): Speech-to-Text (Deepgram) and Text-to-Speech
    # (ElevenLabs) providers for the conversational voice pipeline. Neither
    # is in the Sprint 6.1 required-production-secrets list - USE_MOCK_CLIENTS
    # continues to gate provider selection the same way every other
    # mock/production adapter pair in this codebase does.
    DEEPGRAM_API_KEY: str | None = Field(None, validation_alias="DEEPGRAM_API_KEY")
    ELEVENLABS_API_KEY: str | None = Field(None, validation_alias="ELEVENLABS_API_KEY")
    ELEVENLABS_VOICE_ID: str = Field("21m00Tcm4TlvDq8ikWAM", validation_alias="ELEVENLABS_VOICE_ID")

    # Enrichment API Keys
    PROSPEO_API_KEY: str | None = Field(None, validation_alias="PROSPEO_API_KEY")
    KASPR_API_KEY: str | None = Field(None, validation_alias="KASPR_API_KEY")
    CONTACTOUT_API_KEY: str | None = Field(None, validation_alias="CONTACTOUT_API_KEY")

    # Gemini Integration
    GEMINI_API_KEY: str | None = Field(None, validation_alias="GEMINI_API_KEY")

    # HubSpot CRM Integration
    HUBSPOT_API_KEY: str | None = Field(None, validation_alias="HUBSPOT_API_KEY")

    # Google Calendar Integration
    GOOGLE_CLIENT_ID: str | None = Field(None, validation_alias="GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET: str | None = Field(None, validation_alias="GOOGLE_CLIENT_SECRET")
    GOOGLE_REFRESH_TOKEN: str | None = Field(None, validation_alias="GOOGLE_REFRESH_TOKEN")

    # Signed engagement tokens (chatbot/CTA webhook) - also the JWT signing
    # key for API authentication (app.core.security.JWTAuthProvider). No
    # insecure default: if unset, JWT auth fails closed rather than trusting
    # unsigned/unverifiable tokens.
    SECRET_KEY: str | None = Field(None, validation_alias="SECRET_KEY")

    # Static API-key registry for server-to-server auth, e.g.
    # "key1:tenant_a,key2:tenant_b". Parsed via tenant_api_key_registry.
    # No default keys are provisioned - an empty registry rejects every key.
    TENANT_API_KEYS: str = Field("", validation_alias="TENANT_API_KEYS")

    # Shared secret Unipile is configured to send back in the `Unipile-Auth`
    # header on every webhook delivery (see developer.unipile.com/docs/webhooks-2).
    UNIPILE_WEBHOOK_SECRET: str | None = Field(None, validation_alias="UNIPILE_WEBHOOK_SECRET")

    # Apollo proxy rate limit, requests per tenant per 60s window.
    APOLLO_RATE_LIMIT_PER_MINUTE: int = Field(10, validation_alias="APOLLO_RATE_LIMIT_PER_MINUTE")

    # ICP search/preview proxy rate limit, requests per tenant per 60s window.
    ICP_RATE_LIMIT_PER_MINUTE: int = Field(10, validation_alias="ICP_RATE_LIMIT_PER_MINUTE")

    # Resend inbound-email webhook signing secret ("whsec_..."), delivered via
    # Svix per resend.com/docs/webhooks/verify-webhooks-requests.
    RESEND_WEBHOOK_SECRET: str | None = Field(None, validation_alias="RESEND_WEBHOOK_SECRET")

    # Safety limits
    MAX_LINKEDIN_INVITES_PER_DAY: int = Field(20, validation_alias="MAX_LINKEDIN_INVITES_PER_DAY")
    GLOBAL_MAX_RETRY_ATTEMPTS: int = Field(5, validation_alias="GLOBAL_MAX_RETRY_ATTEMPTS")
    
    # Testing & Dev
    USE_MOCK_CLIENTS: bool = Field(False, validation_alias="USE_MOCK_CLIENTS")

    # Compliance: comma-separated policy names ProductionComplianceProvider
    # loads at runtime (see services/compliance/production.py) - lets ops
    # enable/disable/reorder policies without a code change. Unknown names
    # are ignored; MockComplianceProvider always runs the fixed default set
    # regardless of this setting.
    COMPLIANCE_ENABLED_POLICIES: str = Field("DO_NOT_CONTACT,BUSINESS_HOURS", validation_alias="COMPLIANCE_ENABLED_POLICIES")

    # Caching (Module 12): configurable TTLs for the read-through cache
    # layer in front of Apollo, waterfall enrichment, and buying signals.
    APOLLO_CACHE_TTL_SECONDS: int = Field(3600, validation_alias="APOLLO_CACHE_TTL_SECONDS")
    ENRICHMENT_CACHE_TTL_SECONDS: int = Field(86400, validation_alias="ENRICHMENT_CACHE_TTL_SECONDS")
    BUYING_SIGNALS_CACHE_TTL_SECONDS: int = Field(1800, validation_alias="BUYING_SIGNALS_CACHE_TTL_SECONDS")

    # Read from .env.production if it's there
    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env.production"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @model_validator(mode='after')
    def validate_production_secrets(self) -> 'Settings':
        """Fails fast at startup - not at first request - when a required
        secret is missing under ENVIRONMENT=production. Development/test
        environments are never subject to this check, so mock-mode local
        work is unaffected regardless of which secrets are configured."""
        if self.ENVIRONMENT != "production":
            return self
        missing = [name for name in _REQUIRED_PRODUCTION_SECRETS if not getattr(self, name)]
        if missing:
            raise RuntimeError(
                "Missing required production secret(s): "
                f"{', '.join(missing)}. Set these environment variables before "
                "starting the app with ENVIRONMENT=production."
            )
        return self

    @property
    def tenant_api_key_registry(self) -> dict:
        """Parses TENANT_API_KEYS ("key1:tenant_a,key2:tenant_b") into an
        {api_key: tenant_id} dict. Re-parsed on every access (cheap) rather
        than cached, so it reflects settings changes made at runtime (e.g.
        by tests)."""
        registry: dict = {}
        for pair in self.TENANT_API_KEYS.split(","):
            pair = pair.strip()
            if not pair or ":" not in pair:
                continue
            key, _, tenant_id = pair.partition(":")
            key, tenant_id = key.strip(), tenant_id.strip()
            if key and tenant_id:
                registry[key] = tenant_id
        return registry

settings = Settings()
