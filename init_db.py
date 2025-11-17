#!/usr/bin/env python3
"""
Quick database initialization script for local development.

Usage:
    uv run python init_db.py

This script creates the database tables if they don't exist.
"""

from src.config import logger

if __name__ == '__main__':
    logger.info('🔧 Initializing database...')

    # Import app from app.py - this properly initializes the database
    from app import app
    from src.database import ensure_tables

    # Create tables within app context
    with app.app_context():
        logger.info('Creating database tables...')
        ensure_tables()
        logger.info('✅ Database tables created successfully!')

        # Verify by checking if we can query users
        from src.database import User

        user_count = User.query.count()
        logger.info(f'Current users in database: {user_count}')
        logger.info('🎉 Database initialization complete!')
