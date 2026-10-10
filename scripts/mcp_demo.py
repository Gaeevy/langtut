"""Create a disposable MCP fixture database; refuses to overwrite any existing file."""

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import User, UserSpreadsheet


def main() -> None:
    """Seed synthetic accounts without loading Google or production configuration."""
    path = Path("data/mcp-demo.db")
    path.parent.mkdir(exist_ok=True)
    with path.open("xb"):
        pass
    engine = create_engine(f"sqlite:///{path.resolve()}")
    User.__table__.create(engine)
    UserSpreadsheet.__table__.create(engine)
    with Session(engine) as session:
        session.add_all(
            [
                User(id=1, google_user_id="demo-1", email="learner@example.com"),
                User(id=2, google_user_id="demo-2", email="empty@example.com"),
                User(id=3, google_user_id="demo-3", email="other@example.com"),
                UserSpreadsheet(
                    user_id=1, spreadsheet_id="demo-a", spreadsheet_name="Portuguese basics"
                ),
                UserSpreadsheet(user_id=1, spreadsheet_id="demo-b", spreadsheet_name="Travel"),
                UserSpreadsheet(
                    user_id=3, spreadsheet_id="demo-c", spreadsheet_name="Other vocabulary"
                ),
            ]
        )
        session.commit()
    engine.dispose()
    print("Created data/mcp-demo.db: learner@example.com, empty@example.com, other@example.com")


if __name__ == "__main__":
    main()
