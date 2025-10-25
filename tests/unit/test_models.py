import pytest
from app.models import Session, Task, TaskStatus, TestCase, TestCaseType, TestCaseStatus
from app.database import Base, engine, SessionLocal


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database for each test."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)


def test_create_session(db_session):
    """Test creating a session."""
    session = Session(project_path="/tmp/test")
    db_session.add(session)
    db_session.commit()

    assert session.id is not None
    assert session.project_path == "/tmp/test"
    assert session.created_at is not None


def test_create_task(db_session):
    """Test creating a task."""
    # Create session first
    session = Session(project_path="/tmp/test")
    db_session.add(session)
    db_session.commit()

    # Create task
    task = Task(
        session_id=session.id,
        description="Test task",
        status=TaskStatus.PENDING
    )
    db_session.add(task)
    db_session.commit()

    assert task.id is not None
    assert task.session_id == session.id
    assert task.status == TaskStatus.PENDING


def test_task_test_case_relationship(db_session):
    """Test relationship between task and test cases."""
    # Create session and task
    session = Session(project_path="/tmp/test")
    db_session.add(session)
    db_session.commit()

    task = Task(
        session_id=session.id,
        description="Test task",
        status=TaskStatus.PENDING
    )
    db_session.add(task)
    db_session.commit()

    # Create test cases
    test_case1 = TestCase(
        task_id=task.id,
        name="Test 1",
        test_code="def test_1(): pass",
        test_type=TestCaseType.GENERATED
    )
    test_case2 = TestCase(
        task_id=task.id,
        name="Test 2",
        test_code="def test_2(): pass",
        test_type=TestCaseType.REGRESSION
    )
    db_session.add_all([test_case1, test_case2])
    db_session.commit()

    # Verify relationship
    assert len(task.test_cases) == 2
    assert task.test_cases[0].name in ["Test 1", "Test 2"]


def test_session_cascade_delete(db_session):
    """Test that deleting a session deletes its tasks."""
    # Create session and task
    session = Session(project_path="/tmp/test")
    db_session.add(session)
    db_session.commit()

    task = Task(
        session_id=session.id,
        description="Test task",
        status=TaskStatus.PENDING
    )
    db_session.add(task)
    db_session.commit()

    task_id = task.id

    # Delete session
    db_session.delete(session)
    db_session.commit()

    # Verify task is also deleted
    deleted_task = db_session.query(Task).filter(Task.id == task_id).first()
    assert deleted_task is None
