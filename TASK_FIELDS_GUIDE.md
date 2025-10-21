# Task Fields Guide

## Overview

Tasks now include comprehensive metadata to better organize and track your automation work, including project location and git information.

## Task Fields

### Core Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `task_name` | string | Yes | Unique identifier for the task |
| `description` | string | Yes | What the task should accomplish |

### Project Context Fields

| Field | Type | Required | Auto-Detected | Description |
|-------|------|----------|---------------|-------------|
| `root_folder` | string | No | No | Project root directory path |
| `branch_name` | string | No | Yes* | Git branch to work on |
| `git_repo` | string | No | Yes* | Git repository URL (read-only) |

\* Auto-detected from `root_folder` if it's a git repository

### Status Fields (Read-Only)

| Field | Type | Description |
|-------|------|-------------|
| `status` | enum | pending, running, paused, testing, completed, failed |
| `summary` | string | Summary of what was accomplished |
| `error_message` | string | Error details if failed |
| `created_at` | datetime | When task was created |
| `updated_at` | datetime | Last update time |
| `completed_at` | datetime | When task completed |

## Creating Tasks

### Basic Task (No Project Context)

```bash
curl -X POST http://localhost:8000/api/v1/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "task_name": "simple-task",
    "description": "Create a hello world function"
  }'
```

Uses default project folder: `/tmp/claude_projects`

### Task with Root Folder

```bash
curl -X POST http://localhost:8000/api/v1/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "task_name": "my-feature",
    "description": "Implement user authentication",
    "root_folder": "/Users/me/myproject"
  }'
```

**Auto-detects**:
- Current git branch
- Git repository URL

### Task with Specific Branch

```bash
curl -X POST http://localhost:8000/api/v1/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "task_name": "feature-login",
    "description": "Add login functionality",
    "root_folder": "/Users/me/myproject",
    "branch_name": "feature/user-login"
  }'
```

**Use cases**:
- Override auto-detected branch
- Specify branch before it's created
- Work on different branch than current

## Git Integration

### Auto-Detection

If `root_folder` is a git repository, the system automatically detects:

1. **Current Branch**
   ```bash
   git rev-parse --abbrev-ref HEAD
   ```

2. **Remote URL**
   ```bash
   git config --get remote.origin.url
   ```

### Example Workflow

```bash
# 1. You're working on a feature branch
cd /Users/me/myproject
git checkout -b feature/new-api

# 2. Create task (auto-detects branch "feature/new-api")
curl -X POST http://localhost:8000/api/v1/tasks \
  -d '{
    "task_name": "new-api",
    "description": "Create REST API endpoints",
    "root_folder": "/Users/me/myproject"
  }'

# 3. Check task shows correct branch
curl http://localhost:8000/api/v1/tasks/by-name/new-api/status
```

**Response**:
```json
{
  "task_name": "new-api",
  "root_folder": "/Users/me/myproject",
  "branch_name": "feature/new-api",
  "status": "running",
  ...
}
```

## Query Responses

### Task Status Response

```json
{
  "id": "abc-123",
  "task_name": "user-auth",
  "root_folder": "/Users/me/myproject",
  "branch_name": "feature/auth",
  "status": "running",
  "progress": "Task is running - 3 interactions so far",
  "summary": null,
  "error_message": null,
  "test_summary": {
    "total": 0,
    "passed": 0,
    "failed": 0,
    "pending": 0
  }
}
```

### Full Task Response

```json
{
  "id": "abc-123",
  "task_name": "user-auth",
  "session_id": "session-456",
  "description": "Implement user authentication with JWT",
  "root_folder": "/Users/me/myproject",
  "branch_name": "feature/auth",
  "git_repo": "https://github.com/user/myproject.git",
  "status": "completed",
  "summary": "Implemented JWT authentication with login/logout endpoints",
  "error_message": null,
  "created_at": "2025-10-21T10:00:00",
  "updated_at": "2025-10-21T10:15:00",
  "completed_at": "2025-10-21T10:15:00",
  "test_cases": [...],
  "interactions": [...]
}
```

## Use Cases

### 1. Feature Development

```bash
# Task for a specific feature branch
curl -X POST http://localhost:8000/api/v1/tasks \
  -d '{
    "task_name": "add-payment",
    "description": "Integrate Stripe payment processing",
    "root_folder": "/Users/me/ecommerce",
    "branch_name": "feature/stripe-integration"
  }'
```

### 2. Bug Fixes

```bash
# Task for a bugfix branch
curl -X POST http://localhost:8000/api/v1/tasks \
  -d '{
    "task_name": "fix-login-error",
    "description": "Fix null pointer exception in login flow",
    "root_folder": "/Users/me/myapp",
    "branch_name": "bugfix/login-npe"
  }'
```

### 3. Multiple Projects

```bash
# Project A
curl -X POST http://localhost:8000/api/v1/tasks \
  -d '{
    "task_name": "project-a-api",
    "root_folder": "/Users/me/project-a"
  }'

# Project B
curl -X POST http://localhost:8000/api/v1/tasks \
  -d '{
    "task_name": "project-b-ui",
    "root_folder": "/Users/me/project-b"
  }'
```

### 4. Non-Git Projects

```bash
# Works fine without git
curl -X POST http://localhost:8000/api/v1/tasks \
  -d '{
    "task_name": "script-task",
    "description": "Create data processing script",
    "root_folder": "/Users/me/scripts"
  }'
```

**Result**: `branch_name` and `git_repo` will be `null`

## Filtering and Querying

### List Tasks by Status

```bash
curl "http://localhost:8000/api/v1/tasks?status=running&limit=50"
```

### Get Specific Task

```bash
curl http://localhost:8000/api/v1/tasks/by-name/my-task
```

### Python Client Example

```python
import requests

BASE_URL = "http://localhost:8000/api/v1"

# Create task with full context
response = requests.post(f"{BASE_URL}/tasks", json={
    "task_name": "add-api-endpoint",
    "description": "Create /api/users endpoint with CRUD operations",
    "root_folder": "/Users/me/api-server",
    "branch_name": "feature/user-endpoint"
})

task = response.json()
print(f"Created task: {task['task_name']}")
print(f"Branch: {task['branch_name']}")
print(f"Repo: {task['git_repo']}")

# Monitor progress
import time
while True:
    status = requests.get(
        f"{BASE_URL}/tasks/by-name/{task['task_name']}/status"
    ).json()

    print(f"Status: {status['status']} on branch {status['branch_name']}")

    if status['status'] in ['completed', 'failed']:
        break

    time.sleep(5)
```

## Benefits

### Organization
✅ Know which project/branch each task is for
✅ Track tasks across multiple projects
✅ See git context at a glance

### Context
✅ Claude CLI works in correct directory
✅ Git operations use correct branch
✅ Tests run in proper environment

### Traceability
✅ Link tasks to git branches
✅ Track work by repository
✅ Audit what was done where

## Configuration

### Set Default Project Path

In `.env`:
```bash
DEFAULT_PROJECT_PATH=/Users/me/projects
```

### Environment Variables

```bash
# Default project location (when no root_folder specified)
DEFAULT_PROJECT_PATH=/Users/me/default-workspace

# Database connection
DATABASE_URL=mysql+pymysql://root:sitebuilder@localhost/claudesys

# Server config
HOST=0.0.0.0
PORT=8000

# Claude CLI command
CLAUDE_CLI_COMMAND=claude
```

## Migration Notes

### Existing Tasks

Tasks created before this update will have:
- `root_folder`: `null` or auto-filled from session
- `branch_name`: `null`
- `git_repo`: `null`

### Backward Compatibility

Old API calls still work:
```bash
# Still supported
curl -X POST http://localhost:8000/api/v1/tasks \
  -d '{
    "task_name": "old-style",
    "description": "Task description"
  }'
```

`project_path` is still supported but deprecated. Use `root_folder` instead.

## Best Practices

### 1. Always Specify Root Folder

```bash
# Good
"root_folder": "/Users/me/myproject"

# Not ideal (uses default)
# (no root_folder)
```

### 2. Let Branch Auto-Detect

```bash
# Let system detect current branch
{
  "root_folder": "/Users/me/myproject"
  # branch_name auto-detected
}

# Only override when needed
{
  "root_folder": "/Users/me/myproject",
  "branch_name": "specific-branch"
}
```

### 3. Use Descriptive Task Names

```bash
# Good - includes context
"task_name": "api-user-crud"
"task_name": "fix-login-bug-123"
"task_name": "feature-payment-stripe"

# Less clear
"task_name": "task1"
"task_name": "fix"
```

### 4. One Task Per Feature/Branch

```bash
# Good - focused task
{
  "task_name": "user-registration",
  "description": "Implement user registration endpoint",
  "branch_name": "feature/user-registration"
}

# Not recommended - too broad
{
  "task_name": "entire-auth-system",
  "description": "Build complete authentication system"
}
```

## Troubleshooting

### Branch Not Detected

**Problem**: `branch_name` is `null` even though project is a git repo

**Solutions**:
1. Check `root_folder` path is correct
2. Verify it's a git repository: `cd /path && git status`
3. Ensure git commands work: `git rev-parse --abbrev-ref HEAD`
4. Manually specify: `"branch_name": "your-branch"`

### Wrong Branch Detected

**Problem**: Shows branch "main" but you're on "feature/xyz"

**Solutions**:
1. Check your actual branch: `git branch --show-current`
2. Explicitly set branch: `"branch_name": "feature/xyz"`
3. Update your working directory: `git checkout feature/xyz`

### Root Folder Not Found

**Problem**: Error about root_folder not existing

**Solutions**:
1. Create the directory: `mkdir -p /path/to/project`
2. Use absolute paths, not relative
3. Check path spelling and permissions

## Summary

The enhanced task fields provide:

✅ **Better Organization** - Track tasks by project and branch
✅ **Git Integration** - Auto-detect branch and repo info
✅ **Context Awareness** - Claude works in right location
✅ **Traceability** - Link tasks to specific branches
✅ **Flexibility** - Works with or without git

Create tasks with full context for the best automation experience! 🚀
