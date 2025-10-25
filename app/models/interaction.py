from sqlalchemy import Column, String, DateTime, Text, ForeignKey, Enum, Integer, Float
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum
from app.database import Base


class InteractionType(str, enum.Enum):
    USER_REQUEST = "user_request"
    CLAUDE_RESPONSE = "claude_response"
    SIMULATED_HUMAN = "simulated_human"
    TOOL_RESULT = "tool_result"


class ClaudeInteraction(Base):
    __tablename__ = "claude_interactions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id = Column(String(36), ForeignKey("tasks.id"), nullable=False)
    interaction_type = Column(Enum(InteractionType, native_enum=False, length=20), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Token usage tracking (from Claude CLI result event)
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    cache_creation_tokens = Column(Integer, nullable=True)
    cache_read_tokens = Column(Integer, nullable=True)

    # Time tracking
    duration_ms = Column(Integer, nullable=True)  # Duration in milliseconds
    cost_usd = Column(Float, nullable=True)  # Total cost in USD

    task = relationship("Task", back_populates="interactions")
