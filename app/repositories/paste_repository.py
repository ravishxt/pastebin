from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Select, Update, select, update
from sqlalchemy.orm import Session

from app.domain.models import AccessLog, Paste, PasteStatus
from app.domain.state_machine import InvalidPasteStateTransition, validate_transition
from app.observability import get_correlation_id


logger = logging.getLogger(__name__)


class PasteRepository:
    """
    Repository for Paste aggregates.

    All database interaction for Paste should go through this class.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def create_paste(
        self,
        *,
        content: str,
        max_views: int,
        expires_at: Optional[datetime] = None,
        password_hash: Optional[str] = None,
    ) -> Paste:
        """
        Create and persist a new Paste.

        Note: Paste content is set only at creation time and is not exposed
        for updates via this repository.
        """

        paste = Paste(
            content=content,
            max_views=max_views,
            expires_at=expires_at,
            password_hash=password_hash,
        )
        self._session.add(paste)
        # Flush so that generated primary key and defaults are populated.
        self._session.flush()
        return paste

    def get_paste_by_id(self, paste_id: uuid.UUID) -> Optional[Paste]:
        """Return a Paste by its id, or ``None`` if not found."""

        stmt: Select[tuple[Paste]] = select(Paste).where(Paste.id == paste_id)
        return self._session.execute(stmt).scalar_one_or_none()

    def increment_view_count_atomic(self, paste_id: uuid.UUID) -> int:
        """
        Atomically increment the view count for a Paste.

        Returns the new ``current_views`` value.
        Raises ``LookupError`` if no Paste with the given id exists.
        """

        stmt: Update = (
            update(Paste)
            .where(Paste.id == paste_id)
            .values(current_views=Paste.current_views + 1)
            .returning(Paste.current_views)
        )
        result = self._session.execute(stmt)
        row = result.one_or_none()
        if row is None:
            raise LookupError(f"Paste with id {paste_id} not found.")

        (new_count,) = row
        return int(new_count)

    def update_status_via_state_machine(
        self,
        paste: Paste,
        next_status: PasteStatus | str,
    ) -> Paste:
        """
        Update a Paste status using the state machine.

        Delegates transition validation to the domain state machine, and only
        persists the change if the transition is allowed. Forbidden transitions
        result in ``InvalidPasteStateTransition``.
        """

        current = paste.status
        validate_transition(current_state=current, next_state=next_status)

        if isinstance(next_status, PasteStatus):
            paste.status = next_status
        else:
            try:
                paste.status = PasteStatus(next_status)
            except ValueError as exc:  # Should normally be caught by validate_transition
                raise InvalidPasteStateTransition(
                    f"Unknown paste state {next_status!r}"
                ) from exc

        self._session.add(paste)

        logger.info(
            "Paste status transition",
            extra={
                "event": "paste_status_transition",
                "paste_id": str(paste.id),
                "status_from": current.value,
                "status_to": paste.status.value,
                "correlation_id": get_correlation_id(),
            },
        )

        # Caller is responsible for committing.
        return paste


class AccessLogRepository:
    """
    Repository for AccessLog records.

    All database interaction for AccessLog should go through this class.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def create_access_log(
        self,
        *,
        paste_id: uuid.UUID,
        ip_address: Optional[str],
        success: bool,
        accessed_at: Optional[datetime] = None,
    ) -> AccessLog:
        """
        Create and persist a new AccessLog entry for a Paste.
        """

        log = AccessLog(
            paste_id=paste_id,
            ip_address=ip_address,
            success=success,
            accessed_at=accessed_at or datetime.utcnow(),
        )
        self._session.add(log)
        self._session.flush()
        return log

