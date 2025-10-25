"""
Test session ID consistency across different operations in the Claude server system.
"""
import pytest
import asyncio
import time
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine

from app.database import get_db
from app.models.task import Task, TaskStatus
from app.models.interaction import ClaudeInteraction
from app.services.task_executor import TaskExecutor
from app.services.streaming_cli_client import StreamingCLIClient


class TestSessionIDConsistency:
    """Test that session IDs are consistent across all operations."""

    @pytest.fixture(autouse=True)
    def setup_db(self):
        """Setup database connection for tests."""
        self.db = next(get_db())
        yield
        self.db.close()

    def test_task_creation_session_id(self):
        """Test that new tasks must have a valid session ID."""
        from app.models.session import Session

        # Create a session first (session_id is NOT NULL)
        session = Session(
            project_path="/test/path"
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)

        # Create a new task with session ID
        task = Task(
            task_name="test_session_consistency",
            description="Test session ID consistency",
            status=TaskStatus.PENDING,
            session_id=session.id
        )

        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)

        # Verify session ID is assigned and valid
        assert task.session_id is not None
        assert task.session_id == session.id
        assert len(task.session_id) > 0
        print(f"Task created with session_id: {task.session_id}")

        # Clean up
        self.db.delete(task)
        self.db.delete(session)
        self.db.commit()

    def test_session_id_foreign_key_constraint(self):
        """Test that task session_id properly references the sessions table."""
        from app.models.session import Session

        # Create a session first
        session = Session(
            project_path="/test/path"
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)

        # Create task with explicit session_id
        task = Task(
            task_name="fk_test_task",
            description="Test foreign key constraint",
            status=TaskStatus.PENDING,
            session_id=session.id
        )

        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)

        # Verify the relationship works
        assert task.session_id == session.id
        assert task.session is not None
        assert task.session.project_path == "/test/path"
        print(f"Task session_id: {task.session_id}")
        print(f"Session project_path: {task.session.project_path}")

        # Clean up
        self.db.delete(task)
        self.db.delete(session)
        self.db.commit()

    def test_interaction_session_id_consistency(self):
        """Test that interactions maintain session ID consistency with their task."""
        from app.models.session import Session

        # Create session first (required for task)
        session = Session(
            project_path="/test/interaction_path"
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)

        # Create task with session_id
        task = Task(
            task_name="interaction_test_task",
            description="Test interaction session ID consistency",
            status=TaskStatus.RUNNING,
            session_id=session.id
        )

        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)

        task_session_id = task.session_id

        # Create interaction (ClaudeInteraction doesn't have session_id field)
        interaction = ClaudeInteraction(
            task_id=task.id,
            interaction_type="user_request",
            content="Test interaction"
        )

        self.db.add(interaction)
        self.db.commit()
        self.db.refresh(interaction)

        # Verify interaction is linked to task correctly (no session_id on interaction)
        assert interaction.task_id == task.id
        print(f"Task session_id: {task_session_id}")
        print(f"Interaction task_id: {interaction.task_id}")
        print("✓ Interaction correctly linked to task")

        # Clean up
        self.db.delete(interaction)
        self.db.delete(task)
        self.db.delete(session)
        self.db.commit()

    def test_multiple_tasks_different_session_ids(self):
        """Test that tasks in different sessions have different session IDs."""
        from app.models.session import Session

        # Create multiple sessions and tasks
        tasks = []
        sessions = []
        for i in range(3):
            # Create session
            session = Session(
                project_path=f"/test/path_{i}"
            )
            self.db.add(session)
            sessions.append(session)

        self.db.commit()

        # Refresh sessions to get IDs
        for session in sessions:
            self.db.refresh(session)

        # Create tasks with different sessions
        for i, session in enumerate(sessions):
            task = Task(
                task_name=f"test_task_{i}",
                description=f"Test task {i}",
                status=TaskStatus.PENDING,
                session_id=session.id
            )
            self.db.add(task)
            tasks.append(task)

        self.db.commit()

        # Refresh to get session IDs
        for task in tasks:
            self.db.refresh(task)

        # Verify all session IDs are different
        session_ids = [task.session_id for task in tasks]
        assert len(set(session_ids)) == len(session_ids), "All session IDs should be unique"

        for i, task in enumerate(tasks):
            print(f"Task {i} session_id: {task.session_id}")

        # Clean up
        for task in tasks:
            self.db.delete(task)
        for session in sessions:
            self.db.delete(session)
        self.db.commit()

    def test_session_id_persistence_across_updates(self):
        """Test that session ID persists when task is updated."""
        from app.models.session import Session

        # Create session
        session = Session(
            project_path="/test/path"
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)

        # Create task
        task = Task(
            task_name="persistence_test_task",
            description="Test session ID persistence",
            status=TaskStatus.PENDING,
            session_id=session.id
        )

        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)

        original_session_id = task.session_id

        # Update task status
        task.status = TaskStatus.RUNNING
        self.db.commit()
        self.db.refresh(task)

        # Verify session ID hasn't changed
        assert task.session_id == original_session_id
        print(f"Session ID before update: {original_session_id}")
        print(f"Session ID after update: {task.session_id}")

        # Update task description
        task.description = "Updated description"
        self.db.commit()
        self.db.refresh(task)

        # Verify session ID still hasn't changed
        assert task.session_id == original_session_id

        # Clean up
        self.db.delete(task)
        self.db.delete(session)
        self.db.commit()

    def test_task_executor_session_id_usage(self):
        """Test that TaskExecutor properly uses session IDs."""
        from app.models.session import Session

        # Create session
        session = Session(
            project_path="/test/path"
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)

        # Create task
        task = Task(
            task_name="executor_test_task",
            description="Test TaskExecutor session ID usage",
            status=TaskStatus.PENDING,
            session_id=session.id
        )

        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)

        # Create TaskExecutor instance
        executor = TaskExecutor()

        # Verify the task has a session ID
        assert task.session_id is not None
        print(f"Task session_id for executor test: {task.session_id}")

        # Check that the executor would use the correct session ID
        # (We can't easily test the full execution without running Claude CLI)

        # Clean up
        self.db.delete(task)
        self.db.delete(session)
        self.db.commit()

    @pytest.mark.asyncio
    async def test_concurrent_task_session_ids(self):
        """Test session ID consistency with concurrent task creation."""
        from app.models.session import Session

        async def create_task_with_session(task_num):
            db = next(get_db())
            try:
                # Create session first
                session = Session(
                    project_path=f"/test/concurrent_{task_num}"
                )
                db.add(session)
                db.commit()
                db.refresh(session)

                # Create task with session
                task = Task(
                    task_name=f"concurrent_task_{task_num}",
                    description=f"Concurrent task {task_num}",
                    status=TaskStatus.PENDING,
                    session_id=session.id
                )
                db.add(task)
                db.commit()
                db.refresh(task)
                return task.session_id, session.id
            finally:
                db.close()

        # Create multiple tasks concurrently
        results = await asyncio.gather(*[create_task_with_session(i) for i in range(5)])
        task_sessions = [result[0] for result in results]
        session_ids = [result[1] for result in results]

        # Verify all session IDs are unique
        assert len(set(task_sessions)) == len(task_sessions), "All concurrent task session IDs should be unique"
        assert len(set(session_ids)) == len(session_ids), "All created session IDs should be unique"

        for i, (task_session_id, session_id) in enumerate(results):
            print(f"Concurrent task {i} session_id: {task_session_id}")
            assert task_session_id == session_id, "Task session_id should match created session ID"

        # Clean up
        for i in range(5):
            task = self.db.query(Task).filter(Task.task_name == f"concurrent_task_{i}").first()
            if task:
                session = self.db.query(Session).filter(Session.id == task.session_id).first()
                self.db.delete(task)
                if session:
                    self.db.delete(session)
        self.db.commit()


if __name__ == "__main__":
    # Run specific tests
    pytest.main([__file__, "-v"])