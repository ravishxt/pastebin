from __future__ import annotations

import os

from flask import Flask
from flask_cors import CORS

from .config import get_config
from .db import SessionLocal, init_db
from .observability import init_observability
from .api.pastes import api_bp
from .worker.expiry_worker import start_expiry_worker

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


    CORS(
        app
    )

    # Initialize infrastructure layers
    init_db(app)
    init_observability(app)

    # Register API blueprints
    app.register_blueprint(api_bp)

    # Start background expiry worker (disabled in testing)
    if not app.config.get("TESTING", False):
        start_expiry_worker(app)

    return app

