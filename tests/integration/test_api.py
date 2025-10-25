import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import Base, engine, SessionLocal
from app.models import Session, Task, TaskStatus
import os

client = TestClient(app)


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database for each test."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)


def test_root_endpoint():
    """Test root endpoint returns correct information."""
    response = client.get("/")
    assert response.status_code == 200
    assert "message" in response.json()
    assert "version" in response.json()


def test_health_check():
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_create_session():
    """Test creating a new session."""
    response = client.post(
        "/api/v1/sessions",
        json={"project_path": "/tmp/test_project"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert data["project_path"] == "/tmp/test_project"
    assert "created_at" in data


def test_get_session(db_session):
    """Test getting session details."""
    # Create a session first
    create_response = client.post(
        "/api/v1/sessions",
        json={"project_path": "/tmp/test_project"}
    )
    session_id = create_response.json()["id"]

    # Get the session
    response = client.get(f"/api/v1/sessions/{session_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == session_id
    assert data["project_path"] == "/tmp/test_project"


def test_get_nonexistent_session():
    """Test getting a session that doesn't exist."""
    response = client.get("/api/v1/sessions/nonexistent-id")
    assert response.status_code == 404


def test_create_task(db_session):
    """Test creating a new task."""
    # Create a session first
    session_response = client.post(
        "/api/v1/sessions",
        json={"project_path": "/tmp/test_project"}
    )
    session_id = session_response.json()["id"]

    # Create a task
    # Note: This will start background execution, but we're just testing the API
    response = client.post(
        "/api/v1/tasks",
        json={
            "session_id": session_id,
            "description": "Create a simple calculator function"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert data["session_id"] == session_id
    assert data["description"] == "Create a simple calculator function"
    assert "status" in data


def test_create_task_invalid_session():
    """Test creating a task with invalid session."""
    response = client.post(
        "/api/v1/tasks",
        json={
            "session_id": "invalid-session-id",
            "description": "Some task"
        }
    )
    assert response.status_code == 404


def test_get_task_status(db_session):
    """Test getting task status."""
    # Create session and task
    session_response = client.post(
        "/api/v1/sessions",
        json={"project_path": "/tmp/test_project"}
    )
    session_id = session_response.json()["id"]

    task_response = client.post(
        "/api/v1/tasks",
        json={
            "session_id": session_id,
            "description": "Test task"
        }
    )
    task_id = task_response.json()["id"]

    # Get task status
    response = client.get(f"/api/v1/tasks/{task_id}/status")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == task_id
    assert "status" in data
    assert "progress" in data
    assert "test_summary" in data


def test_get_session_tasks(db_session):
    """Test getting all tasks for a session."""
    # Create session
    session_response = client.post(
        "/api/v1/sessions",
        json={"project_path": "/tmp/test_project"}
    )
    session_id = session_response.json()["id"]

    # Create multiple tasks
    for i in range(3):
        client.post(
            "/api/v1/tasks",
            json={
                "session_id": session_id,
                "description": f"Test task {i}"
            }
        )

    # Get all tasks
    response = client.get(f"/api/v1/sessions/{session_id}/tasks")
    assert response.status_code == 200
    tasks = response.json()
    assert len(tasks) == 3
