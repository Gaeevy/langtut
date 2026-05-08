"""Service layer for irregular verbs feature."""

from app.database import VerbForm, VerbInfinitive, VerbTense, db
from app.models import VerbPracticeContext, VerbPracticeResult

PERSON_LABELS: dict[int, str] = {
    1: "eu",
    2: "tu",
    3: "ele/ela/você",
    4: "nós",
    5: "eles/elas/vocês",
}


class VerbsService:
    """Business logic for irregular verbs browse and practice."""

    def list_tenses(self) -> list[dict]:
        """Return all tenses with forms count."""
        rows = (
            db.session.query(
                VerbTense.id,
                VerbTense.value,
                db.func.count(VerbForm.id).label("forms_count"),
            )
            .outerjoin(VerbForm, VerbForm.tense_id == VerbTense.id)
            .group_by(VerbTense.id, VerbTense.value, VerbTense.display_order)
            .order_by(VerbTense.display_order.asc().nullslast(), VerbTense.value.asc())
            .all()
        )

        return [
            {"id": row.id, "value": row.value, "forms_count": int(row.forms_count or 0)}
            for row in rows
        ]

    def list_infinitives_for_tense(self, tense_id: int) -> list[dict]:
        """Return infinitives that have forms in the selected tense."""
        rows = (
            db.session.query(VerbInfinitive.id, VerbInfinitive.value)
            .join(VerbForm, VerbForm.infinitive_id == VerbInfinitive.id)
            .filter(VerbForm.tense_id == tense_id)
            .group_by(VerbInfinitive.id, VerbInfinitive.value)
            .order_by(VerbInfinitive.value.asc())
            .all()
        )
        return [{"id": row.id, "value": row.value} for row in rows]

    def get_practice_context(self, tense_id: int, infinitive_id: int) -> VerbPracticeContext | None:
        """Build one practice page context for infinitive + tense."""
        forms = (
            VerbForm.query.filter_by(tense_id=tense_id, infinitive_id=infinitive_id)
            .order_by(VerbForm.person.asc())
            .all()
        )
        if not forms:
            return None

        tense = db.session.get(VerbTense, tense_id)
        infinitive = db.session.get(VerbInfinitive, infinitive_id)
        if not tense or not infinitive:
            return None

        return VerbPracticeContext(
            infinitive_id=infinitive.id,
            infinitive=infinitive.value,
            tense_id=tense.id,
            tense=tense.value,
            forms={form.person: form.value for form in forms},
            person_labels=PERSON_LABELS,
        )

    def check_answers(
        self,
        tense_id: int,
        infinitive_id: int,
        submitted_forms: dict[int, str],
    ) -> VerbPracticeResult | None:
        """Validate five submitted forms against stored values."""
        context = self.get_practice_context(tense_id=tense_id, infinitive_id=infinitive_id)
        if not context:
            return None

        expected_forms = context.forms
        normalized_submitted = {
            person: submitted_forms.get(person, "").strip() for person in PERSON_LABELS
        }

        per_person_correct = {
            person: normalized_submitted[person].casefold()
            == expected_forms[person].strip().casefold()
            for person in PERSON_LABELS
        }
        total_correct = sum(1 for is_ok in per_person_correct.values() if is_ok)

        return VerbPracticeResult(
            infinitive=context.infinitive,
            tense=context.tense,
            expected_forms=expected_forms,
            submitted_forms=normalized_submitted,
            per_person_correct=per_person_correct,
            total_correct=total_correct,
        )
