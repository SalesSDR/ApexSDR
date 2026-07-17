import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, Boolean, Text, ForeignKey, DateTime, Index, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB

from app.models.base import Base, TenantMixin

class WorkspaceSetting(Base, TenantMixin):
    __tablename__ = "workspace_settings"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    follow_up_delay_hours: Mapped[int] = mapped_column(Integer, default=24)
    call_delay_hours: Mapped[int] = mapped_column(Integer, default=48)
    max_follow_ups: Mapped[int] = mapped_column(Integer, default=3)
    working_hours_start: Mapped[str] = mapped_column(String(5), default="09:00")  # HH:MM
    working_hours_end: Mapped[str] = mapped_column(String(5), default="17:00")    # HH:MM
    timezone: Mapped[str] = mapped_column(String(50), default="UTC")
    exclude_weekends: Mapped[bool] = mapped_column(Boolean, default=True)

class Campaign(Base, TenantMixin):
    __tablename__ = "campaigns"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Relationships
    prospects = relationship("Prospect", back_populates="campaign")

class Prospect(Base, TenantMixin):
    __tablename__ = "prospects"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    campaign_id: Mapped[Optional[str]] = mapped_column(ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    linkedin_url: Mapped[str] = mapped_column(Text, nullable=False)
    phone_number: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    company_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    provider_id: Mapped[Optional[str]] = mapped_column(String(100), index=True, nullable=True)
    current_state: Mapped[str] = mapped_column(String(50), default="PROSPECT_CREATED", index=True, nullable=False)
    
    # Relationships
    campaign = relationship("Campaign", back_populates="prospects")
    workflow_state = relationship("WorkflowState", back_populates="prospect", cascade="all, delete-orphan", uselist=False)
    follow_ups = relationship("FollowUp", back_populates="prospect", cascade="all, delete-orphan")
    activity_timeline = relationship("ActivityTimeline", back_populates="prospect", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_prospects_tenant_state", "tenant_id", "current_state"),
    )

class WorkflowState(Base, TenantMixin):
    __tablename__ = "workflow_states"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    prospect_id: Mapped[str] = mapped_column(ForeignKey("prospects.id", ondelete="CASCADE"), unique=True, nullable=False)
    state: Mapped[str] = mapped_column(String(50), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), onupdate=func.now(), default=func.now(), nullable=False)
    
    # Relationships
    prospect = relationship("Prospect", back_populates="workflow_state")

class FollowUp(Base, TenantMixin):
    __tablename__ = "follow_ups"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    prospect_id: Mapped[str] = mapped_column(ForeignKey("prospects.id", ondelete="CASCADE"), nullable=False)
    sequence_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="PENDING", index=True, nullable=False)  # PENDING, EXECUTED, CANCELED
    
    # Relationships
    prospect = relationship("Prospect", back_populates="follow_ups")

    __table_args__ = (
        Index("idx_followups_status_scheduled", "status", "scheduled_for"),
    )

class ActivityTimeline(Base, TenantMixin):
    __tablename__ = "activity_timelines"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    prospect_id: Mapped[str] = mapped_column(ForeignKey("prospects.id", ondelete="CASCADE"), nullable=False)
    channel: Mapped[str] = mapped_column(String(30), nullable=False)        # LINKEDIN, EMAIL, CALL, SYSTEM
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)     # SENT, ACCEPTED, REPLY, FAILED
    description: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), nullable=False)
    
    # Relationships
    prospect = relationship("Prospect", back_populates="activity_timeline")
