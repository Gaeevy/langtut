# Railway Deployment - Database Persistence Fix

## Problem

Railway was purging the SQLite database after each deployment because:

1. **Volumes are not available during build phase** - The database initialization was happening during the build process when the volume mount (`/app/data`) was not yet available.
2. **Database created in ephemeral build container** - Any database file created during build was lost when the runtime container started.
3. **Volume only mounted at runtime** - The persistent volume is only available when the application is running, not during the build process.

## Solution

The fix involves several changes to ensure database initialization happens at **runtime** when the volume is available:

### 1. Modified Database Initialization (`src/database.py`)

- **Deferred table creation**: In Railway environment, database tables are created on first access rather than during app initialization
- **Runtime volume verification**: Check if volume directory exists and create it if needed
- **Robust error handling**: Graceful fallback if volume is not immediately available

### 2. Added Database Initialization Check

```python
def ensure_database_initialized():
    """Ensure database is initialized - call this before any database operations"""
```

This function is called before any database operation to ensure tables exist.

### 3. Startup Check Script (`startup_check.py`)

- Verifies volume mount is available and writable
- Tests database initialization before starting the main application
- Provides detailed logging for debugging deployment issues

### 4. Updated Procfile

```
web: python startup_check.py && gunicorn --bind 0.0.0.0:$PORT --workers 2 --timeout 120 --keep-alive 2 --max-requests 1000 --max-requests-jitter 100 app:app
```

The startup check runs before the main application to verify everything is working.

### 5. Database Utilities (`db_utils.py`)

Provides tools for:
- Backing up and restoring the database
- Exporting/importing user data as JSON
- Checking database status

## Railway Configuration

Your `railway.toml` is correctly configured:

```toml
[env]
DATABASE_PATH = "/app/data/app.db"
RAILWAY_ENVIRONMENT = "production"

[[volumes]]
mountPath = "/app/data"
name = "langtut-database"
```

## Deployment Process

1. **Build Phase**: App code is built, but no database operations occur
2. **Runtime Phase**: 
   - Volume is mounted to `/app/data`
   - Startup check verifies volume and initializes database
   - Main application starts with persistent database

## Verification

After deployment, you can verify the fix by:

1. **Check the health endpoint**: `https://your-app.railway.app/test`
2. **View database info**: `https://your-app.railway.app/admin/db-info`
3. **Check logs**: Look for "Database tables created successfully" in Railway logs

## Data Persistence

With this fix:
- ✅ User data persists across deployments
- ✅ Database is created in the persistent volume
- ✅ No data loss during Railway deployments
- ✅ Automatic database initialization on first run

## Backup Strategy

Use the database utilities for regular backups:

```bash
# Export users to JSON (can be done via admin endpoint)
python db_utils.py export

# Create SQL backup
python db_utils.py backup
```

## Troubleshooting

If you still experience issues:

1. **Check Railway logs** for database initialization messages
2. **Verify volume mount** using the `/test` endpoint
3. **Use database utilities** to check database status
4. **Export data before deployment** as a safety measure

The key insight is that Railway volumes are only available at runtime, not during the build phase. This fix ensures all database operations happen when the persistent storage is available. 