"""Verify auth cutover against a synthetic legacy SQLite database."""

import sqlite3
import subprocess
import sys
from contextlib import closing

import pytest
from flask import Flask

from app.database import GoogleSheetsConnection, User, check_auth_schema, db
from scripts.migrate_auth import migrate_auth


@pytest.fixture
def legacy_database(tmp_path):
    path = tmp_path / "legacy.sqlite"
    with closing(sqlite3.connect(path)) as connection:
        connection.executescript("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY, google_user_id VARCHAR(255) NOT NULL,
                email VARCHAR(255), name VARCHAR(255), created_at DATETIME, last_login DATETIME
            );
            CREATE TABLE refresh_tokens (
                id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, token_encrypted TEXT NOT NULL,
                created_at DATETIME NOT NULL, last_used DATETIME NOT NULL, last_rotated DATETIME NOT NULL
            );
            INSERT INTO users (id, google_user_id) VALUES
                (1, 'google-one'), (2, 'google-two'), (3, 'google-three');
            INSERT INTO refresh_tokens VALUES
                (1, 1, 'older', '2024-01-01', '2024-01-01', '2024-01-01'),
                (2, 1, 'tie-lower-id', '2024-01-01', '2024-02-01', '2024-01-01'),
                (3, 1, 'tie-higher-id', '2024-01-01', '2024-02-01', '2024-01-02'),
                (4, 1, 'highest-id-but-older', '2024-01-01', '2024-01-01', '2024-01-01'),
                (5, 2, 'other-user', '2024-01-01', '2024-01-01', '2024-01-01'),
                (6, 999, 'orphan', '2024-01-01', '2024-01-01', '2024-01-01');
        """)
    return path


def test_auth_migration_copies_latest_encrypted_grants_once(legacy_database):
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{legacy_database}"
    db.init_app(app)

    with app.app_context():
        with pytest.raises(RuntimeError, match=r"scripts\.migrate_auth"):
            check_auth_schema()

    assert migrate_auth(legacy_database) == 2
    with app.app_context():
        check_auth_schema()
        assert [user.session_version for user in User.query.order_by(User.id)] == [0, 0, 0]
        first = db.session.get(GoogleSheetsConnection, 1)
        assert (first.google_user_id, first.token_encrypted) == ("google-one", "tie-higher-id")
        assert first.last_rotated.isoformat().startswith("2024-01-02")
        assert first.granted_scopes is None
        second = db.session.get(GoogleSheetsConnection, 2)
        assert second.token_encrypted == "other-user"
        assert db.session.get(GoogleSheetsConnection, 3) is None
        assert db.session.get(GoogleSheetsConnection, 999) is None
        first.token_encrypted = "rotated"
        db.session.delete(second)
        db.session.commit()

    assert migrate_auth(legacy_database) == 0
    with closing(sqlite3.connect(legacy_database)) as connection:
        assert connection.execute(
            "SELECT user_id, token_encrypted FROM google_sheets_connections"
        ).fetchall() == [(1, "rotated")]
        assert connection.execute("SELECT COUNT(*) FROM refresh_tokens").fetchone() == (6,)


def test_failed_auth_migration_rolls_back_schema(legacy_database):
    with closing(sqlite3.connect(legacy_database)) as connection, connection:
        connection.execute("ALTER TABLE refresh_tokens DROP COLUMN last_rotated")

    with pytest.raises(sqlite3.OperationalError):
        migrate_auth(legacy_database)

    with closing(sqlite3.connect(legacy_database)) as connection:
        assert "session_version" not in {
            row[1] for row in connection.execute("PRAGMA table_info(users)")
        }
        assert (
            connection.execute(
                "SELECT name FROM sqlite_schema WHERE name = 'google_sheets_connections'"
            ).fetchone()
            is None
        )


def test_migration_command_reports_counts_without_payloads(legacy_database):
    result = subprocess.run(
        [sys.executable, "-m", "scripts.migrate_auth", "--database", str(legacy_database)],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout == "Auth migration complete. Sheets connections copied: 2\n"
    assert result.stderr == ""
