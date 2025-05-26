#!/usr/bin/env python3
"""
Startup check script for Railway deployment.
This script verifies that the database can be initialized properly.
"""
import os
import sys
from pathlib import Path

def check_environment():
    """Check if we're in Railway environment"""
    is_railway = bool(os.getenv('RAILWAY_ENVIRONMENT'))
    print(f"Environment: {'Railway' if is_railway else 'Local'}")
    return is_railway

def check_volume_mount():
    """Check if the volume mount is available"""
    database_path = os.getenv('DATABASE_PATH', '/app/data/app.db')
    database_dir = os.path.dirname(database_path)
    
    print(f"Expected database path: {database_path}")
    print(f"Expected database directory: {database_dir}")
    
    # Check if directory exists
    if os.path.exists(database_dir):
        print(f"✅ Volume directory exists: {database_dir}")
        
        # Check if it's writable
        try:
            test_file = os.path.join(database_dir, 'test_write.tmp')
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
            print(f"✅ Volume directory is writable")
            return True
        except Exception as e:
            print(f"❌ Volume directory is not writable: {e}")
            return False
    else:
        print(f"❌ Volume directory does not exist: {database_dir}")
        try:
            os.makedirs(database_dir, exist_ok=True)
            print(f"✅ Created volume directory: {database_dir}")
            return True
        except Exception as e:
            print(f"❌ Cannot create volume directory: {e}")
            return False

def check_database_initialization():
    """Check if database can be initialized"""
    try:
        # Import Flask app and database
        from src import create_app
        from src.database import init_database, ensure_database_initialized, db, User
        
        print("Creating Flask app...")
        app = create_app()
        
        print("Initializing database...")
        init_database(app)
        
        with app.app_context():
            print("Ensuring database is initialized...")
            if ensure_database_initialized():
                print("✅ Database initialization successful")
                
                # Test basic database operations using ensure_database_initialized again
                try:
                    # This will call ensure_database_initialized internally
                    from src.database import get_or_create_user
                    # Try a simple database operation that will trigger table creation if needed
                    user_count = User.query.count()
                    print(f"✅ Database query successful - Users: {user_count}")
                except Exception as e:
                    print(f"❌ Database query failed, trying to create tables: {e}")
                    # Force table creation
                    db.create_all()
                    user_count = User.query.count()
                    print(f"✅ Database tables created and query successful - Users: {user_count}")
                
                return True
            else:
                print("❌ Database initialization failed")
                return False
                
    except Exception as e:
        print(f"❌ Database initialization error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main startup check"""
    print("🚀 Railway Startup Check")
    print("=" * 50)
    
    # Check environment
    is_railway = check_environment()
    
    if is_railway:
        # Check volume mount
        print("\n📁 Checking volume mount...")
        volume_ok = check_volume_mount()
        
        if not volume_ok:
            print("❌ Volume mount check failed")
            sys.exit(1)
    
    # Check database initialization
    print("\n🗄️ Checking database initialization...")
    db_ok = check_database_initialization()
    
    if not db_ok:
        print("❌ Database initialization check failed")
        sys.exit(1)
    
    print("\n✅ All startup checks passed!")
    print("🎉 Application is ready to run")

if __name__ == '__main__':
    main() 