"""What a passing gate does, per stage: the plan's marks, the red tree, the acceptance and the delivery, the
integration — through the output port StageDelivery."""

from __future__ import annotations

from ...domain.model.stage_story import Presence
from ...domain.model.story_state import Detail
from ...domain.service.acceptance_rules import AcceptanceRules
from .check_stage import on_pass, Run


def delivered(run: Run) -> bool:
    return bool(run.story.status.value == "delivered")


@on_pass("plan")
def _plan_passed(run: Run) -> None:
    if delivered(run):
        # Delivered is delivered: a plan gate run over a delivered story (a check, a re-verification) leaves the
        # story and the marks the delivery rests on as they are.
        run.result.note("story", f"{run.story_id} is delivered — checked, its marks are left as they are")
    else:
        run.delivery.plan_marks(run.story_id, run.story_path)


@on_pass("test")
def _test_passed(run: Run) -> None:
    if run.kind == "story" and not delivered(run):
        run.delivery.red_tree(run.result, run.story_id)


@on_pass("document")
def _document_passed(run: Run) -> None:
    result, story_id, story_path = run.result, run.story_id, run.story_path
    if delivered(run):
        # Delivered is delivered: a document gate run over a delivered story checks it and leaves the story's
        # `delivered:` date as it is.
        result.note("story", f"{story_id} is delivered — checked, its marks are left as they are")
        return
    if run.kind != "task":
        facts = run.delivery.acceptance(story_id, story_path)
        if facts.refused is not None:
            result.fail("acceptance", facts.refused)
            return
        if facts.applies and facts.acceptance is not None:
            step = AcceptanceRules.at_delivery(facts.acceptance)
            result.take(step.findings)
            if step.ask is Presence.PRESENT:
                asked, where, refused = run.delivery.ask(story_id, story_path, run.criteria)
                if refused is not None:
                    result.fail("acceptance", refused)
                    return
                result.take(AcceptanceRules.asked(Detail(asked), Detail(where)))
            if step.goes_on is Presence.ABSENT:
                return
    if result.failed:
        return
    if run.delivery.in_worktree():
        # In its worktree a story is delivered when its code is on the main line: the integrate step merges it,
        # holds it to the gate once more, and the integrate gate writes the delivery.
        result.ok("integrate", f"every check passed — {story_id} is delivered once its worktree is integrated into "
                               f"the main checkout (the runner's integrate step)")
        return
    run.delivery.deliver(result, story_id, story_path, run.front)


@on_pass("adopt")
def _adopt_passed(run: Run) -> None:
    if delivered(run):
        return
    if run.delivery.in_worktree():
        run.result.ok("integrate", f"every check passed — {run.story_id} is adopted once its tests are integrated into "
                                   f"the main checkout (the runner's integrate step)")
        return
    run.delivery.deliver(run.result, run.story_id, run.story_path, run.front)


@on_pass("integrate")
def _integrate_passed(run: Run) -> None:
    run.delivery.integrate(run.result, run.story_id, run.story_path, run.front, run.close)
