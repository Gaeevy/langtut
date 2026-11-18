"""Build Google OAuth flows and verify the identity returned by Google."""

import json
from enum import StrEnum
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from google.auth.transport.requests import Request
from google.oauth2 import id_token
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from pydantic import BaseModel, Field, SecretStr


class GoogleIdentity(BaseModel):
    google_user_id: str = Field(min_length=1)
    email: str = ""
    name: str = ""


class GoogleOAuthPurpose(StrEnum):
    LOGIN = "login"
    CONNECT_SHEETS = "connect_sheets"


class GoogleOAuthTransaction(BaseModel):
    state: str
    redirect_uri: str
    code_verifier: str = Field(repr=False)
    purpose: GoogleOAuthPurpose
    expires_at: int
    user_id: int | None = None
    session_version: int | None = None


class GoogleOAuthService:
    """Hold Google client configuration and create a flow per OAuth operation."""

    def __init__(
        self, client_config: dict, identity_scopes: list[str], sheets_scopes: list[str]
    ) -> None:
        if not isinstance(client_config, dict):
            raise ValueError("Invalid Google OAuth client configuration")
        client_type = "web" if "web" in client_config else "installed"
        settings = client_config.get(client_type)
        required_fields = ("client_id", "client_secret", "auth_uri", "token_uri")
        if not isinstance(settings, dict) or any(
            not isinstance(settings.get(field), str) or not settings[field].strip()
            for field in required_fields
        ):
            raise ValueError("Invalid Google OAuth client configuration")
        if "openid" not in identity_scopes:
            raise ValueError("Google sign-in requires the openid scope")

        self._client_config = client_config
        self._identity_scopes = list(identity_scopes)
        self._sheets_scopes = list(sheets_scopes)
        self.client_id = settings["client_id"]
        self.client_secret = settings["client_secret"]
        self.token_uri = settings["token_uri"]

    @classmethod
    def from_settings(
        cls,
        *,
        client_json: SecretStr | None,
        client_file: str | None,
        identity_scopes: list[str],
        sheets_scopes: list[str],
    ) -> "GoogleOAuthService":
        """Load the configured Google OAuth client, preferring inline JSON."""
        try:
            if client_json:
                payload = client_json.get_secret_value()
            elif client_file:
                payload = Path(client_file).read_text(encoding="utf-8")
            else:
                raise ValueError("Google OAuth client configuration is required")
            client_config = json.loads(payload)
        except (OSError, UnicodeError, json.JSONDecodeError):
            raise ValueError("Could not load Google OAuth client configuration") from None
        return cls(client_config, identity_scopes, sheets_scopes)

    def _create_flow(
        self,
        redirect_uri: str,
        purpose: GoogleOAuthPurpose,
        *,
        state: str | None = None,
        code_verifier: str | None = None,
    ) -> Flow:
        return Flow.from_client_config(
            self._client_config,
            scopes=self._scopes_for(purpose),
            redirect_uri=redirect_uri,
            state=state,
            code_verifier=code_verifier,
            autogenerate_code_verifier=code_verifier is None,
        )

    def _scopes_for(self, purpose: GoogleOAuthPurpose) -> list[str]:
        if purpose == GoogleOAuthPurpose.CONNECT_SHEETS:
            return self._identity_scopes + self._sheets_scopes
        return self._identity_scopes

    def start_login(
        self, redirect_uri: str, *, expires_at: int
    ) -> tuple[str, GoogleOAuthTransaction]:
        return self._start(redirect_uri, GoogleOAuthPurpose.LOGIN, expires_at=expires_at)

    def start_connection(
        self,
        redirect_uri: str,
        *,
        expires_at: int,
        user_id: int,
        session_version: int,
        login_hint: str,
    ) -> tuple[str, GoogleOAuthTransaction]:
        return self._start(
            redirect_uri,
            GoogleOAuthPurpose.CONNECT_SHEETS,
            expires_at=expires_at,
            user_id=user_id,
            session_version=session_version,
            login_hint=login_hint,
        )

    def _start(
        self,
        redirect_uri: str,
        purpose: GoogleOAuthPurpose,
        *,
        expires_at: int,
        user_id: int | None = None,
        session_version: int | None = None,
        login_hint: str = "",
    ) -> tuple[str, GoogleOAuthTransaction]:
        flow = self._create_flow(redirect_uri, purpose)
        options = {"access_type": "online"}
        if purpose == GoogleOAuthPurpose.CONNECT_SHEETS:
            options.update(access_type="offline", prompt="consent", login_hint=login_hint)
        url, state = flow.authorization_url(**options)
        return url, GoogleOAuthTransaction(
            state=state,
            redirect_uri=redirect_uri,
            code_verifier=flow.code_verifier,
            purpose=purpose,
            expires_at=expires_at,
            user_id=user_id,
            session_version=session_version,
        )

    def complete_authorization(
        self, authorization_response: str, transaction: GoogleOAuthTransaction
    ) -> tuple[GoogleIdentity, Credentials]:
        """Verify OAuth state, exchange the code, and verify the Google ID token."""
        state_params = parse_qs(urlsplit(authorization_response).query, keep_blank_values=True)
        if len(state_params.get("state", [])) != 1:
            raise ValueError("Google callback must include one state parameter")

        flow = self._create_flow(
            transaction.redirect_uri,
            transaction.purpose,
            state=transaction.state,
            code_verifier=transaction.code_verifier,
        )

        # OAuthlib rejects changed scopes before application code can handle partial consent.
        # Read the granted scope through its documented response hook, then validate it below.
        def accept_returned_scopes(response):
            payload = json.loads(response.text)
            if "scope" in payload:
                flow.oauth2session.scope = payload["scope"].split()
            return response

        flow.oauth2session.register_compliance_hook("access_token_response", accept_returned_scopes)
        flow.fetch_token(authorization_response=authorization_response)
        credentials = flow.credentials
        if not credentials.id_token:
            raise ValueError("Missing Google ID token")
        claims = id_token.verify_oauth2_token(credentials.id_token, Request(), self.client_id)
        identity = GoogleIdentity(
            google_user_id=claims["sub"],
            email=claims.get("email", ""),
            name=claims.get("name", ""),
        )
        return identity, credentials
