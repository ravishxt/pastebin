from __future__ import annotations

import os

from flask import Flask

from .config import get_config
from .db import init_db
from .observability import init_observability


def create_app(env_name: str | None = None) -> Flask:
    """
    Application factory for the Flask backend.

    The configuration is selected based on the provided ``env_name`` or,
    if not given, the ``APP_ENV`` environment variable (falling back to
    ``development``).
    """
    if env_name is None:
        env_name = os.getenv("APP_ENV", "development")

    app = Flask(__name__)
    app_config = get_config(env_name)
    app.config.from_object(app_config)

    # Initialize infrastructure layers
    init_db(app)
    init_observability(app)

    # Blueprint registration will live here once API modules are implemented.
    # from .api import register_blueprints
    # register_blueprints(app)

    return app

