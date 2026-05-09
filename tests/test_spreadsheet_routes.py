"""Integration tests for spreadsheet switcher, validation, and rename APIs."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.session_manager import SessionKeys


@pytest.fixture
def app_with_db(tmp_path):
    """Flask app with SQLite database and all tables."""
    from app import create_app
    from app.database import db

    db_path = tmp_path / "integration.sqlite"
    application = create_app()
    application.config.update(
        TESTING=True,
        SECRET_KEY="integration-test-secret",
        SQLALCHEMY_DATABASE_URI=f"sqlite:///{db_path}",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SESSION_TYPE="null",
    )
    db.init_app(application)
    with application.app_context():
        db.create_all()
    return application


def _session_as_user(client, user_id: int) -> None:
    with client.session_transaction() as sess:
        sess[SessionKeys.USER_ID.value] = user_id


def _seed_user_two_sheets():
    """Create one user with two spreadsheets; first is active."""
    from app.database import User, UserSpreadsheet, db
    from app.models import UserSpreadsheetProperty

    props = UserSpreadsheetProperty.get_default().to_db_string()
    user = User(google_user_id="gid_integration", email="int@test.dev", name="Integration")
    db.session.add(user)
    db.session.commit()

    a = UserSpreadsheet(
        user_id=user.id,
        spreadsheet_id="sheet_a",
        spreadsheet_name="Sheet A",
        is_active=True,
        properties=props,
    )
    b = UserSpreadsheet(
        user_id=user.id,
        spreadsheet_id="sheet_b",
        spreadsheet_name="Sheet B",
        is_active=False,
        properties=props,
    )
    db.session.add_all([a, b])
    db.session.commit()
    return user


def test_activate_spreadsheet_returns_summary_and_updates_db(app_with_db, monkeypatch):
    monkeypatch.setattr(
        "app.services.auth_manager.auth_manager.is_authenticated",
        lambda: True,
    )
    with app_with_db.app_context():
        user = _seed_user_two_sheets()
        user_id = user.id

    client = app_with_db.test_client()
    _session_as_user(client, user_id)

    response = client.post("/settings/activate-spreadsheet", json={"spreadsheet_id": "sheet_b"})
    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    assert body["spreadsheet"]["spreadsheet_id"] == "sheet_b"
    assert body["spreadsheet"]["is_active"] is True

    from app.database import UserSpreadsheet

    with app_with_db.app_context():
        active = UserSpreadsheet.query.filter_by(user_id=user_id, is_active=True).first()
        assert active is not None
        assert active.spreadsheet_id == "sheet_b"
        inactive = UserSpreadsheet.query.filter_by(user_id=user_id, is_active=False).all()
        assert len(inactive) == 1
        assert inactive[0].spreadsheet_id == "sheet_a"


def test_validate_spreadsheet_adds_sheet_and_returns_spreadsheet_payload(app_with_db, monkeypatch):
    monkeypatch.setattr(
        "app.services.auth_manager.auth_manager.is_authenticated",
        lambda: True,
    )
    monkeypatch.setattr(
        "app.services.settings_service.validate_spreadsheet_access",
        lambda sid: "Mock Title",
    )
    monkeypatch.setattr(
        "app.services.settings_service.read_all_card_sets",
        lambda sid: [SimpleNamespace(name="Tab1", cards=[1, 2])],
    )

    from app.database import User, db

    with app_with_db.app_context():
        user = User(google_user_id="gid_val", email="val@test.dev", name="V")
        db.session.add(user)
        db.session.commit()
        user_id = user.id

    client = app_with_db.test_client()
    _session_as_user(client, user_id)

    response = client.post(
        "/validate-spreadsheet",
        json={"spreadsheet_url": "https://docs.google.com/spreadsheets/d/abc123xyz"},
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    assert body["spreadsheet"]["spreadsheet_id"] == "abc123xyz"
    assert body["spreadsheet"]["spreadsheet_name"] == "Mock Title"
    assert body["spreadsheet"]["is_active"] is True
    assert any(cs["name"] == "Tab1" for cs in body["card_sets"])

    from app.database import UserSpreadsheet

    with app_with_db.app_context():
        row = UserSpreadsheet.query.filter_by(user_id=user_id, spreadsheet_id="abc123xyz").first()
        assert row is not None
        assert row.is_active is True


def test_rename_spreadsheet_clear_display_name(app_with_db, monkeypatch):
    monkeypatch.setattr(
        "app.services.auth_manager.auth_manager.is_authenticated",
        lambda: True,
    )
    with app_with_db.app_context():
        user = _seed_user_two_sheets()
        user_id = user.id

    client = app_with_db.test_client()
    _session_as_user(client, user_id)

    response = client.post(
        "/settings/rename-spreadsheet",
        json={"spreadsheet_id": "sheet_a", "new_name": "   "},
    )
    assert response.status_code == 200
    assert response.get_json()["success"] is True

    from app.database import UserSpreadsheet

    with app_with_db.app_context():
        row = UserSpreadsheet.query.filter_by(spreadsheet_id="sheet_a").first()
        assert row.spreadsheet_name is None
