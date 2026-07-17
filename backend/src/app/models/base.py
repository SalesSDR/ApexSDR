import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.ext.asyncio import AsyncAttrs

class Base(AsyncAttrs, DeclarativeBase):
    """
    SQLAlchemy unified declarative base incorporating AsyncAttrs.
    """
    pass

class TenantMixin:
    """
    Mixin class injecting multi-tenant isolation tracking.
    """
    tenant_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
