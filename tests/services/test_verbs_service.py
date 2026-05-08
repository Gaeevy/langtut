"""Tests for irregular verbs service."""

from flask import Flask

from app.database import db
from app.import_verbs import upsert_from_import_payload
from app.models import VerbImportRequest
from app.services.verbs_service import VerbsService


def _create_payload() -> VerbImportRequest:
    return VerbImportRequest(
        infinitive="ter",
        tense="presente do indicativo",
        forms={
            1: {"value": "tenho", "differs_from_regular": True},
            2: {"value": "tens", "differs_from_regular": True},
            3: {"value": "tem", "differs_from_regular": True},
            4: {"value": "temos", "differs_from_regular": False},
            5: {"value": "têm", "differs_from_regular": True},
        },
    )


def test_check_answers_after_import():
    """Service checks answers correctly after import helper inserts rows."""
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

    with app.app_context():
        db.create_all()
        service = VerbsService()

        import_result = upsert_from_import_payload(_create_payload())
        assert import_result["created_forms"] == 5
        assert import_result["updated_forms"] == 0

        tenses = service.list_tenses()
        assert len(tenses) == 1
        assert tenses[0]["forms_count"] == 5

        infinitives = service.list_infinitives_for_tense(import_result["tense_id"])
        assert len(infinitives) == 1
        assert infinitives[0]["value"] == "ter"

        check_result = service.check_answers(
            tense_id=import_result["tense_id"],
            infinitive_id=import_result["infinitive_id"],
            submitted_forms={1: "tenho", 2: "tens", 3: "tem", 4: "temos", 5: "têm"},
        )
        assert check_result is not None
        assert check_result.total_correct == 5
        assert check_result.is_fully_correct is True


def test_import_helper_updates_existing_rows():
    """Second import for same key updates existing rows."""
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

    with app.app_context():
        db.create_all()
        upsert_from_import_payload(_create_payload())

        payload = _create_payload()
        payload.forms[1].value = "TENHO"
        result = upsert_from_import_payload(payload)

        assert result["created_forms"] == 0
        assert result["updated_forms"] == 5
