from sqlalchemy import Column, String, DateTime, Text, ForeignKey, Enum, Integer, JSON, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum
from app.database import Base


class TaskStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    STOPPED = "STOPPED"
    TESTING = "TESTING"
    COMPLETED = "COMPLETED"  # Task completed before limits reached
    FAILED = "FAILED"
    FINISHED = "FINISHED"  # Task met end criteria successfully
    EXHAUSTED = "EXHAUSTED"  # Task hit max iterations or max tokens


class Task(Base):
    __tablename__ = "tasks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    task_name = Column(String(200), unique=True, nullable=False, index=True)
    session_id = Column(String(36), ForeignKey("sessions.id"), nullable=False)
    description = Column(Text, nullable=False)

    # User identification for multi-user support
    user_id = Column(String(100), nullable=True, index=True)  # Username from frontend (e.g., userInfo.user_name)

    # Project context
    root_folder = Column(String(500), nullable=True)
    branch_name = Column(String(200), nullable=True)
    base_branch = Column(String(200), nullable=True)  # Branch to branch off from (e.g., main, develop)
    git_repo = Column(String(500), nullable=True)
    worktree_path = Column(String(500), nullable=True)  # Git worktree path if using worktree

    # User-specified project context for Claude prompts
    # Format: Free text that will be included in Claude's project context
    # Example: "This is a Go project that handles CRUD operations. Dependencies: reverse_strategy_sdk for Get/Runtime/Cache. Testing: ./test directory contains regression test cases."
    project_context = Column(Text, nullable=True)

    # Multi-project configuration (JSON)
    # Format: [
    #   {"path": "/path/to/project1", "access": "write", "context": "Main service project", "branch_name": "feature-branch"},
    #   {"path": "/path/to/project2", "access": "read", "context": "Shared SDK for runtime operations"},
    #   {"path": "/path/to/project3", "access": "write", "context": "Testing utilities"}
    # ]
    # Projects with "write" access will get git worktree branches created
    # Projects with "read" access are read-only (no worktree needed)
    projects = Column(JSON, nullable=True)

    # Task status and results
    status = Column(Enum(TaskStatus), default=TaskStatus.PENDING)
    summary = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)

    # End criteria configuration (JSON)
    # Format: {"criteria": "success description", "max_iterations": 20, "max_tokens": 100000}
    end_criteria_config = Column(JSON, nullable=True)

    # Token tracking (needs to be queryable for monitoring)
    total_tokens_used = Column(Integer, default=0)  # Track cumulative output tokens

    # Human-in-the-loop: Custom input to override auto-generated response
    custom_human_input = Column(Text, nullable=True)

    # User input queue system for high-priority input handling
    # Format: [{"input": "message", "timestamp": "2023-...", "id": "uuid"}, ...]
    user_input_queue = Column(JSON, nullable=True)

    # Quick flag to check if user input is pending (for performance)
    user_input_pending = Column(Boolean, default=False, nullable=False)

    # Flag to prevent duplicate processing when immediate processing is active
    immediate_processing_active = Column(Boolean, default=False, nullable=False)

    # Process tracking
    process_pid = Column(Integer, nullable=True)

    # Claude CLI session tracking (for continuing conversations with -r flag)
    claude_session_id = Column(String(100), nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    session = relationship("Session", back_populates="tasks")
    test_cases = relationship("TestCase", back_populates="task", cascade="all, delete-orphan")
    interactions = relationship("ClaudeInteraction", back_populates="task", cascade="all, delete-orphan")

    @property
    def interaction_count(self):
        """Calculate the number of Claude response interactions."""
        from app.models.interaction import InteractionType
        return len([
            i for i in self.interactions
            if i.interaction_type == InteractionType.CLAUDE_RESPONSE
        ])
