"""Build Google OAuth flows and verify the identity returned by Google."""

import json
from dataclasses import dataclass
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


@dataclass(frozen=True, repr=False)
class GoogleOAuthTransaction:
    state: str
    redirect_uri: str
    code_verifier: str


class GoogleOAuthService:
    """Hold Google client configuration and create a flow per OAuth operation."""

    def __init__(self, client_config: dict, scopes: list[str]) -> None:
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
        if "openid" not in scopes:
            raise ValueError("Google sign-in requires the openid scope")

        self._client_config = client_config
        self._scopes = list(scopes)
        self.client_id = settings["client_id"]
        self.client_secret = settings["client_secret"]
        self.token_uri = settings["token_uri"]

    @classmethod
    def from_settings(
        cls, *, client_json: SecretStr | None, client_file: str | None, scopes: list[str]
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
        return cls(client_config, scopes)

    def _create_flow(
        self, redirect_uri: str, *, state: str | None = None, code_verifier: str | None = None
    ) -> Flow:
        return Flow.from_client_config(
            self._client_config,
            scopes=self._scopes,
            redirect_uri=redirect_uri,
            state=state,
            code_verifier=code_verifier,
            autogenerate_code_verifier=code_verifier is None,
        )

    def start_login(self, redirect_uri: str) -> tuple[str, GoogleOAuthTransaction]:
        """Return the combined consent URL and the transaction for the callback."""
        flow = self._create_flow(redirect_uri)
        url, state = flow.authorization_url(access_type="offline", include_granted_scopes="true")
        return url, GoogleOAuthTransaction(state, redirect_uri, flow.code_verifier)

    def complete_login(
        self, authorization_response: str, transaction: GoogleOAuthTransaction
    ) -> tuple[GoogleIdentity, Credentials]:
        """Verify OAuth state, exchange the code, and verify the Google ID token."""
        state_params = parse_qs(urlsplit(authorization_response).query, keep_blank_values=True)
        if len(state_params.get("state", [])) != 1:
            raise ValueError("Google callback must include one state parameter")

        flow = self._create_flow(
            transaction.redirect_uri,
            state=transaction.state,
            code_verifier=transaction.code_verifier,
        )
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
