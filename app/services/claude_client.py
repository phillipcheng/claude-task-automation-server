import os
from anthropic import Anthropic
from typing import List, Dict, Optional
from dotenv import load_dotenv

load_dotenv()


class ClaudeClient:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not found in environment variables")
        self.client = Anthropic(api_key=self.api_key)
        self.model = "claude-3-5-sonnet-20241022"

    async def send_message(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        max_tokens: int = 4096,
    ) -> str:
        """
        Send a message to Claude and get a response.

        Args:
            messages: List of message dicts with 'role' and 'content'
            system_prompt: Optional system prompt
            max_tokens: Maximum tokens in response

        Returns:
            Claude's response text
        """
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                messages=messages,
                system=system_prompt if system_prompt else None,
            )
            return response.content[0].text
        except Exception as e:
            raise Exception(f"Error communicating with Claude: {str(e)}")

    async def generate_code(
        self,
        task_description: str,
        project_context: str,
        conversation_history: List[Dict[str, str]],
    ) -> str:
        """
        Generate code based on task description and project context.

        Args:
            task_description: Description of the task to implement
            project_context: Context about the project structure
            conversation_history: Previous interactions

        Returns:
            Claude's response with code and explanations
        """
        system_prompt = """You are an expert software engineer. You are given a task to implement
for an existing project. Generate clean, well-tested, production-ready code.
When implementing features, also suggest appropriate test cases."""

        messages = conversation_history.copy()

        if not messages:
            messages.append({
                "role": "user",
                "content": f"""Project Context:
{project_context}

Task to Implement:
{task_description}

Please implement this task. Provide the code and explain your implementation."""
            })

        return await self.send_message(messages, system_prompt=system_prompt)

    async def generate_test_cases(
        self,
        task_description: str,
        implementation_summary: str,
    ) -> str:
        """
        Generate test cases for the implemented task.

        Args:
            task_description: Description of the task
            implementation_summary: Summary of the implementation

        Returns:
            Test cases in pytest format
        """
        system_prompt = """You are an expert in writing comprehensive test cases.
Generate pytest test cases that thoroughly test the implementation."""

        messages = [{
            "role": "user",
            "content": f"""Task: {task_description}

Implementation: {implementation_summary}

Generate comprehensive pytest test cases for this implementation.
Return ONLY the test code without explanations."""
        }]

        return await self.send_message(messages, system_prompt=system_prompt)
