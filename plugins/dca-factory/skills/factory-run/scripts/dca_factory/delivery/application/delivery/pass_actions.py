"""What a passing gate does, per stage: the plan's marks, the red tree, the acceptance and the delivery, the
integration — through the output port StageDelivery."""

from __future__ import annotations

from ....building_blocks import DomainException
from ...domain.model.stage_story import Presence
from ...domain.model.verdict import Said
from ...domain.model.acceptance import ACCEPTANCE, AcceptanceStep
from ...domain.service.adopt_checks import AdoptChecks, Adoption
from ..shared.stage_delivery import Landing
from .check_stage import on_pass, Run
from .adopt_on_plan import AdoptOnPlanCommand
from .deliver_story import DeliverStoryCommand

DELIVERED_LEFT = "a delivered story is checked and its marks are left as they are"


def delivered(run: Run) -> bool:
    return bool(run.story.content.written_status.value == "delivered")


def deliver(run: Run, landing: Landing) -> bool:
    """The delivery a passing gate makes: what goes before the story's state — the spec merged, a task's findings
    closed —, the story delivered by the gate through its aggregate (`run.deliveries`, one input port per landing),
    what is kept beside it. False where any of it refused, the reason in the verdict."""
    result = run.result
    if not run.delivery.prepare(result, run.story_id, run.story_path, run.front, landing):
        return False
    try:
        done = run.deliveries[landing].execute(DeliverStoryCommand(run.story.id, run.now()))
    except DomainException as refused:
        result.fail("delivered", str(refused))
        return False
    run.delivery.delivered(result, run.story_id, run.story_path, run.front, done.delivery, landing)
    return not result.failed


def integrate(run: Run) -> None:
    """The story where it lands — the main checkout takes its commit, or its own checkout is published —, delivered
    there, and handed on: committed on the main line, or its branch pushed."""
    landing = run.delivery.landing()
    if not run.delivery.take_in(run.result, run.story_id, run.story_path, landing):
        return
    if deliver(run, landing):
        run.delivery.hand_on(run.result, run.story_id, run.story_path, run.front, landing, run.close)


@on_pass("plan", rule=(
    "GATE-PASS-PLAN",
    "GATE-PASS-ADOPT",
))
def _plan_passed(run: Run) -> None:
    if delivered(run):
        # Delivered is delivered: a plan gate run over a delivered story (a check, a re-verification) leaves the
        # story and the marks the delivery rests on as they are.
        run.result.note("story", f"{run.story_id} is delivered — checked, its marks are left as they are")
    else:
        run.delivery.plan_marks(run.story_id, run.story_path)
        adoption = run.evidence.plan_adoption(run.story.id)
        outcome = AdoptChecks.outcome(run.story, adoption)
        if adoption is not None and outcome is Adoption.WHOLE:
            try:
                run.adoptions.execute(AdoptOnPlanCommand(run.story.id, adoption, run.now()))
            except DomainException as refused:
                run.result.fail("plan-adopts", str(refused))
                return
            run.delivery.adopted(run.result, run.story_id, run.story_path)
        elif adoption is not None and outcome is not Adoption.NONE:
            run.delivery.split_off(run.result, run.story_id, run.story_path,
                                   [(row.key.value, row.test.value) for row in adoption.rows])


@on_pass("test", rule="GATE-PASS-RED-TREE")
def _test_passed(run: Run) -> None:
    if run.kind == "story" and not delivered(run):
        run.delivery.red_tree(run.result, run.story_id)


@on_pass("document", rule=(
    "GATE-ACCEPTANCE",
    "GATE-DELIVER",
))
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
            step = AcceptanceStep.at_delivery(facts.acceptance)
            result.take(step.findings)
            if step.ask is Presence.PRESENT:
                asked, where, refused = run.delivery.ask(story_id, story_path, run.criteria)
                if refused is not None:
                    result.fail("acceptance", refused)
                    return
                result.take((ACCEPTANCE.wait(Said(f"{asked} asks a human to accept the story before it is delivered — "
                                                   f"{where}, answered through /factory-decisions")),))
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
    deliver(run, Landing.STORY)


@on_pass("adopt", rule="GATE-PASS-ADOPTED")
def _adopt_passed(run: Run) -> None:
    if delivered(run):
        return
    if run.delivery.in_worktree():
        run.result.ok("integrate", f"every check passed — {run.story_id} is adopted once its tests are integrated into "
                                   f"the main checkout (the runner's integrate step)")
        return
    deliver(run, Landing.STORY)


@on_pass("integrate", rule="GATE-INTEGRATED")
def _integrate_passed(run: Run) -> None:
    integrate(run)
