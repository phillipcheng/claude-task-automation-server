# Claude Task Automation Server - Architecture

A Python-based HTTP system that automates software development tasks using Claude AI with human-in-the-loop capabilities, real-time monitoring, and git worktree isolation.

## Project Structure

```
claude-task-automation-server/
├── app/                          # Backend (FastAPI + SQLAlchemy)
│   ├── main.py                   # FastAPI application entry point
│   ├── database.py               # SQLAlchemy ORM configuration
│   ├── schemas.py                # Pydantic validation schemas
│   ├── api/
│   │   └── endpoints.py          # REST API endpoints
│   ├── models/                   # SQLAlchemy data models
│   │   ├── session.py            # Project session model
│   │   ├── task.py               # Main task model with lifecycle
│   │   ├── test_case.py          # Test case tracking
│   │   ├── interaction.py        # Claude interaction logging
│   │   ├── prompt.py             # Prompt templates
│   │   └── project.py            # Project configuration
│   └── services/                 # Business logic
│       ├── task_executor.py      # Task orchestration
│       ├── streaming_cli_client.py # Claude CLI wrapper
│       ├── intelligent_responder.py # Auto-response logic
│       ├── user_input_manager.py  # User input queue
│       ├── git_worktree.py       # Git worktree management
│       ├── criteria_analyzer.py  # End criteria evaluation
│       ├── test_runner.py        # Test execution
│       └── claude_client.py      # Claude API interface
├── web/                          # Frontend (React + TypeScript)
│   ├── src/
│   │   ├── main.tsx              # React entry point
│   │   ├── App.tsx               # Root component with tabs
│   │   ├── components/
│   │   │   ├── Tasks/            # Task management
│   │   │   ├── Chat/             # Chat interface
│   │   │   └── Projects/         # Project management
│   │   ├── services/api.ts       # Axios API client
│   │   └── types/                # TypeScript definitions
│   └── vite.config.ts            # Vite build configuration
├── docs/                         # Documentation
├── tests/                        # Test suite
├── static/                       # Built frontend assets
└── requirements.txt              # Python dependencies
```

## Technology Stack

### Backend
- **FastAPI** - REST API framework
- **SQLAlchemy** - ORM (supports SQLite/MySQL)
- **Pydantic** - Request/response validation
- **Uvicorn** - ASGI server

### Frontend
- **React 18** - UI framework
- **TypeScript** - Type safety
- **Vite** - Build tool
- **Axios** - HTTP client

## Core Components

### 1. Task Executor (`app/services/task_executor.py`)

The central orchestration engine that manages task lifecycle:

```
PENDING → RUNNING → TESTING → COMPLETED/FAILED
                ↓
            STOPPED (resumable)
```

Key responsibilities:
- Conversation loop with Claude CLI
- Token usage tracking
- End criteria evaluation
- Test generation and execution
- Multi-project worktree management

### 2. Streaming CLI Client (`app/services/streaming_cli_client.py`)

Wraps Claude CLI with real-time streaming:
- Executes commands with `--output-format stream-json`
- Parses NDJSON output in real-time
- Supports session resumption (`-r` flag)
- Handles image attachments

### 3. Intelligent Responder (`app/services/intelligent_responder.py`)

AI-driven auto-response system:
- Analyzes Claude output for questions/completions/errors
- Generates context-aware responses
- Detects and answers multiple choice questions
- Can escalate to user when uncertain

### 4. User Input Manager (`app/services/user_input_manager.py`)

Queue-based input system:
- High-priority input queue
- Supports image attachments
- Prevents race conditions
- Immediate processing during execution

### 5. Git Worktree Manager (`app/services/git_worktree.py`)

Enables parallel task execution:
- Creates isolated worktrees per task
- Branch isolation prevents conflicts
- Automatic cleanup on completion

## Database Models

| Model | Purpose |
|-------|---------|
| **Task** | Core execution unit with status, git context, token tracking |
| **ClaudeInteraction** | Conversation history with token/cost metrics |
| **Session** | Project session container |
| **Project** | Project configuration and access control |
| **TestCase** | Generated and regression test tracking |
| **Prompt** | Prompt template library |

### Task Status Flow

```
PENDING     → Created, waiting to start
RUNNING     → Claude actively working
PAUSED      → During auto-response generation
STOPPED     → User manually stopped (resumable)
TESTING     → Running test suite
COMPLETED   → All tests passed (final)
FAILED      → Tests failed or error (final)
FINISHED    → Met end criteria (final)
EXHAUSTED   → Hit max iterations/tokens (final)
```

## API Endpoints

### Task Management
```
POST   /api/v1/tasks                     # Create task
GET    /api/v1/tasks                     # List tasks
GET    /api/v1/tasks/by-name/{name}      # Get by name
GET    /api/v1/tasks/{id}/status         # Status summary
GET    /api/v1/tasks/{id}/conversation   # Conversation history
POST   /api/v1/tasks/by-name/{name}/start   # Start execution
POST   /api/v1/tasks/by-name/{name}/stop    # Stop execution
POST   /api/v1/tasks/by-name/{name}/resume  # Resume execution
POST   /api/v1/tasks/by-name/{name}/set-input  # Send user input
GET    /api/v1/tasks/by-name/{name}/stream  # SSE stream
DELETE /api/v1/tasks/by-name/{name}      # Delete task
```

### Project Management
```
POST   /api/v1/projects          # Create project
GET    /api/v1/projects          # List projects
GET    /api/v1/projects/{id}     # Get project
PUT    /api/v1/projects/{id}     # Update project
DELETE /api/v1/projects/{id}     # Delete project
```

## Communication Architecture

### REST API
Standard HTTP request/response for CRUD operations.

### Server-Sent Events (SSE)
Real-time task updates via `GET /api/v1/tasks/by-name/{name}/stream`:
- Chat messages from Claude
- Status updates
- Progress information
- Token usage metrics

### Background Task Execution
```
Request Handler
   ├─→ Create Task in database
   ├─→ Schedule: background_tasks.add_task(executor.execute_task)
   └─→ Return immediately (non-blocking)

Background:
   TaskExecutor.execute_task() runs independently
   └─→ Updates pushed via SSE
```

## Task Execution Flow

1. **Initialization**: Load task, set status to RUNNING
2. **Build Prompt**: Include project context, multi-project info
3. **Conversation Loop**:
   - Send message to Claude CLI (streaming)
   - Save interaction to database
   - Check user input queue
   - Generate auto-response or wait (chat mode)
   - Evaluate end criteria
4. **Test Phase**: Generate and run tests
5. **Finalize**: Set final status based on results

## Key Features

### Multi-Project Support
```json
{
  "projects": [
    {"path": "/project1", "access": "write", "branch_name": "feature"},
    {"path": "/project2", "access": "read", "context": "Shared SDK"}
  ]
}
```

### Human-in-the-Loop
- Send input at any time via `/set-input`
- High-priority queue interrupts auto-response
- Image attachment support

### Operation Modes
- **Automation Mode**: Auto-responds to Claude
- **Chat Mode**: Waits for user input after each response

### End Criteria
```json
{
  "end_criteria": "All tests pass",
  "max_iterations": 20,
  "max_tokens": 100000
}
```

## Frontend Architecture

### Component Structure
- **Tasks**: Task list, creation, detail view, integrated chat
- **Chat**: Dedicated chat-mode interface
- **Projects**: Project management

### API Service (`web/src/services/api.ts`)
Axios-based client with methods for all backend endpoints plus SSE subscription.

### Build Configuration
- Dev server: port 3000 with API proxy to :8000
- Production: Compiled to `/static/` directory

## Configuration

### Environment Variables
```
CLAUDE_CLI_COMMAND=claude
DATABASE_URL=sqlite:///./tasks.db
HOST=0.0.0.0
PORT=8000
```

### Running the Server
```bash
# Development
uvicorn app.main:app --reload --port 8000

# Production
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Frontend Development
```bash
cd web
npm install
npm run dev      # Dev server on :3000
npm run build    # Production build to /static/
```

## Claude CLI Integration

```bash
# New conversation
claude "message" --output-format stream-json -p

# Resume session
claude "message" -r {session_id}

# With images
claude "message" --image /path/to/image.png
```

## Production Considerations

### Current Limitations
- SQLite is single-threaded
- In-process background tasks
- Single server deployment

### Recommended Upgrades
- **Database**: PostgreSQL/MySQL for concurrent writes
- **Task Queue**: Celery with Redis for distributed workers
- **Caching**: Redis for session state
- **Monitoring**: Prometheus metrics, health endpoint at `/health`
