"""What judges a stage stays out of its reach: a plan announces the guarded paths it will change, each with a reason;
a stage that changed a guarded path the plan did not announce is refused and puts it back."""

from __future__ import annotations

import typing

from ....building_blocks import DomainService
from ..gateway.stage_evidence import StageEvidence
from ..model.story import Story
from ..model.story_words import Place
from ..model.verdict import CheckName, Findings, Said
from .delivery_checks import PIPELINE

GUARDED = CheckName("guarded")


def _listed(paths: typing.Sequence[Place]) -> Said:
    """At most six paths, as a finding names them."""
    return Said(", ".join(p.value for p in paths[:6]) + (" …" if len(paths) > 6 else ""))


class GuardChecks(DomainService):
    """The plan gate's check of `## Guarded changes`, and the check after every later stage that what judges it is as
    it was."""

    @staticmethod
    def announced(story: Story, evidence: StageEvidence) -> Findings:
        """Every path the plan's `## Guarded changes` names is guarded, and each carries a reason. Silent where the
        plan announces nothing."""
        facts = evidence.guarded(story.id)
        if not facts.announced:
            return ()
        outside = [c.path for c in facts.announced if not facts.guarded.covers(c.path)]
        bare = [c.path for c in facts.announced if not c.reasoned()]
        found = []
        if outside:
            found.append(GUARDED.fail(Said(
                f"`## Guarded changes` names {_listed(outside).value}, which the guarded set ({facts.guarded.named().value}) "
                f"does not hold — the section lists only guarded paths; any other file goes under `## Files`")))
        if bare:
            found.append(GUARDED.fail(Said(
                f"`## Guarded changes` names {_listed(bare).value} without a reason — each guarded change says in one line "
                f"why the story changes what judges it (`- \\`<path>\\` — <reason>`)")))
        if not found:
            found.append(GUARDED.ok(Said(
                f"the plan announces {len(facts.announced)} guarded change(s), each with a reason: "
                f"{_listed([c.path for c in facts.announced]).value} — the acceptance shows their diff first")))
        return tuple(found)

    @staticmethod
    def untouched(story: Story, evidence: StageEvidence) -> Findings:
        """No stage changed a guarded path the plan did not announce; an announced one passes, named. Silent without a
        record of what the story changed."""
        facts = evidence.guarded(story.id)
        if facts.changed is None:
            return ()
        unannounced = facts.unannounced()
        if unannounced:
            return (PIPELINE.fail(Said(
                f"a stage changed what judges it: {_listed(unannounced).value} — guarded ({facts.guarded.named().value}) and "
                f"not announced in the plan's `## Guarded changes`; put it back (git) and the stage runs again. A story "
                f"that has to change it says so in its plan, with the reason")),)
        touched = facts.touched()
        if touched:
            return (PIPELINE.ok(Said(f"the guarded change(s) the plan announced: {_listed(touched).value} — the acceptance "
                                     f"shows their diff")),)
        return (PIPELINE.ok(Said(f"no stage of {story.id.value} changed a guarded path")),)
