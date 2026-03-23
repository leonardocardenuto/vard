import argparse
from pathlib import Path

import psycopg2

from api.core.config import get_settings

settings = get_settings()


def normalize_postgres_dsn(dsn: str) -> str:
    return dsn.replace("postgresql+psycopg2://", "postgresql://", 1)


def ensure_migrations_table(cursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            filename text PRIMARY KEY,
            applied_at timestamptz NOT NULL DEFAULT now()
        );
        """
    )


def get_applied(cursor) -> set[str]:
    cursor.execute("SELECT filename FROM schema_migrations")
    return {row[0] for row in cursor.fetchall()}


def apply_migrations(directory: Path) -> None:
    files = sorted(directory.glob("*.sql"))
    if not files:
        print(f"No migration files found in {directory}")
        return

    with psycopg2.connect(normalize_postgres_dsn(settings.database_url)) as conn:
        with conn.cursor() as cursor:
            ensure_migrations_table(cursor)
            applied = get_applied(cursor)

            for file in files:
                if file.name in applied:
                    print(f"skip  {file.name}")
                    continue

                sql = file.read_text(encoding="utf-8")
                print(f"apply {file.name}")
                cursor.execute(sql)
                cursor.execute(
                    "INSERT INTO schema_migrations (filename) VALUES (%s)",
                    (file.name,),
                )

        conn.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply SQL migrations from sql/ folder")
    parser.add_argument("--dir", default="sql", help="Migration folder")
    args = parser.parse_args()

    apply_migrations(Path(args.dir))


if __name__ == "__main__":
    main()
