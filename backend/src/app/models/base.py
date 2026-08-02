from sqlalchemy import String
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


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
