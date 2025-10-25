"""Service for extracting and checking task ending criteria using LLM."""

import json
import asyncio
from typing import Dict, Optional, Tuple
from app.services.streaming_cli_client import StreamingCLIClient
import os


class CriteriaAnalyzer:
    """Analyzes task descriptions to extract ending criteria and checks task completion."""

    def __init__(self, cli_command: str = None):
        cli_cmd = cli_command or os.getenv("CLAUDE_CLI_COMMAND", "claude")
        self.streaming_client = StreamingCLIClient(cli_command=cli_cmd)

    async def extract_ending_criteria(self, task_description: str) -> Tuple[Optional[str], bool]:
        """
        Extract ending criteria from task description using LLM.

        Args:
            task_description: The task description to analyze

        Returns:
            Tuple of (criteria_description, has_clear_criteria)
            - criteria_description: Human-readable success criteria, or None if unclear
            - has_clear_criteria: Whether clear ending criteria was found
        """
        prompt = f"""Analyze the following task description and extract the ending criteria - what would indicate this task is complete and successful.

Task Description:
{task_description}

Please provide:
1. A clear, specific description of what indicates task completion (2-3 sentences max)
2. Whether the ending criteria is clear and measurable (yes/no)

Respond in JSON format:
{{
    "criteria": "description of success criteria",
    "is_clear": true/false,
    "reasoning": "brief explanation"
}}

Examples:
- "Add a login button to the homepage" → {{"criteria": "A functional login button is visible on the homepage and clicking it triggers login flow", "is_clear": true}}
- "Make the app better" → {{"criteria": "Unclear - no specific success criteria defined", "is_clear": false}}
- "Fix all type errors in the build" → {{"criteria": "Build runs successfully with zero type errors", "is_clear": true}}
"""

        try:
            # Use streaming client to analyze
            response, _, _, _ = await self.streaming_client.send_message_streaming(
                message=prompt,
                project_path=None,  # No project context needed for this
            )

            # Extract JSON from response
            json_match = self._extract_json(response)
            if json_match:
                result = json.loads(json_match)
                criteria = result.get("criteria", "").strip()
                is_clear = result.get("is_clear", False)

                if is_clear and criteria:
                    return criteria, True
                else:
                    return None, False

            return None, False

        except Exception as e:
            print(f"Error extracting ending criteria: {e}")
            return None, False

    async def check_task_completion(
        self,
        ending_criteria: str,
        task_description: str,
        conversation_history: str,
        latest_response: str
    ) -> Tuple[bool, str]:
        """
        Check if task has met its ending criteria based on conversation.

        Args:
            ending_criteria: The success criteria to check against
            task_description: Original task description
            conversation_history: Summary of conversation so far
            latest_response: Latest response from Claude

        Returns:
            Tuple of (is_complete, reasoning)
        """
        prompt = f"""Based on the conversation history, determine if the following task has met its ending criteria.

Task Description:
{task_description}

Ending Criteria (Success Condition):
{ending_criteria}

Latest Response from Claude:
{latest_response}

Has the task met its ending criteria? Respond in JSON format:
{{
    "is_complete": true/false,
    "reasoning": "brief explanation of why the criteria is/isn't met",
    "confidence": 0.0-1.0
}}

Be strict - only mark as complete if the ending criteria is clearly and fully met.
"""

        try:
            response, _, _, _ = await self.streaming_client.send_message_streaming(
                message=prompt,
                project_path=None,
            )

            # Extract JSON from response
            json_match = self._extract_json(response)
            if json_match:
                result = json.loads(json_match)
                is_complete = result.get("is_complete", False)
                reasoning = result.get("reasoning", "Unknown")
                confidence = result.get("confidence", 0.0)

                # Require high confidence (>0.7) for completion
                if is_complete and confidence > 0.7:
                    return True, reasoning
                else:
                    return False, reasoning

            return False, "Could not parse completion check"

        except Exception as e:
            print(f"Error checking task completion: {e}")
            return False, f"Error: {str(e)}"

    def _extract_json(self, text: str) -> Optional[str]:
        """Extract JSON from text that may contain markdown code blocks."""
        import re

        # Try to find JSON in code blocks first
        json_block_pattern = r'```(?:json)?\s*(\{.*?\})\s*```'
        match = re.search(json_block_pattern, text, re.DOTALL)
        if match:
            return match.group(1)

        # Try to find raw JSON
        json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
        match = re.search(json_pattern, text, re.DOTALL)
        if match:
            return match.group(0)

        return None
