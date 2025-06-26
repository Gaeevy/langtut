from googleapiclient.discovery import build

from src.auth import dict_to_credentials
from src.database import add_user_spreadsheet, get_or_create_user, get_user_active_spreadsheet


def get_google_user_info(credentials_dict):
    """Extract user information from Google OAuth credentials"""
    try:
        # Convert dict back to credentials object
        credentials = dict_to_credentials(credentials_dict)

        # Use the OAuth2 API to get user info (simpler and more reliable)
        service = build('oauth2', 'v2', credentials=credentials)
        user_info_response = service.userinfo().get().execute()

        return {
            'google_user_id': user_info_response.get('id') or user_info_response.get('email'),
            'email': user_info_response.get('email'),
            'name': user_info_response.get('name'),
        }

    except Exception as e:
        print(f'Error getting Google user info: {e}')
        return None


def get_current_user_from_session(session):
    """Get current user from Flask session"""
    if 'user_id' in session:
        from src.database import User

        return User.query.get(session['user_id'])
    return None


def login_user(session, credentials_dict):
    """Login user and store in session"""
    # Get user info from Google
    user_info = get_google_user_info(credentials_dict)
    if not user_info or not user_info['google_user_id']:
        raise Exception('Could not extract user information from Google')

    # Get or create user in database
    user = get_or_create_user(
        google_user_id=user_info['google_user_id'], email=user_info['email'], name=user_info['name']
    )

    # Store user ID in session
    session['user_id'] = user.id
    session['google_user_id'] = user.google_user_id

    print(f'User logged in: {user.email} (ID: {user.id})')
    return user


def get_user_spreadsheet_id(session):
    """Get the user's active spreadsheet ID from database"""
    user = get_current_user_from_session(session)
    if not user:
        return None

    active_spreadsheet = get_user_active_spreadsheet(user.id)
    if active_spreadsheet:
        return active_spreadsheet.spreadsheet_id

    return None


def set_user_spreadsheet(session, spreadsheet_id, spreadsheet_url=None, spreadsheet_name=None):
    """Set a spreadsheet as active for the current user"""
    user = get_current_user_from_session(session)
    if not user:
        raise Exception('User not logged in')

    # Add/update spreadsheet in database
    user_spreadsheet = add_user_spreadsheet(
        user_id=user.id,
        spreadsheet_id=spreadsheet_id,
        spreadsheet_url=spreadsheet_url,
        spreadsheet_name=spreadsheet_name,
        make_active=True,
    )

    print(f'Set active spreadsheet {spreadsheet_id} for user {user.email}')
    return user_spreadsheet


def clear_user_session(session):
    """Clear user session data"""
    keys_to_remove = ['user_id', 'google_user_id', 'credentials']
    for key in keys_to_remove:
        session.pop(key, None)
