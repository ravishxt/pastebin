from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.db import Base


class PasteStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    VIEWED = "VIEWED"
    EXPIRED = "EXPIRED"
    DELETED = "DELETED"


class Paste(Base):
    """Paste entity persisted via SQLAlchemy."""

    __tablename__ = "pastes"
    __table_args__ = (
        CheckConstraint("max_views >= 1", name="ck_pastes_max_views_min_1"),
        CheckConstraint(
            "current_views >= 0",
            name="ck_pastes_current_views_non_negative",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    max_views: Mapped[int] = mapped_column(Integer, nullable=False)
    current_views: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    status: Mapped[PasteStatus] = mapped_column(
        Enum(PasteStatus, name="paste_status_enum"),
        nullable=False,
        default=PasteStatus.ACTIVE,
        server_default=PasteStatus.ACTIVE.value,
    )
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    access_logs: Mapped[list["AccessLog"]] = relationship(
        back_populates="paste",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    @validates("content")
    def _validate_immutable_content(self, key: str, value: str) -> str:
        """
        Enforce that ``content`` is immutable after initial creation.

        The value can be set on new instances, but any subsequent attempt to
        change it will raise an error.
        """

        if getattr(self, "content", None) is not None and self.content != value:
            raise ValueError("Paste content is immutable and cannot be modified.")
        return value


class AccessLog(Base):
    """Access log entries for paste views."""

    __tablename__ = "access_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    paste_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pastes.id", ondelete="CASCADE"),
        nullable=False,
    )
    accessed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    success: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    paste: Mapped["Paste"] = relationship(back_populates="access_logs")

