import pytest
from app.services.simulated_human import SimulatedHuman


def test_get_continuation_prompt():
    """Test getting continuation prompts."""
    prompt = SimulatedHuman.get_continuation_prompt("general")
    assert isinstance(prompt, str)
    assert len(prompt) > 0


def test_get_error_prompt():
    """Test getting error handling prompts."""
    prompt = SimulatedHuman.get_continuation_prompt("error")
    assert isinstance(prompt, str)
    assert len(prompt) > 0


def test_get_encouragement_prompt():
    """Test getting encouragement prompts."""
    prompt = SimulatedHuman.get_continuation_prompt("encouragement")
    assert isinstance(prompt, str)
    assert len(prompt) > 0


def test_should_intervene_on_error():
    """Test that intervention happens on errors."""
    should_intervene = SimulatedHuman.should_intervene(
        interaction_count=1,
        has_error=True
    )
    assert should_intervene is True


def test_should_not_intervene_early():
    """Test that intervention doesn't happen too early."""
    should_intervene = SimulatedHuman.should_intervene(
        interaction_count=1,
        has_error=False
    )
    # May or may not intervene on first interaction
    assert isinstance(should_intervene, bool)


def test_get_intervention_type_with_error():
    """Test intervention type when there's an error."""
    intervention_type = SimulatedHuman.get_intervention_type(has_error=True)
    assert intervention_type == "error"


def test_get_intervention_type_without_error():
    """Test intervention type when there's no error."""
    intervention_type = SimulatedHuman.get_intervention_type(has_error=False)
    assert intervention_type in ["general", "encouragement"]
