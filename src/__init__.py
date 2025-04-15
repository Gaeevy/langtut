import os
from flask import Flask
from flask_session import Session
from src.utils import ensure_utf8_encoding
from src.config import (
    SECRET_KEY, SESSION_TYPE, SESSION_PERMANENT, SESSION_USE_SIGNER,
    SESSION_COOKIE_SECURE, SESSION_COOKIE_HTTPONLY, SESSION_COOKIE_SAMESITE,
    JSON_AS_ASCII, JSONIFY_MIMETYPE, FLASK_DEBUG
)

# Set default encoding to UTF-8
ensure_utf8_encoding()

app = Flask(__name__, template_folder='../templates', static_folder='../static')

# Configure the app from config module
app.secret_key = SECRET_KEY or os.urandom(24)  # For session management

# Application settings
app.config['SESSION_TYPE'] = SESSION_TYPE
app.config['SESSION_PERMANENT'] = SESSION_PERMANENT
app.config['SESSION_USE_SIGNER'] = SESSION_USE_SIGNER
app.config['SESSION_COOKIE_SECURE'] = SESSION_COOKIE_SECURE
app.config['SESSION_COOKIE_HTTPONLY'] = SESSION_COOKIE_HTTPONLY
app.config['SESSION_COOKIE_SAMESITE'] = SESSION_COOKIE_SAMESITE

# Set default encoding for Flask
app.config['JSON_AS_ASCII'] = JSON_AS_ASCII
app.config['JSONIFY_MIMETYPE'] = JSONIFY_MIMETYPE

# Initialize Flask-Session
Session(app)

# Import routes after app is created to avoid circular imports
from src import routes

def create_app():
    """Function to create and configure the Flask app."""
    return app 