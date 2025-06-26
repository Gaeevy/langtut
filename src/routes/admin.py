"""
Admin routes for the Language Learning Flashcard App.

Handles database administration and debugging functionality.
"""

import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from flask import Blueprint, Response, jsonify, request

from src.database import User, UserSpreadsheet, db
from src.utils import format_timestamp

# Create blueprint
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


@admin_bp.route('/db-info')
def db_info() -> dict[str, Any]:
    """Get database information and statistics."""
    try:
        # Get table counts
        user_count = User.query.count()
        spreadsheet_count = UserSpreadsheet.query.count()

        # Get recent activity
        recent_users = User.query.order_by(User.created_at.desc()).limit(5).all()
        recent_spreadsheets = (
            UserSpreadsheet.query.order_by(UserSpreadsheet.created_at.desc()).limit(5).all()
        )

        return jsonify(
            {
                'success': True,
                'stats': {'users': user_count, 'spreadsheets': spreadsheet_count},
                'recent_activity': {
                    'users': [
                        {
                            'id': user.id,
                            'email': user.email,
                            'created_at': format_timestamp(user.created_at),
                        }
                        for user in recent_users
                    ],
                    'spreadsheets': [
                        {
                            'id': sheet.id,
                            'spreadsheet_id': sheet.spreadsheet_id,
                            'created_at': format_timestamp(sheet.created_at),
                        }
                        for sheet in recent_spreadsheets
                    ],
                },
            }
        )

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@admin_bp.route('/users')
def list_users() -> dict[str, Any]:
    """List all users in the database."""
    try:
        users = User.query.order_by(User.created_at.desc()).all()

        return jsonify({'success': True, 'users': [user.to_dict() for user in users]})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@admin_bp.route('/spreadsheets')
def list_spreadsheets() -> dict[str, Any]:
    """List all spreadsheets in the database."""
    try:
        spreadsheets = UserSpreadsheet.query.order_by(UserSpreadsheet.created_at.desc()).all()

        return jsonify(
            {'success': True, 'spreadsheets': [sheet.to_dict() for sheet in spreadsheets]}
        )

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@admin_bp.route('/user/<int:user_id>')
def get_user_details(user_id: int) -> dict[str, Any]:
    """Get detailed information about a specific user."""
    try:
        user = User.query.filter(User.id == user_id).first()

        if not user:
            return jsonify({'success': False, 'error': 'User not found'})

        return jsonify({'success': True, 'user': user.to_dict()})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@admin_bp.route('/export-db')
def export_database() -> Response:
    """Export database contents as JSON."""
    try:
        # Export users
        users = User.query.all()
        users_data = [user.to_dict() for user in users]

        # Export spreadsheets
        spreadsheets = UserSpreadsheet.query.all()
        spreadsheets_data = [sheet.to_dict() for sheet in spreadsheets]

        export_data = {
            'export_date': format_timestamp(datetime.now()),
            'users': users_data,
            'spreadsheets': spreadsheets_data,
        }

        # Create JSON response
        response = Response(
            json.dumps(export_data, indent=2),
            mimetype='application/json',
            headers={'Content-Disposition': 'attachment; filename=database_export.json'},
        )

        return response

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@admin_bp.route('/query', methods=['POST'])
def execute_query() -> dict[str, Any]:
    """Execute a custom database query (READ-ONLY for safety)."""
    try:
        data = request.get_json()
        if not data or 'query' not in data:
            return jsonify({'success': False, 'error': 'Query is required'})

        query = data['query'].strip().upper()

        # Security check: only allow SELECT queries
        if not query.startswith('SELECT'):
            return jsonify({'success': False, 'error': 'Only SELECT queries are allowed'})

        # Additional security: block dangerous keywords
        dangerous_keywords = ['DROP', 'DELETE', 'UPDATE', 'INSERT', 'ALTER', 'CREATE', 'TRUNCATE']
        for keyword in dangerous_keywords:
            if keyword in query:
                return jsonify({'success': False, 'error': f'Keyword {keyword} is not allowed'})

        result = db.session.execute(data['query'])
        rows = result.fetchall()

        # Convert to list of dictionaries
        columns = result.keys()
        result_data = [dict(zip(columns, row, strict=False)) for row in rows]

        return jsonify(
            {
                'success': True,
                'columns': list(columns),
                'data': result_data,
                'row_count': len(result_data),
            }
        )

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@admin_bp.route('/volume-check')
def volume_check() -> dict[str, Any]:
    """Check file system and volume information."""
    try:
        # Get current working directory
        current_dir = Path.cwd()

        # Check if data directory exists
        data_dir = current_dir / 'data'
        data_dir_exists = data_dir.exists()

        # Check database file
        db_file = data_dir / 'app.db'
        db_file_exists = db_file.exists()
        db_file_size = db_file.stat().st_size if db_file_exists else 0

        # Get disk usage (if available)
        try:
            statvfs = os.statvfs(current_dir)
            free_bytes = statvfs.f_frsize * statvfs.f_bavail
            total_bytes = statvfs.f_frsize * statvfs.f_blocks
        except AttributeError:
            # Windows doesn't have statvfs
            total_bytes, used_bytes, free_bytes = shutil.disk_usage(current_dir)

        # List files in data directory
        data_files = []
        if data_dir_exists:
            try:
                for file_path in data_dir.iterdir():
                    if file_path.is_file():
                        data_files.append(
                            {
                                'name': file_path.name,
                                'size': file_path.stat().st_size,
                                'modified': format_timestamp(
                                    datetime.fromtimestamp(file_path.stat().st_mtime)
                                ),
                            }
                        )
            except PermissionError:
                data_files = ['Permission denied']

        return jsonify(
            {
                'success': True,
                'file_system': {
                    'current_directory': str(current_dir),
                    'data_directory_exists': data_dir_exists,
                    'database_file_exists': db_file_exists,
                    'database_file_size': db_file_size,
                    'data_files': data_files,
                },
                'disk_usage': {
                    'total_bytes': total_bytes,
                    'free_bytes': free_bytes,
                    'used_bytes': total_bytes - free_bytes,
                },
            }
        )

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
