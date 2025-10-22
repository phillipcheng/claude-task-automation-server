# Claude Task Automation Server

A Python-based HTTP request/response system that automates task completion using Claude AI. This system manages tasks with full lifecycle control, intelligent auto-responses, git worktree isolation, and automated testing.

## Features

- **Human-in-the-Loop**: View conversations, monitor Claude's work, and provide custom input when needed
- **Web UI**: Modern web interface for visual task management and monitoring
- **Task Lifecycle Management**: Create, start, stop, and resume tasks with full control
- **Git Worktree Isolation**: Parallel task execution on same project using isolated branches
- **Intelligent Auto-Responses**: Context-aware replies to Claude's questions
- **Task Execution**: Asynchronous task execution using Claude Code CLI
- **Real-time Monitoring**: Track Claude's responses and task progress
- **Test Generation**: Automatic test case generation and validation
- **CLI-Based**: Uses your local Claude Code CLI (no API key needed!)
- **Simple API**: Task name-based endpoints (no manual session management)

## Architecture

### Core Components

1. **HTTP API Server** - FastAPI-based REST server
2. **Database** - SQLite with SQLAlchemy ORM
3. **Claude CLI Client** - Integration with Claude Code command-line tool
4. **Task Executor** - Async task runner with simulated human feedback
5. **Test Manager** - Generates and runs test cases

### Database Models

- **Session**: Represents a project session
- **Task**: Represents a task to be completed
- **TestCase**: Stores generated and regression test cases
- **ClaudeInteraction**: Logs all interactions with Claude

## Prerequisites

- Python 3.8 or higher
- **Claude Code CLI** installed and accessible in your PATH
  - Make sure you have an active Claude subscription
  - Test that you can run `claude --version` in your terminal

## Installation

1. Clone the repository or navigate to the project directory:

```bash
cd /Users/bytedance/python/claudeserver
```

2. Create a virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. (Optional) Set up environment variables:

```bash
cp .env.example .env
# Edit .env if you need to customize settings
```

Optional environment variables:
- `CLAUDE_CLI_COMMAND`: Command to run Claude CLI (default: "claude")
- `DATABASE_URL`: Database connection string (default: sqlite:///./tasks.db)
- `HOST`: Server host (default: 0.0.0.0)
- `PORT`: Server port (default: 8000)

## Usage

### Starting the Server

```bash
python -m app.main
```

Or using uvicorn directly:

```bash
uvicorn app.main:app --reload
```

The server will start on `http://localhost:8000`.

**Web UI**: Open browser to `http://localhost:8000/` for visual task management
**API Docs**: Available at `http://localhost:8000/docs`

### Quick Start (Web UI)

Open your browser and navigate to `http://localhost:8000/` to access the web interface.

1. Fill in the task creation form
2. Click "Create Task" (optionally enable auto-start)
3. Monitor task progress in real-time
4. Use Start/Stop/Resume buttons as needed

See [WEB_UI_GUIDE.md](docs/WEB_UI_GUIDE.md) for complete web UI documentation.

### Quick Start (Command Line)

**1. Create a task (doesn't auto-start):**

```bash
curl -X POST http://localhost:8000/api/v1/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "task_name": "add-login-feature",
    "description": "Implement user login with OAuth",
    "root_folder": "/path/to/your/project",
    "auto_start": false
  }'
```

**2. Start the task when ready:**

```bash
curl -X POST http://localhost:8000/api/v1/tasks/by-name/add-login-feature/start
```

**3. Monitor progress:**

```bash
curl http://localhost:8000/api/v1/tasks/by-name/add-login-feature/status
```

**4. Stop/resume if needed:**

```bash
# Stop
curl -X POST http://localhost:8000/api/v1/tasks/by-name/add-login-feature/stop

# Resume
curl -X POST http://localhost:8000/api/v1/tasks/by-name/add-login-feature/resume
```

### API Endpoints

#### Task Management

**Create Task:**
```bash
POST /api/v1/tasks
{
  "task_name": "my-task",
  "description": "Task description",
  "root_folder": "/path/to/project",
  "auto_start": false  // default: false
}
```

**Start Task:**
```bash
POST /api/v1/tasks/by-name/{task_name}/start
```

**Stop Task:**
```bash
POST /api/v1/tasks/by-name/{task_name}/stop
```

**Resume Task:**
```bash
POST /api/v1/tasks/by-name/{task_name}/resume
```

**Get Task Status:**
```bash
GET /api/v1/tasks/by-name/{task_name}/status
```

Response:
```json
{
  "id": "task-uuid",
  "task_name": "add-login-feature",
  "status": "running",
  "progress": "Task is running - 5 interactions so far",
  "latest_claude_response": "I'm implementing the login form...",
  "waiting_for_input": false,
  "test_summary": {
    "total": 3,
    "passed": 2,
    "failed": 0,
    "pending": 1
  }
  "created_at": "2024-01-01T00:00:00",
  ...
}
```

#### Query Task Status

```bash
curl http://localhost:8000/api/v1/tasks/{task_id}/status
```

Response:
```json
{
  "id": "task-uuid",
  "status": "running",
  "summary": "Implementation in progress...",
  "progress": "Task is running - 5 interactions so far",
  "test_summary": {
    "total": 3,
    "passed": 2,
    "failed": 1,
    "pending": 0
  }
}
```

#### Get Full Task Details

```bash
curl http://localhost:8000/api/v1/tasks/{task_id}
```

This returns complete task information including all interactions and test cases.

#### Get Session Tasks

```bash
curl http://localhost:8000/api/v1/sessions/{session_id}/tasks
```

### Task Lifecycle

1. **PENDING**: Task created, waiting to be started
2. **RUNNING**: Claude is actively working on the task
3. **PAUSED**: Task paused (internal), auto-response being generated
4. **STOPPED**: Task manually stopped by user
5. **TESTING**: Implementation complete, running tests
6. **COMPLETED**: All tests passed successfully
7. **FAILED**: Tests failed or execution error

**Lifecycle Control:**
- `PENDING` → `START` → `RUNNING`
- `RUNNING` → `STOP` → `STOPPED`
- `STOPPED` → `RESUME` → `RUNNING`

## How It Works

### Task Execution Flow

1. **Session Creation**: Create a session for your project
2. **Task Submission**: Submit a task description
3. **Async Execution**: Task runs in background with Claude
4. **Simulated Feedback**: System provides encouragement during pauses
5. **Test Generation**: Claude generates test cases for the implementation
6. **Test Validation**: Both generated and regression tests are run
7. **Completion**: Task marked complete when all tests pass

### Intelligent Auto-Responses

The system provides intelligent auto-responses by:
- Analyzing Claude's responses for questions, choices, errors
- Generating context-aware replies instead of generic prompts
- Answering multiple choice questions intelligently
- Handling yes/no questions with appropriate defaults
- Suggesting alternatives when errors occur
- Confirming completion and requesting verification

### Test Case Management

- **Generated Tests**: Claude creates 2-5 test cases for each task
- **Regression Tests**: Existing tests in `tests/` directory are run
- **Validation**: Task only completes when ALL tests pass

## Testing

Run the regression test suite:

```bash
pytest tests/ -v
```

Run specific test files:

```bash
pytest tests/test_api.py -v
pytest tests/test_models.py -v
pytest tests/test_simulated_human.py -v
```

## Project Structure

```
claudeserver/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application
│   ├── database.py          # Database configuration
│   ├── schemas.py           # Pydantic schemas
│   ├── models/              # SQLAlchemy models
│   │   ├── __init__.py
│   │   ├── session.py
│   │   ├── task.py
│   │   ├── test_case.py
│   │   └── interaction.py
│   ├── api/                 # API endpoints
│   │   ├── __init__.py
│   │   └── endpoints.py
│   └── services/            # Business logic
│       ├── __init__.py
│       ├── claude_client.py
│       ├── simulated_human.py
│       ├── test_runner.py
│       └── task_executor.py
├── tests/                   # Regression tests
│   ├── __init__.py
│   ├── test_api.py
│   ├── test_models.py
│   └── test_simulated_human.py
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

## Configuration

### Environment Variables

- `ANTHROPIC_API_KEY`: Your Anthropic API key (required)
- `DATABASE_URL`: Database connection string
- `HOST`: Server host address
- `PORT`: Server port number

### Execution Parameters

These can be modified in `app/services/task_executor.py`:

- `max_iterations`: Maximum number of Claude interactions (default: 20)
- `max_pauses`: Maximum number of simulated human interventions (default: 5)

## Example Workflow

```bash
# 1. Start the server
python -m app.main

# 2. Create a session
SESSION_ID=$(curl -X POST http://localhost:8000/api/v1/sessions \
  -H "Content-Type: application/json" \
  -d '{"project_path": "/tmp/myproject"}' | jq -r '.id')

# 3. Create a task
TASK_ID=$(curl -X POST http://localhost:8000/api/v1/tasks \
  -H "Content-Type: application/json" \
  -d "{
    \"session_id\": \"$SESSION_ID\",
    \"description\": \"Create a function to validate email addresses\"
  }" | jq -r '.id')

# 4. Monitor task status
watch -n 2 "curl -s http://localhost:8000/api/v1/tasks/$TASK_ID/status | jq"

# 5. Get full task details when complete
curl http://localhost:8000/api/v1/tasks/$TASK_ID | jq
```

## Troubleshooting

### Common Issues

1. **Claude CLI Not Found**:
   - Ensure Claude Code is installed and in your PATH
   - Test with: `claude --version`
   - Set custom path in .env: `CLAUDE_CLI_COMMAND=/path/to/claude`

2. **Database Locked**: Close any other connections to the SQLite database

3. **Test Failures**: Check that pytest is installed and project path is correct

4. **Task Stuck in Running**:
   - Check server logs for Claude CLI errors
   - Ensure Claude CLI is working: Try running `claude "Hello"` in terminal
   - Check that your Claude subscription is active

### Logs

The application logs to stdout. Redirect to a file if needed:

```bash
python -m app.main > server.log 2>&1
```

## Security Notes

- The system uses your local Claude CLI with your existing subscription
- No API keys are stored or transmitted
- The system grants most permissions to Claude except malicious operations
- Consider adding authentication for production use
- Review generated code before deploying to production

## Documentation

Comprehensive documentation is available in the [`docs/`](docs/) folder:

- **[HUMAN_IN_THE_LOOP.md](docs/HUMAN_IN_THE_LOOP.md)** - Monitor and control Claude with custom input ⭐ NEW
- **[WEB_UI_GUIDE.md](docs/WEB_UI_GUIDE.md)** - Web interface user guide
- **[QUICKSTART.md](docs/QUICKSTART.md)** - 5-minute setup guide
- **[TASK_LIFECYCLE.md](docs/TASK_LIFECYCLE.md)** - Task lifecycle management (create/start/stop/resume)
- **[GIT_WORKTREE_GUIDE.md](docs/GIT_WORKTREE_GUIDE.md)** - Parallel task execution with git worktrees
- **[PARALLEL_TASKS_DESIGN.md](docs/PARALLEL_TASKS_DESIGN.md)** - Branch isolation for parallel tasks
- **[INTELLIGENT_AUTO_ANSWER.md](docs/INTELLIGENT_AUTO_ANSWER.md)** - Context-aware auto-response algorithm
- **[TASK_STATUS_API.md](docs/TASK_STATUS_API.md)** - Real-time task status and Claude responses
- **[API_USAGE_GUIDE.md](docs/API_USAGE_GUIDE.md)** - Complete API reference and usage
- **[ARCHITECTURE.md](docs/ARCHITECTURE.md)** - System architecture and design
- **[CLI_INTEGRATION.md](docs/CLI_INTEGRATION.md)** - Claude CLI integration details

## Examples

Ready-to-use example scripts:

```bash
# Simple create and monitor
python examples/simple_task_monitor.py "task-name" "description" /project

# Bash version
./examples/monitor_task.sh "task-name" "description" /project

# Manual lifecycle control
python examples/create_and_start.py "task-name" "description" /project
```

## License

MIT License

## Contributing

Contributions are welcome! Please ensure all tests pass before submitting pull requests.
