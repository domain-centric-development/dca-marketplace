"""A story's route through its stages: which stage runs how from where it starts, and where it goes once a gate, a
stage or the judge sent it back — decided over the stage table and what the run says, never over a file."""

from __future__ import annotations

import enum
import typing

from ....building_blocks import DomainService, Value
from ..model.stage import PIPELINE, Pipeline, Stage, StageName, StoryKind, Trait, Window
from ..model.story_state import Detail, GateReport, HandOverText, MAX_ROUNDS, Rounds, VerdictWord

JUDGE, TEST = StageName("judge"), StageName("test")


class Move(enum.Enum):
    """How the run takes a stage of the route."""

    SKIP = "skip"           # the story's kind does not run it
    STAGE = "stage"         # a process of its own
    BUILDER = "builder"     # the shared builder starts here and carries the rest of its window
    CARRIED = "carried"     # carried by the shared builder started before it
    VERIFIER = "verifier"   # the shared verifier carries the rest of the route


class Around(enum.Enum):
    """What the run does around a stage."""

    PAUSE = "pause"             # the requests about other stories are worked before it
    GATE_BEFORE = "gate-before"  # its gate runs before it
    REVIEWS = "reviews"         # the reviews run before it, one process per perspective
    GATE_AFTER = "gate-after"   # its gate runs once its file is written
    VERDICT = "verdict"         # the judge's verdict decides what comes after it


class RouteStep(Value):
    """One stage of the route and how the run takes it; `skipped` says why a kind does not run it."""

    stage: StageName
    move: Move
    around: typing.FrozenSet[Around]
    skipped: typing.Optional[Detail] = None


class Judged(enum.Enum):
    """What the judge's verdict means for the run."""

    PASS = "pass"                       # on to the document stage
    AGAIN = "changes-requested"         # a round back to the stage the judge names
    CONFLICT = "story-conflict"         # the story or the plan is wrong: a person decides
    MISSING = "missing"                 # no `verdict:` line: the judge stage is not finished
    UNKNOWN = "unknown"                 # a word that is none of the three


class Refusal(enum.Enum):
    """What the integrate gate refused the story for on the main line."""

    MOVED = "moved"             # nothing but the main line moving on meanwhile
    MAIN_TESTS = "main-tests"   # the resolution dropped what the main line added to a test
    CHECKOUT = "checkout"       # the main checkout could not take the story


#: Why a kind runs no stage of the builder: what a person reads beside the skipped stage.
SKIP_REASONS = {StoryKind.JOURNEY: "a journey builds nothing", StoryKind.ADOPT: "an adopted story is not built",
                StoryKind.TASK: "a task has no criterion to test — the existing suite is its evidence"}
#: The kinds that change the code, so the review perspectives have a change to read before the judge; an adoption
#: changes nothing.
REVIEWED_KINDS = frozenset((StoryKind.STORY, StoryKind.JOURNEY, StoryKind.TASK))

ENVIRONMENT = "gate:fail environment"
FAILED, CLOSING = "gate:fail ", "gate:fail story "


def row(name: StageName) -> typing.Optional[Stage]:
    return next((s for s in PIPELINE if s.name == name), None)


class StoryRoute(DomainService):
    """The route of one story run."""

    @staticmethod
    def steps(kind: StoryKind, start: StageName, shared: typing.FrozenSet[Window]) -> typing.Tuple[RouteStep, ...]:
        """The stages from <start> on in the run order, each with how it runs: skipped where the kind does not run it,
        the builder's stages in one process where it is shared, the verifier's likewise — the route ends with it."""
        steps: typing.List[RouteStep] = []
        started, built = False, False
        for stage in (s for s in PIPELINE if Trait.IN_ORDER in s.traits):
            started = started or stage.name == start
            if not started:
                continue
            carried = Window.BUILDER in shared and stage.window is Window.BUILDER
            around = {Around.PAUSE} if stage.name == start or not carried else set()
            if kind not in stage.kinds:
                why = SKIP_REASONS.get(kind, f"a {kind.value} story does not run it")
                steps.append(RouteStep(stage.name, Move.SKIP, frozenset(around), Detail(why)))
                continue
            if Trait.GATED in stage.traits and Trait.POST_GATED not in stage.traits:
                around.add(Around.GATE_BEFORE)
            if carried:
                steps.append(RouteStep(stage.name, Move.CARRIED if built else Move.BUILDER, frozenset(around)))
                built = True
                continue
            if stage.name == JUDGE and kind in REVIEWED_KINDS:
                around.add(Around.REVIEWS)
            if Window.VERIFIER in shared and stage.window is Window.VERIFIER:
                steps.append(RouteStep(stage.name, Move.VERIFIER, frozenset(around)))
                break
            if Trait.POST_GATED in stage.traits:
                around.add(Around.GATE_AFTER)
            if stage.name == JUDGE:
                around.add(Around.VERDICT)
            steps.append(RouteStep(stage.name, Move.STAGE, frozenset(around)))
        return tuple(steps)

    @staticmethod
    def applying(asked: StageName, applies: StageName) -> StageName:
        """The stage that applies an answer: the one the answer names (`applies: test` — an answer that changes a
        test goes back to the test stage, whoever asked), else the stage that asked."""
        return applies if applies in Pipeline.order(StoryKind.STORY) else asked

    @staticmethod
    def resumes_at(asked: StageName, applies: StageName) -> StageName:
        """Where the story resumes for an answer: the earlier of the stage that asked and the one the answer names.
        A plan's question answered `applies: test` still re-plans — the plan lists the tests that change — and the
        test stage after it takes the changed expectation."""
        order = Pipeline.order(StoryKind.STORY)
        named = StoryRoute.applying(asked, applies)
        if asked not in order:
            return named
        return min((asked, named), key=lambda stage: order.index(stage) if stage in order else len(order))

    @staticmethod
    def window(kind: StoryKind, window: Window, start: typing.Optional[StageName] = None) -> typing.Tuple[StageName, ...]:
        """The stages a shared window carries for the kind — from <start> on where one is named."""
        carried, on = [], start is None
        for stage in (s for s in PIPELINE if s.window is window):
            on = on or stage.name == start
            if on and kind in stage.kinds:
                carried.append(stage.name)
        return tuple(carried)

    @staticmethod
    def red_check(kind: StoryKind, start: StageName) -> typing.Optional[StageName]:
        """Where a story that starts at <start> goes when its red proof went stale — the test stage, the only one that
        records it again — or None where the start does not rest on it: a stage that lists no files, the red stage
        itself, a kind that runs no tests."""
        found, test = row(start), row(TEST)
        if found is None or test is None or Trait.LISTS not in found.traits or Trait.RED in found.traits \
                or kind not in test.kinds:
            return None
        return TEST

    @staticmethod
    def converged(rounds: Rounds) -> typing.Optional[Detail]:
        """Where the rounds did not converge, why — None while another round may run."""
        if rounds.value >= MAX_ROUNDS:
            return Detail(f"{MAX_ROUNDS} rounds did not converge")
        return None

    @staticmethod
    def again_from(refused: StageName, resumes: typing.Optional[StageName]) -> StageName:
        """The stage a refused gate's round starts at: the refused stage, or an earlier one the story's state resumes
        at — whose file it reads as an earlier pass's."""
        for stage in (s.name for s in PIPELINE if Trait.IN_ORDER in s.traits):
            if stage == refused:
                break
            if stage == resumes:
                return stage
        return refused

    @staticmethod
    def judged_back(kind: StoryKind, judge: HandOverText) -> StageName:
        """Where the judge's `changes-requested` sends the story: `back: test` — a confirmed defect is in a test, which
        only the test stage may change — to the test stage, anything else to the build; for a kind without that
        stage, the builder stage before it (`back_for`)."""
        for line in judge.value.splitlines():
            if line.strip().lower().startswith("back:"):
                named = line.split(":", 1)[1].strip().strip("`\"' ").lower()
                return StoryRoute.back_for(kind, StageName("test") if named == "test" else StageName("build"))
        return StoryRoute.back_for(kind, StageName("build"))

    @staticmethod
    def back_for(kind: StoryKind, stage: StageName) -> StageName:
        """Where a round goes back to: <stage>, or the last builder stage before it the kind runs."""
        found = row(stage)
        if found is not None and kind in found.kinds:
            return stage
        back = stage
        for builder in (s for s in PIPELINE if s.window is Window.BUILDER):
            if kind in builder.kinds:
                back = builder.name
            if builder.name == stage:
                break
        return back

    @staticmethod
    def judged(verdict: VerdictWord) -> Judged:
        if not verdict.value:
            return Judged.MISSING
        return next((judged for judged in Judged if judged.value == verdict.value), Judged.UNKNOWN)

    @staticmethod
    def environment(report: GateReport) -> typing.Optional[Detail]:
        """A refusal whose cause is the machine, not the story — no stage can put a tool on the PATH, so it counts no
        round: its reason; None for a refusal of the story."""
        lines = report.value.splitlines()
        if not any(line.startswith(ENVIRONMENT) for line in lines):
            return None
        return Detail(next((line[len(ENVIRONMENT + " — "):] for line in lines
                            if line.startswith(ENVIRONMENT + " — ")), ""))

    @staticmethod
    def integration(report: GateReport) -> typing.FrozenSet[Refusal]:
        """What the checks that failed on the main line say — not the report's closing `gate:fail story` line: only
        that the main line moved on, or that a test of the main line lost its side, or that the checkout could not
        take the story; empty for a refusal of the story itself."""
        fails = [line for line in report.value.splitlines() if line.startswith(FAILED) and not line.startswith(CLOSING)]
        if fails and all(line.startswith(FAILED + Refusal.MOVED.value) for line in fails):
            return frozenset((Refusal.MOVED,))
        return frozenset(refusal for refusal in (Refusal.MAIN_TESTS, Refusal.CHECKOUT)
                         if any(line.startswith(FAILED + refusal.value) for line in fails))
