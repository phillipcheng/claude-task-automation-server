# Task Lifecycle Management

## Overview

Tasks now support **manual lifecycle control** - you can create tasks without auto-starting them, then start/stop/resume as needed.

## Task States

```
PENDING → START → RUNNING → STOP → STOPPED → RESUME → RUNNING
                     ↓                                      ↓
                  PAUSED                               TESTING
                     ↓                                      ↓
                  RUNNING                            COMPLETED/FAILED
```

### Status Descriptions

| Status | Description | Can Start? | Can Stop? | Can Resume? |
|--------|-------------|------------|-----------|-------------|
| `PENDING` | Task created, not started | ✅ Yes | ❌ No | ❌ No |
| `RUNNING` | Task actively executing | ❌ No | ✅ Yes | ❌ No |
| `PAUSED` | Temporarily paused (auto) | ❌ No | ✅ Yes | ❌ No |
| `STOPPED` | Manually stopped | ❌ No | ❌ No | ✅ Yes |
| `TESTING` | Running tests | ❌ No | ✅ Yes | ❌ No |
| `COMPLETED` | Successfully finished | ❌ No | ❌ No | ❌ No |
| `FAILED` | Failed with errors | ❌ No | ❌ No | ❌ No |

## API Endpoints

### 1. Create Task (Without Auto-Start)

```bash
POST /api/v1/tasks
```

**Request:**
```json
{
  "task_name": "add-feature",
  "description": "Implement new feature",
  "root_folder": "/path/to/project",
  "auto_start": false  // KEY: Don't start automatically
}
```

**Response:**
```json
{
  "id": "abc-123",
  "task_name": "add-feature",
  "status": "pending",  // Not running yet
  "root_folder": "/path/to/project",
  "branch_name": "task/add-feature",
  "worktree_path": "/path/to/project/.claude_worktrees/add-feature",
  ...
}
```

### 2. Start Task

```bash
POST /api/v1/tasks/by-name/{task_name}/start
```

**Requirements:**
- Task must be in `PENDING` status
- Only works on newly created tasks

**Example:**
```bash
curl -X POST http://localhost:8000/api/v1/tasks/by-name/add-feature/start
```

**Response:**
```json
{
  "message": "Task 'add-feature' started",
  "status": "running"
}
```

### 3. Stop Task

```bash
POST /api/v1/tasks/by-name/{task_name}/stop
```

**Requirements:**
- Task must be in `RUNNING`, `PAUSED`, or `TESTING` status
- Stops execution immediately

**Example:**
```bash
curl -X POST http://localhost:8000/api/v1/tasks/by-name/add-feature/stop
```

**Response:**
```json
{
  "message": "Task 'add-feature' stopped",
  "status": "stopped"
}
```

### 4. Resume Task

```bash
POST /api/v1/tasks/by-name/{task_name}/resume
```

**Requirements:**
- Task must be in `STOPPED` status
- Continues from where it left off

**Example:**
```bash
curl -X POST http://localhost:8000/api/v1/tasks/by-name/add-feature/resume
```

**Response:**
```json
{
  "message": "Task 'add-feature' resumed",
  "status": "running"
}
```

## Workflows

### Workflow 1: Manual Control (Create → Start → Monitor)

```bash
# Step 1: Create task (doesn't start)
curl -X POST http://localhost:8000/api/v1/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "task_name": "add-login",
    "description": "Implement login feature",
    "root_folder": "/myapp",
    "auto_start": false
  }'

# Response: status = "pending"

# Step 2: Start when ready
curl -X POST http://localhost:8000/api/v1/tasks/by-name/add-login/start

# Response: status = "running"

# Step 3: Monitor
curl http://localhost:8000/api/v1/tasks/by-name/add-login/status

# Step 4: Stop if needed
curl -X POST http://localhost:8000/api/v1/tasks/by-name/add-login/stop

# Step 5: Resume later
curl -X POST http://localhost:8000/api/v1/tasks/by-name/add-login/resume
```

### Workflow 2: Auto-Start (Legacy Behavior)

```bash
# Create and auto-start in one call
curl -X POST http://localhost:8000/api/v1/tasks \
  -d '{
    "task_name": "quick-task",
    "description": "Simple task",
    "root_folder": "/myapp",
    "auto_start": true  // Starts immediately
  }'

# Response: status = "running" (already started)
```

### Workflow 3: Batch Creation, Selective Execution

```bash
# Create multiple tasks
curl -X POST http://localhost:8000/api/v1/tasks \
  -d '{"task_name": "task-1", "description": "...", "auto_start": false}'

curl -X POST http://localhost:8000/api/v1/tasks \
  -d '{"task_name": "task-2", "description": "...", "auto_start": false}'

curl -X POST http://localhost:8000/api/v1/tasks \
  -d '{"task_name": "task-3", "description": "...", "auto_start": false}'

# All tasks are PENDING

# Start only task-1 and task-3
curl -X POST http://localhost:8000/api/v1/tasks/by-name/task-1/start
curl -X POST http://localhost:8000/api/v1/tasks/by-name/task-3/start

# task-2 remains PENDING (not started)
```

### Workflow 4: Stop and Resume

```bash
# Task is running
curl http://localhost:8000/api/v1/tasks/by-name/my-task/status
# Status: "running"

# Need to pause for maintenance
curl -X POST http://localhost:8000/api/v1/tasks/by-name/my-task/stop

# Status: "stopped"

# Perform maintenance...

# Resume when ready
curl -X POST http://localhost:8000/api/v1/tasks/by-name/my-task/resume

# Status: "running" again
```

## Use Cases

### Use Case 1: Scheduled Execution

```python
import requests
import time

# Create task at 9 AM
def create_morning_task():
    requests.post("http://localhost:8000/api/v1/tasks", json={
        "task_name": "daily-report",
        "description": "Generate daily report",
        "root_folder": "/analytics",
        "auto_start": false  # Don't start yet
    })

# Start task at 9 PM (after business hours)
def start_nightly_task():
    requests.post(
        "http://localhost:8000/api/v1/tasks/by-name/daily-report/start"
    )

# Schedule
create_morning_task()  # 9 AM
time.sleep(12 * 3600)  # Wait 12 hours
start_nightly_task()   # 9 PM
```

### Use Case 2: Resource Management

```python
# Create multiple tasks
for i in range(5):
    requests.post("http://localhost:8000/api/v1/tasks", json={
        "task_name": f"task-{i}",
        "description": f"Task {i}",
        "root_folder": "/project",
        "auto_start": False
    })

# Start only 2 at a time (resource limit)
def run_with_limit(max_concurrent=2):
    running = 0
    for i in range(5):
        if running < max_concurrent:
            requests.post(f"http://localhost:8000/api/v1/tasks/by-name/task-{i}/start")
            running += 1

        # Monitor and start next when one completes
        # ... (poll status and adjust)
```

### Use Case 3: Emergency Stop

```python
# Task running...

# Emergency: need to stop all tasks
def emergency_stop():
    tasks = requests.get("http://localhost:8000/api/v1/tasks?status=running").json()

    for task in tasks:
        print(f"Stopping {task['task_name']}")
        requests.post(
            f"http://localhost:8000/api/v1/tasks/by-name/{task['task_name']}/stop"
        )

# Later, resume specific tasks
def resume_critical_tasks():
    for task_name in ["critical-task-1", "critical-task-2"]:
        requests.post(
            f"http://localhost:8000/api/v1/tasks/by-name/{task_name}/resume"
        )
```

## Differences: PAUSED vs STOPPED

| Aspect | PAUSED | STOPPED |
|--------|--------|---------|
| **Trigger** | Automatic (by system) | Manual (by user) |
| **Reason** | Waiting for auto-response | User intervention |
| **Resume** | Automatic (system continues) | Manual (user must resume) |
| **Duration** | Short (seconds) | Indefinite (until resumed) |
| **Use Case** | Internal workflow | User control |

**PAUSED Example:**
```
Claude asks: "Should I add validation?"
→ Status: PAUSED
→ System generates answer: "Yes, proceed"
→ Status: RUNNING (auto-resumes)
```

**STOPPED Example:**
```
User: "I need to stop this task for maintenance"
→ POST /stop
→ Status: STOPPED
→ (stays stopped until user resumes)
→ POST /resume
→ Status: RUNNING
```

## Error Handling

### Invalid Transitions

**Starting non-PENDING task:**
```bash
curl -X POST http://localhost:8000/api/v1/tasks/by-name/my-task/start

# Error response:
{
  "detail": "Task can only be started from PENDING status. Current status: running"
}
```

**Stopping completed task:**
```bash
curl -X POST http://localhost:8000/api/v1/tasks/by-name/my-task/stop

# Error response:
{
  "detail": "Task can only be stopped from RUNNING/PAUSED/TESTING status. Current status: completed"
}
```

**Resuming non-STOPPED task:**
```bash
curl -X POST http://localhost:8000/api/v1/tasks/by-name/my-task/resume

# Error response:
{
  "detail": "Task can only be resumed from STOPPED status. Current status: pending"
}
```

## Migration Guide

### Old Behavior (Auto-Start)

```bash
# Tasks started automatically
POST /api/v1/tasks
{
  "task_name": "my-task",
  "description": "..."
}
# → Immediately starts running
```

### New Behavior (Manual Control)

**Option 1: Keep auto-start (backward compatible)**
```bash
POST /api/v1/tasks
{
  "task_name": "my-task",
  "description": "...",
  "auto_start": true  // Add this
}
```

**Option 2: Manual start (new recommended way)**
```bash
# Create
POST /api/v1/tasks
{
  "task_name": "my-task",
  "description": "...",
  "auto_start": false  // Default
}

# Start when ready
POST /api/v1/tasks/by-name/my-task/start
```

## Best Practices

### 1. Default to Manual Start

```python
# Recommended: explicit control
def create_controlled_task(name, desc, folder):
    # Create without starting
    response = requests.post("http://localhost:8000/api/v1/tasks", json={
        "task_name": name,
        "description": desc,
        "root_folder": folder,
        "auto_start": False  # Explicit
    })

    # Verify creation
    task = response.json()
    print(f"Created: {task['task_name']} - Status: {task['status']}")

    # Start when you're ready
    requests.post(f"http://localhost:8000/api/v1/tasks/by-name/{name}/start")
```

### 2. Always Check Status Before Operations

```python
def safe_stop(task_name):
    # Check current status
    status = requests.get(
        f"http://localhost:8000/api/v1/tasks/by-name/{task_name}/status"
    ).json()

    if status['status'] in ['running', 'paused', 'testing']:
        # Safe to stop
        requests.post(
            f"http://localhost:8000/api/v1/tasks/by-name/{task_name}/stop"
        )
    else:
        print(f"Cannot stop task in {status['status']} status")
```

### 3. Handle Errors Gracefully

```python
def start_task_safe(task_name):
    try:
        response = requests.post(
            f"http://localhost:8000/api/v1/tasks/by-name/{task_name}/start"
        )
        response.raise_for_status()
        print(f"Started: {task_name}")
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 400:
            # Invalid state transition
            print(f"Cannot start: {e.response.json()['detail']}")
        elif e.response.status_code == 404:
            print(f"Task not found: {task_name}")
        else:
            raise
```

## Summary

The new lifecycle management provides:

✅ **Explicit control** - Start tasks when you're ready
✅ **Stop capability** - Halt execution at any time
✅ **Resume support** - Continue from where you stopped
✅ **Backward compatible** - `auto_start: true` works like before
✅ **Flexible workflows** - Batch creation, scheduled execution, resource limits

**Default behavior changed:**
- **Old**: Tasks auto-started on creation
- **New**: Tasks stay PENDING until manually started (unless `auto_start: true`)

This gives you full control over task execution timing!
