from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone
from typing import NoReturn

from flask import Flask
from sqlalchemy import Select, select, inspect
from sqlalchemy.exc import ProgrammingError

from app.db import SessionLocal
from app.domain.models import Paste, PasteStatus
from app.observability import get_correlation_id
from app.repositories.paste_repository import PasteRepository


logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 10.0

_worker_started = False
_worker_lock = threading.Lock()


def _expiry_loop(app: Flask) -> NoReturn:
    """Background loop that periodically expires pastes."""

    with app.app_context():
        while True:
            session = SessionLocal()
            try:
                # If tables haven't been created yet (no migrations run), skip work
                # instead of spamming errors.
                bind = session.get_bind()
                inspector = inspect(bind)
                if not inspector.has_table("pastes"):
                    logger.info(
                        "Expiry worker: 'pastes' table not found; skipping cycle",
                        extra={
                            "event": "expiry_worker_no_table",
                            "correlation_id": get_correlation_id() or "expiry-worker",
                        },
                    )
                    session.rollback()
                    time.sleep(POLL_INTERVAL_SECONDS)
                    continue

                now_utc = datetime.now(timezone.utc)

                repo = PasteRepository(session=session)

                stmt: Select[Paste] = select(Paste).where(
                    Paste.status.in_([PasteStatus.ACTIVE, PasteStatus.VIEWED]),
                    Paste.expires_at.isnot(None),
                    Paste.expires_at < now_utc,
                )

                pastes = session.execute(stmt).scalars().all()
                for paste in pastes:
                    repo.update_status_via_state_machine(
                        paste,
                        PasteStatus.EXPIRED,
                    )
                    logger.info(
                        "Expiry worker: transitioned paste to EXPIRED",
                        extra={
                            "event": "expiry_worker_transition",
                            "paste_id": str(paste.id),
                            "correlation_id": get_correlation_id() or "expiry-worker",
                        },
                    )

                session.commit()
            except ProgrammingError:
                # If the table goes missing for some reason, avoid noisy stack traces.
                session.rollback()
                logger.warning(
                    "Expiry worker: database schema not ready; skipping cycle",
                    extra={
                        "event": "expiry_worker_schema_error",
                        "correlation_id": get_correlation_id() or "expiry-worker",
                    },
                )
            except Exception:  # pragma: no cover - defensive logging
                session.rollback()
                logger.exception(
                    "Error in expiry worker loop",
                    extra={
                        "event": "expiry_worker_error",
                        "correlation_id": get_correlation_id() or "expiry-worker",
                    },
                )
            finally:
                session.close()

            time.sleep(POLL_INTERVAL_SECONDS)


def start_expiry_worker(app: Flask) -> None:
    """
    Start the expiry worker in a background thread.

    This function is idempotent and will only start a single worker thread.
    """

    global _worker_started
    with _worker_lock:
        if _worker_started:
            return

        thread = threading.Thread(
            target=_expiry_loop,
            args=(app,),
            name="expiry-worker",
            daemon=True,
        )
        thread.start()
        _worker_started = True

