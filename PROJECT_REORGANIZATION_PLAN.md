# Claude Server Project Reorganization Plan

## Current Issues
- Root directory cluttered with 40+ files including tests, migrations, utilities, and documentation
- Mixed concerns: core app code mixed with development tools and scripts
- Poor discoverability: important files scattered throughout directory structure
- No clear separation between production code, development tools, and testing infrastructure

## Proposed Structure

```
claudeserver/
├── README.md                    # Main project documentation
├── requirements.txt             # Production dependencies
├── requirements-dev.txt         # Development dependencies
├── pyproject.toml              # Modern Python project configuration
├── .env.example                # Environment variables template
├── .gitignore                  # Git ignore rules
│
├── src/                        # Main application source code
│   └── claudeserver/
│       ├── __init__.py
│       ├── main.py            # Application entry point
│       ├── config.py          # Configuration management
│       ├── database.py        # Database connection and setup
│       ├── schemas.py         # Pydantic schemas
│       │
│       ├── api/               # FastAPI routes and endpoints
│       │   ├── __init__.py
│       │   ├── router.py      # Main API router
│       │   ├── tasks.py       # Task-related endpoints
│       │   ├── sessions.py    # Session endpoints
│       │   ├── prompts.py     # Prompt management endpoints
│       │   └── health.py      # Health check endpoints
│       │
│       ├── models/            # SQLAlchemy models
│       │   ├── __init__.py
│       │   ├── base.py        # Base model class
│       │   ├── task.py
│       │   ├── session.py
│       │   ├── interaction.py
│       │   ├── test_case.py
│       │   └── prompt.py
│       │
│       ├── services/          # Business logic services
│       │   ├── __init__.py
│       │   ├── task_service.py      # Task management logic
│       │   ├── claude_service.py    # Claude CLI integration
│       │   ├── git_service.py       # Git worktree operations
│       │   ├── test_service.py      # Test execution
│       │   ├── criteria_service.py  # End criteria analysis
│       │   └── streaming_service.py # Streaming responses
│       │
│       ├── utils/             # Utility functions
│       │   ├── __init__.py
│       │   ├── logging.py     # Logging configuration
│       │   ├── exceptions.py  # Custom exceptions
│       │   └── helpers.py     # Common helper functions
│       │
│       └── static/            # Static web assets
│           ├── index.html     # Web UI
│           ├── css/
│           ├── js/
│           └── assets/
│
├── tests/                     # Test suite
│   ├── __init__.py
│   ├── conftest.py           # Pytest configuration
│   ├── unit/                 # Unit tests
│   │   ├── test_models.py
│   │   ├── test_services.py
│   │   └── test_utils.py
│   ├── integration/          # Integration tests
│   │   ├── test_api.py
│   │   ├── test_workflows.py
│   │   └── test_claude_integration.py
│   └── fixtures/             # Test fixtures and data
│       ├── sample_tasks.json
│       └── mock_responses.py
│
├── scripts/                  # Development and deployment scripts
│   ├── setup.py             # Database setup
│   ├── migrate.py           # Migration runner
│   ├── seed_data.py         # Sample data creation
│   ├── clean_db.py          # Database cleanup
│   └── dev_server.py        # Development server
│
├── migrations/              # Database migrations
│   ├── versions/
│   │   ├── 001_initial_schema.sql
│   │   ├── 002_add_projects_column.sql
│   │   ├── 003_add_criteria_config.sql
│   │   └── ...
│   └── migrate.py          # Migration utilities
│
├── docs/                   # Documentation
│   ├── api/               # API documentation
│   ├── user-guide/        # User guides
│   ├── development/       # Development documentation
│   └── architecture/      # System design docs
│
├── examples/              # Usage examples
│   ├── basic_usage.py
│   ├── multi_project.py
│   └── advanced_workflows.py
│
├── tools/                 # Development tools and utilities
│   ├── monitor.py         # Task monitoring
│   ├── debug_claude.py    # Claude debugging tools
│   └── performance_test.py # Performance testing
│
└── deployment/           # Deployment configurations
    ├── docker/
    │   ├── Dockerfile
    │   └── docker-compose.yml
    ├── systemd/
    │   └── claudeserver.service
    └── nginx/
        └── claudeserver.conf
```

## Key Improvements

### 1. Clear Separation of Concerns
- **src/**: Production application code only
- **tests/**: All testing infrastructure
- **scripts/**: Development and maintenance tools
- **docs/**: All documentation in one place
- **tools/**: Debugging and monitoring utilities

### 2. Modern Python Project Structure
- Use `src/` layout for better import management
- Separate development and production dependencies
- Add `pyproject.toml` for modern Python configuration

### 3. Better API Organization
- Split endpoints by domain (tasks, sessions, prompts)
- Separate health checks and admin endpoints
- Clear router hierarchy

### 4. Improved Services Layer
- Rename services to be more descriptive
- Better separation of business logic
- Clear service responsibilities

### 5. Enhanced Testing Structure
- Separate unit and integration tests
- Centralized test configuration
- Organized test fixtures

### 6. Development Tools Organization
- All development scripts in dedicated directory
- Clear purpose for each tool
- Easy to find and use

## Migration Benefits

1. **Reduced Root Clutter**: From 40+ files to ~10 core files
2. **Better Discoverability**: Clear naming and organization
3. **Easier Maintenance**: Logical grouping of related files
4. **Improved Developer Experience**: Faster navigation and understanding
5. **Professional Structure**: Follows Python packaging best practices
6. **Scalability**: Structure supports future growth

## Implementation Plan

### Phase 1: Core Structure (High Priority)
1. Create new directory structure
2. Move application code to `src/claudeserver/`
3. Reorganize API endpoints
4. Update import statements

### Phase 2: Development Tools (Medium Priority)
1. Move utilities to `scripts/` and `tools/`
2. Reorganize tests into unit/integration
3. Clean up migrations directory

### Phase 3: Documentation & Polish (Low Priority)
1. Reorganize documentation
2. Add `pyproject.toml`
3. Update deployment configurations
4. Create usage examples

## Files to Move/Reorganize

### Root Level Cleanup (Move to appropriate directories)
- `test_*.py` files → `tests/`
- `add_*.py` migration scripts → `scripts/` or `migrations/`
- `create_test_task.py` → `scripts/`
- `monitor_task.py` → `tools/`
- `setup_mysql.py` → `scripts/setup.py`
- `simple_claude_test.py` → `examples/`
- Feature documentation → `docs/`

### Application Code Reorganization
- Split `app/api/endpoints.py` into domain-specific files
- Rename services to be more descriptive
- Move static files to organized structure

### Testing Infrastructure
- Move existing tests to appropriate categories
- Create test configuration files
- Organize test fixtures

This reorganization will make the project much more maintainable and professional while preserving all existing functionality.