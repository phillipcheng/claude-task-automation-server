# Updated API - Task Name Based ✅

## What Changed

The API has been updated to support **task name based** operations. You no longer need to manage session IDs manually!

### Before (Old Way)
```bash
# 1. Create session first
SESSION_ID=$(curl -X POST .../sessions -d '{"project_path": "..."}' | jq -r '.id')

# 2. Create task with session_id
curl -X POST .../tasks -d "{\"session_id\": \"$SESSION_ID\", \"description\": \"...\"}"

# 3. Get status by task ID
curl .../tasks/{task_id}/status
```

### After (New Way) ✨
```bash
# 1. Create task with just name and description
curl -X POST .../tasks -d '{
  "task_name": "my-task",
  "description": "..."
}'

# 2. Get status by task name
curl .../tasks/by-name/my-task/status
```

## New Endpoints

### POST /api/v1/tasks
Create task with task name (session managed automatically)

**Request:**
```json
{
  "task_name": "calculator",
  "description": "Create calculator functions",
  "project_path": "/optional/path"
}
```

### GET /api/v1/tasks/by-name/{task_name}/status
Get task status by name

**Response:**
```json
{
  "task_name": "calculator",
  "status": "running",
  "progress": "Task is running - 3 interactions",
  "test_summary": {...}
}
```

### GET /api/v1/tasks/by-name/{task_name}
Get full task details by name

### GET /api/v1/tasks
List all tasks (with optional filtering)

**Query Parameters:**
- `status` - Filter by status (pending, running, completed, etc.)
- `limit` - Maximum tasks to return (default: 100)

### DELETE /api/v1/tasks/by-name/{task_name}
Delete a task by name

## Database Changes

### New Column: `task_name`
- Added to `tasks` table
- Type: VARCHAR(200)
- Unique constraint
- Indexed for fast lookups

### Migration Applied
```sql
ALTER TABLE tasks ADD COLUMN task_name VARCHAR(200);
CREATE INDEX ix_tasks_task_name ON tasks (task_name);
```

## Session Management (Automatic)

Sessions are now created/reused automatically:

1. **Default Session**: If no `project_path` specified, uses `/tmp/claude_projects`
2. **Per-Project Sessions**: If `project_path` provided, creates/reuses session for that path

### Configuration

Set default project path in `.env`:
```bash
DEFAULT_PROJECT_PATH=/Users/me/projects
```

## Backward Compatibility

All old endpoints still work:
- `POST /api/v1/sessions`
- `GET /api/v1/sessions/{session_id}`
- `POST /api/v1/tasks` (with session_id)
- `GET /api/v1/tasks/{task_id}`
- `GET /api/v1/tasks/{task_id}/status`

## Usage Examples

### Create Task
```bash
curl -X POST http://localhost:8000/api/v1/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "task_name": "user-auth",
    "description": "Implement user authentication with JWT"
  }'
```

### Check Status
```bash
curl http://localhost:8000/api/v1/tasks/by-name/user-auth/status
```

### List Running Tasks
```bash
curl "http://localhost:8000/api/v1/tasks?status=running"
```

### Delete Task
```bash
curl -X DELETE http://localhost:8000/api/v1/tasks/by-name/user-auth
```

## Testing

The API has been tested and verified:

```bash
# Server starts successfully
python3 -m app.main

# Task creation works
✓ Created task with name: "test-calculator"

# Status query works
✓ Retrieved status by task name

# Database updated
✓ task_name column added
✓ Index created
```

## Migration Guide

If you have existing code:

### Option 1: Keep Using Old API
Old endpoints still work - no changes needed!

### Option 2: Switch to Task Names
```python
# Before
session = requests.post("/sessions", json={"project_path": "..."}).json()
task = requests.post("/tasks", json={
    "session_id": session["id"],
    "description": "..."
}).json()
status = requests.get(f"/tasks/{task['id']}/status").json()

# After
task = requests.post("/tasks", json={
    "task_name": "my-task",
    "description": "..."
}).json()
status = requests.get(f"/tasks/by-name/my-task/status").json()
```

## Benefits

✅ **Simpler API** - Just task name + description
✅ **Easy Querying** - Use readable task names
✅ **Auto Sessions** - No manual session management
✅ **Backward Compatible** - Old code still works
✅ **Better UX** - More intuitive for users

## Documentation

- **Simple Usage Guide**: See `SIMPLE_USAGE.md`
- **Full API Docs**: http://localhost:8000/docs
- **Setup Guide**: See `SETUP_COMPLETE.md`

## Summary

The Claude Task Automation Server now supports both:

1. **Simple Task Name API** (New, Recommended) ⭐
   - Create tasks by name
   - Query by name
   - Sessions managed automatically

2. **Session-Based API** (Legacy, Still Supported)
   - Create sessions manually
   - Create tasks with session_id
   - Query by task ID

Choose whichever fits your workflow! 🚀
