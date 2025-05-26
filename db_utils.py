#!/usr/bin/env python3
"""
Database utilities for backup and restore operations.
Useful for Railway deployments to ensure data persistence.
"""
import os
import sys
import sqlite3
import json
from datetime import datetime
from pathlib import Path

def get_database_path():
    """Get the database path based on environment"""
    if os.getenv('RAILWAY_ENVIRONMENT'):
        return os.getenv('DATABASE_PATH', '/app/data/app.db')
    else:
        return os.getenv('DATABASE_PATH', 'data/app.db')

def backup_database(backup_path=None):
    """Create a backup of the database"""
    db_path = get_database_path()
    
    if not os.path.exists(db_path):
        print(f"❌ Database file not found: {db_path}")
        return False
    
    if backup_path is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = f"backup_{timestamp}.sql"
    
    try:
        # Create SQL dump
        conn = sqlite3.connect(db_path)
        with open(backup_path, 'w') as f:
            for line in conn.iterdump():
                f.write(f"{line}\n")
        conn.close()
        
        print(f"✅ Database backed up to: {backup_path}")
        return True
        
    except Exception as e:
        print(f"❌ Backup failed: {e}")
        return False

def restore_database(backup_path):
    """Restore database from backup"""
    if not os.path.exists(backup_path):
        print(f"❌ Backup file not found: {backup_path}")
        return False
    
    db_path = get_database_path()
    db_dir = os.path.dirname(db_path)
    
    # Ensure database directory exists
    os.makedirs(db_dir, exist_ok=True)
    
    try:
        # Remove existing database
        if os.path.exists(db_path):
            os.remove(db_path)
        
        # Create new database from backup
        conn = sqlite3.connect(db_path)
        with open(backup_path, 'r') as f:
            sql_script = f.read()
        
        conn.executescript(sql_script)
        conn.close()
        
        print(f"✅ Database restored from: {backup_path}")
        return True
        
    except Exception as e:
        print(f"❌ Restore failed: {e}")
        return False

def export_users_json(output_path=None):
    """Export users to JSON format"""
    if output_path is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_path = f"users_export_{timestamp}.json"
    
    try:
        from src import create_app
        from src.database import init_database, User, UserSpreadsheet
        
        app = create_app()
        init_database(app)
        
        with app.app_context():
            users = User.query.all()
            users_data = []
            
            for user in users:
                user_dict = user.to_dict()
                # Add spreadsheets
                spreadsheets = UserSpreadsheet.query.filter_by(user_id=user.id).all()
                user_dict['spreadsheets'] = [sheet.to_dict() for sheet in spreadsheets]
                users_data.append(user_dict)
            
            with open(output_path, 'w') as f:
                json.dump(users_data, f, indent=2, default=str)
            
            print(f"✅ Users exported to: {output_path}")
            print(f"📊 Exported {len(users_data)} users")
            return True
            
    except Exception as e:
        print(f"❌ Export failed: {e}")
        return False

def import_users_json(input_path):
    """Import users from JSON format"""
    if not os.path.exists(input_path):
        print(f"❌ Import file not found: {input_path}")
        return False
    
    try:
        from src import create_app
        from src.database import init_database, db, User, UserSpreadsheet
        
        app = create_app()
        init_database(app)
        
        with open(input_path, 'r') as f:
            users_data = json.load(f)
        
        with app.app_context():
            imported_count = 0
            
            for user_data in users_data:
                # Check if user already exists
                existing_user = User.query.filter_by(
                    google_user_id=user_data['google_user_id']
                ).first()
                
                if existing_user:
                    print(f"⚠️ User already exists: {user_data['email']}")
                    continue
                
                # Create user
                user = User(
                    google_user_id=user_data['google_user_id'],
                    email=user_data['email'],
                    name=user_data['name'],
                    created_at=datetime.fromisoformat(user_data['created_at']) if user_data.get('created_at') else datetime.utcnow(),
                    last_login=datetime.fromisoformat(user_data['last_login']) if user_data.get('last_login') else datetime.utcnow()
                )
                db.session.add(user)
                db.session.flush()  # Get the user ID
                
                # Create spreadsheets
                for sheet_data in user_data.get('spreadsheets', []):
                    spreadsheet = UserSpreadsheet(
                        user_id=user.id,
                        spreadsheet_id=sheet_data['spreadsheet_id'],
                        spreadsheet_name=sheet_data.get('spreadsheet_name'),
                        spreadsheet_url=sheet_data.get('spreadsheet_url'),
                        is_active=sheet_data.get('is_active', False),
                        created_at=datetime.fromisoformat(sheet_data['created_at']) if sheet_data.get('created_at') else datetime.utcnow(),
                        last_used=datetime.fromisoformat(sheet_data['last_used']) if sheet_data.get('last_used') else datetime.utcnow()
                    )
                    db.session.add(spreadsheet)
                
                imported_count += 1
                print(f"✅ Imported user: {user_data['email']}")
            
            db.session.commit()
            print(f"✅ Import completed. Imported {imported_count} users")
            return True
            
    except Exception as e:
        print(f"❌ Import failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def show_database_info():
    """Show database information"""
    try:
        from src import create_app
        from src.database import init_database, User, UserSpreadsheet
        
        app = create_app()
        init_database(app)
        
        with app.app_context():
            user_count = User.query.count()
            spreadsheet_count = UserSpreadsheet.query.count()
            active_spreadsheets = UserSpreadsheet.query.filter_by(is_active=True).count()
            
            print(f"📊 Database Statistics:")
            print(f"   Users: {user_count}")
            print(f"   Spreadsheets: {spreadsheet_count}")
            print(f"   Active Spreadsheets: {active_spreadsheets}")
            
            if user_count > 0:
                print(f"\n👥 Recent Users:")
                recent_users = User.query.order_by(User.last_login.desc()).limit(5).all()
                for user in recent_users:
                    print(f"   {user.email} (last login: {user.last_login})")
            
            return True
            
    except Exception as e:
        print(f"❌ Failed to get database info: {e}")
        return False

def main():
    """Main CLI interface"""
    if len(sys.argv) < 2:
        print("Database Utilities")
        print("Usage:")
        print("  python db_utils.py backup [backup_file]")
        print("  python db_utils.py restore <backup_file>")
        print("  python db_utils.py export [output_file]")
        print("  python db_utils.py import <input_file>")
        print("  python db_utils.py info")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == 'backup':
        backup_path = sys.argv[2] if len(sys.argv) > 2 else None
        backup_database(backup_path)
    
    elif command == 'restore':
        if len(sys.argv) < 3:
            print("❌ Please specify backup file")
            sys.exit(1)
        restore_database(sys.argv[2])
    
    elif command == 'export':
        output_path = sys.argv[2] if len(sys.argv) > 2 else None
        export_users_json(output_path)
    
    elif command == 'import':
        if len(sys.argv) < 3:
            print("❌ Please specify import file")
            sys.exit(1)
        import_users_json(sys.argv[2])
    
    elif command == 'info':
        show_database_info()
    
    else:
        print(f"❌ Unknown command: {command}")
        sys.exit(1)

if __name__ == '__main__':
    main() 