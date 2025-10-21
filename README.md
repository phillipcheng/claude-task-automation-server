# Claude Task Automation Server

A Python-based HTTP request/response system that automates task completion using Claude AI. This system creates sessions, manages tasks, generates test cases, and validates implementations through both generated and regression tests.

## Features

- **Session Management**: Create sessions for different projects
- **Task Execution**: Asynchronous task execution using Claude Code CLI
- **Simulated Human Interaction**: Automated encouragement and continuation prompts
- **Test Generation**: Automatic test case generation for each task
- **Regression Testing**: Support for regression test suites
- **Status Tracking**: Real-time task status and progress monitoring
- **CLI-Based**: Uses your local Claude Code CLI (no API key needed!)

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

The server will start on `http://localhost:8000`. API documentation is available at `http://localhost:8000/docs`.

### API Endpoints

#### Create a Session

```bash
curl -X POST http://localhost:8000/api/v1/sessions \
  -H "Content-Type: application/json" \
  -d '{"project_path": "/path/to/your/project"}'
```

Response:
```json
{
  "id": "session-uuid",
  "project_path": "/path/to/your/project",
  "created_at": "2024-01-01T00:00:00",
  "updated_at": "2024-01-01T00:00:00"
}
```

#### Create a Task

```bash
curl -X POST http://localhost:8000/api/v1/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "session-uuid",
    "description": "Create a Python function to calculate fibonacci numbers"
  }'
```

Response:
```json
{
  "id": "task-uuid",
  "session_id": "session-uuid",
  "description": "Create a Python function to calculate fibonacci numbers",
  "status": "pending",
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

1. **PENDING**: Task created and queued
2. **RUNNING**: Claude is actively working on the task
3. **PAUSED**: Task paused, simulated human provides encouragement
4. **TESTING**: Implementation complete, running tests
5. **COMPLETED**: All tests passed successfully
6. **FAILED**: Tests failed or execution error

## How It Works

### Task Execution Flow

1. **Session Creation**: Create a session for your project
2. **Task Submission**: Submit a task description
3. **Async Execution**: Task runs in background with Claude
4. **Simulated Feedback**: System provides encouragement during pauses
5. **Test Generation**: Claude generates test cases for the implementation
6. **Test Validation**: Both generated and regression tests are run
7. **Completion**: Task marked complete when all tests pass

### Simulated Human Interaction

The system simulates human interaction by:
- Providing continuation prompts every 3-5 interactions
- Offering encouragement messages
- Handling errors with appropriate guidance
- Granting most permissions (except malicious operations)

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

## Future Enhancements

- [ ] Add authentication and authorization
- [ ] Support multiple Claude models
- [ ] Add WebSocket support for real-time updates
- [ ] Implement task cancellation
- [ ] Add code review integration
- [ ] Support for multiple programming languages
- [ ] Enhanced error recovery mechanisms

## License

MIT License

## Contributing

Contributions are welcome! Please ensure all tests pass before submitting pull requests.
