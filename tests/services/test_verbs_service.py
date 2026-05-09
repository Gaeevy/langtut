"""Tests for irregular verbs service."""

from flask import Flask

from app.database import User, UserVerbInteraction, db
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


def _create_payload_for_dar() -> VerbImportRequest:
    return VerbImportRequest(
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


def test_least_recently_shown_prefers_never_seen():
    """Least-recently-shown selection prefers verbs with no interaction row."""
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)

    with app.app_context():
        db.create_all()
        service = VerbsService()
        payload_ter = upsert_from_import_payload(_create_payload())
        payload_dar = upsert_from_import_payload(_create_payload_for_dar())
        user = User(google_user_id="u-1", email="u1@example.com")
        db.session.add(user)
        db.session.commit()

        service.mark_practice_completed(
            user_id=user.id,
            tense_id=payload_ter["tense_id"],
            infinitive_id=payload_ter["infinitive_id"],
        )

        next_item = service.get_least_recently_shown_infinitive(
            user_id=user.id,
            tense_id=payload_ter["tense_id"],
        )
        assert next_item is not None
        assert next_item["id"] == payload_dar["infinitive_id"]


def test_mark_practice_completed_upserts_one_row():
    """Completed practice updates one infinitive+tense interaction row."""
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)

    with app.app_context():
        db.create_all()
        payload = upsert_from_import_payload(_create_payload())
        user = User(google_user_id="u-2", email="u2@example.com")
        db.session.add(user)
        db.session.commit()

        service = VerbsService()
        service.mark_practice_completed(
            user_id=user.id,
            tense_id=payload["tense_id"],
            infinitive_id=payload["infinitive_id"],
        )
        first_row = UserVerbInteraction.query.filter_by(
            user_id=user.id,
            tense_id=payload["tense_id"],
            infinitive_id=payload["infinitive_id"],
        ).first()
        assert first_row is not None
        first_last_shown = first_row.last_shown

        service.mark_practice_completed(
            user_id=user.id,
            tense_id=payload["tense_id"],
            infinitive_id=payload["infinitive_id"],
        )
        rows = UserVerbInteraction.query.filter_by(
            user_id=user.id,
            tense_id=payload["tense_id"],
            infinitive_id=payload["infinitive_id"],
        ).all()
        assert len(rows) == 1
        assert rows[0].last_shown >= first_last_shown
        assert rows[0].shown_count == 2


def test_list_infinitives_for_tense_returns_shown_count_for_user():
    """Infinitive list exposes shown_count from user interaction."""
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)

    with app.app_context():
        db.create_all()
        payload = upsert_from_import_payload(_create_payload())
        user = User(google_user_id="u-3", email="u3@example.com")
        db.session.add(user)
        db.session.commit()

        service = VerbsService()
        service.mark_practice_completed(
            user_id=user.id,
            tense_id=payload["tense_id"],
            infinitive_id=payload["infinitive_id"],
        )

        infinitives = service.for_user(user.id).list_infinitives_for_tense(payload["tense_id"])
        assert len(infinitives) == 1
        assert infinitives[0]["shown_count"] == 1
