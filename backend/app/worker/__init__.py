from __future__ import annotations

"""
Worker-related setup.

This module is intended for background job workers (e.g., Celery, RQ).
Business logic and concrete worker implementations will be added later.
"""

from flask import Flask


def create_worker_app() -> Flask:
    """
    Create and return a Flask application instance suitable for worker
    processes.

    For now this simply delegates to the main application factory; it can
    be customized later as the worker requirements become clearer.
    """
    from app import create_app  # local import to avoid circular dependency

    return create_app()

