# Railway Volume Fix - Step by Step Guide

## The Problem

Your Railway volume is not actually mounting. The volume check shows:
```json
{
  "volume_mounted": false,
  "root_device": 14680309,
  "data_device": 14680309
}
```

This means `/app/data` is just a regular directory, not a mounted volume, which is why your database gets reset on each deployment.

## The Solution

### Step 1: Remove Volume Configuration from railway.toml

✅ **DONE** - I've already removed the incorrect volume configuration from `railway.toml`.

The old syntax `[[volumes]]` in `railway.toml` is no longer supported. Volumes must be created through the Railway dashboard.

### Step 2: Create Volume in Railway Dashboard

1. **Go to your Railway project dashboard**
2. **Right-click on the project canvas** or use **Command Palette (⌘K)**
3. **Select "Create Volume"**
4. **Configure the volume:**
   - **Name**: `langtut-database` (or any name you prefer)
   - **Size**: Start with 1GB (you can grow it later)
   - **Region**: Same as your service

### Step 3: Attach Volume to Your Service

1. **After creating the volume, you'll be prompted to attach it to a service**
2. **Select your main application service**
3. **Set the mount path to**: `/app/data`
4. **Confirm the attachment**

### Step 4: Verify Volume Environment Variables

After attaching the volume, Railway will automatically set these environment variables:
- `RAILWAY_VOLUME_NAME`: The name of your volume
- `RAILWAY_VOLUME_MOUNT_PATH`: Should be `/app/data`

### Step 5: Deploy and Test

1. **Commit and push the updated railway.toml**:
   ```bash
   git add railway.toml
   git commit -m "Fix Railway volume configuration - remove deprecated volume syntax"
   git push origin master
   ```

2. **Railway will automatically redeploy**

3. **Test the volume mount** by visiting: `https://your-app.railway.app/admin/volume-check`

4. **You should see**:
   ```json
   {
     "volume_mounted": true,
     "root_device": 14680309,
     "data_device": 14680310,  // Different device ID
     "persistence_test": "PASS - File persisted from previous deployment"
   }
   ```

## Verification Steps

### 1. Check Volume Mount Status
Visit: `https://your-app.railway.app/admin/volume-check`

### 2. Check Database Persistence
1. Log in to your app and create some data
2. Redeploy the service
3. Check if your data is still there

### 3. Check Database Info
Visit: `https://your-app.railway.app/admin/db-info`

## Troubleshooting

### If Volume Still Not Mounting

1. **Check Railway Dashboard**: Ensure the volume shows as "Attached" to your service
2. **Check Mount Path**: Must be exactly `/app/data`
3. **Restart Service**: Sometimes a manual restart helps
4. **Check Logs**: Look for any volume-related errors in deployment logs

### If Database Still Gets Reset

1. **Check DATABASE_PATH**: Should be `/app/data/app.db`
2. **Check Permissions**: Volume is mounted as root, might need `RAILWAY_RUN_UID=0`
3. **Check Initialization**: Database should only be created at runtime, not build time

## Important Notes

- **Volumes are only available at runtime**, not during build
- **Volume mount path must be absolute**: `/app/data`
- **Database initialization must happen at runtime**, not during build
- **Volumes are mounted as root user**

## Current Configuration

Your app is now configured to:
1. ✅ Initialize database at runtime when volume is available
2. ✅ Use `/app/data/app.db` as database path
3. ✅ Call `ensure_database_initialized()` before all database operations
4. ✅ Have multiple fallback initialization points
5. ✅ Include diagnostic routes for troubleshooting

Once you create and attach the volume through the Railway dashboard, your database persistence should work correctly. 