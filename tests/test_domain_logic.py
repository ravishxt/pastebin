from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Generator
from uuid import UUID

import pytest
from sqlalchemy import Select, create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.db import Base
from app.domain.models import AccessLog, Paste, PasteStatus
from app.domain.state_machine import (
    InvalidPasteStateTransition,
    validate_transition,
)
from app.repositories.paste_repository import (
    AccessLogRepository,
    PasteRepository,
)
from app.services.paste_service import (
    PasteNotFoundError,
    PasteService,
    PasteUnavailableError,
)


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="function")
def engine() -> Generator:
    """
    Create a fresh in-memory SQLite engine for each test function.

    This keeps tests focused on domain behavior while using a real database
    session for repository/service operations.
    """

    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture(scope="function")
def session(engine) -> Generator[Session, None, None]:
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    with SessionLocal() as session:
        yield session
        session.rollback()


@pytest.fixture
def paste_repo(session: Session) -> PasteRepository:
    return PasteRepository(session=session)


@pytest.fixture
def access_log_repo(session: Session) -> AccessLogRepository:
    return AccessLogRepository(session=session)


@pytest.fixture
def paste_service(engine) -> PasteService:
    """Service with its own session factory; each call gets a new session from the test engine."""
    from app.services.paste_service import PasteService

    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return PasteService(session_factory=session_factory)


# ---------------------------------------------------------------------------
# 1. Invalid state transition fails.
# ---------------------------------------------------------------------------


def test_invalid_state_transition_fails() -> None:
    with pytest.raises(InvalidPasteStateTransition):
        validate_transition(PasteStatus.EXPIRED, PasteStatus.ACTIVE)


# ---------------------------------------------------------------------------
# 2. Expired paste cannot be accessed.
# ---------------------------------------------------------------------------


def test_expired_paste_cannot_be_accessed(session: Session, paste_service: PasteService) -> None:
    # Create an already-expired paste (by status).
    paste = Paste(
        content="secret",
        max_views=5,
        current_views=1,
        status=PasteStatus.EXPIRED,
    )
    session.add(paste)
    session.commit()

    with pytest.raises(PasteUnavailableError):
        paste_service.retrieve_paste_for_view(paste_id=paste.id, ip_address="127.0.0.1")


# ---------------------------------------------------------------------------
# 3. View limit enforced correctly.
# 6. AccessLog created on view.
# ---------------------------------------------------------------------------


def test_view_limit_enforced_and_access_log_created(
    session: Session,
    paste_service: PasteService,
    engine,
) -> None:
    # Paste with a single allowed view.
    paste = Paste(
        content="once only",
        max_views=1,
        current_views=0,
        status=PasteStatus.ACTIVE,
    )
    session.add(paste)
    session.commit()

    # First view should succeed and consume the single allowed view.
    viewed = paste_service.retrieve_paste_for_view(
        paste_id=paste.id,
        ip_address="127.0.0.1",
    )
    # Service returns a dict DTO.
    assert viewed["current_views"] == 1
    assert viewed["max_views"] == 1
    assert viewed["status"] == "EXPIRED"

    # An AccessLog entry should have been created (in the service's session).
    # Use a new session to see committed data.
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    with SessionLocal() as s:
        stmt: Select[AccessLog] = select(AccessLog).where(AccessLog.paste_id == paste.id)
        logs = s.execute(stmt).scalars().all()
    assert len(logs) == 1
    assert logs[0].ip_address == "127.0.0.1"
    assert logs[0].success is True

    # Second view attempt should fail because paste is expired.
    with pytest.raises(PasteUnavailableError):
        paste_service.retrieve_paste_for_view(
            paste_id=paste.id,
            ip_address="127.0.0.1",
        )


# ---------------------------------------------------------------------------
# 4. Content cannot be modified.
# ---------------------------------------------------------------------------


def test_paste_content_is_immutable(session: Session) -> None:
    paste = Paste(
        content="immutable content",
        max_views=3,
        current_views=0,
        status=PasteStatus.ACTIVE,
    )
    session.add(paste)
    session.flush()

    # Attempting to modify content after initial creation should fail via validator.
    with pytest.raises(ValueError):
        paste.content = "new content"
        session.flush()


# ---------------------------------------------------------------------------
# 5. Expiry worker transitions state correctly (core domain behavior).
# ---------------------------------------------------------------------------


def test_expiry_worker_like_logic_expires_pastes(session: Session, paste_repo: PasteRepository) -> None:
    now_utc = datetime.now(timezone.utc)

    should_expire = Paste(
        content="expired by worker",
        max_views=5,
        current_views=0,
        status=PasteStatus.ACTIVE,
        expires_at=now_utc - timedelta(seconds=1),
    )
    should_stay_active = Paste(
        content="still active",
        max_views=5,
        current_views=0,
        status=PasteStatus.ACTIVE,
        expires_at=now_utc + timedelta(hours=1),
    )
    session.add_all([should_expire, should_stay_active])
    session.commit()

    # Mimic the selection logic used by the expiry worker.
    stmt: Select[Paste] = select(Paste).where(
        Paste.status.in_([PasteStatus.ACTIVE, PasteStatus.VIEWED]),
        Paste.expires_at.isnot(None),
        Paste.expires_at < now_utc,
    )
    for paste in session.execute(stmt).scalars().all():
        paste_repo.update_status_via_state_machine(paste, PasteStatus.EXPIRED)

    session.commit()
    session.refresh(should_expire)
    session.refresh(should_stay_active)

    assert should_expire.status == PasteStatus.EXPIRED
    assert should_stay_active.status == PasteStatus.ACTIVE


# ---------------------------------------------------------------------------
# 7. Atomic view increment works.
# ---------------------------------------------------------------------------


def test_atomic_view_increment(session: Session, paste_repo: PasteRepository) -> None:
    paste = Paste(
        content="increment views",
        max_views=10,
        current_views=0,
        status=PasteStatus.ACTIVE,
    )
    session.add(paste)
    session.commit()

    first = paste_repo.increment_view_count_atomic(paste.id)
    second = paste_repo.increment_view_count_atomic(paste.id)
    session.commit()

    # Values returned by the repository should reflect consecutive increments.
    assert first == 1
    assert second == 2

    # Database state should match the last value.
    refreshed = session.get(Paste, paste.id)
    assert refreshed is not None
    assert refreshed.current_views == 2

