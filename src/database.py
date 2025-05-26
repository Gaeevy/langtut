from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
import os

db = SQLAlchemy()

class User(db.Model):
    """User model for storing Google OAuth user information"""
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    google_user_id = Column(String(255), unique=True, nullable=False, index=True)
    email = Column(String(255))
    name = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, default=datetime.utcnow)
    
    # Relationship to user spreadsheets
    spreadsheets = relationship('UserSpreadsheet', back_populates='user', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<User {self.email}>'
    
    def get_active_spreadsheet(self):
        """Get the user's currently active spreadsheet"""
        return UserSpreadsheet.query.filter_by(
            user_id=self.id, 
            is_active=True
        ).first()
    
    def to_dict(self):
        return {
            'id': self.id,
            'google_user_id': self.google_user_id,
            'email': self.email,
            'name': self.name,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None
        }


class UserSpreadsheet(db.Model):
    """Model for storing user's linked spreadsheets"""
    __tablename__ = 'user_spreadsheets'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    spreadsheet_id = Column(String(255), nullable=False, index=True)
    spreadsheet_name = Column(String(255))  # User-defined name (future feature)
    spreadsheet_url = Column(Text)  # Full URL for reference
    is_active = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_used = Column(DateTime, default=datetime.utcnow)
    
    # Relationship to user
    user = relationship('User', back_populates='spreadsheets')
    
    # Unique constraint to prevent duplicate spreadsheets per user
    __table_args__ = (
        db.UniqueConstraint('user_id', 'spreadsheet_id', name='unique_user_spreadsheet'),
    )
    
    def __repr__(self):
        return f'<UserSpreadsheet {self.spreadsheet_id} for user {self.user_id}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'spreadsheet_id': self.spreadsheet_id,
            'spreadsheet_name': self.spreadsheet_name,
            'spreadsheet_url': self.spreadsheet_url,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_used': self.last_used.isoformat() if self.last_used else None
        }


def init_database(app):
    """Initialize database with Flask app"""
    # Configure database path for different environments
    if os.getenv('RAILWAY_ENVIRONMENT'):
        # Railway production environment
        # Use /app/data for persistent storage (Railway volume mount)
        database_path = os.getenv('DATABASE_PATH', '/app/data/app.db')
    else:
        # Local development
        database_path = os.getenv('DATABASE_PATH', 'data/app.db')
    
    # Convert to absolute path if not already
    if not os.path.isabs(database_path):
        database_path = os.path.abspath(database_path)
    
    # Ensure data directory exists
    database_dir = os.path.dirname(database_path)
    try:
        os.makedirs(database_dir, exist_ok=True)
        print(f"Database directory created/verified: {database_dir}")
    except Exception as e:
        print(f"Error creating database directory: {e}")
        # Fallback strategies
        if os.getenv('RAILWAY_ENVIRONMENT'):
            # Railway fallback: use /tmp (not persistent but works)
            database_path = '/tmp/app.db'
            print(f"Railway fallback: using temporary database at {database_path}")
        else:
            # Local fallback: current directory
            database_path = os.path.abspath('app.db')
            print(f"Local fallback: using database at {database_path}")
    
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{database_path}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    print(f"Database URI: {app.config['SQLALCHEMY_DATABASE_URI']}")
    print(f"Environment: {'Railway' if os.getenv('RAILWAY_ENVIRONMENT') else 'Local'}")
    
    # Initialize SQLAlchemy with app
    db.init_app(app)
    
    # Store database path in app config for later use
    app.config['DATABASE_PATH'] = database_path
    
    # For Railway: defer table creation to runtime when volume is available
    if os.getenv('RAILWAY_ENVIRONMENT'):
        print("Railway environment detected - database tables will be created on first access")
    else:
        # Local development: create tables immediately
        with app.app_context():
            try:
                db.create_all()
                print(f"Database initialized successfully at: {database_path}")
            except Exception as e:
                print(f"Error initializing database: {e}")
                raise


def ensure_database_initialized():
    """Ensure database is initialized - call this before any database operations"""
    from flask import current_app
    
    try:
        # Try a simple query to check if database is working
        from sqlalchemy import text
        with db.engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        print(f"Database not initialized, attempting to create tables: {e}")
        try:
            # In Railway environment, ensure the volume directory exists
            if os.getenv('RAILWAY_ENVIRONMENT'):
                database_path = current_app.config.get('DATABASE_PATH')
                if database_path:
                    database_dir = os.path.dirname(database_path)
                    if not os.path.exists(database_dir):
                        print(f"Creating volume directory: {database_dir}")
                        os.makedirs(database_dir, exist_ok=True)
            
            db.create_all()
            print("Database tables created successfully")
            
            # Verify tables were created
            from sqlalchemy import text
            with db.engine.connect() as conn:
                result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table';"))
                tables = [row[0] for row in result]
                print(f"Database tables verified: {tables}")
            
            return True
        except Exception as create_error:
            print(f"Failed to create database tables: {create_error}")
            return False


def get_or_create_user(google_user_id, email=None, name=None):
    """Get existing user or create new one"""
    # Ensure database is initialized before any operations
    ensure_database_initialized()
    
    user = User.query.filter_by(google_user_id=google_user_id).first()
    
    if not user:
        user = User(
            google_user_id=google_user_id,
            email=email,
            name=name
        )
        db.session.add(user)
        db.session.commit()
        print(f"Created new user: {email}")
    else:
        # Update last login and user info
        user.last_login = datetime.utcnow()
        if email:
            user.email = email
        if name:
            user.name = name
        db.session.commit()
    
    return user


def add_user_spreadsheet(user_id, spreadsheet_id, spreadsheet_url=None, spreadsheet_name=None, make_active=True):
    """Add a new spreadsheet for a user"""
    # Check if spreadsheet already exists for this user
    existing = UserSpreadsheet.query.filter_by(
        user_id=user_id, 
        spreadsheet_id=spreadsheet_id
    ).first()
    
    if existing:
        # Update existing spreadsheet
        existing.last_used = datetime.utcnow()
        if spreadsheet_url:
            existing.spreadsheet_url = spreadsheet_url
        if spreadsheet_name:
            existing.spreadsheet_name = spreadsheet_name
        if make_active:
            # Deactivate other spreadsheets for this user
            UserSpreadsheet.query.filter_by(user_id=user_id, is_active=True).update({'is_active': False})
            existing.is_active = True
        db.session.commit()
        return existing
    
    # Create new spreadsheet record
    if make_active:
        # Deactivate other spreadsheets for this user
        UserSpreadsheet.query.filter_by(user_id=user_id, is_active=True).update({'is_active': False})
    
    user_spreadsheet = UserSpreadsheet(
        user_id=user_id,
        spreadsheet_id=spreadsheet_id,
        spreadsheet_url=spreadsheet_url,
        spreadsheet_name=spreadsheet_name,
        is_active=make_active
    )
    
    db.session.add(user_spreadsheet)
    db.session.commit()
    
    print(f"Added spreadsheet {spreadsheet_id} for user {user_id}")
    return user_spreadsheet


def get_user_active_spreadsheet(user_id):
    """Get the user's currently active spreadsheet"""
    return UserSpreadsheet.query.filter_by(
        user_id=user_id, 
        is_active=True
    ).first()


def get_user_spreadsheets(user_id):
    """Get all spreadsheets for a user"""
    return UserSpreadsheet.query.filter_by(user_id=user_id).order_by(
        UserSpreadsheet.last_used.desc()
    ).all()


def set_active_spreadsheet(user_id, spreadsheet_id):
    """Set a specific spreadsheet as active for a user"""
    # Deactivate all spreadsheets for this user
    UserSpreadsheet.query.filter_by(user_id=user_id, is_active=True).update({'is_active': False})
    
    # Activate the specified spreadsheet
    spreadsheet = UserSpreadsheet.query.filter_by(
        user_id=user_id, 
        spreadsheet_id=spreadsheet_id
    ).first()
    
    if spreadsheet:
        spreadsheet.is_active = True
        spreadsheet.last_used = datetime.utcnow()
        db.session.commit()
        return spreadsheet
    
    return None


def remove_user_spreadsheet(user_id, spreadsheet_id):
    """Remove a spreadsheet from a user's collection"""
    spreadsheet = UserSpreadsheet.query.filter_by(
        user_id=user_id, 
        spreadsheet_id=spreadsheet_id
    ).first()
    
    if spreadsheet:
        db.session.delete(spreadsheet)
        db.session.commit()
        return True
    
    return False 