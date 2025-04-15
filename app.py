"""
Language Tutor Application

This is the main entry point for the application.
"""
import os
import pathlib
from src import create_app
from src.config import FLASK_DEBUG, CLIENT_SECRETS_FILE


if __name__ == '__main__':
    # Check if the client secrets file exists
    if not pathlib.Path(CLIENT_SECRETS_FILE).exists():
        print(f"WARNING: {CLIENT_SECRETS_FILE} not found. OAuth authentication will not work.")
        print("You'll need to create a project in Google Cloud Console and download the client secret.")
        print("See README.md for instructions.")
    
    # For OAuth callback to work properly, we need to ensure localhost is used
    # and environment variable is set to allow insecure OAuth for development
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
    print("NOTICE: OAuth insecure transport enabled for local development")
    print("IMPORTANT: Don't use this in production!")
    
    # Create and run the app
    app = create_app()
    app.run(debug=FLASK_DEBUG, host='localhost', port=8080)
