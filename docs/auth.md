# Authentication System Refactoring Plan

**Goal**: Centralize authentication logic into an `AuthManager` class with secure refresh token storage.

## Current Problems

- ❌ Auth logic scattered across multiple files (`services/auth.py`, `user_manager.py`, `gsheet.py`)
- ❌ Refresh tokens stored in session (security risk)
- ❌ Inconsistent authentication checks (sometimes `AUTH_CREDENTIALS`, sometimes `USER_ID`)
- ❌ Manual token refresh logic - not automatic
- ❌ No standardized route protection (no `@require_auth` decorator)
- ❌ Mixed concerns between auth, user management, and session management

## Target Architecture

```
AuthManager (src/services/auth_manager.py)
├── OAuth Flow Management
│   ├── initiate_login()
│   ├── handle_callback()
│   └── create_flow()
├── Credential Management
│   ├── get_credentials() -> Credentials | None
│   ├── refresh_credentials() -> bool
│   ├── store_access_token()
│   └── get_refresh_token_from_db()
├── Authentication State
│   ├── is_authenticated() -> bool
│   ├── require_auth() -> decorator
│   └── get_current_user() -> User | None
└── Session Management
    ├── clear_auth_session()
    └── login_user()

RefreshToken Model (database.py)
├── id (primary key)
├── user_id (foreign key to User)
├── token_encrypted (text)
├── created_at (timestamp)
├── last_used (timestamp)
└── expires_at (timestamp)

UserManager (user_manager.py) - Simplified
├── get_user_info()
├── create_or_update_user()
└── get_user_by_google_id()
```

## OAuth Flow & Token Lifecycle

### Authentication Flows

```
┌──────────────────────────────────────────────────────────────────────┐
│ SCENARIO 1: First Time Login / Re-Authentication (No Session)       │
└──────────────────────────────────────────────────────────────────────┘

1. User visits /learn → @require_auth checks session → No user_id found
2. Redirect to /auth → AuthManager.initiate_login()
3. User authorizes in Google → Google redirects to /oauth2callback
4. AuthManager.handle_callback() processes:
   a. Exchange authorization code for tokens
      - Access token (expires in ~1 hour)
      - Refresh token (long-lived, doesn't expire unless revoked)
      - ID token (contains google_user_id, email, name)
   b. Decode ID token to get google_user_id
   c. Find or create User in database using google_user_id
   d. Store refresh token in RefreshToken table (ENCRYPTED)
   e. Store access token + expiry in session (unencrypted - short-lived)
   f. Store user_id in session
5. Redirect to /learn → User authenticated


┌──────────────────────────────────────────────────────────────────────┐
│ SCENARIO 2: Active Session, Valid Access Token                      │
└──────────────────────────────────────────────────────────────────────┘

1. User visits /learn → @require_auth checks session
2. user_id exists in session → Call AuthManager.get_credentials()
3. Access token in session and not expired → Return credentials
4. Continue to /learn


┌──────────────────────────────────────────────────────────────────────┐
│ SCENARIO 3: Active Session, Expired Access Token                    │
└──────────────────────────────────────────────────────────────────────┘

1. User visits /learn → @require_auth checks session
2. user_id exists in session → Call AuthManager.get_credentials()
3. Access token expired → AuthManager._refresh_credentials(user_id)
4. Get refresh token from database (decrypt it)
5. Use refresh token to get new access token from Google
6. Google responds with new access token (MAY include new refresh token)
7. If Google rotated refresh token → Update database
8. Store new access token in session
9. Update last_used timestamp in RefreshToken table
10. Continue to /learn


┌──────────────────────────────────────────────────────────────────────┐
│ SCENARIO 4: Session Expired (No session, but DB has refresh token)  │
└──────────────────────────────────────────────────────────────────────┘

1. User visits /learn → @require_auth checks session → No user_id
2. Redirect to /auth → Start fresh OAuth flow (Scenario 1)
3. User re-authenticates → New refresh token stored in DB
4. Old refresh token remains in DB (can be cleaned up later)

Note: We DON'T automatically restore from database if session is gone.
This is a security feature - forces re-authentication after session expiry.
```

### Token Lifecycle & Rotation

**Access Token:**
- **Lifetime**: ~1 hour (Google's default)
- **Storage**: Flask session (unencrypted - short-lived is acceptable)
- **Refresh**: Automatic using refresh token from database
- **Rotation**: New token on every refresh

**Refresh Token:**
- **Lifetime**: Indefinite (until user revokes or policy expires)
- **Storage**: Database table (ENCRYPTED with Fernet)
- **Rotation Strategy**:
  - **On re-authentication**: New refresh token from OAuth flow → Stored in database
  - **On access token refresh**: Google MAY provide new refresh token → Update if provided
  - **Policy**: Google revokes after 6 months of inactivity or if user changes password
- **Multiple tokens**: User can have multiple refresh tokens (different sessions/devices)

**How We Get google_user_id:**
- Extracted from ID token during OAuth callback
- ID token is JWT containing: `sub` (google_user_id), `email`, `name`, etc.
- Used to find/create User record in database

### Token Rotation Logic

```python
# On OAuth callback (re-authentication)
def handle_callback():
    credentials = flow.credentials
    # Always get new refresh token on full OAuth flow
    refresh_token = credentials.refresh_token
    # Store/replace in database - this rotates the token
    save_refresh_token(user.id, refresh_token)

# On access token refresh
def _refresh_credentials():
    old_refresh_token = get_from_database(user_id)
    credentials.refresh(Request())  # Get new access token

    # Check if Google rotated the refresh token
    if credentials.refresh_token and credentials.refresh_token != old_refresh_token:
        # Google gave us a new one - update database
        update_refresh_token(user_id, credentials.refresh_token)

    # Update last_used timestamp regardless
    touch_refresh_token(user_id)
```

## Security Improvements

1. **Refresh Token Storage**
   - Store in database with encryption (not session)
   - Use separate `RefreshToken` table (no User table migration needed)
   - Encrypt using Fernet symmetric encryption
   - Each session can have its own refresh token

2. **Access Token Storage**
   - Store in session (short-lived ~1 hour, acceptable risk)
   - Automatic refresh before expiry (5-minute buffer)
   - Never stored in database

3. **Token Rotation**
   - Refresh token rotated on every re-authentication (full OAuth flow)
   - Google may rotate refresh token during access token refresh (we handle it)
   - Clean up expired/unused tokens periodically

## Implementation Steps

### Phase 1: Database Model

- [ ] Add `cryptography` to `pyproject.toml` dependencies
  - [ ] Run `uv add cryptography`

- [ ] Add token encryption utilities to `utils.py`
  - [ ] `get_encryption_key()` - Get key from config/environment
  - [ ] `encrypt_token(token: str) -> str` - Encrypt using Fernet
  - [ ] `decrypt_token(encrypted: str) -> str` - Decrypt using Fernet
  - [ ] Use `cryptography.fernet.Fernet` for symmetric encryption

- [ ] Create `RefreshToken` model in `database.py`
  - [ ] Add fields: `id`, `user_id`, `token_encrypted`, `created_at`, `last_used`, `last_rotated`
  - [ ] Add foreign key relationship to `User` with backref
  - [ ] Add helper methods:
    - [ ] `encrypt_and_store(token: str)` - Encrypt and store token
    - [ ] `get_decrypted_token() -> str` - Decrypt and return token
    - [ ] `rotate_token(new_token: str)` - Update token and rotation timestamp

- [ ] Update `database.py` `ensure_tables()` to create `RefreshToken` table
  - [ ] Will auto-create on next run, no migration needed

- [ ] Add `ENCRYPTION_KEY` to `.secrets.toml`
  - [ ] Generate with: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
  - [ ] Add to config validation

### Phase 2: Create AuthManager

- [ ] Add new SessionKeys to `session_manager.py`
  - [ ] `ACCESS_TOKEN` - Access token string
  - [ ] `ACCESS_TOKEN_EXPIRY` - Token expiry datetime
  - [ ] Keep existing: `USER_ID`, `AUTH_STATE`, `AUTH_REDIRECT_URI`

- [ ] Create `src/services/auth_manager.py` with `AuthManager` class
  - [ ] Add comprehensive class docstring (see above)
  - [ ] Import all required dependencies

- [ ] **OAuth Flow Methods**
  - [ ] `initiate_login(host: str) -> str`
    - Create OAuth flow using _create_flow()
    - Generate authorization URL with offline access
    - Store state in session
    - Store redirect_uri in session
    - Return authorization URL

  - [ ] `handle_callback(authorization_response: str, host: str) -> User`
    - Validate state parameter
    - Create OAuth flow with stored state
    - Fetch tokens using authorization_response
    - Decode ID token to extract google_user_id, email, name
    - Find or create User in database using google_user_id
    - Call _save_refresh_token() with user.id and refresh_token
    - Store access token + expiry in session
    - Store user_id in session
    - Return User object

  - [ ] `_create_flow(redirect_uri: str, state: str | None = None) -> Flow`
    - Load client secrets from config
    - Create Flow with scopes and redirect_uri
    - Include state if provided
    - Return Flow object

- [ ] **Credential Management Methods**
  - [ ] `get_credentials() -> Credentials | None`
    - Check if user_id in session
    - Get access token + expiry from session
    - If valid (not expired with 5-min buffer) → Return Credentials from session
    - If expired → Call _refresh_credentials(user_id)
    - If refresh successful → Return Credentials from session
    - If refresh failed → Return None

  - [ ] `_refresh_credentials(user_id: int) -> bool`
    - Get most recent RefreshToken from database for user_id
    - Decrypt refresh token
    - Create Credentials object with refresh token
    - Call credentials.refresh(Request())
    - Check if Google provided new refresh token
    - If new token → Call RefreshToken.rotate_token()
    - If same token → Call RefreshToken.touch()
    - Store new access token + expiry in session
    - Commit database changes
    - Return True on success, False on failure

  - [ ] `_save_refresh_token(user_id: int, token: str) -> None`
    - Create new RefreshToken record
    - Call encrypt_and_store(token)
    - Set user_id, created_at, last_used, last_rotated
    - Add to database session
    - Commit

  - [ ] `_credentials_from_session() -> Credentials | None`
    - Get access token + expiry from session
    - Create Credentials object (without refresh token)
    - Return Credentials

- [ ] **Authentication State Methods**
  - [ ] `is_authenticated() -> bool`
    - Try to get valid credentials using get_credentials()
    - Return True if credentials exist and valid, False otherwise

  - [ ] `require_auth` - Decorator for route protection
    - Check is_authenticated()
    - If True → Call wrapped function
    - If False → Redirect to auth.auth route
    - Preserve functools.wraps for proper function metadata

  - [ ] `get_current_user() -> User | None`
    - Get user_id from session
    - Query User.query.get(user_id)
    - Return User or None

- [ ] **Session Methods**
  - [ ] `clear_auth_session() -> None`
    - Clear auth namespace (AUTH_STATE, AUTH_CREDENTIALS, etc.)
    - Clear user namespace (USER_ID, USER_GOOGLE_ID)
    - Keep learning namespace (optional - decide later)

  - [ ] `logout() -> None`
    - Get user_id from session
    - Delete all RefreshToken records for user_id (or just current session)
    - Call clear_auth_session()
    - Optional: Revoke tokens with Google API

### Phase 3: Refactor Existing Code

- [ ] **Update `src/routes/auth.py`**
  - [ ] Refactor `/auth` route to use `AuthManager.initiate_login()`
  - [ ] Refactor `/oauth2callback` to use `AuthManager.handle_callback()`
  - [ ] Refactor `/clear` to use `AuthManager.logout()`

- [ ] **Update `src/user_manager.py`**
  - [ ] Remove `is_authenticated()` (move to AuthManager)
  - [ ] Remove `login_user()` credential handling (move to AuthManager)
  - [ ] Keep only user DB operations: `get_user_by_google_id()`, `create_or_update_user()`
  - [ ] Keep `get_current_user()` as alias to `AuthManager.get_current_user()`

- [ ] **Update `src/gsheet.py`**
  - [ ] Replace direct `get_credentials()` calls with `AuthManager.get_credentials()`
  - [ ] Remove credential imports from `services/auth.py`

- [ ] **Delete `src/services/auth.py`**
  - [ ] All utilities merged into `AuthManager`
  - [ ] `get_redirect_uri()` → `AuthManager._get_redirect_uri()`
  - [ ] `create_oauth_flow()` → `AuthManager._create_flow()`
  - [ ] `credentials_to_dict()` → Not needed (we store access token directly)

### Phase 4: Route Protection

- [ ] **Add `@require_auth` decorator**
  - [ ] Implement in `AuthManager`
  - [ ] Auto-redirects to login if not authenticated
  - [ ] Automatically refreshes tokens if needed

- [ ] **Apply decorator to protected routes**
  - [ ] `flashcard.py` routes
  - [ ] `settings.py` routes
  - [ ] `api.py` routes (or use different approach for API)

### Phase 5: Automatic Token Refresh

- [ ] **Add before_request handler**
  - [ ] Check if user is authenticated
  - [ ] Check if access token expires soon (< 5 minutes)
  - [ ] Automatically refresh if needed
  - [ ] Handle refresh failures gracefully

- [ ] **Update SessionKeys**
  - [ ] Add `ACCESS_TOKEN_EXPIRY` key
  - [ ] Store expiry time in session for quick checks

### Phase 6: Testing & Validation

- [ ] **Unit Tests**
  - [ ] Test `AuthManager.get_credentials()` with expired tokens
  - [ ] Test `AuthManager.refresh_credentials()`
  - [ ] Test `@require_auth` decorator
  - [ ] Test encryption/decryption of refresh tokens

- [ ] **Integration Tests**
  - [ ] Test full OAuth flow
  - [ ] Test token refresh flow
  - [ ] Test logout and session clearing
  - [ ] Test accessing protected routes

- [ ] **Manual Testing**
  - [ ] Login via OAuth
  - [ ] Verify refresh token stored in database (encrypted)
  - [ ] Wait for token expiry or manually expire
  - [ ] Verify automatic refresh works
  - [ ] Test logout clears all auth data
  - [ ] Test accessing protected routes without auth

### Phase 7: Cleanup & Documentation

- [ ] **Remove deprecated code**
  - [ ] Remove old auth functions from `user_manager.py`
  - [ ] Consider removing/merging `services/auth.py`
  - [ ] Clean up unused session keys

- [ ] **Update documentation**
  - [ ] Update `docs/architecture.md` with new auth flow
  - [ ] Document `AuthManager` API
  - [ ] Add security notes about token storage

- [ ] **Update cursor rules**
  - [ ] Add AuthManager usage patterns
  - [ ] Document `@require_auth` decorator usage

## Implementation Details

### RefreshToken Model Schema

```python
class RefreshToken(db.Model):
    """Store encrypted refresh tokens for users.

    Each row represents a refresh token for a user session. Users can have
    multiple refresh tokens (e.g., different devices, different sessions).

    Tokens are encrypted at rest using Fernet symmetric encryption.
    """
    __tablename__ = 'refresh_tokens'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    token_encrypted = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    last_used = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    last_rotated = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Relationship
    user = db.relationship('User', backref=db.backref('refresh_tokens', lazy=True))

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
```

### Token Encryption

```python
# In utils.py
from cryptography.fernet import Fernet
from app.config import config


def get_encryption_key() -> bytes:
    """Get encryption key from config."""
    # Key should be in .secrets.toml or environment
    key = config.get('ENCRYPTION_KEY')
    if not key:
        raise ValueError("ENCRYPTION_KEY not configured")
    return key.encode()


def encrypt_token(token: str) -> str:
    """Encrypt token using Fernet symmetric encryption."""
    f = Fernet(get_encryption_key())
    return f.encrypt(token.encode()).decode()


def decrypt_token(encrypted_token: str) -> str:
    """Decrypt token using Fernet symmetric encryption."""
    f = Fernet(get_encryption_key())
    return f.decrypt(encrypted_token.encode()).decode()
```

### Extracting google_user_id from ID Token

```python
# In AuthManager.handle_callback()
from google.auth.transport import requests
from google.oauth2 import id_token

# After fetching tokens
credentials = flow.credentials

# Verify and decode the ID token
id_info = id_token.verify_oauth2_token(
    credentials.id_token,
    requests.Request(),
    config.client_id
)

# Extract user info from decoded token
google_user_id = id_info['sub']  # Subject = unique Google user ID
email = id_info['email']
name = id_info.get('name', '')  # Optional field

# Now find or create user
user = User.query.filter_by(google_user_id=google_user_id).first()
if not user:
    user = User(google_user_id=google_user_id, email=email)
    db.session.add(user)
    db.session.commit()
```

### AuthManager Class Docstring

```python
class AuthManager:
    """Centralized authentication manager for Google OAuth2.

    This class handles the complete OAuth2 authentication lifecycle including:
    - OAuth flow initiation and callback handling
    - Secure token storage (access tokens in session, refresh tokens in database)
    - Automatic token refresh with transparent error handling
    - Authentication state management
    - Route protection via decorator

    Architecture & Token Storage:
    -----------------------------
    Access Tokens:
        - Stored in Flask session (unencrypted)
        - Lifetime: ~1 hour
        - Acceptable to store in session due to short lifetime
        - Automatically refreshed when expired

    Refresh Tokens:
        - Stored in database (RefreshToken table, ENCRYPTED with Fernet)
        - Lifetime: Indefinite (until user revokes or Google policy expires)
        - Used only to obtain new access tokens
        - Never exposed to client or stored in session

    User Identification:
        - google_user_id extracted from ID token during OAuth callback
        - Used to find/create User record in database
        - Session stores user_id for quick lookups

    Authentication Flow:
    --------------------
    Initial Login (No Session):
        1. User accesses protected route → Redirected to /auth
        2. initiate_login() creates OAuth flow → User authorizes in Google
        3. Google redirects to /oauth2callback with authorization code
        4. handle_callback() exchanges code for tokens:
           - Access token (short-lived)
           - Refresh token (long-lived)
           - ID token (contains google_user_id, email, name)
        5. Extract google_user_id from ID token
        6. Find or create User in database
        7. Store refresh token in database (ENCRYPTED)
        8. Store access token + expiry in session
        9. Store user_id in session
        10. User is authenticated

    Returning User (Has Session):
        1. User accesses protected route → @require_auth checks session
        2. get_credentials() called:
           a. Check if access token in session is valid
           b. If valid → Return credentials immediately
           c. If expired → _refresh_credentials() is called
        3. _refresh_credentials():
           a. Get encrypted refresh token from database
           b. Decrypt refresh token
           c. Use refresh token to get new access token from Google
           d. Check if Google rotated refresh token (may happen)
           e. If rotated → Update database with new refresh token
           f. Store new access token in session
           g. Update last_used timestamp in database
        4. Return valid credentials → User continues seamlessly

    Session Expired:
        1. No session data available
        2. User redirected to login (full OAuth flow)
        3. Security feature: Don't auto-restore from database

    Token Rotation:
    ---------------
    Refresh tokens are rotated in two scenarios:

    1. Re-authentication (Full OAuth Flow):
       - User goes through complete OAuth flow
       - Google issues new refresh token
       - Stored in database (replaces or adds to existing tokens)

    2. Access Token Refresh (Google-Initiated):
       - During automatic access token refresh
       - Google MAY issue new refresh token (not guaranteed)
       - We check and update database if provided
       - Old token remains valid until Google revokes it

    Security Features:
    ------------------
    - Refresh tokens encrypted at rest using Fernet symmetric encryption
    - Encryption key stored in .secrets.toml (never in code)
    - Access tokens only in session (ephemeral, short-lived)
    - Automatic token refresh with 5-minute buffer before expiry
    - Failed refresh → Clear session and redirect to login
    - No silent failures - always clear error handling
    - Session expiry requires re-authentication (no DB restoration)
    - Multiple refresh tokens per user supported (different devices)

    Thread Safety:
    --------------
    - Uses Flask session (thread-local by default)
    - Database operations use SQLAlchemy (handles connection pooling)
    - No shared mutable state in class

    Usage Examples:
    ---------------
    Route Protection:
        @flashcard_bp.route('/learn')
        @auth_manager.require_auth
        def learn():
            user = auth_manager.get_current_user()
            return render_template('card.html', user=user)

    Service Layer:
        def read_spreadsheet():
            creds = auth_manager.get_credentials()  # Auto-refreshes
            if not creds:
                raise AuthenticationError("Not authenticated")
            gc = gspread.authorize(creds)
            return gc.open_by_key(spreadsheet_id)

    Manual Auth Check:
        if auth_manager.is_authenticated():
            # User is authenticated with valid credentials
            pass

    Logout:
        auth_manager.logout()  # Clears session + removes refresh tokens

    Error Handling:
    ---------------
    - OAuth errors: Redirect to error page with message
    - Refresh failures: Clear session and redirect to login
    - Database errors: Log and treat as not authenticated
    - Decryption errors: Remove corrupted token and redirect to login

    Dependencies:
    -------------
    - google.oauth2.credentials (Credentials object)
    - google_auth_oauthlib.flow (OAuth flow)
    - app.database (User, RefreshToken models)
    - app.session_manager (SessionManager, SessionKeys)
    - app.utils (encrypt_token, decrypt_token)
    - app.config (OAuth configuration)

    Notes:
    ------
    - Google refresh tokens don't expire unless:
      * User revokes access
      * User changes password
      * 6 months of inactivity (Google policy)
      * Manually revoked by us
    - Access tokens expire after ~1 hour (Google default)
    - ID tokens are only used during OAuth callback (not stored)
    - Multiple refresh tokens per user allow multi-device sessions
    """
```

### AuthManager Usage Examples

```python
# In routes
from app.services.auth_manager import auth_manager


@flashcard_bp.route('/learn')
@auth_manager.require_auth
def learn():
    """Protected route - auto-redirects if not authenticated."""
    user = auth_manager.get_current_user()
    return render_template('card.html', user=user)


# In service layer
def read_spreadsheet():
    """Service that needs credentials."""
    creds = auth_manager.get_credentials()  # Auto-refreshes if needed
    if not creds:
        raise AuthenticationError("Not authenticated")
    # Use creds...
```

### Session Key Changes

```python
# NEW SessionKeys to add to session_manager.py:
class SessionKeys:
    # ... existing keys ...

    # OAuth tokens (new)
    ACCESS_TOKEN = "auth.access_token"           # Access token string
    ACCESS_TOKEN_EXPIRY = "auth.access_token_expiry"  # datetime

    # Keep existing:
    AUTH_STATE = "auth.state"                    # OAuth state parameter
    AUTH_REDIRECT_URI = "auth.redirect_uri"      # OAuth redirect URI
    USER_ID = "user.id"                          # User database ID
    USER_GOOGLE_ID = "user.google_id"            # Google user ID

# DEPRECATED - will be removed:
# - AUTH_CREDENTIALS = "auth.credentials"  # Was storing entire creds dict with refresh token
#   → Split into ACCESS_TOKEN + refresh token moved to database

# Summary of changes:
# ✅ Add: ACCESS_TOKEN (access token only, no refresh token)
# ✅ Add: ACCESS_TOKEN_EXPIRY (for quick expiry checks)
# ❌ Remove: AUTH_CREDENTIALS (was storing refresh token insecurely)
# ✅ Keep: AUTH_STATE, AUTH_REDIRECT_URI, USER_ID, USER_GOOGLE_ID
```

## Migration Strategy

1. **Implement new system alongside old** (no breaking changes)
2. **Test thoroughly** with new AuthManager
3. **Switch routes one-by-one** to use AuthManager
4. **Remove old code** once all routes migrated
5. **Clean up deprecated session keys**

## Security Checklist

- [ ] Refresh tokens encrypted in database
- [ ] Encryption key in `.secrets.toml` (not in code)
- [ ] Access tokens only in session (short-lived)
- [ ] Token refresh automatic and transparent
- [ ] Failed refresh redirects to login (no silent failures)
- [ ] Logout revokes tokens from database
- [ ] Expired tokens cleaned up periodically
- [ ] All protected routes use `@require_auth`

## Testing Scenarios

1. **Happy Path**
   - [ ] User logs in successfully
   - [ ] Access token stored in session
   - [ ] Refresh token stored in database (encrypted)
   - [ ] User can access protected routes

2. **Token Refresh**
   - [ ] Access token expires
   - [ ] System automatically refreshes using refresh token from DB
   - [ ] New access token stored in session
   - [ ] User continues working seamlessly

3. **Token Expiry**
   - [ ] Refresh token expires or is invalid
   - [ ] User redirected to login
   - [ ] Clear error message

4. **Logout**
   - [ ] User logs out
   - [ ] Session cleared
   - [ ] Refresh token removed from database
   - [ ] User redirected to login page

5. **Multiple Sessions**
   - [ ] User logs in from multiple devices
   - [ ] Each session has its own refresh token in DB
   - [ ] Logout from one doesn't affect others

## Implementation Decisions

### Decision 1: Logout Strategy
**Options:**
- **A) Delete all refresh tokens for user** - Logs out all sessions/devices
- **B) Delete only current session's token** - Logs out only this session

**Recommendation**: Option A for simplicity in Phase 1, add session tracking in future if needed.

### Decision 2: Token Cleanup Strategy
**Options:**
- **A) Manual cleanup** - Delete tokens only on logout
- **B) Periodic cleanup** - Background task to remove old tokens (last_used > 6 months)
- **C) On-login cleanup** - Clean up old tokens when user logs in

**Recommendation**: Option A for Phase 1, add Option C later (clean up tokens older than 6 months on login).

### Decision 3: Multiple Refresh Tokens
**Current behavior**: User can have multiple refresh tokens (one per login)

**Implications:**
- ✅ Supports multiple devices/browsers
- ✅ Each session independent
- ❌ Cleanup logic more complex
- ❌ Could accumulate many tokens

**Recommendation**: Keep current behavior, add cleanup on login to remove tokens > 6 months old.

### Decision 4: Learning Session Preservation
**Question**: Should logout clear learning namespace (cards, progress)?

**Options:**
- **A) Clear everything** - Fresh start on re-login
- **B) Keep learning data** - Preserve in-progress session

**Recommendation**: Option A for security - clear everything on logout.

## Notes

- **Encryption key**: Generate with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
- **Token cleanup**: Will implement basic cleanup on login (remove tokens > 6 months old)
- **Audit logging**: Consider adding in Phase 7 for security monitoring
- **Rate limiting**: Consider rate limiting OAuth endpoints to prevent abuse
- **ID token**: Only used during OAuth callback, never stored (ephemeral)
- **Access token buffer**: Refresh 5 minutes before expiry to prevent edge cases
- **Refresh token lifespan**: Google revokes after 6 months of inactivity

## Timeline Estimate

- Phase 1 (Database): 1-2 hours
- Phase 2 (AuthManager): 3-4 hours
- Phase 3 (Refactoring): 2-3 hours
- Phase 4 (Route Protection): 1-2 hours
- Phase 5 (Auto-refresh): 1-2 hours
- Phase 6 (Testing): 2-3 hours
- Phase 7 (Cleanup): 1 hour

**Total**: 11-17 hours

## Success Criteria

✅ All authentication logic centralized in `AuthManager`
✅ Refresh tokens stored securely in database
✅ Automatic token refresh works transparently
✅ All protected routes use `@require_auth` decorator
✅ No manual credential checks in routes
✅ Clean separation between auth, user management, and session management
✅ All tests passing
✅ Documentation updated
