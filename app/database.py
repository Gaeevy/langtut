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

    def get_active_spreadsheet_id(self):
        """Get the ID of the user's active spreadsheet.

        Returns:
            Spreadsheet ID string if user has an active spreadsheet, None otherwise
        """
        active = self.get_active_spreadsheet()
        return active.spreadsheet_id if active else None

    def get_all_spreadsheets(self):
        """Get all spreadsheets for this user, ordered by last used"""
        return (
            UserSpreadsheet.query.filter_by(user_id=self.id)
            .order_by(UserSpreadsheet.last_used.desc())
            .all()
        )

    def add_spreadsheet(
        self, spreadsheet_id, spreadsheet_url=None, spreadsheet_name=None, make_active=True
    ):
        """Add a spreadsheet to user's account.

        Args:
            spreadsheet_id: Google Sheets spreadsheet ID
            spreadsheet_url: Optional spreadsheet URL
            spreadsheet_name: Optional spreadsheet name
            make_active: Whether to set this as the active spreadsheet (default True)

        Returns:
            UserSpreadsheet object
        """
        # Check if spreadsheet already exists for this user
        existing = UserSpreadsheet.query.filter_by(
            user_id=self.id, spreadsheet_id=spreadsheet_id
        ).first()

        if existing:
            # Update existing spreadsheet
            existing.last_used = datetime.utcnow()
            if spreadsheet_url:
                existing.spreadsheet_url = spreadsheet_url
            if spreadsheet_name:
                existing.spreadsheet_name = spreadsheet_name
            if make_active:
                # Deactivate all other spreadsheets
                UserSpreadsheet.query.filter_by(user_id=self.id, is_active=True).update(
                    {"is_active": False}
                )
                existing.is_active = True
            db.session.commit()
            return existing

        # Deactivate all other spreadsheets if this should be active
        if make_active:
            UserSpreadsheet.query.filter_by(user_id=self.id, is_active=True).update(
                {"is_active": False}
            )

        # Create new spreadsheet with default properties
        from app.models import UserSpreadsheetProperty

        default_properties = UserSpreadsheetProperty.get_default()

        new_spreadsheet = UserSpreadsheet(
            user_id=self.id,
            spreadsheet_id=spreadsheet_id,
            spreadsheet_url=spreadsheet_url,
            spreadsheet_name=spreadsheet_name,
            is_active=make_active,
            properties=default_properties.to_db_string(),
        )

        db.session.add(new_spreadsheet)
        db.session.commit()
        return new_spreadsheet

    def activate_spreadsheet(self, spreadsheet_id):
        """Set a specific spreadsheet as active for this user.

        Args:
            spreadsheet_id: Google Sheets spreadsheet ID to activate

        Returns:
            UserSpreadsheet object if found, None otherwise
        """
        # Deactivate all spreadsheets
        UserSpreadsheet.query.filter_by(user_id=self.id, is_active=True).update(
            {"is_active": False}
        )

        # Activate target spreadsheet
        target_spreadsheet = UserSpreadsheet.query.filter_by(
            user_id=self.id, spreadsheet_id=spreadsheet_id
        ).first()

        if target_spreadsheet:
            target_spreadsheet.is_active = True
            target_spreadsheet.last_used = datetime.utcnow()
            db.session.commit()
            return target_spreadsheet

        return None

    def remove_spreadsheet(self, spreadsheet_id):
        """Remove a spreadsheet from user's account.

        Args:
            spreadsheet_id: Google Sheets spreadsheet ID to remove

        Returns:
            True if removed successfully, False if not found
        """
        spreadsheet = UserSpreadsheet.query.filter_by(
            user_id=self.id, spreadsheet_id=spreadsheet_id
        ).first()

        if spreadsheet:
            db.session.delete(spreadsheet)
            db.session.commit()
            return True

        return False

    def to_dict(self):
        return {
            "id": self.id,
            "google_user_id": self.google_user_id,
            "email": self.email,
            "name": self.name,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_login": self.last_login.isoformat() if self.last_login else None,
        }


class RefreshToken(db.Model):
    """Store encrypted refresh tokens for users.

    Each row represents a refresh token for a user session. Users can have
    multiple refresh tokens (e.g., different devices, different sessions).

    Tokens are encrypted at rest using Fernet symmetric encryption.
    """

    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    token_encrypted = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_used = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_rotated = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationship to user
    user = relationship("User", backref=db.backref("refresh_tokens", lazy=True))

    def __repr__(self):
        return f"<RefreshToken {self.id} for user {self.user_id}>"

    def encrypt_and_store(self, token: str) -> None:
        """Encrypt and store refresh token.

        Args:
            token: Plain text refresh token from Google OAuth
        """
        from app.utils import encrypt_token

        self.token_encrypted = encrypt_token(token)

    def get_decrypted_token(self) -> str:
        """Decrypt and return refresh token.

        Returns:
            Plain text refresh token

        Raises:
            ValueError: If token cannot be decrypted (corrupted or wrong key)
        """
        from app.utils import decrypt_token

        return decrypt_token(self.token_encrypted)

    def rotate_token(self, new_token: str) -> None:
        """Rotate refresh token (store new one).

        Called when Google provides a new refresh token during access token refresh.
        Updates the encrypted token and rotation timestamp.

        Args:
            new_token: New plain text refresh token from Google
        """
        from app.utils import encrypt_token

        self.token_encrypted = encrypt_token(new_token)
        self.last_rotated = datetime.utcnow()
        self.last_used = datetime.utcnow()

    def touch(self) -> None:
        """Update last_used timestamp.

        Called when the refresh token is used to obtain a new access token.
        """
        self.last_used = datetime.utcnow()


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
        from app.models import UserSpreadsheetProperty

        return UserSpreadsheetProperty.from_db_string(self.properties)

    def set_properties(self, properties):
        """Set properties from UserSpreadsheetProperty object."""
        from app.models import UserSpreadsheetProperty

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
    from app.config import config

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
        RefreshToken.query.first()
        _tables_created = True
    except:
        # Tables don't exist, create them
        db.create_all()
        _tables_created = True
