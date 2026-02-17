from __future__ import annotations

import os

from app import create_app


def main() -> None:
    env = os.getenv("APP_ENV", "development")
    app = create_app(env)

    host = os.getenv("FLASK_RUN_HOST", "0.0.0.0")
    port = int(os.getenv("FLASK_RUN_PORT", "5000"))

    app.run(host=host, port=port)


if __name__ == "__main__":
    main()

