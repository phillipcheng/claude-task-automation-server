import subprocess
import json
import tempfile
import os
from typing import List, Dict, Optional


class ClaudeCLIClient:
    """Client for interacting with Claude Code CLI."""

    def __init__(self, cli_command: str = "claude"):
        """
        Initialize Claude CLI client.

        Args:
            cli_command: Command to invoke Claude CLI (default: "claude")
        """
        self.cli_command = cli_command
        self._verify_cli_available()

    def _verify_cli_available(self):
        """Verify that Claude CLI is available."""
        try:
            result = subprocess.run(
                [self.cli_command, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode != 0:
                raise Exception(f"Claude CLI not available: {result.stderr}")
        except FileNotFoundError:
            raise Exception(
                f"Claude CLI command '{self.cli_command}' not found. "
                "Please ensure Claude Code is installed and in your PATH."
            )
        except Exception as e:
            raise Exception(f"Error verifying Claude CLI: {str(e)}")

    async def send_message(
        self,
        message: str,
        project_path: Optional[str] = None,
        continue_conversation: bool = False,
    ) -> str:
        """
        Send a message to Claude via CLI.

        Args:
            message: The message to send to Claude
            project_path: Path to the project directory
            continue_conversation: Whether to continue previous conversation

        Returns:
            Claude's response text
        """
        try:
            # Prepare command
            cmd = [self.cli_command]

            # Add message
            cmd.append(message)

            # Execute command with working directory set via cwd parameter
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout for complex tasks
                cwd=project_path if project_path and os.path.exists(project_path) else None,
            )

            if result.returncode != 0:
                error_msg = result.stderr or "Unknown error"
                raise Exception(f"Claude CLI error: {error_msg}")

            return result.stdout.strip()

        except subprocess.TimeoutExpired:
            raise Exception("Claude CLI request timed out after 5 minutes")
        except Exception as e:
            raise Exception(f"Error communicating with Claude CLI: {str(e)}")

    async def send_message_interactive(
        self,
        messages: List[str],
        project_path: Optional[str] = None,
    ) -> List[str]:
        """
        Send multiple messages in sequence to Claude via CLI.

        Args:
            messages: List of messages to send sequentially
            project_path: Path to the project directory

        Returns:
            List of Claude's responses
        """
        responses = []

        for message in messages:
            response = await self.send_message(
                message=message,
                project_path=project_path,
                continue_conversation=True,
            )
            responses.append(response)

        return responses

    async def generate_code(
        self,
        task_description: str,
        project_context: str,
        project_path: str,
    ) -> str:
        """
        Generate code based on task description.

        Args:
            task_description: Description of the task to implement
            project_context: Context about the project structure
            project_path: Path to the project

        Returns:
            Claude's response with code and explanations
        """
        message = f"""I need you to implement the following task for this project.

Project Context:
{project_context}

Task to Implement:
{task_description}

Please implement this task step by step. Generate clean, production-ready code.
Most permissions are granted for file operations, code generation, and testing.
When you complete the implementation, please provide a summary of what you've done.

Start implementing now."""

        return await self.send_message(message, project_path=project_path)

    async def continue_task(
        self,
        continuation_prompt: str,
        project_path: str,
    ) -> str:
        """
        Continue working on a task.

        Args:
            continuation_prompt: Prompt to continue the task
            project_path: Path to the project

        Returns:
            Claude's response
        """
        return await self.send_message(
            message=continuation_prompt,
            project_path=project_path,
            continue_conversation=True,
        )

    async def generate_test_cases(
        self,
        task_description: str,
        implementation_summary: str,
        project_path: str,
    ) -> str:
        """
        Generate test cases for the implemented task.

        Args:
            task_description: Description of the task
            implementation_summary: Summary of the implementation
            project_path: Path to the project

        Returns:
            Test cases in pytest format
        """
        message = f"""Based on the following implementation, generate comprehensive pytest test cases.

Task: {task_description}

Implementation Summary: {implementation_summary}

Please generate pytest test cases that thoroughly test this implementation.
Create the test file in the appropriate location in the project.
Return the test code you created."""

        return await self.send_message(message, project_path=project_path)

    async def get_project_context(self, project_path: str) -> str:
        """
        Get project context by asking Claude to analyze the project.

        Args:
            project_path: Path to the project

        Returns:
            Project context summary
        """
        message = """Please analyze this project structure and provide a brief summary:
- What type of project is this?
- What are the main directories and files?
- What programming language(s) are used?
- Are there any existing tests?

Keep the summary concise (3-5 sentences)."""

        try:
            return await self.send_message(message, project_path=project_path)
        except Exception as e:
            # If project doesn't exist or can't be analyzed, return basic info
            return f"New or empty project at {project_path}"
