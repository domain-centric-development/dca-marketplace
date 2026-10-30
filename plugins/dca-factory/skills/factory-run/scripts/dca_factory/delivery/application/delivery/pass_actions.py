"""What a passing gate does, per stage: the plan's marks, the red tree, the acceptance and the delivery, the
integration — through the output port StageDelivery."""

from __future__ import annotations

from ...domain.model.stage_story import Presence
from ...domain.model.story_state import Detail
from ...domain.service.acceptance_rules import AcceptanceRules
from ...domain.service.adopt_checks import AdoptChecks, Adoption
from .check_stage import on_pass, Run
from .pipeline_rules import rule

DELIVERED_LEFT = "a delivered story is checked and its marks are left as they are"


def delivered(run: Run) -> bool:
    return bool(run.story.status.value == "delivered")


@on_pass("plan", rule=(
    rule("GATE-PASS-PLAN", "the plan gate passed for a story not yet delivered",
         "what the later gates compare against is taken once, when the plan holds",
         ok="the story's digest, the baseline of the tests that existed before it (once per story, in git) and the "
            "plan's signal are recorded", note=DELIVERED_LEFT, reports=("story",)),
    rule("GATE-PASS-ADOPT", "the plan gate passed and the plan's `## Adopt` holds",
         "what already holds is adopted, not built again",
         ok="whole: the story becomes `status: adopted` and runs the adopt path; split: the held scenarios move to "
            "a story `<id>-holds` with `status: adopted`, this one builds the rest", reports=("plan-adopts",)),
))
def _plan_passed(run: Run) -> None:
    if delivered(run):
        # Delivered is delivered: a plan gate run over a delivered story (a check, a re-verification) leaves the
        # story and the marks the delivery rests on as they are.
        run.result.note("story", f"{run.story_id} is delivered — checked, its marks are left as they are")
    else:
        run.delivery.plan_marks(run.story_id, run.story_path)
        adoption = run.evidence.plan_adoption(run.story.story)
        outcome = AdoptChecks.outcome(run.story, adoption)
        if adoption is not None and outcome is not Adoption.NONE:
            run.delivery.adopt(run.result, run.story_id, run.story_path,
                               [(row.key.value, row.test.value) for row in adoption.rows], outcome is Adoption.WHOLE)


@on_pass("test", rule=rule(
    "GATE-PASS-RED-TREE", "the test gate passed for a story (kind `story`) not yet delivered",
    "tidy's moved tests are proven red again on the tree the test stage left",
    ok="the tree is recorded as the red tree — kept as it was when a test was let through green", reports=()))
def _test_passed(run: Run) -> None:
    if run.kind == "story" and not delivered(run):
        run.delivery.red_tree(run.result, run.story_id)


@on_pass("document", rule=(
    rule("GATE-ACCEPTANCE", "the document gate passed for a story that is not a task, and the profile's "
                            "`acceptance:` takes it (`all`, or `pages` with a browser test)",
         "a person looks at what a story shows before it counts as delivered",
         ok="the acceptance record says accepted — the delivery goes on",
         fail="the acceptance asks for a correction — written into the story, which runs again from plan",
         wait="no acceptance yet: a record `accept-<n>.md` is written beside the story and the story waits (exit 3)"),
    rule("GATE-DELIVER", "the document or adopt gate passed and nothing failed",
         "a story is delivered by the gate that last checked it, never by a stage",
         ok="in the story's worktree: delivered once integrated (the runner's integrate step); in the checkout: "
            "the delivery is written — the spec merged, `status: delivered`, the judge's confirmed findings kept",
         fail="the spec after the story would not hold its shape — nothing is written",
         note=DELIVERED_LEFT, reports=("integrate", "spec", "delivered", "findings", "story")),
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


@on_pass("adopt", rule=rule(
    "GATE-PASS-ADOPTED", "the adopt gate passed for a story not yet delivered",
    "an adopted story is delivered like a built one, its tests the evidence",
    ok="in the worktree: delivered once integrated; in the checkout: the delivery is written as for a built story",
    reports=("integrate",)))
def _adopt_passed(run: Run) -> None:
    if delivered(run):
        return
    if run.delivery.in_worktree():
        run.result.ok("integrate", f"every check passed — {run.story_id} is adopted once its tests are integrated into "
                                   f"the main checkout (the runner's integrate step)")
        return
    run.delivery.deliver(run.result, run.story_id, run.story_path, run.front)


@on_pass("integrate", rule=rule(
    "GATE-INTEGRATED", "the integrate gate passed in the story's worktree",
    "the main line moves only by a fast-forward of a story that held every gate on it",
    ok="with `claim_remote:` the story is published as one commit on its claim branch; else the main checkout "
       "fast-forwards to the story's commit, the delivery is written and committed (`chore(<context>): deliver <id>`)",
    fail="the main checkout is on another branch, the target moved (merged again), or the commit failed",
    reports=("published", "checkout", "moved", "integrated", "committed")))
def _integrate_passed(run: Run) -> None:
    run.delivery.integrate(run.result, run.story_id, run.story_path, run.front, run.close)
