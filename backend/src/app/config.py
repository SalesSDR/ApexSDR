import os
from typing import Optional
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    ENVIRONMENT: str = Field("production", validation_alias="ENVIRONMENT")
    DATABASE_URL: Optional[str] = Field(None, validation_alias="DATABASE_URL")
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
    UNIPILE_ACCOUNT_ID: Optional[str] = Field(None, validation_alias="UNIPILE_ACCOUNT_ID")
    UNIPILE_EMAIL_ACCOUNT_ID: Optional[str] = Field(None, validation_alias="UNIPILE_EMAIL_ACCOUNT_ID")

    # Apollo Integration
    APOLLO_API_KEY: Optional[str] = Field(None, validation_alias="APOLLO_API_KEY")

    # Twilio Integration
    TWILIO_ACCOUNT_SID: Optional[str] = Field(None, validation_alias="TWILIO_ACCOUNT_SID")
    TWILIO_AUTH_TOKEN: Optional[str] = Field(None, validation_alias="TWILIO_AUTH_TOKEN")
    TWILIO_FROM_NUMBER: Optional[str] = Field(None, validation_alias="TWILIO_FROM_NUMBER")
    NGROK_DOMAIN: Optional[str] = Field("YOUR_NGROK_DOMAIN", validation_alias="NGROK_DOMAIN")

    # Enrichment API Keys
    PROSPEO_API_KEY: Optional[str] = Field(None, validation_alias="PROSPEO_API_KEY")
    KASPR_API_KEY: Optional[str] = Field(None, validation_alias="KASPR_API_KEY")
    CONTACTOUT_API_KEY: Optional[str] = Field(None, validation_alias="CONTACTOUT_API_KEY")

    # Gemini Integration
    GEMINI_API_KEY: Optional[str] = Field(None, validation_alias="GEMINI_API_KEY")

    # Safety limits
    MAX_LINKEDIN_INVITES_PER_DAY: int = Field(20, validation_alias="MAX_LINKEDIN_INVITES_PER_DAY")
    GLOBAL_MAX_RETRY_ATTEMPTS: int = Field(5, validation_alias="GLOBAL_MAX_RETRY_ATTEMPTS")

    # Read from .env.production if it's there
    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env.production"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
