"""Commit-aware wake-up signal; the database outbox remains the source of truth."""
import select

import psycopg2
from psycopg2 import sql
from sqlalchemy import text

from api.core.config import get_settings

PUSH_CHANNEL = "vard_push_ready"


def notify_push(db):
    # PostgreSQL delivers this only if the surrounding transaction commits.
    db.execute(text("SELECT pg_notify(:channel, '')"), {"channel": PUSH_CHANNEL})


class PushListener:
    def __init__(self):
        dsn = get_settings().database_url.replace("postgresql+psycopg2://", "postgresql://", 1)
        self.connection = psycopg2.connect(dsn, connect_timeout=5)
        try:
            self.connection.autocommit = True
            with self.connection.cursor() as cursor:
                cursor.execute(sql.SQL("LISTEN {}").format(sql.Identifier(PUSH_CHANNEL)))
        except Exception:
            self.connection.close()
            raise

    def wait(self, timeout=2):
        ready, _, _ = select.select([self.connection], [], [], timeout)
        if ready:
            self.connection.poll()
            self.connection.notifies.clear()
        return bool(ready)

    def close(self):
        self.connection.close()
