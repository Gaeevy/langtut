"""Read-only spreadsheet-name lookup for the explicitly public MCP experiment."""

from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, EmailStr, TypeAdapter, ValidationError
from sqlalchemy import Engine, create_engine, func, select
from sqlalchemy.orm import Session

from app.database import User, UserSpreadsheet


class LookupStatus(StrEnum):
    OK = "ok"
    USER_NOT_FOUND = "user_not_found"
    INVALID_EMAIL = "invalid_email"
    AMBIGUOUS_USER = "ambiguous_user"
    UNAVAILABLE = "unavailable"


class SpreadsheetNames(BaseModel):
    """Public response; never includes account or spreadsheet identifiers."""

    status: LookupStatus
    spreadsheets: list[str] = []
    truncated: bool = False


def readonly_engine(path: Path) -> Engine:
    """Open an existing SQLite database without permitting writes or implicit creation."""
    if not path.is_file():
        raise ValueError("MCP database must already exist")
    return create_engine(
        f"sqlite+pysqlite:///{path.resolve().as_uri()}?mode=ro&uri=true",
        hide_parameters=True,
    )


def list_spreadsheet_names(engine: Engine, email: str) -> SpreadsheetNames:
    """Look up a normalized email and return at most 50 stored display names.

    Email is a public search filter, not an authenticated identity. Ambiguous matches
    fail closed because the existing database does not require unique email addresses.
    """
    if len(email) > 254:
        return SpreadsheetNames(status=LookupStatus.INVALID_EMAIL)
    try:
        normalized = str(TypeAdapter(EmailStr).validate_python(email.strip())).lower()
    except ValidationError:
        return SpreadsheetNames(status=LookupStatus.INVALID_EMAIL)

    with Session(engine) as session:
        users = session.scalars(
            select(User.id).where(func.lower(User.email) == normalized).limit(2)
        ).all()
        if not users:
            return SpreadsheetNames(status=LookupStatus.USER_NOT_FOUND)
        if len(users) > 1:
            return SpreadsheetNames(status=LookupStatus.AMBIGUOUS_USER)
        names = session.scalars(
            select(UserSpreadsheet.spreadsheet_name)
            .where(UserSpreadsheet.user_id == users[0])
            .order_by(UserSpreadsheet.id)
            .limit(51)
        ).all()
        return SpreadsheetNames(
            status=LookupStatus.OK,
            spreadsheets=[
                (name.strip() if name and name.strip() else "Unnamed spreadsheet")[:255]
                for name in names[:50]
            ],
            truncated=len(names) > 50,
        )
