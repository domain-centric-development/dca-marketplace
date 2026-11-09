"""What a gate's own runs of the profile's commands prove: the build compiles, the stage's commands pass, and the
test commands the policy requires run whole and green — a red test outside the story run again alone once."""

from __future__ import annotations

import typing

from ....building_blocks import Value
from .story_words import Count
from .suite_run import Requirement, SUITE, SuiteRun
from .story_state import Detail
from .verdict import CheckName, Finding, Findings, Said  # noqa: F401

FLAKY = CheckName("flaky")
TEST = CheckName("test")


class SuiteJudged(Value):
    """The findings of a suite's run, and the tests noted flaky."""

    findings: Findings
    flaky: typing.Tuple[Detail, ...]

    @classmethod
    def of(cls, suite: SuiteRun, requirement: Requirement) -> SuiteJudged:
        """A test command passes only when its reports show it executed tests and none failed. A red test outside the
        story that is green on its own run is noted flaky and counts as green; red again, the run stays red."""
        found: typing.List[Finding] = []
        if suite.still:
            first = suite.still[0]
            found.append(SUITE.note(Said(
                f"{', '.join(r.test.value for r in suite.still)} — outside this story's change (not written, changed "
                f"or named in its table), red again on its own run (`{first.alone.value}`): the suite is red, not "
                f"this story's code alone")))
        for retried in suite.flaky:
            found.append(FLAKY.note(Said(
                f"flaky {retried.test.value} — red in `{suite.run.command.value}`, green on its own run "
                f"(`{retried.alone.value}`); a test this story did not write, change or name, so no round is counted")))
        run, key = suite.run, suite.key.value
        executed, failed = suite.executed.value, suite.failed.value
        if run.code.value != 0 or failed:
            found.append(requirement.red(TEST, Said(f"`{run.command.value}` ({key}) failed — {failed} failing "
                                                    f"case(s):\n{run.output.value}")))
        elif executed:
            found.append(TEST.ok(Said(f"`{run.command.value}` ({key}) ran {executed} case(s), none "
                                      f"failed{run.reused.value}")))
        elif suite.exit_code_only:
            found.append(TEST.skip(Said(f"`{run.command.value}` ({key}) exited 0 and writes no report "
                                        f"(`testEvidence: exit-code`) — nothing shows a test ran")))
        else:
            said = Said(f"`{run.command.value}` ({key}) exited 0, but no report written by this run shows an executed "
                        f"test — a runner that matched nothing exits 0 too")
            found.append({Requirement.REQUIRED: TEST.fail, Requirement.OPTIONAL: TEST.note,
                          Requirement.UNDECLARED: TEST.skip}[requirement](said))
        return cls(tuple(found), tuple(r.test for r in suite.flaky))

    @staticmethod
    def retries(failed: Count, own: Count) -> bool:
        """Whether the red tests of a run are run again, each alone: some and at most FLAKY_LIMIT, none of them the
        story's own — a red test of the story's own stands as it is. Green alone, a test is flaky and the run counts
        green; red again, the run stays red."""
        return 0 < failed.value <= FLAKY_LIMIT.value and own.value == 0



#: How many red tests outside the story a gate runs again, each alone, once (WP-113): a whole suite red in a test the
#: story did not write, change or name, green alone, was the suite's load or order, not this story — the gate passes
#: with `flaky <test>` noted. More red tests than this outside the story is a broken suite, not a flake.
FLAKY_LIMIT = Count(3)
