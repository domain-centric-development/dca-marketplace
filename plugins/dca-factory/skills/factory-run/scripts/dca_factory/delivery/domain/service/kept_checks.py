"""What a stage that changes files must keep: its hand-overs list every file it changed, the tests that existed before
the story still expect what they did, and every test is the version the test stage saw fail."""

from __future__ import annotations

import typing

from ....building_blocks import DomainService
from ..gateway.stage_evidence import StageEvidence
from ..model.stage import PIPELINE, Pipeline, StageName, Trait
from ..model.stage_story import MappedTest, Presence, StageStory, TestChange, Unobserved
from ..model.story_state import Detail
from ..model.verdict import CheckName, Finding, Findings, Said

FILES_LISTED = CheckName("files-listed")
TESTS_KEPT = CheckName("tests-kept")
RED_PROOF = CheckName("red-proof")

#: How a changed test is named in a finding.
SUFFIX = {TestChange.CHANGED: "", TestChange.REMOVED: " (removed)", TestChange.SWITCHED_OFF: " (switched off)"}
LISTING = frozenset(s.name for s in PIPELINE if Trait.LISTS in s.traits)


class KeptChecks(DomainService):
    """The checks over what a stage changed."""

    @staticmethod
    def files_listed(story: StageStory, stage: StageName, tests: typing.Tuple[MappedTest, ...],
                     evidence: StageEvidence) -> Findings:
        """The test, build and tidy hand-overs name every file the stage changed, so the next stage can read those
        instead of searching — checked against what the stage changed, never against the claim. A test file the
        stage put back to the version the test stage saw red is not the stage's change to list: it was restored, not
        changed."""
        facts = evidence.stage_changes(story.story, stage, tests)
        name = stage.value
        own = Pipeline.hand_over(stage)
        hand_over = own.value if own else "?"
        if facts.unobserved is Unobserved.STAGE_OPEN:
            return (FILES_LISTED.skip(Said(f"the {name} stage is still open — its changed-files record is written at "
                                           f"its end, and the gate after the stage checks it")),)
        if facts.unobserved is Unobserved.NO_RECORD:
            return (FILES_LISTED.skip(Said(f"no changed-files record for {name} — the stage was not snapshotted")),)
        if facts.unobserved is Unobserved.NOT_OBSERVED:
            return (FILES_LISTED.skip(Said(f"the {name} stage's changes were not observed — {facts.reason.value}")),)
        changed = [p.value for p in facts.changed]
        if facts.listed is None:
            if not changed:
                # A tidy that found nothing to tidy has nothing to list; the record says so, not the hand-over.
                return (FILES_LISTED.ok(Said(f"the {name} stage changed no file, so {hand_over} has nothing to "
                                             f"list")),)
            return (FILES_LISTED.fail(Said(f"{hand_over} has no `## Files` section (nor a `## Changed` or `## Moves` "
                                           f"table) — list every file the stage changed, one line each")),)
        listed = {p.value for p in facts.listed}
        read = " / ".join(h.value for h in facts.hand_overs)
        missing = [p for p in changed if p not in listed and not any(p.endswith("/" + n) for n in listed)]
        restored = [p for p in missing if any(r.value == p for r in facts.restored)]
        missing = [p for p in missing if p not in restored]
        if missing:
            return (FILES_LISTED.fail(Said(f"{read} does not list what the stage changed: {', '.join(missing[:8])}"
                                           + (" …" if len(missing) > 8 else ""))),)
        found: typing.List[Finding] = []
        put_back = (f"; {', '.join(restored)} restored to the version the test stage saw red — a restoration is not "
                    f"this stage's change to list") if restored else ""
        unchanged = sorted(n for n in listed if "/" in n and n not in changed
                           and not any(p.endswith("/" + n) or p == n for p in changed))
        if unchanged:
            found.append(FILES_LISTED.note(Said(f"listed but not changed by this stage: {', '.join(unchanged[:5])}")))
        found.append(FILES_LISTED.ok(Said(f"{read} list(s) the {len(changed) - len(restored)} file(s) the stage "
                                          f"changed{put_back}")))
        return tuple(found)

    @staticmethod
    def tests_kept(story: StageStory, evidence: StageEvidence) -> Findings:
        """A test that existed before the story keeps every line it expected; it changes only where a decision is
        about it, or where the story says that behaviour changes and the plan lists the test with what backs it."""
        kept = evidence.kept_tests(story.story)
        if kept is None:
            return (TESTS_KEPT.skip(Said("no baseline of the tests that existed before this story (the plan gate "
                                         "records one in a git repository)")),)
        found: typing.List[Finding] = []
        if kept.lost:
            found.append(TESTS_KEPT.skip(Said(
                f"the baseline of {', '.join(p.value for p in kept.lost)} is gone from the object store (pruned by "
                f"`git gc`?) — not compared")))
        if kept.arranged:
            found.append(TESTS_KEPT.note(Said(
                f"{', '.join(p.value for p in kept.arranged)} changed only around its assertions — every assertion it "
                f"had is still there, at most with more arguments (a type the test builds gained a field)")))
        for test in kept.renamed:
            names = ", ".join(f"{r.was.value} → {r.now.value} ("
                              + ("named in a glossary" if r.in_glossary is Presence.PRESENT else "in no glossary")
                              + ")" for r in test.renames)
            found.append(TESTS_KEPT.note(Said(
                f"{test.place.value} follows a rename the story made — {names}; every assertion it had holds under "
                f"the new name")))
        if not kept.changed:
            found.append(TESTS_KEPT.ok(Said("no test that existed before this story changed what it expects")))
            return tuple(found)
        entries = [(test.place.value, test.place.value + SUFFIX[test.how]) for test in kept.changed]
        # A decision changes the tests it is about, not any test: one the test or the build stage asked about a
        # test, one whose record names the file, or — for a plan's question — the tests the re-plan lists.
        decided = evidence.decided_tests(story.story)
        planned = {change.place.value: change.cites.value for change in evidence.planned_test_changes(story.story)}

        def covers(rel: str) -> bool:
            return rel in planned or any((record.stage in LISTING) or rel.rsplit("/", 1)[-1] in record.text.value
                                         for record in decided)

        named = [entry for _rel, entry in entries]
        if decided and all(covers(rel) for rel, _entry in entries):
            found.append(TESTS_KEPT.ok(Said(f"{', '.join(named)} changed on decision "
                                            f"{', '.join(r.record.value for r in decided)}")))
            return tuple(found)
        # The story may say itself that behaviour changes (`## Changed expectations`); the plan names the tests that
        # change with it (`## Changed tests`), each backed by that section or by a decision a human answered.
        story_says = story.changed_expectations.value > 0
        answered = {record.value for record in evidence.answered_records(story.story)}
        backed, unbacked, unlisted = [], [], []
        for rel, entry in entries:
            if rel not in planned:
                unlisted.append(entry)
            elif story_says or any(rid in planned[rel] for rid in answered):
                backed.append(entry)
            else:
                unbacked.append(entry)
        if backed and not unbacked and not unlisted:
            found.append(TESTS_KEPT.ok(Said(
                f"{', '.join(backed)} changed as the plan lists, backed by "
                + ("the story's `## Changed expectations`" if story_says else "an answered decision"))))
            return tuple(found)
        if unlisted:
            found.append(TESTS_KEPT.fail(Said(
                f"{', '.join(unlisted)} existed before this story and no longer expects what it did, and the plan's "
                f"`## Changed tests` does not list it. Keep the old lines and add a case — or, where the story changes "
                f"that behaviour, the plan lists the test with what backs the change.")))
        if unbacked:
            found.append(TESTS_KEPT.fail(Said(
                f"{', '.join(unbacked)} is listed under the plan's `## Changed tests`, but nothing a human wrote backs "
                f"it: the story has no `## Changed expectations`, and the row cites no answered decision. The plan "
                f"stage asks (one record listing the tests), and the row cites its id.")))
        return tuple(found)

    @staticmethod
    def stale(moved: typing.Tuple[Detail, ...], decided: Presence, reproof: Presence) -> typing.Tuple[Detail, ...]:
        """The tests whose red proof no longer holds: changed since the test stage saw them fail — none where an
        answered decision of the test stage changed what they expect, or where a tidy re-proves them on the tree the
        test stage left."""
        return () if decided is Presence.PRESENT or reproof is Presence.PRESENT else moved

    @staticmethod
    def red_proof(story: StageStory, stage: StageName, tests: typing.Tuple[MappedTest, ...],
                  evidence: StageEvidence) -> Findings:
        """At build and tidy: every test's red proof was taken against the test as it is now."""
        proof = evidence.red_proof(story.story, stage, tests)
        if proof is None:
            return ()
        if proof.reproof is Presence.PRESENT:
            return (RED_PROOF.ok(Said("tidy changed a test it may rework — `red-reproof` runs it on the tree the "
                                      "test stage left")),)
        entries, unbound = proof.entries.value, proof.unbound.value
        if unbound and unbound == entries:
            return (RED_PROOF.skip(Said("the red record names no test-file digests (written by an older gate) — "
                                        "whether a test changed since it was seen failing is not checked")),)
        if not proof.moved:
            return (RED_PROOF.ok(Said(f"{entries - unbound} test(s) are the version that was seen failing")),)
        moved = ", ".join(m.value for m in proof.moved)
        decided = evidence.decided_tests(story.story)
        if not KeptChecks.stale(proof.moved, Presence.PRESENT if decided else Presence.ABSENT, proof.reproof):
            return (RED_PROOF.ok(Said(f"{moved} changed after it was seen failing, on decision "
                                      f"{', '.join(r.record.value for r in decided)}")),)
        return (RED_PROOF.fail(Said(
            f"{moved} changed after the test stage saw it fail — the red proof is about the earlier version, so its "
            f"green now proves nothing. The test stage runs again and records it red as it is; a change of what it "
            f"expects is a human's decision.")),)
