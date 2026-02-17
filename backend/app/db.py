from __future__ import annotations

import typing as t

from flask import Flask
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import declarative_base, scoped_session, sessionmaker


Base = declarative_base()

_engine: Engine | None = None
SessionLocal: scoped_session = scoped_session(
    sessionmaker(autocommit=False, autoflush=False)
)


def get_engine() -> Engine:
    """
    Return the global SQLAlchemy engine.

    This expects that ``init_db(app)`` has been called during application
    startup to configure the engine from Flask config.
    """
    if _engine is None:  # type: ignore[truthy-function]
        raise RuntimeError("Database engine is not initialized. Call init_db(app) first.")
    return t.cast(Engine, _engine)


def init_db(app: Flask) -> None:
    """
    Initialize the SQLAlchemy engine and session factory for the Flask app.

    Reads the database URL from ``app.config['SQLALCHEMY_DATABASE_URI']``.
    """
    global _engine

    database_uri = app.config.get("SQLALCHEMY_DATABASE_URI")
    if not database_uri:
        raise RuntimeError(
            "SQLALCHEMY_DATABASE_URI is not configured on the Flask app."
        )

    _engine = create_engine(
        database_uri,
        future=app.config.get("SQLALCHEMY_FUTURE", True),
        echo=app.config.get("SQLALCHEMY_ECHO", False),
    )
    SessionLocal.configure(bind=_engine)

    @app.teardown_appcontext
    def remove_session(_exc: Exception | None) -> None:  # type: ignore[unused-variable]
        """Remove the scoped session at the end of the request."""

        SessionLocal.remove()

