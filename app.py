"""
Language Tutor Application

This is the main entry point for the application.
"""
import os
import pathlib
from src import create_app
from src.config import FLASK_DEBUG, CLIENT_SECRETS_FILE, settings

# Create the app instance for Gunicorn
app = create_app()

if __name__ == '__main__':
    # Detect if we're in development (running directly with python app.py)
    is_development = True
    
    # Only set insecure transport for local development
    if is_development:
        os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
        print("NOTICE: OAuth insecure transport enabled for local development")
        print("IMPORTANT: Don't use this in production!")
        
        # Check if the client secrets file exists (only relevant in development)
        if not pathlib.Path(CLIENT_SECRETS_FILE).exists():
            print(f"WARNING: {CLIENT_SECRETS_FILE} not found. OAuth authentication will not work.")
            print("You'll need to create a project in Google Cloud Console and download the client secret.")
            print("See README.md for instructions.")
    
    # Run the app in development mode
    app.run(debug=FLASK_DEBUG, host='localhost', port=8080)
else:
    # Production mode (running with Gunicorn)
    # Don't set OAUTHLIB_INSECURE_TRANSPORT in production
    print("Running in production mode")
    
    # Check if we have client secrets configured (via env var or file)
    has_client_secrets = (
        settings.get("CLIENT_SECRETS_JSON") is not None or 
        pathlib.Path(CLIENT_SECRETS_FILE).exists()
    )
    
    if not has_client_secrets:
        print("WARNING: No client secrets configured. OAuth authentication will not work.")
        print("Set LANGTUT_CLIENT_SECRETS_JSON environment variable or provide client_secret.json file.")
