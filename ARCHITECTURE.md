# System Architecture

## Overview

The Claude Task Automation Server is an HTTP-based system that uses Claude AI to complete software development tasks autonomously. It manages sessions, executes tasks asynchronously, simulates human interaction, and validates implementations through automated testing.

## High-Level Architecture

```
┌─────────────┐
│   Client    │
│ (HTTP/REST) │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────────┐
│         FastAPI Server                  │
│  ┌────────────────────────────────┐    │
│  │      API Endpoints             │    │
│  │  - POST /sessions              │    │
│  │  - POST /tasks                 │    │
│  │  - GET  /tasks/{id}/status     │    │
│  └────────────┬───────────────────┘    │
└───────────────┼────────────────────────┘
                │
                ▼
┌───────────────────────────────────────────┐
│         Business Logic Layer              │
│  ┌──────────────┐  ┌──────────────┐      │
│  │ Task Executor│  │Claude Client │      │
│  └──────┬───────┘  └──────┬───────┘      │
│         │                 │               │
│  ┌──────▼───────┐  ┌─────▼────────┐      │
│  │Simulated     │  │Test Runner   │      │
│  │Human         │  │              │      │
│  └──────────────┘  └──────────────┘      │
└───────────────────┬───────────────────────┘
                    │
                    ▼
┌───────────────────────────────────────────┐
│         Data Persistence Layer            │
│  ┌──────────────────────────────────┐    │
│  │  SQLAlchemy ORM + SQLite         │    │
│  │  - Sessions                      │    │
│  │  - Tasks                         │    │
│  │  - TestCases                     │    │
│  │  - ClaudeInteractions            │    │
│  └──────────────────────────────────┘    │
└───────────────────────────────────────────┘
```

## Core Components

### 1. HTTP API Layer (`app/api/`)

**Purpose**: Handles HTTP requests and responses

**Files**:
- `endpoints.py`: Defines all REST API endpoints

**Key Endpoints**:
- `POST /api/v1/sessions` - Create new session
- `GET /api/v1/sessions/{id}` - Get session details
- `POST /api/v1/tasks` - Create and start task execution
- `GET /api/v1/tasks/{id}` - Get full task details
- `GET /api/v1/tasks/{id}/status` - Get task status summary
- `GET /api/v1/sessions/{id}/tasks` - List session tasks

**Responsibilities**:
- Request validation (via Pydantic schemas)
- Response serialization
- Background task scheduling
- Error handling

### 2. Database Layer (`app/database.py`, `app/models/`)

**Purpose**: Data persistence and ORM models

**Database**: SQLite with SQLAlchemy ORM

**Models**:

#### Session (`models/session.py`)
- Represents a project session
- Fields: id, project_path, created_at, updated_at
- Relationships: One-to-Many with Tasks

#### Task (`models/task.py`)
- Represents a task to be completed
- Fields: id, session_id, description, status, summary, error_message, timestamps
- States: PENDING, RUNNING, PAUSED, TESTING, COMPLETED, FAILED
- Relationships: Many-to-One with Session, One-to-Many with TestCases and Interactions

#### TestCase (`models/test_case.py`)
- Stores test cases (generated or regression)
- Fields: id, task_id, name, test_code, test_type, status, output
- Types: GENERATED, REGRESSION
- States: PENDING, PASSED, FAILED

#### ClaudeInteraction (`models/interaction.py`)
- Logs all interactions with Claude
- Fields: id, task_id, interaction_type, content, created_at
- Types: USER_REQUEST, CLAUDE_RESPONSE, SIMULATED_HUMAN

### 3. Business Logic Layer (`app/services/`)

#### TaskExecutor (`services/task_executor.py`)

**Purpose**: Orchestrates task execution

**Workflow**:
1. Initialize task as RUNNING
2. Get project context
3. Send initial request to Claude
4. Enter conversation loop:
   - Send message to Claude
   - Log response
   - Check if task complete
   - Determine if intervention needed
   - Add simulated human feedback if needed
   - Mark as PAUSED during intervention
5. Extract summary when complete
6. Generate test cases
7. Run tests (generated + regression)
8. Mark task as COMPLETED or FAILED

**Configuration**:
- `max_iterations`: 20 (prevents infinite loops)
- `max_pauses`: 5 (limits simulated interventions)

#### ClaudeClient (`services/claude_client.py`)

**Purpose**: Interface with Anthropic's Claude API

**Key Methods**:
- `send_message()`: Send messages to Claude
- `generate_code()`: Generate code for task
- `generate_test_cases()`: Create test cases

**Configuration**:
- Model: claude-3-5-sonnet-20241022
- Max tokens: 4096 (configurable)

#### SimulatedHuman (`services/simulated_human.py`)

**Purpose**: Simulate human interaction to keep Claude engaged

**Behavior**:
- Intervenes every 3-5 interactions
- Always intervenes on errors
- Provides different types of prompts:
  - General continuation: "Please continue."
  - Encouragement: "Great progress! Keep going."
  - Error handling: "Let's fix that issue."

**Logic**:
```python
should_intervene = (
    has_error OR
    (interaction_count > 0 AND interaction_count % random(3,5) == 0)
)
```

#### TestRunner (`services/test_runner.py`)

**Purpose**: Execute and validate test cases

**Capabilities**:
- Run individual test cases (pytest)
- Run regression test suites
- Validate test code syntax
- Capture test output and results
- Timeout handling (60s per test, 300s for regression)

### 4. Schema Layer (`app/schemas.py`)

**Purpose**: Request/Response validation using Pydantic

**Schemas**:
- `SessionCreate` / `SessionResponse`
- `TaskCreate` / `TaskResponse`
- `TaskStatusResponse`
- `TestCaseResponse`
- `InteractionResponse`

## Data Flow

### Task Creation Flow

```
Client Request
    │
    ▼
[POST /tasks] → Validate Request
    │
    ▼
Create Task in DB (status=PENDING)
    │
    ▼
Schedule Background Task
    │
    ▼
Return Task Response to Client
    │
    │ (async)
    ▼
Background: TaskExecutor.execute_task()
    │
    ▼
Update status to RUNNING
    │
    ▼
Conversation Loop with Claude
    │
    ├─→ Send message to Claude
    ├─→ Log interaction
    ├─→ Check completion
    └─→ Add simulated human if needed
    │
    ▼
Update status to TESTING
    │
    ▼
Generate Test Cases
    │
    ▼
Run Tests
    │
    ▼
Update status to COMPLETED/FAILED
```

### Status Query Flow

```
Client Request
    │
    ▼
[GET /tasks/{id}/status]
    │
    ▼
Query Task from DB
    │
    ▼
Calculate Test Summary
    │
    ▼
Generate Progress Message
    │
    ▼
Return Status Response
```

## Asynchronous Processing

### Background Tasks

Tasks execute asynchronously using FastAPI's `BackgroundTasks`:

```python
@router.post("/tasks")
async def create_task(
    task_data: TaskCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    # Create task in DB
    db_task = Task(...)
    db.commit()

    # Schedule async execution
    background_tasks.add_task(executor.execute_task, db_task.id)

    # Return immediately
    return db_task
```

### State Management

Task state is managed through the database:
- Each state transition is committed to DB
- Clients poll for status updates
- Future: Could add WebSocket support for real-time updates

## Conversation Management

### Claude Interaction Pattern

```python
conversation_history = [
    {"role": "user", "content": "Task description..."},
    {"role": "assistant", "content": "I'll implement..."},
    {"role": "user", "content": "Please continue."},
    {"role": "assistant", "content": "Continuing..."},
    # ... more interactions
]
```

### Intervention Strategy

1. **Error Detection**: Check if response contains error indicators
2. **Intervention Decision**: Based on interaction count and errors
3. **Intervention Type**: Select appropriate prompt type
4. **State Update**: Mark task as PAUSED → RUNNING
5. **Logging**: Save intervention to database

## Test Management

### Test Generation

1. Claude generates test code based on implementation
2. Validate syntax before saving
3. Store as TestCase with type=GENERATED

### Test Execution

1. **Generated Tests**:
   - Create temporary test file
   - Run pytest
   - Capture output
   - Update test status

2. **Regression Tests**:
   - Look for `tests/` directory in project
   - Run all tests with pytest
   - Parse results

### Completion Criteria

Task is COMPLETED only if:
- All generated tests PASS
- All regression tests PASS
- No execution errors

## Security Considerations

### Current Implementation

- No authentication (development only)
- API key stored in environment variables
- Most permissions granted to Claude
- Malicious operations blocked (as per Claude's guidelines)

### Production Recommendations

1. Add authentication (JWT, OAuth)
2. Add authorization (role-based access)
3. Rate limiting
4. Input validation and sanitization
5. Audit logging
6. Secret management (HashiCorp Vault, AWS Secrets Manager)

## Scalability Considerations

### Current Limitations

- SQLite (single-threaded writes)
- In-process background tasks
- No task queuing system
- No load balancing

### Scaling Recommendations

1. **Database**: PostgreSQL or MySQL
2. **Task Queue**: Celery with Redis/RabbitMQ
3. **Caching**: Redis for session/task state
4. **Load Balancing**: Multiple server instances
5. **Storage**: Separate file storage (S3, MinIO)
6. **Monitoring**: Prometheus + Grafana

## Error Handling

### Levels

1. **HTTP Layer**: FastAPI exception handlers
2. **Service Layer**: Try-catch with error logging
3. **Database Layer**: Transaction rollback
4. **External API**: Retry logic with exponential backoff

### Error Recording

All errors are:
- Logged to stdout
- Stored in task.error_message
- Included in status responses

## Configuration

### Environment Variables

```
ANTHROPIC_API_KEY - Claude API key (required)
DATABASE_URL      - Database connection string
HOST              - Server host (default: 0.0.0.0)
PORT              - Server port (default: 8000)
```

### Execution Parameters

In `TaskExecutor`:
- `max_iterations = 20`
- `max_pauses = 5`

In `TestRunner`:
- Test timeout: 60 seconds
- Regression timeout: 300 seconds

## Future Enhancements

### High Priority
1. WebSocket support for real-time updates
2. Task cancellation
3. Authentication and authorization
4. PostgreSQL support

### Medium Priority
1. Task priority and queuing
2. Webhook notifications
3. Code review integration
4. Multi-language support

### Low Priority
1. UI dashboard
2. Metrics and analytics
3. Cost tracking
4. Team collaboration features

## Testing Strategy

### Unit Tests
- Individual components
- Mock external dependencies
- Test edge cases

### Integration Tests
- API endpoint tests
- Database operations
- End-to-end workflows

### Regression Tests
- Ensure existing functionality works
- Run on every deployment
- Located in `tests/` directory

## Deployment

### Development
```bash
python -m app.main
```

### Production
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Docker (Future)
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## Monitoring

### Health Checks
- `/health` endpoint
- Database connectivity
- Claude API availability

### Metrics to Track
- Task success rate
- Average completion time
- API response times
- Error rates
- Claude API usage

## Conclusion

This architecture provides a solid foundation for autonomous task completion with Claude. It's designed to be:
- **Modular**: Clear separation of concerns
- **Extensible**: Easy to add new features
- **Maintainable**: Well-documented and tested
- **Scalable**: Can grow with requirements

The system successfully implements the core requirements:
✓ HTTP request/response based
✓ Session management
✓ Async task execution
✓ Claude interaction with simulated human feedback
✓ Test generation and validation
✓ Status tracking and querying
