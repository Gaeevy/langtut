"""Import helpers for irregular verbs."""

import logging

from app.database import VerbForm, VerbInfinitive, VerbTense, db
from app.models import VerbImportRequest

logger = logging.getLogger(__name__)


def upsert_from_import_payload(payload: VerbImportRequest) -> dict:
    """Create or update verb rows from one denormalized payload."""
    infinitive_value = payload.infinitive.strip()
    tense_value = payload.tense.strip()

    infinitive = VerbInfinitive.query.filter_by(value=infinitive_value).first()
    if not infinitive:
        infinitive = VerbInfinitive(value=infinitive_value)
        db.session.add(infinitive)
        db.session.flush()

    tense = VerbTense.query.filter_by(value=tense_value).first()
    if not tense:
        tense = VerbTense(value=tense_value)
        db.session.add(tense)
        db.session.flush()

    created_forms = 0
    updated_forms = 0

    for person, form_input in payload.forms.items():
        verb_form = VerbForm.query.filter_by(
            infinitive_id=infinitive.id,
            tense_id=tense.id,
            person=person,
        ).first()

        if not verb_form:
            verb_form = VerbForm(
                infinitive_id=infinitive.id,
                tense_id=tense.id,
                person=person,
                value=form_input.value.strip(),
                differs_from_regular=form_input.differs_from_regular,
            )
            db.session.add(verb_form)
            created_forms += 1
        else:
            verb_form.value = form_input.value.strip()
            verb_form.differs_from_regular = form_input.differs_from_regular
            updated_forms += 1

    db.session.commit()

    logger.info(
        "Upserted irregular forms for infinitive='%s', tense='%s': created=%d, updated=%d",
        infinitive.value,
        tense.value,
        created_forms,
        updated_forms,
    )

    return {
        "infinitive_id": infinitive.id,
        "tense_id": tense.id,
        "created_forms": created_forms,
        "updated_forms": updated_forms,
    }
