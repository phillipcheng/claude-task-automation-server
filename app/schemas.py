from pydantic import BaseModel, Field
from typing import Optional, List
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
        from_attributes = True


class TaskCreate(BaseModel):
    task_name: str
    description: str
    root_folder: Optional[str] = None  # Project root folder
    branch_name: Optional[str] = None  # Git branch to work on
    use_worktree: bool = True  # Use git worktree for isolation (default: True)
    auto_start: bool = False  # Automatically start task execution (default: False)
    project_path: Optional[str] = None  # Deprecated, use root_folder


class TestCaseResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    test_type: TestCaseType
    status: TestCaseStatus
    output: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class InteractionResponse(BaseModel):
    id: str
    interaction_type: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True


class TaskResponse(BaseModel):
    id: str
    task_name: str
    session_id: str
    description: str
    root_folder: Optional[str]
    branch_name: Optional[str]
    git_repo: Optional[str]
    worktree_path: Optional[str]
    status: TaskStatus
    summary: Optional[str]
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime]
    test_cases: List[TestCaseResponse] = []
    interactions: List[InteractionResponse] = []

    class Config:
        from_attributes = True


class TaskStatusResponse(BaseModel):
    id: str
    task_name: str
    root_folder: Optional[str]
    branch_name: Optional[str]
    status: TaskStatus
    summary: Optional[str]
    error_message: Optional[str]
    progress: str
    test_summary: dict
    latest_claude_response: Optional[str] = None  # Latest response from Claude
    waiting_for_input: bool = False  # Whether Claude is waiting for user input

    class Config:
        from_attributes = True
