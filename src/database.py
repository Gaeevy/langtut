from datetime import datetime
from pathlib import Path

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

db = SQLAlchemy()


class User(db.Model):
    """User model for storing Google OAuth user information"""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    google_user_id = Column(String(255), unique=True, nullable=False, index=True)
    email = Column(String(255))
    name = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, default=datetime.utcnow)

    # Relationship to user spreadsheets
    spreadsheets = relationship(
        "UserSpreadsheet", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<User {self.email}>"

    def get_active_spreadsheet(self):
        """Get the user's currently active spreadsheet"""
        return UserSpreadsheet.query.filter_by(user_id=self.id, is_active=True).first()

    def to_dict(self):
        return {
            "id": self.id,
            "google_user_id": self.google_user_id,
            "email": self.email,
            "name": self.name,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_login": self.last_login.isoformat() if self.last_login else None,
        }


class UserSpreadsheet(db.Model):
    """Model for storing user's linked spreadsheets"""

    __tablename__ = "user_spreadsheets"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    spreadsheet_id = Column(String(255), nullable=False, index=True)
    spreadsheet_name = Column(String(255))  # User-defined name (future feature)
    spreadsheet_url = Column(Text)  # Full URL for reference
    is_active = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_used = Column(DateTime, default=datetime.utcnow)
    properties = Column(Text)  # JSON string storage

    # Relationship to user
    user = relationship("User", back_populates="spreadsheets")

    # Unique constraint to prevent duplicate spreadsheets per user
    __table_args__ = (
        db.UniqueConstraint("user_id", "spreadsheet_id", name="unique_user_spreadsheet"),
    )

    def __repr__(self):
        return f"<UserSpreadsheet {self.spreadsheet_id} for user {self.user_id}>"

    def get_properties(self):
        """Get UserSpreadsheetProperty object from JSON string."""
        from src.models import UserSpreadsheetProperty

        return UserSpreadsheetProperty.from_db_string(self.properties)

    def set_properties(self, properties):
        """Set properties from UserSpreadsheetProperty object."""
        from src.models import UserSpreadsheetProperty

        if isinstance(properties, UserSpreadsheetProperty):
            self.properties = properties.to_db_string()
        elif isinstance(properties, dict):
            # Create UserSpreadsheetProperty from dict
            prop_obj = UserSpreadsheetProperty(**properties)
            self.properties = prop_obj.to_db_string()
        else:
            raise ValueError("Properties must be UserSpreadsheetProperty object or dict")

    def get_language_settings(self) -> dict:
        """Get language settings from properties."""
        props = self.get_properties()
        return props.get_language_dict()

    def set_language_settings(self, language_settings: dict):
        """Set language settings in properties."""
        props = self.get_properties()
        props.set_language_dict(language_settings)
        self.set_properties(props)

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "spreadsheet_id": self.spreadsheet_id,
            "spreadsheet_name": self.spreadsheet_name,
            "spreadsheet_url": self.spreadsheet_url,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_used": self.last_used.isoformat() if self.last_used else None,
            "properties": self.properties,
            "language_settings": self.get_language_settings(),  # Add language settings to dict
        }


# Simple flag to track if tables have been created
_tables_created = False


def init_database(app):
    """Initialize database with Flask app"""
    from src.config import config

    # Get database path from config
    database_path = Path(config.database_path).resolve()

    # Ensure directory exists (for local development)
    database_path.parent.mkdir(parents=True, exist_ok=True)

    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{database_path}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)


def ensure_tables():
    """Create tables if they don't exist (Railway-safe)"""
    global _tables_created
    if _tables_created:
        return

    try:
        # Quick check if tables exist
        User.query.first()
        _tables_created = True
    except:
        # Tables don't exist, create them
        db.create_all()
        _tables_created = True


def get_or_create_user(google_user_id, email=None, name=None):
    """Get existing user or create new one"""
    ensure_tables()

    user = User.query.filter_by(google_user_id=google_user_id).first()

    if not user:
        user = User(google_user_id=google_user_id, email=email, name=name)
        db.session.add(user)
        db.session.commit()
    else:
        user.last_login = datetime.utcnow()
        if email and user.email != email:
            user.email = email
        if name and user.name != name:
            user.name = name
        db.session.commit()

    return user


def add_user_spreadsheet(
    user_id, spreadsheet_id, spreadsheet_url=None, spreadsheet_name=None, make_active=True
):
    """Add a spreadsheet to user's account"""
    ensure_tables()

    existing = UserSpreadsheet.query.filter_by(
        user_id=user_id, spreadsheet_id=spreadsheet_id
    ).first()

    if existing:
        existing.last_used = datetime.utcnow()
        if spreadsheet_url:
            existing.spreadsheet_url = spreadsheet_url
        if spreadsheet_name:
            existing.spreadsheet_name = spreadsheet_name
        if make_active:
            UserSpreadsheet.query.filter_by(user_id=user_id, is_active=True).update(
                {"is_active": False}
            )
            existing.is_active = True
        db.session.commit()
        return existing

    if make_active:
        UserSpreadsheet.query.filter_by(user_id=user_id, is_active=True).update(
            {"is_active": False}
        )

    # Create new spreadsheet with default properties
    from src.models import UserSpreadsheetProperty

    default_properties = UserSpreadsheetProperty.get_default()

    new_spreadsheet = UserSpreadsheet(
        user_id=user_id,
        spreadsheet_id=spreadsheet_id,
        spreadsheet_url=spreadsheet_url,
        spreadsheet_name=spreadsheet_name,
        is_active=make_active,
        properties=default_properties.to_db_string(),  # Initialize with default properties
    )

    db.session.add(new_spreadsheet)
    db.session.commit()
    return new_spreadsheet


def get_user_active_spreadsheet(user_id):
    """Get user's currently active spreadsheet"""
    ensure_tables()
    return UserSpreadsheet.query.filter_by(user_id=user_id, is_active=True).first()


def get_user_spreadsheets(user_id):
    """Get all spreadsheets for a user"""
    ensure_tables()
    return (
        UserSpreadsheet.query.filter_by(user_id=user_id)
        .order_by(UserSpreadsheet.last_used.desc())
        .all()
    )


def set_active_spreadsheet(user_id, spreadsheet_id):
    """Set a specific spreadsheet as active for the user"""
    ensure_tables()

    UserSpreadsheet.query.filter_by(user_id=user_id, is_active=True).update({"is_active": False})

    target_spreadsheet = UserSpreadsheet.query.filter_by(
        user_id=user_id, spreadsheet_id=spreadsheet_id
    ).first()

    if target_spreadsheet:
        target_spreadsheet.is_active = True
        target_spreadsheet.last_used = datetime.utcnow()
        db.session.commit()
        return target_spreadsheet

    return None


def remove_user_spreadsheet(user_id, spreadsheet_id):
    """Remove a spreadsheet from user's account"""
    ensure_tables()

    spreadsheet = UserSpreadsheet.query.filter_by(
        user_id=user_id, spreadsheet_id=spreadsheet_id
    ).first()

    if spreadsheet:
        db.session.delete(spreadsheet)
        db.session.commit()
        return True

    return False
