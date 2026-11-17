"""Migrate a stopped LangTut SQLite database to independent login and Sheets grants."""

import argparse
import sqlite3
from contextlib import closing
from pathlib import Path

_MIGRATION = "independent_sessions_and_google_sheets"


def migrate_auth(database: Path) -> int:
    """Apply the migration once and return the number of connections copied."""
    database_uri = f"{database.resolve().as_uri()}?mode=rw"
    with closing(sqlite3.connect(database_uri, uri=True)) as connection, connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("BEGIN IMMEDIATE")
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_schema WHERE type='table'")
        }
        if not {"users", "refresh_tokens"} <= tables:
            raise ValueError("Expected an existing LangTut SQLite database")
        connection.execute("CREATE TABLE IF NOT EXISTS schema_migrations (name TEXT PRIMARY KEY)")
        if connection.execute(
            "SELECT 1 FROM schema_migrations WHERE name = ?", (_MIGRATION,)
        ).fetchone():
            return 0

        user_columns = {row[1] for row in connection.execute("PRAGMA table_info(users)")}
        if "session_version" not in user_columns:
            connection.execute(
                "ALTER TABLE users ADD COLUMN session_version INTEGER NOT NULL DEFAULT 0"
            )
        connection.execute("""
            CREATE TABLE IF NOT EXISTS google_sheets_connections (
                user_id INTEGER PRIMARY KEY NOT NULL REFERENCES users (id) ON DELETE CASCADE,
                google_user_id VARCHAR(255) NOT NULL,
                token_encrypted TEXT NOT NULL,
                granted_scopes JSON,
                created_at DATETIME NOT NULL,
                last_used DATETIME NOT NULL,
                last_rotated DATETIME NOT NULL
            )
        """)
        copied = connection.execute("""
            INSERT INTO google_sheets_connections
                (user_id, google_user_id, token_encrypted, created_at, last_used, last_rotated)
            SELECT ranked.user_id, users.google_user_id, ranked.token_encrypted,
                ranked.created_at, ranked.last_used, ranked.last_rotated
            FROM (
                SELECT refresh_tokens.*,
                    ROW_NUMBER() OVER (
                        PARTITION BY user_id ORDER BY last_used DESC, id DESC
                    ) AS grant_rank
                FROM refresh_tokens
            ) AS ranked
            JOIN users ON users.id = ranked.user_id
            WHERE ranked.grant_rank = 1
            ON CONFLICT(user_id) DO NOTHING
        """).rowcount
        connection.execute("INSERT INTO schema_migrations (name) VALUES (?)", (_MIGRATION,))
        return copied


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True, type=Path, help="Existing SQLite database")
    args = parser.parse_args()
    try:
        copied = migrate_auth(args.database)
    except (sqlite3.Error, ValueError):
        parser.exit(1, "Auth migration failed. Verify the database path and legacy schema.\n")
    print(f"Auth migration complete. Sheets connections copied: {copied}")


if __name__ == "__main__":
    main()
