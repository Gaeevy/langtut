"""
User management utilities for the Language Learning Flashcard App.

Handles user authentication, session management, and database operations for users.
"""

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from src.auth import get_credentials
from src.database import User, add_user_spreadsheet, db, get_user_active_spreadsheet
from src.session_manager import SessionKeys as sk
from src.session_manager import SessionManager as sm


def get_current_user() -> User | None:
    """
    Get the current authenticated user from the session.

    Returns:
        User object if authenticated, None otherwise
    """
    user_id = sm.get(sk.USER_ID)
    if user_id:
        return User.query.get(user_id)
    return None


def login_user(session_obj, credentials_dict):
    """
    Login user and create/update user record.

    Args:
        session_obj: Flask session object (for backward compatibility)
        credentials_dict: OAuth credentials dictionary

    Returns:
        User object for the logged-in user
    """
    # Get user info from credentials using the existing function
    user_info = get_google_user_info(credentials_dict)

    if not user_info:
        raise Exception("Failed to get user information from Google")

    google_user_id = user_info["google_user_id"]
    email = user_info["email"]

    # Find or create user
    user = User.query.filter_by(google_user_id=google_user_id).first()

    if not user:
        # Create new user
        user = User(google_user_id=google_user_id, email=email)
        db.session.add(user)
        db.session.commit()
        print(f"New user created: {email} (ID: {user.id})")
    else:
        # Update existing user email if it changed
        if user.email != email:
            user.email = email
            db.session.commit()
        print(f"User logged in: {email} (ID: {user.id})")

    # Store user info in session using SessionManager
    sm.set(sk.USER_ID, user.id)
    sm.set(sk.USER_GOOGLE_ID, user.google_user_id)

    return user


def clear_user_session(session_obj):
    """
    Clear user authentication data from session.

    Args:
        session_obj: Flask session object (for backward compatibility)
    """
    # Clear auth namespace
    sm.clear_namespace("auth")

    # Clear user namespace
    sm.clear_namespace("user")

    # Clear learning namespace
    sm.clear_namespace("learning")

    print("User session cleared")


def is_authenticated():
    """
    Check if the current user is authenticated.

    Returns:
        bool: True if user is authenticated with valid credentials
    """
    # Check if we have valid credentials
    credentials = get_credentials()
    if not credentials:
        return False

    # Check if we have user session data
    user_id = sm.get(sk.USER_ID)
    return user_id is not None


def get_google_user_info(credentials_dict):
    """Extract user information from Google OAuth credentials"""
    try:
        # Convert dict back to credentials object
        credentials = Credentials(**credentials_dict)

        # Use the OAuth2 API to get user info (simpler and more reliable)
        service = build("oauth2", "v2", credentials=credentials)
        user_info_response = service.userinfo().get().execute()

        return {
            "google_user_id": user_info_response.get("id") or user_info_response.get("email"),
            "email": user_info_response.get("email"),
            "name": user_info_response.get("name"),
        }

    except Exception as e:
        print(f"Error getting Google user info: {e}")
        return None


def get_user_spreadsheet_id(session_obj):
    """Get the user's active spreadsheet ID from database"""
    user = get_current_user()
    if not user:
        return None

    active_spreadsheet = get_user_active_spreadsheet(user.id)
    if active_spreadsheet:
        return active_spreadsheet.spreadsheet_id

    return None


def set_user_spreadsheet(spreadsheet_id, spreadsheet_url=None, spreadsheet_name=None):
    """Set a spreadsheet as active for the current user"""
    user = get_current_user()
    if not user:
        raise Exception("User not logged in")

    # Add/update spreadsheet in database
    user_spreadsheet = add_user_spreadsheet(
        user_id=user.id,
        spreadsheet_id=spreadsheet_id,
        spreadsheet_url=spreadsheet_url,
        spreadsheet_name=spreadsheet_name,
        make_active=True,
    )

    print(f"Set active spreadsheet {spreadsheet_id} for user {user.email}")
    return user_spreadsheet


def get_current_user_from_session(session_obj):
    """Get current user from Flask session (using SessionManager)"""
    user_id = sm.get(sk.USER_ID)
    if user_id:
        return User.query.get(user_id)
    return None
