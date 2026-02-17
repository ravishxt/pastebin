## Backend Flask Project

This repository contains a backend Flask service scaffolded with:

- Flask application factory in `backend/app/__init__.py`
- SQLAlchemy ORM setup in `backend/app/db.py`
- Configuration in `backend/app/config.py`
- Alembic migrations in `backend/migrations/`
- Basic tests in `backend/tests/`

Business/domain logic has intentionally **not** been implemented yet.

### Setup

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
```

### Running the application

Run from the project root:

```bash
cd backend
python run.py
```

Environment variables:

- `APP_ENV` – configuration profile (`development`, `production`, `testing`), default: `development`
- `DATABASE_URL` – SQLAlchemy database URI (overrides default PostgreSQL URL)
- `SECRET_KEY` – Flask secret key

### Database and migrations

The default database URL is:

```text
postgresql+psycopg://postgres:postgres@localhost:5432/backend_db
```

Create the database in PostgreSQL first, then manage schema with Alembic:

```bash
cd backend
alembic revision -m "create initial schema"
alembic upgrade head
```

The Alembic environment is configured to use `Base.metadata` from `app.db` as the migration target metadata.

### Tests

Run tests with:

```bash
pytest
```

