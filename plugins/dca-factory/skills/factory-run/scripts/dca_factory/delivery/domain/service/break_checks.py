"""What a break of the production code proves: a test that is green without ever having been seen red — one an
adoption wrote, one strengthened after its build, a rule's test green already — works when one change to the code
turns it red."""

from __future__ import annotations

import enum
import typing

from ....building_blocks import DomainService, Value
from ..model.stage import StoryKind
from ..model.stage_story import Place, Presence, Selector, StageStory
from ..model.story_state import Detail
from ..model.verdict import CheckName, Finding, FindingState, Findings, Said

BREAK_PROOF = CheckName("break-proof")
INVARIANT_BREAKS = CheckName("invariant-breaks")
ADOPT = CheckName("adopt")
ADOPT_JUDGED = CheckName("adopt-judged")
RED_REPROOF = CheckName("red-reproof")


class BreakOutcome(enum.Enum):
    """What a test did under its break: red, green, nothing to tell — or the break did not apply."""

    RED = "red"
    GREEN = "green"
    UNCHECKED = "unchecked"
    UNAPPLIED = "unapplied"


class BreakResult(Value):
    outcome: BreakOutcome
    said: Detail


class RuleProof(enum.Enum):
    """How a rule's unit test is shown to guard it: red before the build, red under its break, green under it, no
    break that applies, or no verdict."""

    RED = "red"
    KILLED = "killed"
    SURVIVED = "survived"
    NO_BREAK = "no-break"
    UNCHECKED = "unchecked"


class BreakChecks(DomainService):
    """The break proofs and the adopt gate's own checks."""

    @staticmethod
    def verdict(seen: Findings) -> BreakResult:
        """The outcome of a break's run from its `tests-red` findings. A note — red on a timeout — gives no verdict of
        its own: red is red, and the note travels with it."""
        verdicts = [f for f in seen if f.state in (FindingState.PASS, FindingState.FAIL)]
        notes = [f.said.value for f in seen if f.state is FindingState.NOTE]
        if verdicts and all(f.state is FindingState.PASS for f in verdicts):
            return BreakResult(BreakOutcome.RED, Detail((" — " + notes[0][:300]) if notes else ""))
        if any(f.state is FindingState.FAIL and ("passes" in f.said.value or "is green" in f.said.value
                                                 or "green before" in f.said.value) for f in verdicts):
            return BreakResult(BreakOutcome.GREEN, Detail(""))
        said = "; ".join(f.said.value for f in seen if f.state is not FindingState.PASS)[:300]
        return BreakResult(BreakOutcome.UNCHECKED, Detail(said or "no run of it was recorded"))

    @staticmethod
    def proof(selector: Selector, key: Detail, result: typing.Optional[BreakResult], missing: Place) -> Finding:
        """A break proof of one test: `result` None where the test has no break, `missing` where it belongs."""
        name = f"{selector.value} ({key.value})"
        if result is None:
            return BREAK_PROOF.fail(Said(
                f"{name}: no break at {missing.value} — a test that is green without ever being seen red (one an "
                f"adoption wrote, one strengthened after its build) is shown to work by one change to the code that "
                f"turns it red"))
        if result.outcome is BreakOutcome.RED:
            return BREAK_PROOF.ok(Said(f"{name}: red under its break, on a scratch copy{result.said.value}"))
        if result.outcome is BreakOutcome.GREEN:
            return BREAK_PROOF.fail(Said(f"{name}: stays green under its break — the test does not notice the "
                                         f"behaviour it claims to prove"))
        if result.outcome is BreakOutcome.UNAPPLIED:
            return BREAK_PROOF.fail(Said(f"{name}: its break does not apply — {result.said.value}"))
        return BREAK_PROOF.fail(Said(f"{name}: its break could not be checked — {result.said.value}"))

    @staticmethod
    def rule_proof(before: BreakResult, under: typing.Optional[BreakResult]) -> RuleProof:
        """A rule's test: seen red before the build it proves the rule as a criterion's red run does; green already —
        the rule exists — it needs its break (`under`, None where it has none)."""
        if before.outcome is BreakOutcome.RED:
            return RuleProof.RED
        if before.outcome is not BreakOutcome.GREEN:
            return RuleProof.UNCHECKED
        if under is None:
            return RuleProof.NO_BREAK
        return {BreakOutcome.RED: RuleProof.KILLED, BreakOutcome.GREEN: RuleProof.SURVIVED,
                BreakOutcome.UNAPPLIED: RuleProof.NO_BREAK}.get(under.outcome, RuleProof.UNCHECKED)

    @staticmethod
    def invariant(selector: Selector, key: Detail, proof: RuleProof, missing: Place, said: Detail) -> Finding:
        """A survived or missing break is refused."""
        name = f"{selector.value} ({key.value})"
        if proof is RuleProof.RED:
            return INVARIANT_BREAKS.ok(Said(f"{name}: red before the build — the rule is new, its test saw it missing"))
        if proof is RuleProof.KILLED:
            return INVARIANT_BREAKS.ok(Said(f"{name}: green already, red under its break on a scratch copy"))
        if proof is RuleProof.SURVIVED:
            return INVARIANT_BREAKS.fail(Said(f"{name}: stays green under its break — the test does not guard the rule "
                                              f"it names"))
        if proof is RuleProof.NO_BREAK:
            return INVARIANT_BREAKS.fail(Said(
                f"{name}: green before the build, so the rule exists already, and no break applies at {missing.value} "
                f"— one change to the production code that turns exactly this test red"))
        return INVARIANT_BREAKS.fail(Said(f"{name}: no run gave it a verdict — {said.value[:300]}"))

    @staticmethod
    def adopted(story: StageStory) -> Findings:
        """The adopt gate is for an adopted story."""
        if story.kind is StoryKind.ADOPT:
            return ()
        return (ADOPT.fail(Said("the adopt gate is for a story with `status: adopted`")),)

    @staticmethod
    def adopt_judged(verdict: Detail) -> Finding:
        """A fresh judge confirms that each mapped test asserts its scenario before the story counts as adopted."""
        if verdict.value != "pass":
            return ADOPT_JUDGED.fail(Said("judge.md carries no `verdict: pass` — a fresh judge confirms that each mapped "
                                          "test asserts its scenario before the story counts as adopted"))
        return ADOPT_JUDGED.ok(Said("the judge confirmed that the tests prove the scenarios"))

    @staticmethod
    def nothing_written() -> Finding:
        return BREAK_PROOF.skip(Said("the adoption wrote no test of its own — every scenario maps to an existing test, "
                                     "which the judge read"))

    @staticmethod
    def reproof_uncompiled(moved: typing.Tuple[Selector, ...], said: Detail) -> Finding:
        """Tidy's tests that do not compile on the tree the test stage left call production code tidy renamed."""
        return RED_REPROOF.fail(Said(
            f"{', '.join(s.value for s in moved)}: tidy changed the test(s), and they do not compile on the tree the "
            f"test stage left — a test calls production code tidy renamed, which is a change of what it tests:\n"
            f"{said.value}"))

    @staticmethod
    def reproof(selector: Selector, result: BreakResult, timed_out: Presence) -> Finding:
        """A test tidy changed is red again on the tree the test stage left — on an assertion, not a timeout."""
        name = selector.value
        if result.outcome is BreakOutcome.RED and timed_out is Presence.ABSENT:
            return RED_REPROOF.ok(Said(f"{name}: changed by tidy, red again on the tree the test stage left"))
        if result.outcome is BreakOutcome.RED:
            return RED_REPROOF.fail(Said(f"{name}: changed by tidy, and red on the test stage's tree only on a timeout "
                                         f"— an action waited, no assertion failed, so the moved test proves nothing "
                                         f"yet"))
        if result.outcome is BreakOutcome.GREEN:
            return RED_REPROOF.fail(Said(f"{name}: changed by tidy, and green on the tree the test stage left — the move "
                                         f"changed what it asserts; put it back, a change of what it expects is a "
                                         f"human's decision"))
        return RED_REPROOF.fail(Said(f"{name}: changed by tidy, and no run on the test stage's tree gave it a verdict "
                                     f"— {result.said.value}"))
