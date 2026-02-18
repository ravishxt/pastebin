from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.domain.models import Paste, PasteStatus
from app.observability import get_correlation_id
from app.repositories.paste_repository import (
    AccessLogRepository,
    PasteRepository,
)


logger = logging.getLogger(__name__)


def _paste_to_dto(paste: Paste) -> dict[str, Any]:
    """Convert a Paste ORM entity to a plain dict DTO. Status as string value."""
    return {
        "id": paste.id,
        "content": paste.content,
        "max_views": paste.max_views,
        "current_views": paste.current_views,
        "expires_at": paste.expires_at,
        "status": paste.status.value,
        "created_at": paste.created_at,
        "updated_at": paste.updated_at,
    }


class PasteError(Exception):
    """Base class for paste-related errors."""


class InvalidPasteParameters(PasteError):
    """Raised when creating a paste with invalid parameters."""


class PasteNotFoundError(PasteError):
    """Raised when a paste cannot be found."""


class PasteUnavailableError(PasteError):
    """Raised when a paste exists but cannot be viewed (expired/deleted)."""


MAX_CONTENT_BYTES = 10 * 1024  # 10 KiB


@dataclass
class PasteService:
    """
    Application service coordinating paste-related use cases.

    Owns session lifecycle: creates a session per use case, commits on success,
    rolls back on exception, and closes the session in a finally block.
    Returns plain dict DTOs; no ORM entities escape this layer.
    """

    session_factory: Callable[[], Session]

    # -------------------------------------------------------------------------
    # Creation
    # -------------------------------------------------------------------------
    def create_paste(
        self,
        *,
        content: str,
        max_views: int,
        expires_at: Optional[datetime] = None,
        password_hash: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Create a new paste enforcing business rules:

        - ``max_views`` must be >= 1
        - ``expires_at`` (if provided) must be in the future
        - ``content`` size must be <= 10 KiB (UTF-8 bytes)
        """
        if max_views < 1:
            logger.warning(
                "Invalid max_views when creating paste",
                extra={
                    "event": "paste_create_invalid_parameters",
                    "correlation_id": get_correlation_id(),
                },
            )
            raise InvalidPasteParameters("max_views must be >= 1.")

        encoded = content.encode("utf-8")
        if len(encoded) > MAX_CONTENT_BYTES:
            logger.warning(
                "Content too large when creating paste",
                extra={
                    "event": "paste_create_invalid_parameters",
                    "correlation_id": get_correlation_id(),
                },
            )
            raise InvalidPasteParameters(
                f"content must be at most {MAX_CONTENT_BYTES} bytes when UTF-8 encoded."
            )

        if expires_at is not None:
            # Require timezone-aware datetimes; treat naive as UTC only if desired.
            if expires_at.tzinfo is None:
                logger.warning(
                    "Naive expires_at when creating paste",
                    extra={
                        "event": "paste_create_invalid_parameters",
                        "correlation_id": get_correlation_id(),
                    },
                )
                raise InvalidPasteParameters(
                    "expires_at must be a timezone-aware datetime (UTC recommended)."
                )

            now_utc = datetime.now(timezone.utc)
            if expires_at <= now_utc:
                logger.warning(
                    "Past expires_at when creating paste",
                    extra={
                        "event": "paste_create_invalid_parameters",
                        "correlation_id": get_correlation_id(),
                    },
                )
                raise InvalidPasteParameters("expires_at must be in the future.")

        session = self.session_factory()
        try:
            paste_repo = PasteRepository(session=session)
            paste = paste_repo.create_paste(
                content=content,
                max_views=max_views,
                expires_at=expires_at,
                password_hash=password_hash,
            )
            logger.info(
                "Paste created",
                extra={
                    "event": "paste_created",
                    "paste_id": str(paste.id),
                    "correlation_id": get_correlation_id(),
                },
            )
            session.commit()
            return _paste_to_dto(paste)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    # -------------------------------------------------------------------------
    # Deletion
    # -------------------------------------------------------------------------
    def delete_paste(self, paste_id: uuid.UUID) -> dict[str, Any]:
        """
        Logically delete a paste by transitioning it to the DELETED state.

        The allowed transitions are governed by the paste state machine.
        """
        session = self.session_factory()
        try:
            paste_repo = PasteRepository(session=session)
            paste = paste_repo.get_paste_by_id(paste_id)
            if paste is None:
                raise PasteNotFoundError(f"Paste with id {paste_id} not found.")

            if paste.status in (PasteStatus.EXPIRED, PasteStatus.DELETED):
                raise PasteUnavailableError(
                    f"Paste {paste.id} cannot be deleted from status={paste.status.value}."
                )

            paste_repo.update_status_via_state_machine(
                paste,
                PasteStatus.DELETED,
            )
            logger.info(
                "Paste deleted",
                extra={
                    "event": "paste_deleted",
                    "paste_id": str(paste.id),
                    "correlation_id": get_correlation_id(),
                },
            )
            session.commit()
            return {"id": str(paste.id), "status": paste.status.value}
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    # -------------------------------------------------------------------------
    # Retrieval / viewing
    # -------------------------------------------------------------------------
    def retrieve_paste_for_view(
        self,
        paste_id: uuid.UUID,
        *,
        ip_address: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Retrieve a paste for viewing, enforcing view and expiry rules.

        Rules:
        - If status is EXPIRED or DELETED → raise PasteUnavailableError
        - If expires_at < now → transition to EXPIRED and raise PasteUnavailableError
        - If current_views >= max_views → transition to EXPIRED and raise PasteUnavailableError
        - Otherwise:
          - increment view count atomically
          - if current_views reaches max_views → transition to VIEWED or EXPIRED
          - log access
        """
        session = self.session_factory()
        try:
            paste_repo = PasteRepository(session=session)
            access_log_repo = AccessLogRepository(session=session)

            logger.info(
                "Paste access attempt",
                extra={
                    "event": "paste_access_attempt",
                    "paste_id": str(paste_id),
                    "correlation_id": get_correlation_id(),
                },
            )

            paste = paste_repo.get_paste_by_id(paste_id)
            if paste is None:
                raise PasteNotFoundError(f"Paste with id {paste_id} not found.")

            now_utc = datetime.now(timezone.utc)

            # Immediate rejection based on status.
            if paste.status in (PasteStatus.EXPIRED, PasteStatus.DELETED):
                raise PasteUnavailableError(
                    f"Paste {paste.id} is not available (status={paste.status.value})."
                )

            # Time-based expiry.
            if paste.expires_at is not None:
                expires_at = paste.expires_at
                if expires_at.tzinfo is None:
                    # Assume UTC for stored naive datetimes.
                    expires_at = expires_at.replace(tzinfo=timezone.utc)

                if expires_at <= now_utc:
                    paste_repo.update_status_via_state_machine(
                        paste,
                        PasteStatus.EXPIRED,
                    )
                    logger.info(
                        "Paste expired due to time",
                        extra={
                            "event": "paste_auto_expired",
                            "paste_id": str(paste.id),
                            "correlation_id": get_correlation_id(),
                        },
                    )
                    raise PasteUnavailableError(f"Paste {paste.id} has expired.")

            # View-count-based expiry prior to serving this view.
            if paste.current_views >= paste.max_views:
                paste_repo.update_status_via_state_machine(
                    paste,
                    PasteStatus.EXPIRED,
                )
                logger.info(
                    "Paste expired due to max views reached before access",
                    extra={
                        "event": "paste_auto_expired",
                        "paste_id": str(paste.id),
                        "correlation_id": get_correlation_id(),
                    },
                )
                raise PasteUnavailableError(
                    f"Paste {paste.id} has reached its view limit."
                )

            # At this point, the paste is eligible to be viewed. We now:
            # - increment view count atomically
            # - possibly transition status
            # - log access
            new_views = paste_repo.increment_view_count_atomic(paste.id)

            # Re-load the paste so that the caller gets up-to-date state.
            updated = paste_repo.get_paste_by_id(paste.id)
            if updated is None:
                # Highly unlikely under normal operation, but being defensive.
                raise PasteNotFoundError(
                    f"Paste with id {paste_id} disappeared during view operation."
                )

            # Decide status transitions based on the new view count.
            #
            # We use the allowed transitions:
            #   ACTIVE → VIEWED
            #   ACTIVE → EXPIRED
            #   VIEWED → EXPIRED
            #
            # Semantics:
            # - First successful view from ACTIVE moves to VIEWED (if views remain).
            # - When the last allowed view is consumed, the paste moves to EXPIRED.
            if updated.status == PasteStatus.ACTIVE:
                if new_views < updated.max_views:
                    # First successful view: mark as VIEWED.
                    paste_repo.update_status_via_state_machine(
                        updated,
                        PasteStatus.VIEWED,
                    )
                else:
                    # Last allowed view consumed: expire immediately.
                    paste_repo.update_status_via_state_machine(
                        updated,
                        PasteStatus.EXPIRED,
                    )
            elif updated.status == PasteStatus.VIEWED:
                if new_views >= updated.max_views:
                    paste_repo.update_status_via_state_machine(
                        updated,
                        PasteStatus.EXPIRED,
                    )

            # Log successful access.
            access_log_repo.create_access_log(
                paste_id=updated.id,
                ip_address=ip_address,
                success=True,
            )

            logger.info(
                "Paste access successful",
                extra={
                    "event": "paste_access_success",
                    "paste_id": str(updated.id),
                    "correlation_id": get_correlation_id(),
                },
            )
            session.commit()
            return _paste_to_dto(updated)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()


