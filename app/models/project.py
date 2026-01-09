import uuid
from sqlalchemy import Column, String, Text, DateTime, Enum as SQLEnum
from sqlalchemy.sql import func
from app.database import Base
import enum


class AccessType(enum.Enum):
    READ = "read"
    WRITE = "write"


class Project(Base):
    __tablename__ = "projects"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(100), nullable=False, index=True)  # Owner of the project config

    # Project configuration
    name = Column(String(200), nullable=False)
    path = Column(String(500), nullable=False)
    default_access = Column(SQLEnum(AccessType), default=AccessType.WRITE)
    default_branch = Column(String(200), nullable=True)
    default_context = Column(Text, nullable=True)  # Description/context for Claude

    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
