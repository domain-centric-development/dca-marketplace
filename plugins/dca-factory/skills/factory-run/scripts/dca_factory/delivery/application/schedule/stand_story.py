"""Where one story stands: its facts read through the port, decided by the domain."""

from __future__ import annotations

from ...domain.model.story_state import Standing
from ...domain.service.story_standing import StoryStanding
from ..shared.story_facts import StoryFacts


def stand_story(facts: StoryFacts) -> Standing:
    """The story's standing: from its front alone where it does not run, else from its run as well."""
    front = facts.front()
    return StoryStanding.before_run(front) or StoryStanding.in_run(front, facts.run(front))
