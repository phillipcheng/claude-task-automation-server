from sqlalchemy import Column, String, DateTime, Text, ForeignKey, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum
from app.database import Base


class TaskStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    TESTING = "testing"
    COMPLETED = "completed"
    FAILED = "failed"


class Task(Base):
    __tablename__ = "tasks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    task_name = Column(String(200), unique=True, nullable=False, index=True)
    session_id = Column(String(36), ForeignKey("sessions.id"), nullable=False)
    description = Column(Text, nullable=False)

    # Project context
    root_folder = Column(String(500), nullable=True)
    branch_name = Column(String(200), nullable=True)
    git_repo = Column(String(500), nullable=True)
    worktree_path = Column(String(500), nullable=True)  # Git worktree path if using worktree

    # Task status and results
    status = Column(Enum(TaskStatus), default=TaskStatus.PENDING)
    summary = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    session = relationship("Session", back_populates="tasks")
    test_cases = relationship("TestCase", back_populates="task", cascade="all, delete-orphan")
    interactions = relationship("ClaudeInteraction", back_populates="task", cascade="all, delete-orphan")
