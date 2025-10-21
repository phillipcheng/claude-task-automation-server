# Simple Usage Guide - Task Name Based API

## Overview

The Claude Task Automation Server now supports a simplified workflow where you only need to provide a **task name** to create and query tasks. Sessions are managed automatically!

## Quick Start

### 1. Start the Server

```bash
python3 -m app.main
```

Server runs at: http://localhost:8000

### 2. Create a Task (Just Name + Description!)

```bash
curl -X POST http://localhost:8000/api/v1/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "task_name": "calculator",
    "description": "Create a Python calculator module with add, subtract, multiply, divide functions"
  }'
```

**Response:**
```json
{
  "id": "abc-123",
  "task_name": "calculator",
  "session_id": "auto-generated",
  "description": "Create a Python calculator...",
  "status": "pending",
  "created_at": "2025-10-21T10:00:00"
}
```

### 3. Check Status (Using Task Name!)

```bash
curl http://localhost:8000/api/v1/tasks/by-name/calculator/status
```

**Response:**
```json
{
  "task_name": "calculator",
  "status": "running",
  "progress": "Task is running - 3 interactions so far",
  "test_summary": {
    "total": 0,
    "passed": 0,
    "failed": 0,
    "pending": 0
  }
}
```

That's it! Simple and clean! 🎉

## API Endpoints (Name-Based)

### Create Task
```
POST /api/v1/tasks
```

**Body:**
```json
{
  "task_name": "my-task",
  "description": "What to do",
  "project_path": "/optional/path"  // Optional
}
```

### Get Task Status
```
GET /api/v1/tasks/by-name/{task_name}/status
```

### Get Task Details
```
GET /api/v1/tasks/by-name/{task_name}
```

### List All Tasks
```
GET /api/v1/tasks?status=running&limit=50
```

### Delete Task
```
DELETE /api/v1/tasks/by-name/{task_name}
```

## Real Examples

### Example 1: Create a Web Scraper

```bash
curl -X POST http://localhost:8000/api/v1/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "task_name": "web-scraper",
    "description": "Create a web scraper that extracts product prices from e-commerce sites"
  }'
```

### Example 2: Check Status

```bash
curl http://localhost:8000/api/v1/tasks/by-name/web-scraper/status | jq
```

### Example 3: Get Full Details

```bash
curl http://localhost:8000/api/v1/tasks/by-name/web-scraper | jq
```

### Example 4: List Running Tasks

```bash
curl "http://localhost:8000/api/v1/tasks?status=running" | jq
```

### Example 5: Delete Task

```bash
curl -X DELETE http://localhost:8000/api/v1/tasks/by-name/web-scraper
```

## Python Client Example

```python
import requests
import time

# Base URL
BASE_URL = "http://localhost:8000/api/v1"

# Create task
response = requests.post(f"{BASE_URL}/tasks", json={
    "task_name": "fibonacci",
    "description": "Create a function to calculate fibonacci numbers"
})
print(f"Created task: {response.json()['task_name']}")

# Monitor status
task_name = "fibonacci"
while True:
    status = requests.get(f"{BASE_URL}/tasks/by-name/{task_name}/status").json()
    print(f"Status: {status['status']} - {status['progress']}")

    if status['status'] in ['completed', 'failed']:
        break

    time.sleep(5)

# Get results
details = requests.get(f"{BASE_URL}/tasks/by-name/{task_name}").json()
print(f"Summary: {details['summary']}")
```

## How Sessions Work (Automatic!)

When you create a task:

1. **Without project_path**: Uses default session (`/tmp/claude_projects`)
2. **With project_path**: Creates/reuses session for that path

```bash
# Uses default project location
curl -X POST http://localhost:8000/api/v1/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "task_name": "task1",
    "description": "Some task"
  }'

# Uses specific project
curl -X POST http://localhost:8000/api/v1/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "task_name": "task2",
    "description": "Some task",
    "project_path": "/Users/me/myproject"
  }'
```

## Task Names

- **Must be unique**: Can't create two tasks with the same name
- **Use descriptive names**: "calculator", "user-auth", "data-processor"
- **URL-friendly**: Avoid spaces, use hyphens or underscores

## Task Lifecycle

```
CREATE → PENDING → RUNNING ⟷ PAUSED → TESTING → COMPLETED/FAILED
                      ↓
              (Simulated human
               encouragement)
```

## Status Values

- `pending` - Waiting to start
- `running` - Claude is working
- `paused` - Waiting for encouragement
- `testing` - Running tests
- `completed` - All tests passed ✓
- `failed` - Tests failed or error ✗

## Tips

### Monitor Progress
```bash
# Watch status update every 2 seconds
watch -n 2 "curl -s http://localhost:8000/api/v1/tasks/by-name/my-task/status | jq"
```

### List Recent Tasks
```bash
curl http://localhost:8000/api/v1/tasks?limit=10 | jq
```

### Filter by Status
```bash
curl "http://localhost:8000/api/v1/tasks?status=completed" | jq
```

## Configuration

Set default project path in `.env`:

```bash
DEFAULT_PROJECT_PATH=/Users/me/my_projects
```

## Troubleshooting

### Task Name Already Exists

```json
{
  "detail": "Task with name 'calculator' already exists..."
}
```

**Solution**: Use a different name or delete the existing task:
```bash
curl -X DELETE http://localhost:8000/api/v1/tasks/by-name/calculator
```

### Task Not Found

```json
{
  "detail": "Task 'xyz' not found"
}
```

**Solution**: Check the task name spelling or list all tasks:
```bash
curl http://localhost:8000/api/v1/tasks | jq
```

## Legacy API (Still Supported)

The old session-based API still works:

```bash
# Create session
curl -X POST http://localhost:8000/api/v1/sessions \
  -d '{"project_path": "/tmp/test"}'

# Create task with session_id
# (old way - not recommended)
```

## API Documentation

Full interactive API docs: http://localhost:8000/docs

## Complete Workflow Example

```bash
#!/bin/bash

# 1. Create task
echo "Creating task..."
curl -X POST http://localhost:8000/api/v1/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "task_name": "email-validator",
    "description": "Create a Python function to validate email addresses with regex"
  }'

# 2. Monitor progress
echo "\nMonitoring progress..."
for i in {1..20}; do
    status=$(curl -s http://localhost:8000/api/v1/tasks/by-name/email-validator/status | jq -r '.status')
    echo "Status: $status"

    if [ "$status" = "completed" ] || [ "$status" = "failed" ]; then
        break
    fi

    sleep 5
done

# 3. Get results
echo "\nFetching results..."
curl -s http://localhost:8000/api/v1/tasks/by-name/email-validator | jq '{
    task_name: .task_name,
    status: .status,
    summary: .summary,
    test_count: (.test_cases | length)
}'
```

## Summary

✅ **Create**: Just provide task_name and description
✅ **Query**: Use task_name to check status
✅ **No Sessions**: Managed automatically
✅ **Simple API**: Clean and intuitive

Happy automating! 🚀
