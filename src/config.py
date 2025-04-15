from dynaconf import Dynaconf

settings = Dynaconf(
    envvar_prefix="LANGTUT",
    settings_files=["settings.toml", ".secrets.toml"],
    environments=True,
    load_dotenv=True,
)

# Google Sheets API settings
SPREADSHEET_ID = settings.get("SPREADSHEET_ID", "15_PsHfMb440wtUgZ0d1aJmu5YIXoo9JKytlJINxOV8Q")

# Google OAuth2 settings
CLIENT_SECRETS_FILE = settings.get("CLIENT_SECRETS_FILE", "client_secret.json")
SCOPES = settings.get("SCOPES", ["https://www.googleapis.com/auth/spreadsheets"])
API_SERVICE_NAME = settings.get("API_SERVICE_NAME", "sheets")
API_VERSION = settings.get("API_VERSION", "v4")

# Application settings
MAX_CARDS_PER_SESSION = settings.get("MAX_CARDS_PER_SESSION", 2)  # Maximum number of cards per learning session

# Flask settings
SECRET_KEY = settings.get("SECRET_KEY", None)  # Will use random key if not set
FLASK_DEBUG = settings.get("DEBUG", False)
SESSION_TYPE = settings.get("SESSION_TYPE", "filesystem")
SESSION_PERMANENT = settings.get("SESSION_PERMANENT", False)
SESSION_USE_SIGNER = settings.get("SESSION_USE_SIGNER", True)
SESSION_COOKIE_SECURE = settings.get("SESSION_COOKIE_SECURE", False)  # Set to True in production
SESSION_COOKIE_HTTPONLY = settings.get("SESSION_COOKIE_HTTPONLY", True)
SESSION_COOKIE_SAMESITE = settings.get("SESSION_COOKIE_SAMESITE", "Lax")
JSON_AS_ASCII = settings.get("JSON_AS_ASCII", False)
JSONIFY_MIMETYPE = settings.get("JSONIFY_MIMETYPE", "application/json; charset=utf-8") 