"""
Intelligent Auto-Responder for Claude interactions.

Analyzes Claude's responses and generates contextually appropriate replies
to keep tasks moving forward autonomously.
"""

import re
import random
from typing import Dict, List, Tuple, Optional


class IntelligentResponder:
    """
    Generates intelligent auto-responses based on Claude's output.

    Analyzes Claude's responses for:
    - Questions requiring decisions
    - Implementation completion indicators
    - Error messages or blockers
    - Progress updates
    """

    def __init__(self):
        self.question_patterns = [
            r'\?',  # Any question mark
            r'should i',
            r'would you like',
            r'do you want',
            r'which (?:one|approach|option|method)',
            r'(?:prefer|choose|select)',
            r'let me know',
            r'what (?:should|would)',
        ]

        self.completion_indicators = [
            r'completed',
            r'finished',
            r'done',
            r'implemented',
            r'successfully',
            r'all tests? pass',
            r'ready',
        ]

        self.error_indicators = [
            r'error',
            r'failed',
            r'exception',
            r'cannot',
            r'unable',
            r'issue',
            r'problem',
            r'bug',
        ]

        self.choice_patterns = [
            r'(?:option |approach )?(\d+)[:.)]',  # "option 1:", "1.", "1)"
            r'\[([a-zA-Z])\]',  # "[a]", "[B]"
        ]

    def analyze_response(self, claude_response: str) -> Dict[str, any]:
        """
        Analyze Claude's response to determine its type and content.

        Args:
            claude_response: Claude's latest response text

        Returns:
            Dict with analysis results:
            {
                'has_question': bool,
                'has_choices': bool,
                'choices': List[str],
                'seems_complete': bool,
                'has_error': bool,
                'response_type': str
            }
        """
        response_lower = claude_response.lower()

        # Check for questions
        has_question = any(
            re.search(pattern, response_lower, re.IGNORECASE)
            for pattern in self.question_patterns
        )

        # Check for multiple choice options
        choices = self._extract_choices(claude_response)
        has_choices = len(choices) > 0

        # Check for completion
        seems_complete = any(
            re.search(pattern, response_lower, re.IGNORECASE)
            for pattern in self.completion_indicators
        )

        # Check for errors
        has_error = any(
            re.search(pattern, response_lower, re.IGNORECASE)
            for pattern in self.error_indicators
        )

        # Determine response type
        response_type = self._determine_response_type(
            has_question, has_choices, seems_complete, has_error
        )

        return {
            'has_question': has_question,
            'has_choices': has_choices,
            'choices': choices,
            'seems_complete': seems_complete,
            'has_error': has_error,
            'response_type': response_type,
        }

    def generate_response(
        self,
        claude_response: str,
        task_description: str = "",
        iteration: int = 0
    ) -> str:
        """
        Generate an intelligent auto-response based on Claude's output.

        Args:
            claude_response: Claude's latest response
            task_description: Original task description for context
            iteration: Current iteration number

        Returns:
            Generated response string
        """
        analysis = self.analyze_response(claude_response)

        if analysis['response_type'] == 'multiple_choice':
            return self._respond_to_choice(analysis['choices'], task_description)
        elif analysis['response_type'] == 'yes_no_question':
            return self._respond_to_yes_no(claude_response, task_description)
        elif analysis['response_type'] == 'open_question':
            return self._respond_to_open_question(claude_response, task_description)
        elif analysis['response_type'] == 'error':
            return self._respond_to_error(claude_response)
        elif analysis['response_type'] == 'completion':
            return self._respond_to_completion()
        else:
            return self._respond_general_continuation(iteration)

    def _extract_choices(self, text: str) -> List[str]:
        """Extract numbered or lettered choices from text."""
        choices = []

        # Look for numbered options (1., 2., 3., etc.)
        numbered = re.findall(r'(?:^|\n)\s*(\d+)[:.)\]]\s*([^\n]+)', text, re.MULTILINE)
        if numbered:
            choices = [num for num, _ in numbered]

        # Look for lettered options ([a], [b], etc.)
        if not choices:
            lettered = re.findall(r'(?:^|\n)\s*\[([a-zA-Z])\]\s*([^\n]+)', text, re.MULTILINE)
            if lettered:
                choices = [letter for letter, _ in lettered]

        return choices[:10]  # Limit to 10 choices

    def _determine_response_type(
        self,
        has_question: bool,
        has_choices: bool,
        seems_complete: bool,
        has_error: bool
    ) -> str:
        """Determine the type of response needed."""
        if has_error:
            return 'error'
        if seems_complete:
            return 'completion'
        if has_choices:
            return 'multiple_choice'
        if has_question:
            # Check if it's a yes/no question or open-ended
            return 'yes_no_question'  # Simplified for now
        return 'continuation'

    def _respond_to_choice(self, choices: List[str], task_description: str) -> str:
        """Respond to multiple choice questions."""
        if not choices:
            return "Please proceed with your best judgment."

        # Strategy: Pick the most comprehensive option (usually the last or "all of the above")
        templates = [
            f"Let's go with option {choices[0]}. Please proceed with that approach.",
            f"Option {choices[0]} sounds good. Please implement that.",
            f"I'd prefer option {choices[0]}. Continue with that approach.",
            f"Please proceed with option {choices[0]}.",
        ]

        # If there are many options, tend to pick the first or a middle one
        if len(choices) >= 3:
            # 40% first, 40% middle, 20% last
            rand = random.random()
            if rand < 0.4:
                selected = choices[0]
            elif rand < 0.8:
                selected = choices[len(choices) // 2]
            else:
                selected = choices[-1]
        else:
            selected = choices[0]

        return random.choice(templates).replace(choices[0], selected)

    def _respond_to_yes_no(self, claude_response: str, task_description: str) -> str:
        """Respond to yes/no questions."""
        response_lower = claude_response.lower()

        # Bias towards "yes" for implementation questions
        implementation_keywords = ['implement', 'add', 'create', 'should i', 'would you like']
        if any(keyword in response_lower for keyword in implementation_keywords):
            responses = [
                "Yes, please proceed with that.",
                "Yes, that sounds good. Please continue.",
                "Yes, go ahead with the implementation.",
                "Yes, please implement that feature.",
                "That would be great. Please proceed.",
            ]
        else:
            # For other questions, give neutral/positive responses
            responses = [
                "Yes, please continue.",
                "That works. Please proceed.",
                "Sounds good. Keep going.",
                "Yes, go ahead.",
            ]

        return random.choice(responses)

    def _respond_to_open_question(self, claude_response: str, task_description: str) -> str:
        """Respond to open-ended questions."""
        response_lower = claude_response.lower()

        # Extract key question words
        if 'how' in response_lower:
            return "Please use your best judgment based on best practices. Proceed with what you think is best."
        elif 'what' in response_lower:
            return "Choose the approach that follows industry best practices. Continue with your recommendation."
        elif 'where' in response_lower:
            return "Place it where it makes the most sense organizationally. Use standard conventions for the project."
        elif 'which' in response_lower:
            return "Select the option that is most maintainable and follows best practices. Proceed with that."
        else:
            return "Use your best judgment and proceed with the implementation. Follow standard best practices."

    def _respond_to_error(self, claude_response: str) -> str:
        """Respond to error situations."""
        responses = [
            "I see the error. Please try an alternative approach and continue.",
            "Let's work around that issue. Please try a different method.",
            "Please resolve the error using an alternative approach, then continue with the task.",
            "Try to fix the error and proceed. Use a different approach if needed.",
            "Please address the error and continue with the implementation.",
        ]
        return random.choice(responses)

    def _respond_to_completion(self) -> str:
        """Respond when Claude indicates completion."""
        responses = [
            "Great! Please make sure everything is complete and all tests pass.",
            "Excellent work. Please verify everything is working correctly.",
            "Good job! Please double-check the implementation and run any tests.",
            "Nice! Please ensure the implementation is production-ready.",
            "Well done. Please make a final review and confirm completion.",
        ]
        return random.choice(responses)

    def _respond_general_continuation(self, iteration: int) -> str:
        """General continuation prompts."""
        if iteration < 5:
            responses = [
                "Please continue with the implementation.",
                "Keep going. Please proceed with the next steps.",
                "Continue with the task.",
                "Please move forward with the implementation.",
            ]
        elif iteration < 10:
            responses = [
                "Good progress. Please continue with the remaining work.",
                "You're making good progress. Keep going.",
                "Nice work so far. Please finish the remaining tasks.",
                "Excellent. Please complete the remaining implementation.",
            ]
        else:
            responses = [
                "We're getting close. Please finish up the remaining work.",
                "Almost there. Please complete the final tasks.",
                "Great progress. Please wrap up the implementation.",
                "Nearly done. Please finalize everything.",
            ]

        return random.choice(responses)

    def should_continue_conversation(
        self,
        claude_response: str,
        interaction_count: int,
        max_interactions: int = 20
    ) -> bool:
        """
        Determine if conversation should continue.

        Args:
            claude_response: Latest response from Claude
            interaction_count: Number of interactions so far
            max_interactions: Maximum allowed interactions

        Returns:
            True if should continue, False if should stop
        """
        if interaction_count >= max_interactions:
            return False

        analysis = self.analyze_response(claude_response)

        # Stop if task seems complete and no questions
        if analysis['seems_complete'] and not analysis['has_question']:
            return False

        # Continue if there are questions or work in progress
        return True
