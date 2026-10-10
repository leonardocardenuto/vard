from __future__ import annotations

import os
import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session


TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
if not TEST_DATABASE_URL:
    if os.getenv("APP_ENV") != "test":
        raise RuntimeError(
            "API integration tests require TEST_DATABASE_URL or APP_ENV=test with DATABASE_URL."
        )
    TEST_DATABASE_URL = os.getenv("DATABASE_URL")

if not TEST_DATABASE_URL or not TEST_DATABASE_URL.startswith(
    ("postgresql://", "postgresql+psycopg2://")
):
    raise RuntimeError("API integration tests require a PostgreSQL database URL.")

# These values must be set before importing the application because its settings
# and database engine are initialized at import time.
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ.setdefault("JWT_SECRET_KEY", "vard-api-integration-test-secret")
os.environ["REDIS_URL"] = ""
os.environ["FALL_MONITOR_ENABLED"] = "false"

from api.db import Base, get_db  # noqa: E402
from api.main import app  # noqa: E402


@pytest.fixture(scope="session")
def test_engine() -> Generator[Engine, None, None]:
    schema = f"test_{uuid.uuid4().hex}"
    admin_engine = create_engine(TEST_DATABASE_URL, future=True)

    with admin_engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))

    engine = create_engine(
        TEST_DATABASE_URL,
        future=True,
        connect_args={"options": f"-csearch_path={schema},public"},
    )
    Base.metadata.create_all(engine)

    try:
        yield engine
    finally:
        engine.dispose()
        with admin_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        admin_engine.dispose()


@pytest.fixture
def db_session(test_engine: Engine) -> Generator[Session, None, None]:
    connection = test_engine.connect()
    transaction = connection.begin()
    session = Session(
        bind=connection,
        autoflush=False,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )

    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
