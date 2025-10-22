# API Usage Guide - When to Use Which Endpoint

## TL;DR - What You Should Use

**99% of the time, use task-name-based APIs. Ignore session APIs.**

```bash
# ✅ Use these (recommended)
POST   /api/v1/tasks                              # Create task
GET    /api/v1/tasks/by-name/{task_name}/status   # Check status
GET    /api/v1/tasks/by-name/{task_name}          # Get full details
DELETE /api/v1/tasks/by-name/{task_name}          # Delete task
GET    /api/v1/tasks?root_folder=/path            # List tasks for project

# ❌ Don't use these (legacy, for backward compatibility only)
POST   /api/v1/sessions                           # Manual session creation
GET    /api/v1/sessions/{session_id}              # Get session
GET    /api/v1/sessions/{session_id}/tasks        # List session tasks
GET    /api/v1/tasks/{task_id}                    # Get task by ID
GET    /api/v1/tasks/{task_id}/status             # Get status by ID
```

## API Comparison

### Modern Task-Name API vs Legacy Session API

| Scenario | Modern Approach (✅ Use This) | Legacy Approach (❌ Don't Use) |
|----------|------------------------------|--------------------------------|
| **Create task for project** | `POST /api/v1/tasks` with `root_folder` | `POST /api/v1/sessions` then `POST /api/v1/tasks` |
| **Check task status** | `GET /api/v1/tasks/by-name/my-task/status` | `GET /api/v1/tasks/{uuid}/status` (need to save UUID) |
| **List project tasks** | `GET /api/v1/tasks?root_folder=/myproject` | `GET /api/v1/sessions/{session_id}/tasks` (need session_id) |
| **Delete task** | `DELETE /api/v1/tasks/by-name/my-task` | `DELETE /api/v1/tasks/{uuid}` (need UUID) |

## When to Use Each Endpoint

### 1. Creating Tasks

**✅ Modern Way:**
```bash
curl -X POST http://localhost:8000/api/v1/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "task_name": "add-login-feature",
    "description": "Implement user login with OAuth",
    "root_folder": "/Users/me/myproject"
  }'
```

**Benefits:**
- No manual session management
- Session auto-created based on `root_folder`
- Simple, one-step process

**❌ Legacy Way (Don't do this):**
```bash
# Step 1: Create session manually
curl -X POST http://localhost:8000/api/v1/sessions \
  -d '{"project_path": "/Users/me/myproject"}'
# Response: {"id": "abc-123-def-456", ...}

# Step 2: Use session_id to create task
curl -X POST http://localhost:8000/api/v1/tasks \
  -d '{
    "session_id": "abc-123-def-456",  # Have to remember this!
    "description": "..."
  }'
```

**Why legacy is worse:**
- Two-step process
- Need to store and manage session IDs
- More complex for no benefit

---

### 2. Checking Task Status

**✅ Modern Way:**
```bash
curl http://localhost:8000/api/v1/tasks/by-name/add-login-feature/status
```

**Benefits:**
- Use memorable task name
- No need to save UUIDs
- Human-readable URL

**❌ Legacy Way (Don't do this):**
```bash
curl http://localhost:8000/api/v1/tasks/abc-123-def-456/status
```

**Why legacy is worse:**
- Need to store task UUID from creation response
- Non-human-readable
- Hard to remember or type manually

---

### 3. Listing Tasks for a Project

**✅ Modern Way:**
```bash
# All tasks for a specific project
curl "http://localhost:8000/api/v1/tasks?root_folder=/Users/me/myproject"

# Running tasks for a project
curl "http://localhost:8000/api/v1/tasks?root_folder=/Users/me/myproject&status=running"

# All running tasks (across all projects)
curl "http://localhost:8000/api/v1/tasks?status=running"
```

**Benefits:**
- Filter by project path directly
- Combine filters (status + project)
- No session ID needed

**❌ Legacy Way (Don't do this):**
```bash
# Need to know session_id for the project
curl http://localhost:8000/api/v1/sessions/abc-123/tasks
```

**Why legacy is worse:**
- Need to find/store session_id
- Can't combine with status filter
- Less flexible

---

### 4. Deleting Tasks

**✅ Modern Way:**
```bash
curl -X DELETE http://localhost:8000/api/v1/tasks/by-name/add-login-feature
```

**Benefits:**
- Use task name (easy to remember)
- Automatic worktree cleanup
- One command

**❌ Legacy Way (Don't do this):**
```bash
curl -X DELETE http://localhost:8000/api/v1/tasks/abc-123-def-456
```

**Why legacy is worse:**
- Need to store/lookup task UUID
- Less convenient

---

## Common Use Cases

### Use Case 1: Create and Monitor a Task

```bash
# 1. Create task
curl -X POST http://localhost:8000/api/v1/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "task_name": "implement-search",
    "description": "Add search functionality to the app",
    "root_folder": "/Users/me/myapp"
  }'

# 2. Monitor status (poll every 10 seconds)
while true; do
  curl http://localhost:8000/api/v1/tasks/by-name/implement-search/status | jq
  sleep 10
done

# 3. When complete, delete
curl -X DELETE http://localhost:8000/api/v1/tasks/by-name/implement-search
```

---

### Use Case 2: Manage Multiple Tasks on Same Project

```bash
# Create multiple tasks for same project
curl -X POST http://localhost:8000/api/v1/tasks \
  -d '{"task_name": "add-auth", "root_folder": "/myapp", ...}'

curl -X POST http://localhost:8000/api/v1/tasks \
  -d '{"task_name": "add-api", "root_folder": "/myapp", ...}'

curl -X POST http://localhost:8000/api/v1/tasks \
  -d '{"task_name": "add-tests", "root_folder": "/myapp", ...}'

# List all tasks for this project
curl "http://localhost:8000/api/v1/tasks?root_folder=/myapp"

# Check which are running
curl "http://localhost:8000/api/v1/tasks?root_folder=/myapp&status=running"
```

---

### Use Case 3: Monitor All Active Tasks

```bash
# Get all running tasks (across all projects)
curl "http://localhost:8000/api/v1/tasks?status=running"

# Get all pending tasks
curl "http://localhost:8000/api/v1/tasks?status=pending"

# Get recent completed tasks
curl "http://localhost:8000/api/v1/tasks?status=completed&limit=10"
```

---

### Use Case 4: Dashboard/Monitoring Script

```python
import requests
import time

API_BASE = "http://localhost:8000/api/v1"

def monitor_project(root_folder: str):
    """Monitor all tasks for a project."""
    while True:
        # Get all tasks for project
        response = requests.get(
            f"{API_BASE}/tasks",
            params={"root_folder": root_folder}
        )
        tasks = response.json()

        print(f"\n=== Project: {root_folder} ===")
        for task in tasks:
            print(f"  {task['task_name']}: {task['status']}")

            # Get detailed status
            status = requests.get(
                f"{API_BASE}/tasks/by-name/{task['task_name']}/status"
            ).json()

            if status['waiting_for_input']:
                print(f"    ⚠️  Waiting for input!")
                print(f"    Claude says: {status['latest_claude_response'][:100]}...")

        time.sleep(30)

# Usage
monitor_project("/Users/me/myapp")
```

---

## Session API - When Would You Actually Use It?

### Answer: Almost Never

Sessions are **automatically managed internally**. You should not need to interact with them directly.

### The ONLY Scenario Where Session API Might Be Useful

**If you want to inspect the internal session structure for debugging:**

```bash
# Get all tasks
curl http://localhost:8000/api/v1/tasks

# Notice they have session_id in response
# {
#   "session_id": "abc-123",
#   "task_name": "my-task",
#   ...
# }

# Inspect the session (for debugging only)
curl http://localhost:8000/api/v1/sessions/abc-123
# Response:
# {
#   "id": "abc-123",
#   "project_path": "/Users/me/myapp",
#   "created_at": "...",
#   "updated_at": "..."
# }

# See all tasks in session (equivalent to filtering by root_folder)
curl http://localhost:8000/api/v1/sessions/abc-123/tasks
```

**But even this is better done with:**
```bash
curl "http://localhost:8000/api/v1/tasks?root_folder=/Users/me/myapp"
```

---

## API Endpoint Reference

### Recommended APIs (Use These)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/tasks` | Create new task (session auto-managed) |
| `GET` | `/api/v1/tasks/by-name/{task_name}` | Get full task details by name |
| `GET` | `/api/v1/tasks/by-name/{task_name}/status` | Get task status by name |
| `GET` | `/api/v1/tasks?status=X&root_folder=Y` | List tasks with filters |
| `DELETE` | `/api/v1/tasks/by-name/{task_name}` | Delete task by name |

### Legacy APIs (Backward Compatibility Only)

| Method | Endpoint | Description | Why Avoid |
|--------|----------|-------------|-----------|
| `POST` | `/api/v1/sessions` | Create session manually | Auto-created by task API |
| `GET` | `/api/v1/sessions/{session_id}` | Get session details | Session IDs are internal |
| `GET` | `/api/v1/sessions/{session_id}/tasks` | List session tasks | Use `/tasks?root_folder=` |
| `GET` | `/api/v1/tasks/{task_id}` | Get task by UUID | Task names are more convenient |
| `GET` | `/api/v1/tasks/{task_id}/status` | Get status by UUID | Use task name instead |

---

## Migration from Legacy to Modern API

### If You're Using Session API

**Old code:**
```python
# Don't do this
session = requests.post(f"{API}/sessions", json={
    "project_path": "/myapp"
}).json()

task = requests.post(f"{API}/tasks", json={
    "session_id": session['id'],
    "description": "..."
}).json()

# Store task['id'] somewhere...
task_id = task['id']

# Later...
status = requests.get(f"{API}/tasks/{task_id}/status").json()
```

**New code:**
```python
# Do this instead
task = requests.post(f"{API}/tasks", json={
    "task_name": "add-feature",
    "description": "...",
    "root_folder": "/myapp"
}).json()

# Later... (no need to store IDs)
status = requests.get(f"{API}/tasks/by-name/add-feature/status").json()
```

---

## Summary

### ✅ Use Task-Name-Based API

**Why:**
- Simple, one-step task creation
- No manual session management
- Human-readable task names
- Filter tasks by project folder
- Modern, intuitive design

### ❌ Avoid Session API

**Why:**
- Legacy design
- Requires managing session IDs
- More complex for no benefit
- Task-name API does everything better

### The Only Exception

**Debugging internal structure** - But even then, filtering tasks by `root_folder` is usually better.

---

## Quick Reference Card

```bash
# ===== TASK OPERATIONS =====

# Create task
POST /api/v1/tasks
{
  "task_name": "my-task",
  "description": "...",
  "root_folder": "/project"
}

# Check status
GET /api/v1/tasks/by-name/my-task/status

# Get full details
GET /api/v1/tasks/by-name/my-task

# Delete task
DELETE /api/v1/tasks/by-name/my-task

# ===== QUERY OPERATIONS =====

# All tasks for a project
GET /api/v1/tasks?root_folder=/project

# Running tasks for a project
GET /api/v1/tasks?root_folder=/project&status=running

# All running tasks (any project)
GET /api/v1/tasks?status=running

# Recent tasks
GET /api/v1/tasks?limit=10
```

**That's it! You don't need anything else.**
