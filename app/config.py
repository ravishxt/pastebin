import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent


class BaseConfig:
    """Base application configuration shared across environments."""

    APP_NAME: str = "backend"

    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-key-change-me")

    # Database
    SQLALCHEMY_DATABASE_URI: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://evermile:password@localhost:5432/hookrelay",
    )
    SQLALCHEMY_ECHO: bool = False
    SQLALCHEMY_FUTURE: bool = True

    # Alembic
    ALEMBIC_CONFIG: str = os.getenv(
        "ALEMBIC_CONFIG",
        str(BASE_DIR / "alembic.ini"),
    )

    # Other Flask-style config flags
    TESTING: bool = False
    DEBUG: bool = False


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    SQLALCHEMY_ECHO = False


class ProductionConfig(BaseConfig):
    DEBUG = False


class TestingConfig(BaseConfig):
    TESTING = True
    SQLALCHEMY_ECHO = False

    SQLALCHEMY_DATABASE_URI: str = os.getenv(
        "TEST_DATABASE_URL",
        "postgresql+psycopg://evermile:password@localhost:5432/hookrelay",
    )


CONFIG_BY_NAME = {
    "development": DevelopmentConfig,
    "dev": DevelopmentConfig,
    "production": ProductionConfig,
    "prod": ProductionConfig,
    "testing": TestingConfig,
    "test": TestingConfig,
}


def get_config(env_name: str | None) -> type[BaseConfig]:
    """Return a config class for the given environment name."""
    if not env_name:
        return DevelopmentConfig
    return CONFIG_BY_NAME.get(env_name, DevelopmentConfig)

