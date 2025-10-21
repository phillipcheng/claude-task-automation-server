import random
from typing import List


class SimulatedHuman:
    """Simulates human responses to encourage Claude to continue working."""

    CONTINUATION_PROMPTS = [
        "Please continue with the implementation.",
        "Great progress! Please proceed with the next steps.",
        "Looking good. Continue with the remaining tasks.",
        "Nice work. Please keep going.",
        "Excellent. What's next?",
        "Continue, please.",
        "Please proceed.",
        "Keep going with the implementation.",
        "Continue with the next part.",
        "Please move forward with the task.",
    ]

    ENCOURAGEMENT_PROMPTS = [
        "Good job so far. Please continue.",
        "This looks promising. Keep working on it.",
        "You're on the right track. Please continue.",
        "Great! Please finish the remaining parts.",
        "Nice work. Complete the implementation.",
    ]

    ERROR_HANDLING_PROMPTS = [
        "I see there's an issue. Please try to fix it and continue.",
        "Let's address that error and move forward.",
        "Please resolve the error and proceed.",
        "Try a different approach to fix this issue.",
    ]

    @staticmethod
    def get_continuation_prompt(context: str = "general") -> str:
        """
        Get a simulated human prompt to encourage continuation.

        Args:
            context: Context of the interaction (general, error, encouragement)

        Returns:
            A simulated human instruction
        """
        if context == "error":
            prompts = SimulatedHuman.ERROR_HANDLING_PROMPTS
        elif context == "encouragement":
            prompts = SimulatedHuman.ENCOURAGEMENT_PROMPTS
        else:
            prompts = SimulatedHuman.CONTINUATION_PROMPTS

        return random.choice(prompts)

    @staticmethod
    def should_intervene(interaction_count: int, has_error: bool = False) -> bool:
        """
        Determine if simulated human should intervene.

        Args:
            interaction_count: Number of interactions so far
            has_error: Whether there's an error in recent responses

        Returns:
            True if should intervene
        """
        # Always intervene on errors
        if has_error:
            return True

        # Intervene every 3-5 interactions to encourage continuation
        if interaction_count > 0 and interaction_count % random.randint(3, 5) == 0:
            return True

        return False

    @staticmethod
    def get_intervention_type(has_error: bool = False) -> str:
        """
        Determine type of intervention.

        Args:
            has_error: Whether there's an error

        Returns:
            Intervention type (general, error, encouragement)
        """
        if has_error:
            return "error"

        # 30% chance of encouragement, 70% general continuation
        return "encouragement" if random.random() < 0.3 else "general"
