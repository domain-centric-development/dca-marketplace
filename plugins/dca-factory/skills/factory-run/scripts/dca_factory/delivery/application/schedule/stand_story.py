"""Where one story stands: its facts read through the port, decided by the domain."""

from __future__ import annotations

from ...domain.model.story_state import Standing
from ...domain.service.story_standing import StoryStanding
from ..shared.story_facts import StoryFacts
from ..delivery.pipeline_rules import decides
from ..delivery.pipeline_workflow import workflow


@decides(
    "RUN-STANDING-1",
    "RUN-STANDING-2",
)
def stand_story(facts: StoryFacts) -> Standing:
    """The story's standing: from its front alone where it does not run, else from its run as well."""
    front = facts.front()
    return StoryStanding.before_run(front) or StoryStanding(workflow()).in_run(front, facts.run(front))
