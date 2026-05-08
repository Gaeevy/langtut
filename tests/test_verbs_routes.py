"""Tests for irregular verbs routes and API."""

from pathlib import Path

from flask import Flask

from app.database import db
from app.import_verbs import upsert_from_import_payload
from app.models import VerbImportRequest
from app.routes import register_blueprints
from app.services.auth_manager import auth_manager


def _seed_verbs() -> dict:
    return upsert_from_import_payload(
        VerbImportRequest(
            infinitive="dar",
            tense="presente do indicativo",
            forms={
                1: {"value": "dou", "differs_from_regular": True},
                2: {"value": "dás", "differs_from_regular": True},
                3: {"value": "dá", "differs_from_regular": True},
                4: {"value": "damos", "differs_from_regular": False},
                5: {"value": "dão", "differs_from_regular": True},
            },
        )
    )


def test_verbs_routes_render(monkeypatch):
    """Authenticated user can open verbs list and practice pages."""
    template_folder = Path(__file__).resolve().parents[1] / "app" / "templates"
    app = Flask(__name__, template_folder=str(template_folder))
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret"
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)
    register_blueprints(app)
    monkeypatch.setattr(auth_manager, "is_authenticated", lambda: True)

    with app.app_context():
        db.create_all()
        seed = _seed_verbs()

    client = app.test_client()
    index_response = client.get("/verbs")
    assert index_response.status_code == 200
    assert b"Irregular Verbs" in index_response.data

    practice_response = client.get(f"/verbs/practice/{seed['tense_id']}/{seed['infinitive_id']}")
    assert practice_response.status_code == 200
    assert b"Verb Practice" in practice_response.data

    submit_response = client.post(
        f"/verbs/practice/{seed['tense_id']}/{seed['infinitive_id']}",
        data={
            "form_1": "dou",
            "form_2": "dás",
            "form_3": "dá",
            "form_4": "damos",
            "form_5": "dão",
        },
    )
    assert submit_response.status_code == 200
    assert b"Score: 5/5" in submit_response.data


def test_verbs_api_forms_accepts_authenticated_user(monkeypatch):
    """Import API allows authenticated user without admin list."""
    template_folder = Path(__file__).resolve().parents[1] / "app" / "templates"
    app = Flask(__name__, template_folder=str(template_folder))
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret"
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)
    register_blueprints(app)
    monkeypatch.setattr(auth_manager, "is_authenticated", lambda: True)

    with app.app_context():
        db.create_all()

    client = app.test_client()

    payload = {
        "infinitive": "ser",
        "tense": "presente do indicativo",
        "forms": {
            "1": {"value": "sou", "differs_from_regular": True},
            "2": {"value": "és", "differs_from_regular": True},
            "3": {"value": "é", "differs_from_regular": True},
            "4": {"value": "somos", "differs_from_regular": True},
            "5": {"value": "são", "differs_from_regular": True},
        },
    }

    response = client.post("/api/verbs/forms", json=payload)
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True


def test_verbs_api_forms_rejects_unauthorized(monkeypatch):
    """Import API rejects callers without auth and import key."""
    template_folder = Path(__file__).resolve().parents[1] / "app" / "templates"
    app = Flask(__name__, template_folder=str(template_folder))
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret"
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)
    register_blueprints(app)
    monkeypatch.setattr(auth_manager, "is_authenticated", lambda: False)

    with app.app_context():
        db.create_all()

    client = app.test_client()
    response = client.post(
        "/api/verbs/forms",
        json={
            "infinitive": "ser",
            "tense": "presente do indicativo",
            "forms": {
                "1": {"value": "sou", "differs_from_regular": True},
                "2": {"value": "és", "differs_from_regular": True},
                "3": {"value": "é", "differs_from_regular": True},
                "4": {"value": "somos", "differs_from_regular": True},
                "5": {"value": "são", "differs_from_regular": True},
            },
        },
    )
    assert response.status_code == 401
