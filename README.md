# Backend – Pastebin Service

## Overview

This repository contains the backend service for a Pastebin-style application built using Flask, PostgreSQL, and SQLAlchemy.

The project is structured using a layered architecture to ensure clean separation of concerns, maintainability, and production readiness.

---

# Tech Stack

* Flask (Application framework)
* PostgreSQL (Relational database)
* SQLAlchemy (ORM)
* Alembic (Database migrations)
* Pytest (Testing)

---

# Architecture Overview

The backend follows a strict layered architecture:

API → Service → Repository → Domain → Database

Each layer has a single responsibility:

* **API Layer (`app/api/`)**
  Handles HTTP requests and responses. Contains route definitions and request/response schemas.

* **Service Layer (`app/services/`)**
  Contains business logic. Coordinates domain logic and repository calls.

* **Repository Layer (`app/repositories/`)**
  Responsible for database interaction using SQLAlchemy.

* **Domain Layer (`app/domain/`)**
  Contains core business models and state machine logic. Independent from Flask.

* **Worker (`app/worker/`)**
  Background process responsible for cleaning expired pastes.

* **Observability (`app/observability/`)**
  Structured logging and instrumentation hooks.

---

# Project Structure

```
app/
  api/
  services/
  repositories/
  domain/
  worker/
  observability/
  config.py
  db.py
migrations/
tests/
run.py
```

---

# Setup

## 1. Create Virtual Environment

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
```

## 2. Install Dependencies

```bash
pip install -r requirements.txt
```

---

# Configuration

Environment variables:

* `APP_ENV` – `development`, `production`, or `testing` (default: development)
* `DATABASE_URL` – Overrides default PostgreSQL connection string
* `SECRET_KEY` – Flask secret key

Default database URL:

```
postgresql+psycopg://postgres:postgres@localhost:5432/backend_db
```

---

# Running the Application

```bash
cd backend
python run.py
```

The application uses the Flask app factory pattern for environment-specific initialization.

---

# Database Setup & Migrations

1. Create the database in PostgreSQL.

2. Generate a migration:

```bash
cd backend
alembic revision -m "create initial schema"
```

3. Apply migrations:

```bash
alembic upgrade head
```

Alembic is configured to use `Base.metadata` from `app.db`.

---

# Background Worker

The expiry worker runs in a continuous loop with a 10-second polling interval.

Responsibilities:

* Identify expired pastes
* Delete or mark them accordingly

This separates asynchronous lifecycle management from request handling.

---

# Testing

Run tests with:

```bash
pytest
```

Tests include:

* App factory initialization
* Domain logic validation

---

# Production Readiness

* Layered architecture
* PostgreSQL transactional consistency
* Versioned migrations
* Background processing
* Environment-based configuration
* Structured logging
* Unit testing

---

# Design Goals

* Maintainable codebase
* Clear separation of concerns
* Scalable structure
* Testable business logic
* Production-grade configuration

This backend is structured intentionally to resemble real-world service architecture rather than a tutorial project.
