"""What a story does to the spec: its plan's delta agrees with what the spec's rules derive, a change of what holds
has a person behind it, every test the spec names is still there, and the story's commit holds them all."""

from __future__ import annotations

import typing

from ....building_blocks import DomainService
from ..gateway.stage_evidence import StageEvidence
from ..model.stage_story import MappedTest, StageStory
from ..model.verdict import CheckName, Findings, Said

SPEC_DELTA = CheckName("spec-delta")
SPEC_TESTS = CheckName("spec-tests")
TESTS_COMMITTED = CheckName("tests-committed")


class SpecChecks(DomainService):
    """The checks between a story and the spec."""

    @staticmethod
    def delta(story: StageStory, evidence: StageEvidence) -> Findings:
        """What follows from comparing the story with the spec the spec's rules derive; what the plan names must agree
        with it, and every change or removal of what holds needs a person's sentence behind it — the plan stage asks
        where there is none."""
        delta = evidence.spec_delta(story)
        if delta is None:
            return ()
        target = delta.target.value
        if delta.problems:
            return (SPEC_DELTA.fail(Said(f"{delta.plan.value} `## Spec delta` against {target}: "
                                         + "; ".join(p.value for p in delta.problems))),)
        if delta.touched:
            touched = ", ".join(k.value for k in delta.touched)
            backing = evidence.spec_backing(story)
            if backing is None:
                return (SPEC_DELTA.fail(Said(
                    f"the story changes or removes what holds ({touched} in {target}) and no person said so — no "
                    f"`## Changed expectations` in the story, no answered decision. The plan stage asks (one record "
                    f"naming the keys); the answer backs it.")),)
            return (SPEC_DELTA.ok(Said(f"{touched} changed or removed in {target}, backed by {backing.value}")),)
        return (SPEC_DELTA.ok(Said(f"{delta.adds.value} added, {delta.holds.value} held in {target} — nothing that "
                                   f"holds changes")),)

    @staticmethod
    def tests(story: StageStory, tests: typing.Tuple[MappedTest, ...], evidence: StageEvidence) -> Findings:
        """Every `Test:` line of the spec the story changes still names a test that is there — one this story renamed
        or moved is named under tests.md's `## Moved tests` (or is the story's own criterion), and the gate writes
        the new selector at delivery."""
        found = evidence.spec_tests(story, tests)
        if found is None:
            return ()
        if found.absent_moved:
            return (SPEC_TESTS.fail(Said(
                f"tests.md's `## Moved tests` names a test that is not there: "
                f"{'; '.join(a.value for a in found.absent_moved)} — a row names the test as it is now, not the one "
                f"it replaced")),)
        if not found.wanted.value:
            return ()
        target = found.target.value
        if found.missing:
            return (SPEC_TESTS.fail(Said(
                f"{target} names a test that is gone: {'; '.join(m.value for m in found.missing)} — a test this story "
                f"renamed or moved goes under tests.md's `## Moved tests` (| <key> | <Class>#<method> |)")),)
        return (SPEC_TESTS.ok(Said(f"every test line of {target} names a test that is there")),)

    @staticmethod
    def committed(story: StageStory, tests: typing.Tuple[MappedTest, ...], evidence: StageEvidence) -> Findings:
        """What the main line takes is the story's commit, not its worktree: every test the story maps, and every one
        a `Test:` line of its spec names, sits in a file that commit holds as the worktree has it."""
        commit = evidence.story_commit(story, tests)
        if commit is None:
            return ()
        head = commit.head.value
        if commit.missing:
            return (TESTS_COMMITTED.fail(Said(
                f"the story's commit {head} lacks what its tests need: {'; '.join(m.value for m in commit.missing)} — "
                f"the worktree has the file, the main line would not: a file the stages made goes into the commit when "
                f"a hand-over lists it (tests.md's `## Files`); an ignored one is the person's to add (`git add -f`) "
                f"or to un-ignore")),)
        return (TESTS_COMMITTED.ok(Said(f"the story's commit {head} holds every test file its mapping and its spec "
                                        f"name ({commit.files.value})")),)
