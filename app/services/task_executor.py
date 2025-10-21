import asyncio
from typing import List, Dict, Optional
from sqlalchemy.orm import Session as DBSession
from app.database import SessionLocal
from app.models import (
    Task,
    TaskStatus,
    ClaudeInteraction,
    InteractionType,
    TestCase,
    TestCaseType,
    TestCaseStatus,
    Session,
)
from app.services.claude_cli_client import ClaudeCLIClient
from app.services.simulated_human import SimulatedHuman
from app.services.test_runner import TestRunner
from datetime import datetime
import re
import os


class TaskExecutor:
    """Executes tasks asynchronously with Claude CLI interaction."""

    def __init__(self, cli_command: str = None):
        # Use environment variable or default to "claude"
        cli_cmd = cli_command or os.getenv("CLAUDE_CLI_COMMAND", "claude")
        self.claude_client = ClaudeCLIClient(cli_command=cli_cmd)
        self.simulated_human = SimulatedHuman()
        self.test_runner = TestRunner()
        self.max_iterations = 20
        self.max_pauses = 5

    async def execute_task(self, task_id: str):
        """
        Execute a task asynchronously.

        Args:
            task_id: ID of the task to execute
        """
        db = SessionLocal()
        try:
            task = db.query(Task).filter(Task.id == task_id).first()
            if not task:
                return

            # Update task status
            task.status = TaskStatus.RUNNING
            db.commit()

            # Get session for project context
            session = db.query(Session).filter(Session.id == task.session_id).first()

            # Use worktree path if available, otherwise use root_folder or session path
            project_path = task.worktree_path or task.root_folder or (session.project_path if session else ".")

            # Execute the task with Claude
            await self._execute_with_claude(db, task, project_path)

        except Exception as e:
            task = db.query(Task).filter(Task.id == task_id).first()
            if task:
                task.status = TaskStatus.FAILED
                task.error_message = str(e)
                db.commit()
        finally:
            db.close()

    async def _execute_with_claude(self, db: DBSession, task: Task, project_path: str):
        """
        Execute task with Claude CLI, handling conversation and pauses.

        Args:
            db: Database session
            task: Task to execute
            project_path: Path to the project
        """
        iteration = 0
        pause_count = 0
        is_first_message = True

        # Get project context (using Claude CLI to analyze)
        try:
            project_context = await self.claude_client.get_project_context(project_path)
        except Exception:
            project_context = self._get_project_context(project_path)

        # Initial user request
        initial_message = f"""I need you to implement the following task for this project.

Task Description:
{task.description}

Project Context:
{project_context}

Please implement this task step by step. Generate clean, production-ready code.
You have most permissions granted for file operations, code generation, and testing.
When you complete the implementation, please provide a summary of what you've done.

Start implementing now."""

        # Save initial interaction
        self._save_interaction(
            db, task.id, InteractionType.USER_REQUEST, initial_message
        )

        while iteration < self.max_iterations:
            iteration += 1

            try:
                # Send message to Claude CLI
                if is_first_message:
                    message_to_send = initial_message
                    is_first_message = False
                else:
                    # For continuation, we'll send a simulated human prompt
                    has_error = False  # We'll detect this from previous response if stored

                    if self.simulated_human.should_intervene(iteration, has_error):
                        if pause_count < self.max_pauses:
                            task.status = TaskStatus.PAUSED
                            db.commit()

                            # Wait a bit to simulate human thinking
                            await asyncio.sleep(1)

                            # Get simulated human response
                            intervention_type = self.simulated_human.get_intervention_type(has_error)
                            human_prompt = self.simulated_human.get_continuation_prompt(intervention_type)

                            message_to_send = human_prompt

                            # Save simulated human interaction
                            self._save_interaction(
                                db, task.id, InteractionType.SIMULATED_HUMAN, human_prompt
                            )

                            task.status = TaskStatus.RUNNING
                            db.commit()
                            pause_count += 1
                        else:
                            # Max pauses reached, stop
                            break
                    else:
                        # No intervention needed, break the loop
                        break

                # Get Claude's response via CLI
                response = await self.claude_client.send_message(
                    message=message_to_send,
                    project_path=project_path,
                    continue_conversation=(not is_first_message),
                )

                # Save Claude's response
                self._save_interaction(
                    db, task.id, InteractionType.CLAUDE_RESPONSE, response
                )

                # Check if task seems complete
                if self._is_task_complete(response):
                    task.summary = self._extract_summary(response)
                    db.commit()
                    break

            except Exception as e:
                task.error_message = f"Error during execution: {str(e)}"
                db.commit()
                break

        # If no summary yet, try to extract from last response
        if not task.summary:
            # Get last Claude response
            last_responses = [i for i in db.query(ClaudeInteraction).filter(
                ClaudeInteraction.task_id == task.id,
                ClaudeInteraction.interaction_type == InteractionType.CLAUDE_RESPONSE
            ).all()]
            if last_responses:
                task.summary = self._extract_summary(last_responses[-1].content)
                db.commit()

        # Generate and run tests
        await self._generate_and_run_tests(db, task, project_path)

    def _get_project_context(self, project_path: str) -> str:
        """
        Get context about the project structure.

        Args:
            project_path: Path to the project

        Returns:
            Project context string
        """
        import os

        context = f"Project Path: {project_path}\n\n"

        try:
            if os.path.exists(project_path):
                # List directory structure (first level only)
                items = os.listdir(project_path)
                context += "Project Structure:\n"
                for item in items[:20]:  # Limit to first 20 items
                    context += f"  - {item}\n"
            else:
                context += "Note: Project path does not exist yet.\n"
        except Exception as e:
            context += f"Error reading project: {str(e)}\n"

        return context

    def _save_interaction(
        self, db: DBSession, task_id: str, interaction_type: InteractionType, content: str
    ):
        """Save an interaction to the database."""
        interaction = ClaudeInteraction(
            task_id=task_id, interaction_type=interaction_type, content=content
        )
        db.add(interaction)
        db.commit()

    def _is_task_complete(self, response: str) -> bool:
        """
        Determine if the task is complete based on Claude's response.

        Args:
            response: Claude's response

        Returns:
            True if task appears complete
        """
        completion_indicators = [
            "implementation is complete",
            "task is complete",
            "finished implementing",
            "implementation done",
            "completed the task",
            "all done",
            "implementation summary",
            "successfully implemented",
        ]

        response_lower = response.lower()
        return any(indicator in response_lower for indicator in completion_indicators)

    def _extract_summary(self, response: str) -> str:
        """
        Extract a summary from Claude's response.

        Args:
            response: Claude's response

        Returns:
            Extracted summary
        """
        # Try to find summary section
        summary_patterns = [
            r"(?i)summary:?\s*(.+?)(?:\n\n|\Z)",
            r"(?i)implementation summary:?\s*(.+?)(?:\n\n|\Z)",
            r"(?i)what (?:i've|i have) done:?\s*(.+?)(?:\n\n|\Z)",
        ]

        for pattern in summary_patterns:
            match = re.search(pattern, response, re.DOTALL)
            if match:
                return match.group(1).strip()[:500]  # Limit to 500 chars

        # If no summary found, take first 300 characters
        return response[:300] + "..." if len(response) > 300 else response

    async def _generate_and_run_tests(
        self,
        db: DBSession,
        task: Task,
        project_path: str,
    ):
        """
        Generate test cases and run them.

        Args:
            db: Database session
            task: Task object
            project_path: Path to the project
        """
        task.status = TaskStatus.TESTING
        db.commit()

        try:
            # Generate test cases using Claude CLI
            test_code = await self.claude_client.generate_test_cases(
                task.description,
                task.summary or "Task implementation",
                project_path
            )

            # Validate test code
            is_valid, error_msg = await self.test_runner.validate_test_code(test_code)

            if is_valid:
                # Create test case record
                test_case = TestCase(
                    task_id=task.id,
                    name=f"Generated test for: {task.description[:50]}",
                    description="Auto-generated test case",
                    test_code=test_code,
                    test_type=TestCaseType.GENERATED,
                    status=TestCaseStatus.PENDING,
                )
                db.add(test_case)
                db.commit()

                # Run the test
                success, output = await self.test_runner.run_test(test_code, project_path)

                test_case.status = TestCaseStatus.PASSED if success else TestCaseStatus.FAILED
                test_case.output = output
                db.commit()

            # Run regression tests if they exist
            regression_passed, regression_output, _ = await self.test_runner.run_regression_tests(
                project_path
            )

            # Determine final task status
            all_tests_passed = (
                is_valid
                and all(tc.status == TestCaseStatus.PASSED for tc in task.test_cases)
                and regression_passed
            )

            if all_tests_passed:
                task.status = TaskStatus.COMPLETED
                task.completed_at = datetime.utcnow()
            else:
                task.status = TaskStatus.FAILED
                task.error_message = "Some tests failed"

            db.commit()

        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error_message = f"Error during testing: {str(e)}"
            db.commit()
