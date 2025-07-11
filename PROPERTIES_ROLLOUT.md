# UserSpreadsheet Properties Rollout Plan

## 🎯 **Objective**
Add a `properties` text column to the `UserSpreadsheet` table to store JSON configuration data, specifically language settings (original, target, hint languages).

## 📊 **Current State**
- UserSpreadsheet table exists with basic columns (id, user_id, spreadsheet_id, etc.)
- No properties/configuration storage
- Language settings are hardcoded

## 🚀 **Two-Phase Rollout Strategy**

### **Phase 1: Infrastructure (Safe Foundation)**
**Goal**: Add basic column and verification without complex logic

**Changes**:
1. **Database Migration**:
   - Add `properties` TEXT column to `user_spreadsheets` table
   - Column allows NULL values (backwards compatible)
   - Migration runs automatically on app startup

2. **Model Updates**:
   - Add `properties` field to `UserSpreadsheet` SQLAlchemy model
   - Simple text field, no complex logic yet

3. **Verification Endpoint**:
   - Add `/admin/table-info` endpoint to verify column exists
   - Returns table schema and column details
   - Helps confirm migration success

4. **Testing**:
   - Local verification: column added successfully
   - Railway deployment: migration runs without issues
   - Endpoint confirms column exists in production

**Success Criteria**:
- ✅ Migration completes without errors
- ✅ Column appears in database schema
- ✅ Existing functionality unchanged
- ✅ Admin endpoint shows new column

**Rollback Plan**:
- If issues occur, previous version continues working (NULL column ignored)
- Can remove column with `ALTER TABLE user_spreadsheets DROP COLUMN properties`

---

### **Phase 2: Feature Implementation**
**Goal**: Add Pydantic models, defaults, and UI integration

**Changes**:
1. **Pydantic Models**:
   - Create `UserSpreadsheetProperty` Pydantic model
   - Add serialization methods (`to_db_string`, `from_db_string`)
   - Default language config: `{"language": {"original": "ru", "target": "pt", "hint": "en"}}`

2. **Database Integration**:
   - Add property accessor methods to `UserSpreadsheet` model
   - Handle JSON serialization/deserialization
   - Initialize new records with default properties

3. **Settings UI**:
   - Add language configuration to settings page
   - Allow users to change original/target/hint languages
   - Save changes to properties column

4. **API Endpoints**:
   - Extend existing endpoints to use language settings
   - Add property management endpoints if needed

**Success Criteria**:
- ✅ Language settings persist correctly
- ✅ UI allows language changes
- ✅ JSON serialization works
- ✅ Default values applied to new spreadsheets

---

## 🔧 **Implementation Details**

### **Phase 1 Technical Specs**

**Migration Function**:
```python
def migrate_database():
    """Add properties column to user_spreadsheets table"""
    try:
        inspector = db.inspect(db.engine)
        columns = [column['name'] for column in inspector.get_columns('user_spreadsheets')]

        if 'properties' not in columns:
            with db.engine.connect() as connection:
                connection.execute(db.text("ALTER TABLE user_spreadsheets ADD COLUMN properties TEXT"))
                connection.commit()
            print("✅ Migration: Added 'properties' column to UserSpreadsheet table")
    except Exception as e:
        print(f"⚠️  Migration warning: {e}")
```

**Model Update**:
```python
class UserSpreadsheet(db.Model):
    # ... existing fields ...
    properties = Column(Text)  # JSON string storage
```

**Verification Endpoint**:
```python
@admin_bp.route('/table-info')
def table_info():
    """Get UserSpreadsheet table schema information"""
    inspector = db.inspect(db.engine)
    columns = inspector.get_columns('user_spreadsheets')
    return jsonify({
        'success': True,
        'table': 'user_spreadsheets',
        'columns': [
            {
                'name': col['name'],
                'type': str(col['type']),
                'nullable': col['nullable'],
                'default': col['default']
            }
            for col in columns
        ]
    })
```

### **Phase 2 Technical Specs**

**Pydantic Model**:
```python
class UserSpreadsheetProperty(BaseModel):
    language: dict = {
        "original": "ru",
        "target": "pt",
        "hint": "en"
    }

    def to_db_string(self) -> str:
        return json.dumps(self.model_dump())

    @classmethod
    def from_db_string(cls, value: str) -> "UserSpreadsheetProperty":
        if not value:
            return cls()
        return cls(**json.loads(value))
```

---

## 📋 **Deployment Checklist**

### **Phase 1 Checklist**
- [ ] Local migration tested
- [ ] Column appears in local database
- [ ] Admin endpoint returns correct schema
- [ ] No breaking changes to existing functionality
- [ ] Deploy to Railway
- [ ] Verify migration logs show success
- [ ] Test admin endpoint on Railway
- [ ] Confirm existing features still work

### **Phase 2 Checklist**
- [ ] Pydantic models tested locally
- [ ] JSON serialization/deserialization works
- [ ] Default values applied correctly
- [ ] Settings UI functional
- [ ] Language changes persist
- [ ] Deploy to Railway
- [ ] Test end-to-end language configuration

---

## 🚨 **Risk Mitigation**

**Phase 1 Risks**:
- **Migration failure**: Column addition is low-risk, allows NULL
- **Railway compatibility**: Simple ALTER TABLE is well-supported
- **Data loss**: No existing data modified

**Phase 2 Risks**:
- **JSON parsing errors**: Handle with try/catch, fallback to defaults
- **UI integration**: Test thoroughly before deployment
- **Data migration**: Existing NULL values handled gracefully

**General Safeguards**:
- Each phase is independently deployable
- Backwards compatibility maintained
- Admin endpoints for verification
- Can rollback to previous version if needed

---

## 📅 **Timeline**

**Phase 1**: Immediate (1-2 hours)
- Implementation: 30 minutes
- Testing: 30 minutes
- Deployment: 30 minutes
- Verification: 30 minutes

**Phase 2**: After Phase 1 success (2-3 hours)
- Pydantic implementation: 1 hour
- UI integration: 1 hour
- Testing & deployment: 1 hour

**Total**: 3-5 hours with safe validation between phases
