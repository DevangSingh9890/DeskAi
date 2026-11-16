from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Index, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.database import Base


class TicketRecord(Base):
    __tablename__ = "tickets"
    __table_args__ = (
        Index("ix_tickets_priority_status", "priority", "status"),
        Index("ix_tickets_category_priority", "category", "priority"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticket_id: Mapped[str] = mapped_column(
        String(32), unique=True, nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    subcategory: Mapped[str] = mapped_column(String(100), nullable=False)
    priority: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="Open"
    )
    assigned_group: Mapped[str] = mapped_column(String(150), nullable=False)
    created_by: Mapped[str] = mapped_column(
        String(150), nullable=False, server_default="user"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    resolution: Mapped[str | None] = mapped_column(Text, nullable=True)


class TicketApprovalRecord(Base):
    __tablename__ = "ticket_approvals"

    approval_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    ticket_data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
