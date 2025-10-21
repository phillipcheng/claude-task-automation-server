# Git Worktree Integration Guide

## Overview

The Claude Task Automation Server uses **git worktrees** to enable multiple tasks to work on the same project simultaneously without conflicts. Each task gets its own isolated working directory!

## Why Git Worktrees?

### The Problem
Without worktrees:
- Multiple tasks on same project = file conflicts
- Tasks can't run in parallel
- Risk of overwriting each other's changes

### The Solution
With worktrees:
- ✅ Each task gets isolated workspace
- ✅ Multiple tasks run in parallel safely
- ✅ Different branches per task
- ✅ No file conflicts

## How It Works

### Project Structure

```
/Users/me/myproject/          # Main repository
├── .git/                     # Git metadata
├── src/                      # Your code
├── .claude_worktrees/        # Worktree directory (auto-created)
│   ├── task-feature-login/   # Worktree for task 1
│   │   ├── src/             # Isolated copy
│   │   └── ...
│   ├── task-add-api/         # Worktree for task 2
│   │   ├── src/             # Isolated copy
│   │   └── ...
│   └── fix-bug-123/          # Worktree for task 3
│       ├── src/             # Isolated copy
│       └── ...
```

### Automatic Behavior

**When you create a task:**
1. System checks if `root_folder` is a git repository
2. Creates worktree in `.claude_worktrees/{task_name}/`
3. Checks out branch (creates new one if needed)
4. Claude works in the worktree directory
5. Changes are isolated from other tasks

## Usage

### Basic Task (Auto Worktree)

```bash
curl -X POST http://localhost:8000/api/v1/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "task_name": "add-login",
    "description": "Implement login functionality",
    "root_folder": "/Users/me/myproject"
  }'
```

**What happens:**
- ✓ Creates worktree: `/Users/me/myproject/.claude_worktrees/add-login/`
- ✓ Creates branch: `task/add-login`
- ✓ Claude works in worktree
- ✓ No conflicts with other tasks

### Task with Specific Branch

```bash
curl -X POST http://localhost:8000/api/v1/tasks \
  -d '{
    "task_name": "feature-api",
    "description": "Create API endpoints",
    "root_folder": "/Users/me/myproject",
    "branch_name": "feature/rest-api"
  }'
```

**Result:**
- Worktree created for branch `feature/rest-api`
- If branch doesn't exist, creates it
- If branch exists, checks it out

### Disable Worktree (Use Main Repo)

```bash
curl -X POST http://localhost:8000/api/v1/tasks \
  -d '{
    "task_name": "simple-task",
    "description": "Quick fix",
    "root_folder": "/Users/me/myproject",
    "use_worktree": false
  }'
```

**Use cases for disabling:**
- Single task on project
- Non-git project
- Debugging worktree issues

## Parallel Task Execution

### Scenario: Multiple Features

```bash
# Task 1: User authentication
curl -X POST http://localhost:8000/api/v1/tasks \
  -d '{
    "task_name": "user-auth",
    "root_folder": "/Users/me/myproject",
    "branch_name": "feature/auth"
  }'

# Task 2: Payment integration (runs in parallel!)
curl -X POST http://localhost:8000/api/v1/tasks \
  -d '{
    "task_name": "payment",
    "root_folder": "/Users/me/myproject",
    "branch_name": "feature/payments"
  }'

# Task 3: Bug fix (also in parallel!)
curl -X POST http://localhost:8000/api/v1/tasks \
  -d '{
    "task_name": "fix-crash",
    "root_folder": "/Users/me/myproject",
    "branch_name": "bugfix/crash-on-load"
  }'
```

**Result:**
```
myproject/.claude_worktrees/
├── user-auth/     # Branch: feature/auth
├── payment/       # Branch: feature/payments
└── fix-crash/     # Branch: bugfix/crash-on-load

All three tasks run simultaneously with no conflicts!
```

## Task Response

### With Worktree

```json
{
  "task_name": "add-feature",
  "root_folder": "/Users/me/myproject",
  "branch_name": "task/add-feature",
  "worktree_path": "/Users/me/myproject/.claude_worktrees/add-feature",
  "git_repo": "https://github.com/user/myproject.git",
  "status": "running"
}
```

### Without Worktree

```json
{
  "task_name": "simple-task",
  "root_folder": "/Users/me/myproject",
  "branch_name": "main",
  "worktree_path": null,
  "git_repo": "https://github.com/user/myproject.git",
  "status": "running"
}
```

## Cleanup

### Automatic Cleanup on Delete

```bash
# Deletes task AND removes worktree
curl -X DELETE http://localhost:8000/api/v1/tasks/by-name/add-feature
```

**Response:**
```json
{
  "message": "Task 'add-feature' deleted successfully",
  "worktree_cleanup": "Removed worktree at /Users/me/myproject/.claude_worktrees/add-feature"
}
```

### Keep Worktree When Deleting

```bash
# Delete task but keep worktree
curl -X DELETE "http://localhost:8000/api/v1/tasks/by-name/add-feature?cleanup_worktree=false"
```

### Manual Cleanup

If worktrees become stale:

```bash
cd /Users/me/myproject
git worktree prune -v
```

## Requirements

### Git Version

Git worktree requires **git 2.5+**

Check your version:
```bash
git --version
# Should show: git version 2.5.0 or higher
```

### System Check

The system automatically checks git version and:
- ✅ Uses worktrees if supported
- ⚠️ Falls back to main repo if not supported

## Branch Naming

### Auto-Created Branches

When no `branch_name` specified:
```
task/{task-name}
```

Examples:
- Task: `add-login` → Branch: `task/add-login`
- Task: `fix/bug-123` → Branch: `task/fix_bug-123`
- Task: `feature api` → Branch: `task/feature_api`

### Custom Branches

When `branch_name` specified:
```
Your exact branch name
```

## Best Practices

### 1. Use Worktrees for Parallel Work

```bash
# Good - Multiple tasks on same project
{
  "root_folder": "/Users/me/project",
  "use_worktree": true
}
```

### 2. One Worktree Per Feature

```bash
# Good - Focused task
"task_name": "add-user-registration"

# Less ideal - Too broad
"task_name": "entire-auth-system"
```

### 3. Clean Up Completed Tasks

```bash
# After task completes successfully
curl -X DELETE http://localhost:8000/api/v1/tasks/by-name/completed-task
```

### 4. Use Descriptive Task Names

```bash
# Good - Clear worktree purpose
"task_name": "feature-oauth-integration"

# Not ideal - Ambiguous
"task_name": "task1"
```

## Workflow Example

### Full Feature Development

```bash
# 1. Start feature task
curl -X POST http://localhost:8000/api/v1/tasks \
  -d '{
    "task_name": "add-search",
    "description": "Add search functionality to the app",
    "root_folder": "/Users/me/myapp",
    "branch_name": "feature/search"
  }'

# Worktree created:
# /Users/me/myapp/.claude_worktrees/add-search/
# Branch: feature/search

# 2. Monitor progress
curl http://localhost:8000/api/v1/tasks/by-name/add-search/status

# 3. Task completes, code is in worktree on branch feature/search

# 4. You review and merge
cd /Users/me/myapp/.claude_worktrees/add-search
git add .
git commit -m "Add search functionality"
git push origin feature/search

# Create PR, merge, etc.

# 5. Clean up
curl -X DELETE http://localhost:8000/api/v1/tasks/by-name/add-search
# Worktree automatically removed
```

## Multiple Projects

### Different Projects = No Problem

```bash
# Project A
curl -X POST http://localhost:8000/api/v1/tasks \
  -d '{
    "task_name": "project-a-feature",
    "root_folder": "/Users/me/project-a"
  }'

# Project B (runs in parallel!)
curl -X POST http://localhost:8000/api/v1/tasks \
  -d '{
    "task_name": "project-b-feature",
    "root_folder": "/Users/me/project-b"
  }'
```

Each project has its own `.claude_worktrees/` directory.

## Troubleshooting

### Worktree Not Created

**Problem:** Task has `worktree_path: null`

**Possible Causes:**
1. Not a git repository
2. Git version < 2.5
3. `use_worktree: false` specified
4. Worktree creation failed

**Solutions:**
```bash
# Check if git repo
cd /path/to/project
git status

# Check git version
git --version

# Try manual worktree creation
git worktree add .claude_worktrees/test-worktree
```

### Worktree Already Exists

**Problem:** Error creating worktree

**Solution:**
```bash
# List existing worktrees
git worktree list

# Remove stale worktree
git worktree remove .claude_worktrees/task-name --force

# Or prune all stale worktrees
git worktree prune
```

### Permission Denied

**Problem:** Can't create worktree directory

**Solution:**
```bash
# Check permissions
ls -la /path/to/project

# Create directory manually
mkdir -p /path/to/project/.claude_worktrees
chmod 755 /path/to/project/.claude_worktrees
```

### Branch Already Checked Out

**Problem:** "branch 'X' is already checked out"

**Cause:** Branch is used in main repo or another worktree

**Solution:**
- Use a different branch name
- Or finish/remove the other task first

## Advanced Usage

### Pre-Create Branch

```bash
# Create branch first
cd /Users/me/myproject
git checkout -b feature/complex-feature

# Then create task using that branch
curl -X POST http://localhost:8000/api/v1/tasks \
  -d '{
    "task_name": "complex-task",
    "root_folder": "/Users/me/myproject",
    "branch_name": "feature/complex-feature"
  }'
```

### Inspect Worktree

```bash
# List all worktrees
git worktree list

# Output:
# /Users/me/myproject         abc123 [main]
# /Users/me/myproject/.claude_worktrees/task1  def456 [feature/task1]
# /Users/me/myproject/.claude_worktrees/task2  789ghi [feature/task2]

# Go to worktree
cd /Users/me/myproject/.claude_worktrees/task1
git status
git log
```

### Force Delete Worktree

```bash
# If normal delete fails
git worktree remove .claude_worktrees/task-name --force
```

## Configuration

### Default Behavior

In the system:
- `use_worktree`: `true` (default)
- Worktree location: `{root_folder}/.claude_worktrees/`
- Auto-cleanup: `true` (when deleting task)

### Environment Variables

None needed! Works out of the box with git.

## Limitations

### Git Version

- Requires git 2.5+
- Older git versions: worktrees disabled automatically

### File System

- Each worktree is a full copy of the working tree
- Disk space needed: ~size of repo × number of tasks
- Recommendation: Clean up completed tasks regularly

### Branch Conflicts

- Can't checkout same branch in multiple worktrees
- Solution: Use different branches per task

## Benefits Summary

✅ **Parallel Execution** - Run multiple tasks simultaneously
✅ **Isolation** - No file conflicts between tasks
✅ **Branch Management** - Each task on its own branch
✅ **Safety** - Changes isolated until ready to merge
✅ **Productivity** - No waiting for other tasks to finish
✅ **Clean History** - Clear branch-per-feature workflow

## Comparison

### Without Worktrees

```
Task 1 starts → modifies files → Task 2 starts → CONFLICT!
```

### With Worktrees

```
Task 1: /project/.claude_worktrees/task1/ (branch A)
Task 2: /project/.claude_worktrees/task2/ (branch B)
Task 3: /project/.claude_worktrees/task3/ (branch C)

All run in parallel, no conflicts! ✅
```

## Summary

Git worktrees enable:
- 🎯 Multiple tasks per project
- 🚀 Parallel execution
- 🔒 Isolated workspaces
- 🌿 Clean branch management
- ✨ Zero conflicts

**Default behavior**: Enabled automatically for all git repositories!

Happy parallel automating! 🎉
