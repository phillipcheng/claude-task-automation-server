from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from app.models.task import TaskStatus
from app.models.test_case import TestCaseType, TestCaseStatus


class SessionCreate(BaseModel):
    project_path: str


class SessionResponse(BaseModel):
    id: str
    project_path: str
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


class TaskCreate(BaseModel):
    task_name: str
    description: str
    user_id: Optional[str] = None  # User identifier for multi-user support
    root_folder: Optional[str] = None  # Project root folder
    branch_name: Optional[str] = None  # Git branch to work on
    base_branch: Optional[str] = None  # Branch to branch off from (e.g., main, develop, master)
    use_worktree: bool = True  # Use git worktree for isolation (default: True)
    auto_start: bool = False  # Automatically start task execution (default: False)
    project_path: Optional[str] = None  # Deprecated, use root_folder

    # Project context for Claude prompts
    project_context: Optional[str] = None  # User-specified project context that will be included in Claude's prompts

    # Chat mode: If True, Claude responds once and waits for user input (no auto-response)
    chat_mode: bool = False  # Default: False (automation mode with auto-response)

    # End criteria configuration
    end_criteria: Optional[str] = None  # Success criteria description
    max_iterations: Optional[int] = 20  # Maximum conversation iterations
    max_tokens: Optional[int] = None  # Maximum cumulative output tokens

    # Multi-project configuration
    # Format: [
    #   {"path": "/path/to/project1", "access": "write", "context": "Main service project", "branch_name": "feature-branch"},
    #   {"path": "/path/to/project2", "access": "read", "context": "Shared SDK for runtime operations"},
    #   {"path": "/path/to/project3", "access": "write", "context": "Testing utilities"}
    # ]
    projects: Optional[List[Dict[str, Any]]] = None  # Multi-project configuration with read/write access

    # MCP servers for custom tools (added on top of default tools)
    # Format: {"serverName": {"command": "npx", "args": ["..."], "env": {"KEY": "value"}}, ...}
    # Example: {"overpass": {"command": "npx", "args": ["@byted/mcp-proxy"], "env": {"MCP_SERVER_PSM": "bytedance.mcp.overpass"}}}
    mcp_servers: Optional[Dict[str, Any]] = None


class TestCaseResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    test_type: TestCaseType
    status: TestCaseStatus
    output: Optional[str]
    created_at: datetime

    class Config:
        orm_mode = True


class InteractionResponse(BaseModel):
    id: str
    interaction_type: str
    content: str
    created_at: datetime

    class Config:
        orm_mode = True


class TaskResponse(BaseModel):
    id: str
    task_name: str
    session_id: str
    description: str
    user_id: Optional[str] = None
    root_folder: Optional[str]
    branch_name: Optional[str]
    base_branch: Optional[str]
    git_repo: Optional[str]
    worktree_path: Optional[str]
    status: TaskStatus
    summary: Optional[str]
    error_message: Optional[str]
    end_criteria_config: Optional[dict] = None
    total_tokens_used: Optional[int] = 0
    interaction_count: Optional[int] = 0
    chat_mode: Optional[bool] = False  # Chat mode flag
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime]
    test_cases: List[TestCaseResponse] = []
    interactions: List[InteractionResponse] = []
    projects: Optional[List[Dict[str, Any]]] = None
    project_context: Optional[str] = None
    mcp_servers: Optional[Dict[str, Any]] = None  # MCP servers for custom tools

    class Config:
        orm_mode = True


class TaskStatusResponse(BaseModel):
    id: str
    task_name: str
    user_id: Optional[str] = None
    root_folder: Optional[str]
    branch_name: Optional[str]
    base_branch: Optional[str]
    status: TaskStatus
    summary: Optional[str]
    error_message: Optional[str]
    end_criteria_config: Optional[dict] = None
    total_tokens_used: Optional[int] = 0
    interaction_count: Optional[int] = 0
    chat_mode: Optional[bool] = False  # Chat mode flag
    progress: str
    test_summary: dict
    latest_claude_response: Optional[str] = None  # Latest response from Claude
    waiting_for_input: bool = False  # Whether Claude is waiting for user input
    projects: Optional[List[Dict[str, Any]]] = None
    project_context: Optional[str] = None
    process_running: bool = False  # Whether there's an active Claude CLI process running
    process_pid: Optional[int] = None  # The PID of the running process (if any)

    class Config:
        orm_mode = True


# Prompt Management Schemas
class PromptCreate(BaseModel):
    title: str
    content: str
    category: Optional[str] = None
    tags: Optional[str] = None
    criteria_config: Optional[dict] = None  # For category="criteria": {"criteria": "...", "max_iterations": 20, "max_tokens": 10000}


class PromptUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[str] = None
    criteria_config: Optional[dict] = None


class PromptResponse(BaseModel):
    id: str
    title: str
    content: str
    category: Optional[str]
    tags: Optional[str]
    usage_count: int
    criteria_config: Optional[dict]
    created_at: datetime
    updated_at: datetime
    last_used_at: Optional[datetime]

    class Config:
        orm_mode = True


# Project Management Schemas
class ProjectConfigSchema(BaseModel):
    """
    Non-searchable project configuration stored as JSON.

    Structure:
    {
        "context": "Description for Claude",
        "idl_repo": "/path/to/idl",
        "idl_file": "api/service.thrift",
        "psm": "oec.reverse.strategy",
        "test_dir": "./...",
        "test_tags": "-tags local",
        "overpass_module": "code.byted.org/oec/rpcv2_xxx"  # For RPC/Web/SDK after IDL change
    }
    """
    context: Optional[str] = None  # Description/context for Claude
    idl_repo: Optional[str] = None  # Path to IDL repository
    idl_file: Optional[str] = None  # IDL file path relative to repo root
    psm: Optional[str] = None  # Platform Service Manager identifier
    test_dir: Optional[str] = None  # Directory containing tests
    test_tags: Optional[str] = None  # Test tags/flags
    overpass_module: Optional[str] = None  # Overpass module dependency after IDL change


class ProjectCreate(BaseModel):
    name: str
    path: str
    user_id: str
    project_type: Optional[str] = "other"  # Project type: rpc, web, idl, sdk, other
    default_branch: str  # Required - branch for release/integration testing
    config: Optional[ProjectConfigSchema] = None  # All non-searchable config


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    path: Optional[str] = None
    project_type: Optional[str] = None
    default_branch: Optional[str] = None
    config: Optional[ProjectConfigSchema] = None


class ProjectResponse(BaseModel):
    id: str
    user_id: str
    name: str
    path: str
    project_type: Optional[str] = "other"
    default_branch: Optional[str]
    config: Optional[dict] = None  # JSON config
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


# Batch Operation Schemas
class BatchDeleteRequest(BaseModel):
    task_names: List[str]
    cleanup_worktree: bool = True


class BatchDeleteResult(BaseModel):
    task_name: str
    success: bool
    message: Optional[str] = None
    error: Optional[str] = None


class BatchDeleteResponse(BaseModel):
    total: int
    successful: int
    failed: int
    results: List[BatchDeleteResult]


# Project batch delete schemas
class ProjectBatchDeleteRequest(BaseModel):
    project_ids: List[str]


class ProjectBatchDeleteResult(BaseModel):
    project_id: str
    project_name: Optional[str] = None
    success: bool
    message: Optional[str] = None
    error: Optional[str] = None


class ProjectBatchDeleteResponse(BaseModel):
    total: int
    successful: int
    failed: int
    results: List[ProjectBatchDeleteResult]
