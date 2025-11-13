# CLAUDE.md - AI Assistant Guide

**Version**: 1.0
**Last Updated**: 2025-11-13
**Purpose**: Comprehensive guide for AI assistants working with the Claude Task Automation Server codebase

---

## Quick Overview

The **Claude Task Automation Server** is a FastAPI-based HTTP server that automates software development tasks by integrating with the Claude Code CLI. It orchestrates task execution with human-in-the-loop capabilities, git worktree isolation for parallel tasks, and intelligent auto-responses.

**Tech Stack**: Python 3.8+, FastAPI, SQLAlchemy, SQLite/MySQL, Claude Code CLI
**Architecture**: Async REST API with background task execution
**Key Innovation**: Bridges autonomous AI execution with human oversight through priority-based user input queues and git worktree isolation

---

## Repository Structure

```
claude-task-automation-server/
├── app/                          # Main application code
│   ├── main.py                   # FastAPI app entry point & route mounting
│   ├── database.py               # SQLAlchemy config (SQLite/MySQL support)
│   ├── schemas.py                # Pydantic models for API validation
│   ├── models/                   # SQLAlchemy ORM models (5 models)
│   │   ├── session.py           # Project session grouping
│   │   ├── task.py              # Core task entity (28 fields)
│   │   ├── test_case.py         # Test tracking
│   │   ├── interaction.py       # Conversation logs
│   │   └── prompt.py            # Reusable prompt templates
│   ├── api/
│   │   └── endpoints.py         # ~1955 lines - Complete REST API
│   └── services/                # Business logic (7 key services)
│       ├── task_executor.py     # Core orchestrator for task execution
│       ├── streaming_cli_client.py  # Claude CLI wrapper with NDJSON streaming
│       ├── intelligent_responder.py # Context-aware auto-response generator
│       ├── user_input_manager.py    # High-priority user input queue
│       ├── git_worktree.py          # Git worktree isolation manager
│       ├── criteria_analyzer.py     # LLM-based completion checker
│       └── test_runner.py           # pytest test execution
├── static/
│   └── index.html               # 225KB single-page web UI
├── docs/                         # 17 comprehensive documentation files
├── tests/                        # Test suite (19 test files)
│   ├── unit/                    # 9 unit test files
│   └── integration/             # 10 integration test files
├── migrations/                   # Database migration scripts
├── examples/                     # Example usage scripts
├── scripts/                      # Utility scripts
├── requirements.txt             # 12 Python dependencies
└── README.md                    # User-facing documentation
```

**Total**: 61 Python files

---

## Core Components

### 1. Database Models (`app/models/`)

#### **Task** (`task.py`) - Core Entity
The central model representing a development task with 28 fields:

**Identity & Organization**:
- `id` (UUID), `task_name` (unique), `session_id`, `description`

**Git Context** (Critical for isolation):
- `root_folder`: Main project path
- `branch_name`: Task-specific branch
- `base_branch`: Source branch (main/develop)
- `worktree_path`: Isolated workspace path (e.g., `/project/.claude_worktrees/task-name/`)
- `git_repo`: Repository URL

**Multi-Project Support**:
- `projects`: JSON array of project configs with path/access/context/branch
- `project_context`: User-specified context text

**Status & Execution**:
- `status`: Enum (PENDING → RUNNING → TESTING → COMPLETED/FAILED/EXHAUSTED)
- `process_pid`: Running Claude CLI process ID
- `claude_session_id`: For conversation continuity (critical!)

**Resource Tracking**:
- `end_criteria_config`: JSON with success criteria + iteration/token limits
- `total_tokens_used`: Cumulative output tokens
- `interaction_count`: Calculated property from relationships

**User Input System**:
- `user_input_queue`: JSON array `[{id, input, timestamp, processed}]`
- `user_input_pending`: Boolean flag for quick checks
- `custom_human_input`: Legacy single-input field

**Results**:
- `summary`, `error_message`, `completed_at`

**Status Lifecycle**:
```
PENDING → START → RUNNING ⇄ PAUSED → TESTING → COMPLETED
            ↓                               ↓
         STOPPED → RESUME → RUNNING      FAILED
                              ↓
                         EXHAUSTED → RETRY
```

#### **ClaudeInteraction** (`interaction.py`) - Conversation Logs
Tracks every message exchanged with Claude:

**Types**: USER_REQUEST, CLAUDE_RESPONSE, SIMULATED_HUMAN, TOOL_RESULT

**Token Tracking**: input_tokens, output_tokens, cache_creation_tokens, cache_read_tokens, cost_usd, duration_ms

**Purpose**: Full audit trail for debugging and analysis

#### **Session** (`session.py`) - Project Grouping
Groups tasks for the same project. Auto-created based on `root_folder`.

#### **TestCase** (`test_case.py`) - Test Tracking
Tracks GENERATED (created by Claude) and REGRESSION (existing) tests.

#### **Prompt** (`prompt.py`) - Template Library
Reusable prompt templates with categories, tags, usage tracking.

---

### 2. Services (`app/services/`)

#### **TaskExecutor** (`task_executor.py`) - Core Orchestrator

**Purpose**: Manages complete task execution lifecycle

**Key Methods**:
```python
async def execute_task(task_id: str)
    # Main entry point - runs entire task lifecycle

async def _execute_with_claude(...)
    # Conversation loop with Claude CLI
    # Checks user input queue FIRST before auto-response
    # Enforces iteration/token limits
    # Real-time streaming with event callbacks

def _get_project_context(task)
    # Builds initial message for Claude
    # CRITICAL: Never exposes absolute paths!
    # Only mentions worktree isolation, not paths
```

**Critical Flow**:
1. Check pending user input (HIGH PRIORITY)
2. Build comprehensive initial message
3. Start conversation loop (max iterations)
4. Stream events → save to DB immediately
5. Check ending criteria after each response
6. Generate auto-response OR use user input
7. Repeat until complete/exhausted
8. Generate and run tests
9. Update final status

**Key Pattern**: User input ALWAYS has priority over auto-generated responses

---

#### **StreamingCLIClient** (`streaming_cli_client.py`) - Claude CLI Wrapper

**Purpose**: Real-time integration with Claude CLI using NDJSON streaming

**Command Format**:
```bash
# First message
claude -p "message" --output-format stream-json --verbose

# Resume conversation (critical for context!)
claude -r {session_id} -p "next message" --output-format stream-json
```

**Key Features**:
- Streams events line-by-line (NDJSON format)
- Extracts `session_id` from first `system.init` event
- Event callbacks for real-time DB persistence
- 256KB buffer limit handling
- Graceful error recovery for chunk limits

**Return Tuple**: `(full_output, pid, session_id, usage_data)`

**Critical**: Always use `-r {session_id}` for conversation continuity!

---

#### **IntelligentResponder** (`intelligent_responder.py`) - Auto-Response Generator

**Purpose**: Context-aware response generation (replaces generic prompts)

**Analysis Capabilities**:
- Question type detection (yes/no, multiple choice, open-ended)
- Completion indicator detection
- Error pattern recognition
- Choice extraction from numbered/lettered lists

**Response Strategies**:
1. **Multiple Choice**: Intelligent selection (40% first, 40% middle, 20% last)
2. **Yes/No**: Biased towards "yes" for implementation questions
3. **Open Questions**: Best practices guidance
4. **Errors**: Alternative approach suggestions
5. **Completion**: Verification requests

**Pattern-Based**: Uses regex, no external LLM calls (for speed)

---

#### **UserInputManager** (`user_input_manager.py`) - Priority Queue System

**Purpose**: High-priority queue for human intervention

**Queue Entry Format**:
```json
{
  "id": "uuid",
  "input": "user message",
  "timestamp": "ISO-8601",
  "processed": false
}
```

**Critical Methods**:
```python
add_user_input(db, task_id, user_input)
    # Thread-safe queue addition
    # Sets user_input_pending = True
    # Uses flag_modified() for SQLAlchemy JSON tracking

get_next_user_input(db, task_id)
    # FIFO retrieval with marking as processed

has_pending_input(db, task_id)
    # Quick boolean check

trigger_immediate_processing(task_id, user_input)
    # Background thread for immediate response
```

**Integration**: Checked at task startup and every iteration loop

**SQLAlchemy Gotcha**: Must use `flag_modified(task, 'user_input_queue')` after modifying JSON fields!

---

#### **GitWorktreeManager** (`git_worktree.py`) - Isolation Manager

**Purpose**: Parallel task execution using git worktrees

**Isolation Structure**:
```
/project/.claude_worktrees/
├── task-feature-login/    # Isolated branch + workspace
├── task-add-api/          # Isolated branch + workspace
└── fix-bug-123/           # Isolated branch + workspace
```

**Key Operations**:
```python
create_worktree(task_name, branch_name, base_branch)
    # Creates isolated workspace
    # git worktree add -b {branch} {path} {base}

create_multi_project_worktrees(projects_config)
    # Multi-repo support
    # Only write-access projects get worktrees

cleanup_task_worktree_and_branch(task_name)
    # Auto-commits changes before removal
    # git worktree remove + branch deletion
```

**Critical Safety**: Always commits changes before cleanup to preserve work

**Multi-Project**: Write-access projects get worktrees, read-only projects referenced directly

---

#### **CriteriaAnalyzer** (`criteria_analyzer.py`) - Completion Checker

**Purpose**: LLM-based task completion detection

**Two-Phase Approach**:
1. **Extraction**: Parse task description → extract success criteria
2. **Validation**: Check if criteria met (requires 70%+ confidence)

**Uses**: Claude CLI itself for meta-analysis (clever recursion)

**Fallback**: Heuristic pattern matching for completion indicators

---

#### **TestRunner** (`test_runner.py`) - Test Executor

**Purpose**: Execute pytest tests for validation

**Methods**:
- `run_test(code)`: Single test in temp file
- `run_regression_tests(path)`: Full test suite
- `validate_test_code(code)`: Syntax checking

---

### 3. API (`app/api/endpoints.py`)

Comprehensive REST API (~1955 lines) with task name-based routing:

**Task Lifecycle**:
```
POST   /api/v1/tasks                          # Create (auto_start optional)
GET    /api/v1/tasks                          # List all
GET    /api/v1/tasks/by-name/{task_name}      # Get details
GET    /api/v1/tasks/by-name/{task_name}/status  # Quick status
POST   /api/v1/tasks/by-name/{task_name}/start   # Start PENDING task
POST   /api/v1/tasks/by-name/{task_name}/stop    # Stop running
POST   /api/v1/tasks/by-name/{task_name}/resume  # Resume stopped
```

**Advanced Operations**:
```
POST   /api/v1/tasks/by-name/{task_name}/clear-and-restart  # Reset & restart
POST   /api/v1/tasks/by-name/{task_name}/retry              # Retry exhausted
POST   /api/v1/tasks/by-name/{task_name}/clone              # Clone task
DELETE /api/v1/tasks/by-name/{task_name}                    # Delete
```

**User Interaction**:
```
POST   /api/v1/tasks/by-name/{task_name}/user-input         # Queue message
GET    /api/v1/tasks/by-name/{task_name}/user-input/status  # Check queue
```

**Monitoring**:
```
GET    /api/v1/tasks/by-name/{task_name}/stream             # SSE conversation stream
GET    /api/v1/tasks/by-name/{task_name}/interactions       # Full history
```

**Design Pattern**: Task name as primary identifier (better UX than UUIDs)

---

## Key Features & Patterns

### 1. Git Worktree Isolation

**Problem**: Multiple tasks on same project = file conflicts

**Solution**: Isolated worktrees per task
```
Task 1: /project/.claude_worktrees/feat-login/  (branch: feat-login)
Task 2: /project/.claude_worktrees/add-api/     (branch: add-api)
```

**Multi-Project Support**:
```json
{
  "projects": [
    {"path": "/main", "access": "write", "branch_name": "feat-x"},
    {"path": "/sdk", "access": "read"}
  ]
}
```
- Write-access: Isolated worktrees created
- Read-only: Direct path reference

**Enforcement**: API rejects non-worktree tasks when parallel tasks exist

---

### 2. Session Continuity

**Critical Pattern**: Persist `claude_session_id` for conversation context

```python
# First message - creates session
output, pid, session_id, usage = await client.send_message(...)
task.claude_session_id = session_id  # SAVE THIS!

# Subsequent messages - resume with -r flag
output, pid, _, usage = await client.send_message_streaming(
    message=next_msg,
    session_id=task.claude_session_id  # Resume conversation
)
```

**Benefits**:
- Context preservation
- Token savings (prompt caching)
- Natural conversation flow

**Session ID Extraction**: From first `system.init` event in NDJSON stream

---

### 3. User Input Priority System

**Critical Rule**: User input ALWAYS has priority over auto-generated responses

**Check Points**:
```python
# 1. Task startup
user_input = get_next_user_input(db, task.id)
if user_input:
    initial_message = user_input
else:
    initial_message = build_initial_message(task)

# 2. Every iteration
if has_pending_input(db, task.id):
    next_message = get_next_user_input(db, task.id)
else:
    next_message = intelligent_responder.generate_response(...)
```

**Why**: Ensures user intent isn't lost to automation

---

### 4. Real-Time Event Streaming

**Pattern**: NDJSON streaming with immediate callbacks

```python
def handle_event(event):
    if event['type'] == 'assistant':
        save_interaction_immediately(event)

await streaming_client.send_message_streaming(
    message=msg,
    event_callback=handle_event  # Called for each line
)
```

**Benefits**:
- Real-time UI updates
- No buffering delays
- Database consistency
- Progress visibility

---

### 5. Ending Criteria (Three-Level Detection)

**Level 1 - LLM-Based** (Primary):
```python
criteria_analyzer.check_ending_criteria(task, claude_response)
# Returns: (is_complete, confidence, reasoning)
# Requires: confidence > 0.7
```

**Level 2 - Heuristic** (Fallback):
```python
# Pattern matching for "implementation is complete", "task is complete", etc.
```

**Level 3 - Resource Limits** (Hard Stop):
```python
if iteration_count >= max_iterations:
    task.status = TaskStatus.EXHAUSTED
if total_tokens >= max_output_tokens:
    task.status = TaskStatus.EXHAUSTED
```

**Retry Capability**: Add more iterations/tokens after exhaustion

---

### 6. Project Context Isolation

**CRITICAL RULE**: Never expose absolute paths to Claude!

```python
# ❌ WRONG - Breaks isolation
context = f"Project path: {worktree_path}"

# ✅ CORRECT - Generic description
context = "Working Directory: Current directory (isolated branch)"
```

**Why**: Prevents Claude from using absolute paths, which would:
- Break worktree isolation
- Cause cross-branch contamination
- Confuse file operations

**Implementation**: See `TaskExecutor._get_project_context()`

---

## Development Workflows

### Creating a New Task Feature

1. **Update Task Model** (`app/models/task.py`):
   - Add new field
   - Update `__init__` if needed
   - Consider migration script in `migrations/`

2. **Update Pydantic Schema** (`app/schemas.py`):
   - Add field to `TaskCreate`, `TaskUpdate`, or `TaskResponse`

3. **Update API Endpoint** (`app/api/endpoints.py`):
   - Add/modify route
   - Validate input
   - Return appropriate response

4. **Update Service Logic** (`app/services/`):
   - Implement business logic
   - Handle database operations
   - Add error handling

5. **Update Web UI** (`static/index.html`):
   - Add form fields
   - Update API calls
   - Handle new data in display

6. **Write Tests** (`tests/`):
   - Unit tests for logic
   - Integration tests for workflows

---

### Modifying Task Execution Flow

**Key File**: `app/services/task_executor.py`

**Common Modifications**:
- **Add Pre-Execution Check**: Add to `execute_task()` before `_execute_with_claude()`
- **Modify Conversation Loop**: Edit `_execute_with_claude()` iteration logic
- **Change Initial Message**: Edit `_get_project_context()`
- **Add Post-Response Processing**: Add after `send_message_streaming()` call
- **Modify Completion Detection**: Edit ending criteria check logic

**Testing**: Use `tests/integration/test_task_step_by_step.py` for validation

---

### Adding a New Service

1. **Create File**: `app/services/new_service.py`

2. **Define Class**:
   ```python
   class NewService:
       def __init__(self, db: Session):
           self.db = db

       async def do_something(self, task_id: str):
           # Implementation
           pass
   ```

3. **Import in Executor**: `from app.services.new_service import NewService`

4. **Integrate**: Call from `TaskExecutor` or API endpoints

5. **Test**: Create `tests/unit/test_new_service.py`

---

### Database Schema Changes

1. **Modify Model**: Update `app/models/*.py`

2. **Create Migration Script**: `migrations/add_new_field.py`
   ```python
   from sqlalchemy import text

   def upgrade(engine):
       with engine.connect() as conn:
           conn.execute(text("ALTER TABLE tasks ADD COLUMN new_field VARCHAR(200)"))
           conn.commit()
   ```

3. **Update Schema**: Modify `app/schemas.py`

4. **Run Migration**: Call migration in `main.py` or manually

5. **Test**: Verify with existing data

---

## Important Conventions

### Naming Conventions

**Files**: `snake_case` (e.g., `task_executor.py`)
**Classes**: `PascalCase` (e.g., `TaskExecutor`)
**Functions**: `snake_case` (e.g., `execute_task`)
**Constants**: `UPPER_CASE` (e.g., `MAX_ITERATIONS`)
**Private Methods**: `_leading_underscore` (e.g., `_get_project_context`)

**Database**:
- Tables: `snake_case` plural (e.g., `tasks`, `claude_interactions`)
- Columns: `snake_case` (e.g., `task_name`, `created_at`)

**API**:
- Routes: kebab-case (e.g., `/clear-and-restart`)
- Query params: snake_case (e.g., `?auto_start=true`)

---

### Error Handling Patterns

**Database Operations**:
```python
try:
    db.add(obj)
    db.commit()
    db.refresh(obj)
except Exception as e:
    db.rollback()
    raise HTTPException(status_code=500, detail=str(e))
```

**Subprocess Operations**:
```python
try:
    result = subprocess.run(..., timeout=30)
    if result.returncode != 0:
        return False, result.stderr
except subprocess.TimeoutExpired:
    return False, "Command timed out"
```

**Graceful Degradation**:
```python
# Chunk size errors are recoverable
if "chunk is longer than limit" in error_msg:
    logger.warning("Chunk limit - continuing")
    continue  # Don't break
```

---

### Logging Strategy

**Levels**:
- `logger.info()`: Normal flow, user actions
- `logger.warning()`: Degraded state, fallbacks
- `logger.error()`: Failures, exceptions

**Debug Markers** (used in development):
```python
print(f"🔍 DEBUG: variable={value}")
print(f"✅ SUCCESS: Operation complete")
print(f"❌ ERROR: {error_message}")
```

---

### SQLAlchemy JSON Fields

**Critical Pattern**: Use `flag_modified()` for JSON field updates

```python
# ❌ WRONG - Changes not detected
task.user_input_queue.append(new_entry)
db.commit()

# ✅ CORRECT - Explicitly mark as modified
task.user_input_queue.append(new_entry)
flag_modified(task, 'user_input_queue')
db.commit()
```

**Affected Fields**: `user_input_queue`, `projects`, `end_criteria_config`

---

### Background Task Execution

**Pattern**: Use FastAPI's `BackgroundTasks`

```python
from fastapi import BackgroundTasks

@app.post("/tasks/by-name/{task_name}/start")
async def start_task(
    task_name: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    task = get_task_by_name(db, task_name)
    background_tasks.add_task(executor.execute_task, task.id)
    return {"message": "Task started"}
```

**Benefits**:
- Non-blocking API responses
- Process-based isolation
- No external dependencies (vs Celery)

**Limitation**: Single-server deployment only

---

## Testing Approach

### Test Organization

```
tests/
├── unit/                    # Isolated component tests
│   ├── test_models.py      # Database models
│   ├── test_simulated_human.py  # Response generation
│   ├── test_ending_criteria.py  # Criteria detection
│   └── ...
└── integration/             # End-to-end workflows
    ├── test_api.py         # HTTP endpoints
    ├── test_worktree_isolation.py  # Git workflows
    ├── test_multi_project_system.py  # Multi-repo
    └── ...
```

### Running Tests

```bash
# All tests
pytest tests/ -v

# Specific category
pytest tests/unit/ -v
pytest tests/integration/ -v

# Specific file
pytest tests/unit/test_models.py -v

# Specific test
pytest tests/unit/test_models.py::test_task_creation -v
```

### Writing Tests

**Unit Test Pattern**:
```python
def test_function_behavior(test_db):
    # Arrange
    task = create_test_task(test_db)

    # Act
    result = function_under_test(task)

    # Assert
    assert result.status == expected_status
```

**Integration Test Pattern**:
```python
def test_full_workflow(test_client, test_db):
    # Create task via API
    response = test_client.post("/api/v1/tasks", json={...})

    # Verify behavior
    assert response.status_code == 200

    # Check database state
    task = test_db.query(Task).first()
    assert task.status == TaskStatus.PENDING
```

---

## Common Tasks

### Add a New Task Status

1. **Update Enum** (`app/models/task.py`):
   ```python
   class TaskStatus(str, Enum):
       PENDING = "pending"
       NEW_STATUS = "new_status"  # Add here
   ```

2. **Update Status Logic** (`app/services/task_executor.py`):
   ```python
   if condition:
       task.status = TaskStatus.NEW_STATUS
   ```

3. **Update Web UI** (`static/index.html`):
   ```javascript
   function getStatusBadge(status) {
       const badges = {
           'new_status': '🆕 New Status',
           // ...
       };
   }
   ```

4. **Update Tests**: Add test cases for new status

---

### Modify Auto-Response Behavior

**File**: `app/services/intelligent_responder.py`

```python
def generate_response(self, claude_response, task_context):
    # Add new detection pattern
    if self._is_new_pattern(claude_response):
        return self._handle_new_pattern(claude_response)

    # Existing logic...
```

**Test**: `tests/unit/test_simulated_human.py`

---

### Add New Ending Criteria Type

**File**: `app/services/criteria_analyzer.py`

```python
async def check_ending_criteria(self, task, claude_response):
    # Add new criteria type
    if self._check_custom_criteria(task, claude_response):
        return True, 0.9, "Custom criteria met"

    # Existing logic...
```

---

### Change Git Worktree Behavior

**File**: `app/services/git_worktree.py`

**Common Modifications**:
- **Change Worktree Location**: Modify `.claude_worktrees/` path
- **Add Pre-Creation Validation**: Add to `create_worktree()`
- **Modify Cleanup Logic**: Edit `cleanup_task_worktree_and_branch()`
- **Change Commit Message**: Edit `_commit_worktree_changes()`

---

## Things to Watch Out For

### 1. Session ID Loss

**Problem**: Not saving `claude_session_id` breaks conversation continuity

**Solution**: Always persist after first message:
```python
task.claude_session_id = session_id
db.commit()
```

---

### 2. Absolute Path Exposure

**Problem**: Exposing worktree paths to Claude breaks isolation

**Solution**: Use generic descriptions, never absolute paths

---

### 3. User Input Queue Race Conditions

**Problem**: Concurrent modifications to JSON queue

**Solution**: Always use `flag_modified()` after queue changes

---

### 4. Worktree Cleanup Without Commit

**Problem**: Losing uncommitted changes during cleanup

**Solution**: Always call `_commit_worktree_changes()` first

---

### 5. Missing Database Rollback

**Problem**: Failed transactions leave database in inconsistent state

**Solution**: Always wrap in try/except with `db.rollback()`

---

### 6. Chunk Size Limit Errors

**Problem**: Claude CLI output exceeds 256KB buffer

**Solution**: Don't break execution loop, log warning and continue

---

### 7. Background Task Exception Handling

**Problem**: Exceptions in background tasks don't surface to API

**Solution**: Comprehensive try/except with status updates:
```python
try:
    await execute_task(task_id)
except Exception as e:
    task.status = TaskStatus.FAILED
    task.error_message = str(e)
    db.commit()
```

---

## Configuration

### Environment Variables

Create `.env` from `.env.example`:

```bash
# Claude CLI
CLAUDE_CLI_COMMAND=claude           # Override if not in PATH

# Database
DATABASE_URL=sqlite:///./tasks.db   # SQLite (dev)
DATABASE_URL=mysql+pymysql://user:pass@host/db  # MySQL (prod)

# Server
HOST=0.0.0.0                        # Listen on all interfaces
PORT=8000                           # Server port

# Defaults
DEFAULT_PROJECT_PATH=/tmp/claude_projects
```

### Database Support

**SQLite** (Development):
```python
DATABASE_URL=sqlite:///./tasks.db
# Uses: check_same_thread=False
```

**MySQL** (Production):
```python
DATABASE_URL=mysql+pymysql://user:pass@host:3306/dbname
# Uses: Connection pooling, pre-ping validation
```

See `docs/MYSQL_SETUP.md` for MySQL configuration details.

---

## Quick Reference

### Starting the Server

```bash
# Development
python -m app.main

# With uvicorn
uvicorn app.main:app --reload

# Production
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Running Tests

```bash
pytest tests/ -v                    # All tests
pytest tests/unit/ -v               # Unit only
pytest tests/integration/ -v        # Integration only
pytest -k "test_name" -v            # Specific test
```

### Database Reset

```bash
rm tasks.db                         # Delete SQLite DB
python -m app.main                  # Recreates on startup
```

### Common API Calls

```bash
# Create task
curl -X POST http://localhost:8000/api/v1/tasks \
  -H "Content-Type: application/json" \
  -d '{"task_name": "test", "description": "Test task", "root_folder": "/path"}'

# Start task
curl -X POST http://localhost:8000/api/v1/tasks/by-name/test/start

# Check status
curl http://localhost:8000/api/v1/tasks/by-name/test/status

# Add user input
curl -X POST http://localhost:8000/api/v1/tasks/by-name/test/user-input \
  -H "Content-Type: application/json" \
  -d '{"input": "Your message"}'
```

---

## Documentation Index

Comprehensive docs in `docs/` folder:

- **HUMAN_IN_THE_LOOP.md** - User intervention system
- **WEB_UI_GUIDE.md** - Web interface guide
- **TASK_LIFECYCLE.md** - Task state management
- **GIT_WORKTREE_GUIDE.md** - Parallel task execution
- **INTELLIGENT_AUTO_ANSWER.md** - Auto-response algorithm
- **TASK_STATUS_API.md** - Real-time monitoring
- **API_USAGE_GUIDE.md** - Complete API reference
- **ARCHITECTURE.md** - System design
- **CLI_INTEGRATION.md** - Claude CLI integration
- **MYSQL_SETUP.md** - MySQL configuration
- **QUICKSTART.md** - 5-minute setup

---

## Best Practices for AI Assistants

### When Modifying This Codebase

1. **Always check user input priority**: Never skip user input queue checks
2. **Preserve session continuity**: Always save and use `claude_session_id`
3. **Never expose absolute paths**: Use generic descriptions for Claude
4. **Use flag_modified() for JSON fields**: SQLAlchemy won't detect changes otherwise
5. **Commit before worktree cleanup**: Preserve work before deletion
6. **Handle exceptions in background tasks**: Update task status on errors
7. **Test worktree isolation**: Verify parallel tasks don't interfere
8. **Validate multi-project configs**: Ensure all paths exist and are git repos
9. **Log important state changes**: Use appropriate log levels
10. **Write tests for new features**: Both unit and integration

### When Debugging Issues

1. **Check task status and error_message**: First place to look
2. **Review ClaudeInteraction records**: Full conversation history
3. **Verify session_id persistence**: Break in continuity = context loss
4. **Check user_input_queue**: Ensure messages processed in order
5. **Validate worktree_path**: Ensure isolation is working
6. **Review process_pid**: Check if Claude CLI is still running
7. **Examine usage_data**: Token limits may be hit
8. **Check git worktree list**: Verify worktrees created/cleaned correctly

---

## Contact & Contributing

- **Issues**: Check logs, review task status, examine interactions
- **Testing**: All tests must pass before changes
- **Documentation**: Update relevant docs in `docs/` folder
- **Code Style**: Follow existing conventions (PEP 8, type hints)

---

**Last Updated**: 2025-11-13
**Codebase Version**: Current state as of latest commit
**AI Assistant Note**: This guide is comprehensive. Refer to specific docs in `docs/` folder for deeper dives into individual features.
