import json
import os
import tempfile
from dynaconf import Dynaconf

settings = Dynaconf(
    envvar_prefix="LANGTUT",
    settings_files=["settings.toml", ".secrets.toml"],
    environments=True,
    load_dotenv=True,
)

# Google Sheets API settings
SPREADSHEET_ID = settings.get("SPREADSHEET_ID", "15_PsHfMb440wtUgZ0d1aJmu5YIXoo9JKytlJINxOV8Q")

# Google OAuth2 settings - handle both file and environment variable
def get_client_secrets_file():
    """Get the client secrets file path, creating from env var if needed"""
    # Check if we have client secrets as environment variable (production)
    client_secrets_json = settings.get("CLIENT_SECRETS_JSON", None)
    
    if client_secrets_json:
        # Create a temporary file with the client secrets
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
        if isinstance(client_secrets_json, str):
            # Parse JSON string if it's a string
            client_secrets_data = json.loads(client_secrets_json)
        else:
            client_secrets_data = client_secrets_json
        
        json.dump(client_secrets_data, temp_file)
        temp_file.close()
        return temp_file.name
    else:
        # Use local file (development)
        return settings.get("CLIENT_SECRETS_FILE", "client_secret.json")

CLIENT_SECRETS_FILE = get_client_secrets_file()
SCOPES = settings.get("SCOPES", [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile"
])
API_SERVICE_NAME = settings.get("API_SERVICE_NAME", "sheets")
API_VERSION = settings.get("API_VERSION", "v4")

# Google Cloud Text-to-Speech settings
def get_google_cloud_credentials():
    """Get Google Cloud service account credentials"""
    # Check for service account key as environment variable (production)
    service_account_json = settings.get("GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON", None)
    
    if service_account_json:
        # Create a temporary file with the service account key
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
        if isinstance(service_account_json, str):
            # Parse JSON string if it's a string
            service_account_data = json.loads(service_account_json)
        else:
            service_account_data = service_account_json
        
        json.dump(service_account_data, temp_file)
        temp_file.close()
        return temp_file.name
    else:
        # Use local file (development)
        local_file = settings.get("GOOGLE_CLOUD_SERVICE_ACCOUNT_FILE", "google-cloud-service-account.json")
        if os.path.exists(local_file):
            return local_file
        return None

GOOGLE_CLOUD_SERVICE_ACCOUNT_FILE = get_google_cloud_credentials()
TTS_ENABLED = settings.get("TTS_ENABLED", True)  # Enable/disable TTS functionality
TTS_LANGUAGE_CODE = settings.get("TTS_LANGUAGE_CODE", "pt-PT")  # European Portuguese
TTS_VOICE_NAME = settings.get("TTS_VOICE_NAME", "pt-PT-Standard-A")  # Female voice
TTS_AUDIO_ENCODING = settings.get("TTS_AUDIO_ENCODING", "MP3")  # Audio format

# Application settings
MAX_CARDS_PER_SESSION = settings.get("MAX_CARDS_PER_SESSION", 10)  # Maximum number of cards per learning session

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