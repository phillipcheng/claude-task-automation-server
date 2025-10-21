from sqlalchemy import Column, String, DateTime, Text, ForeignKey, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum
from app.database import Base


class InteractionType(str, enum.Enum):
    USER_REQUEST = "user_request"
    CLAUDE_RESPONSE = "claude_response"
    SIMULATED_HUMAN = "simulated_human"


class ClaudeInteraction(Base):
    __tablename__ = "claude_interactions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id = Column(String(36), ForeignKey("tasks.id"), nullable=False)
    interaction_type = Column(Enum(InteractionType), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    task = relationship("Task", back_populates="interactions")
