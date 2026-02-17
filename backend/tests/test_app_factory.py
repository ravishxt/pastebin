from __future__ import annotations

from flask import Flask

from app import create_app


def test_create_app_returns_flask_instance() -> None:
    app = create_app("testing")
    assert isinstance(app, Flask)

