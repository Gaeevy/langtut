"""Resolve verified Google identities to local accounts."""

from datetime import UTC, datetime

from app.database import User, db
from app.services.google_oauth import GoogleIdentity


def login_or_create_user(identity: GoogleIdentity) -> User:
    """Find or create the local user by Google subject and update the user's profile."""
    user = User.query.filter_by(google_user_id=identity.google_user_id).first()
    if user is None:
        user = User(
            google_user_id=identity.google_user_id, email=identity.email, name=identity.name
        )
        db.session.add(user)
    else:
        user.last_login = datetime.now(UTC)
        user.email = identity.email or user.email
        user.name = identity.name or user.name
    db.session.commit()
    return user
