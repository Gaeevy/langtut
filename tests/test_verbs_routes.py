"""Tests for irregular verbs routes and API."""

from pathlib import Path
from types import SimpleNamespace

from flask import Flask

from app.database import UserVerbInteraction, db
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
    monkeypatch.setattr(type(auth_manager), "user", property(lambda self: SimpleNamespace(id=1)))

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
    assert b"verbs-answers-data" in practice_response.data
    assert b"verbs_practice.js" in practice_response.data
    assert b"Score: 0/5" in practice_response.data


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
    monkeypatch.setattr(type(auth_manager), "user", property(lambda self: SimpleNamespace(id=1)))

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


def test_verbs_index_hides_form_count_and_has_localstorage_script(monkeypatch):
    """Verbs index removes forms count labels and includes localStorage script."""
    template_folder = Path(__file__).resolve().parents[1] / "app" / "templates"
    app = Flask(__name__, template_folder=str(template_folder))
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret"
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)
    register_blueprints(app)
    monkeypatch.setattr(auth_manager, "is_authenticated", lambda: True)
    monkeypatch.setattr(type(auth_manager), "user", property(lambda self: SimpleNamespace(id=1)))

    with app.app_context():
        db.create_all()
        _seed_verbs()

    client = app.test_client()
    response = client.get("/verbs")
    assert response.status_code == 200
    assert b"(5 forms)" not in response.data
    assert b"verbs_index.js" in response.data
    assert b"Practice" in response.data
    assert b">Load<" not in response.data


def test_verbs_progress_endpoint_updates_interaction(monkeypatch):
    """Progress API stores one interaction row for completed practice."""
    template_folder = Path(__file__).resolve().parents[1] / "app" / "templates"
    app = Flask(__name__, template_folder=str(template_folder))
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret"
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)
    register_blueprints(app)
    monkeypatch.setattr(auth_manager, "is_authenticated", lambda: True)
    monkeypatch.setattr(type(auth_manager), "user", property(lambda self: SimpleNamespace(id=7)))

    with app.app_context():
        db.create_all()
        seed = _seed_verbs()

    client = app.test_client()
    response = client.post(
        "/api/verbs/progress",
        json={
            "infinitive_id": seed["infinitive_id"],
            "tense_id": seed["tense_id"],
            "completed": True,
        },
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True

    with app.app_context():
        row = UserVerbInteraction.query.filter_by(
            user_id=7,
            infinitive_id=seed["infinitive_id"],
            tense_id=seed["tense_id"],
        ).first()
        assert row is not None
        assert row.shown_count == 1


def test_verbs_index_shows_shown_count_badge(monkeypatch):
    """Verbs list renders shown_count badge and no Practice row badge."""
    template_folder = Path(__file__).resolve().parents[1] / "app" / "templates"
    app = Flask(__name__, template_folder=str(template_folder))
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret"
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)
    register_blueprints(app)
    monkeypatch.setattr(auth_manager, "is_authenticated", lambda: True)
    monkeypatch.setattr(type(auth_manager), "user", property(lambda self: SimpleNamespace(id=9)))

    with app.app_context():
        db.create_all()
        seed = _seed_verbs()
        row = UserVerbInteraction(
            user_id=9,
            infinitive_id=seed["infinitive_id"],
            tense_id=seed["tense_id"],
            shown_count=3,
        )
        db.session.add(row)
        db.session.commit()

    client = app.test_client()
    response = client.get("/verbs")
    assert response.status_code == 200
    assert b">3<" in response.data
