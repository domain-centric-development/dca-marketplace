"""Where one story stands: its facts read through the port, decided by the domain."""

from __future__ import annotations

from ...domain.model.story_state import Standing
from ...domain.service.story_standing import StoryStanding
from ..shared.story_facts import StoryFacts
from ..delivery.pipeline_rules import decides, rule


@decides(
    rule("RUN-STANDING-1", "before a run", "a story's state is read from its own files",
         ok="ready, in progress or resumable", fail="stopped: owned files changed, a twin, three rounds, a plan "
         "refused, a story conflict", wait="waiting for a record; published, until merged on the remote",
         skip="delivered, superseded, unreleased, or claimed by another factory"),
    rule("RUN-STANDING-2", "a story in a run", "a story resumes where its files say it stopped",
         ok="at the first stage missing, refused, or due to apply an answer; from plan when the story changed "
            "since its plan"),
)
def stand_story(facts: StoryFacts) -> Standing:
    """The story's standing: from its front alone where it does not run, else from its run as well."""
    front = facts.front()
    return StoryStanding.before_run(front) or StoryStanding.in_run(front, facts.run(front))
