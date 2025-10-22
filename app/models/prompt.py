from sqlalchemy import Column, String, DateTime, Text, Integer
from datetime import datetime
import uuid
from app.database import Base


class Prompt(Base):
    __tablename__ = "prompts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(200), nullable=False, index=True)
    content = Column(Text, nullable=False)
    category = Column(String(100), nullable=True, index=True)  # e.g., "task", "bug-fix", "feature", "refactor"
    tags = Column(Text, nullable=True)  # Comma-separated tags for easier searching
    usage_count = Column(Integer, default=0)  # Track how often prompt is used

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_used_at = Column(DateTime, nullable=True)  # Track when last used
