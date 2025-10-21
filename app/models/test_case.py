from sqlalchemy import Column, String, DateTime, Text, ForeignKey, Boolean, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum
from app.database import Base


class TestCaseType(str, enum.Enum):
    GENERATED = "generated"
    REGRESSION = "regression"


class TestCaseStatus(str, enum.Enum):
    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"


class TestCase(Base):
    __tablename__ = "test_cases"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id = Column(String(36), ForeignKey("tasks.id"), nullable=False)
    name = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    test_code = Column(Text, nullable=False)
    test_type = Column(Enum(TestCaseType), default=TestCaseType.GENERATED)
    status = Column(Enum(TestCaseStatus), default=TestCaseStatus.PENDING)
    output = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    task = relationship("Task", back_populates="test_cases")
