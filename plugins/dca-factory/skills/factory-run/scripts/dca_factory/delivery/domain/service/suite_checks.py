"""What a gate's own runs of the profile's commands prove: the build compiles, the stage's commands pass, and the
test commands the policy requires run whole and green — a red test outside the story run again alone once."""

from __future__ import annotations

import typing

from ....building_blocks import DomainService, Value
from ..model.stage_story import CommandKey, CommandRun, Count, Presence, SuiteCommands, SuiteRun
from ..model.story_state import Detail
from ..model.verdict import CheckName, Finding, Findings, Said

SUITE = CheckName("suite")
FLAKY = CheckName("flaky")
TEST = CheckName("test")


class SuiteJudged(Value):
    """The findings of a suite's run, and the tests noted flaky."""

    findings: Findings
    flaky: typing.Tuple[Detail, ...]


def red(check: CheckName, said: Said, must: Presence, strict: Presence) -> Finding:
    """A red check fails the verdict — unless a policy is declared and this check is not in it. Then the policy
    decides: the red run is reported, and it is not what the commit is judged by."""
    if strict is Presence.PRESENT and must is Presence.ABSENT:
        return check.note(Said(said.value + " — optional (not in `required:`), so it does not decide"))
    return check.fail(said)


#: How many red tests outside the story a gate runs again, each alone, once (WP-113): a whole suite red in a test the
#: story did not write, change or name, green alone, was the suite's load or order, not this story — the gate passes
#: with `flaky <test>` noted. More red tests than this outside the story is a broken suite, not a flake.
FLAKY_LIMIT = Count(3)


class SuiteChecks(DomainService):
    """The checks over the gate's own command runs."""

    @staticmethod
    def retries(failed: Count, own_red: Presence) -> Presence:
        """Whether the red tests of a run are run again, each alone: some and at most FLAKY_LIMIT, none of them the
        story's own — a red test of the story's own stands as it is. Green alone, a test is flaky and the run counts
        green; red again, the run stays red."""
        return Presence.PRESENT if 0 < failed.value <= FLAKY_LIMIT.value and own_red is Presence.ABSENT \
            else Presence.ABSENT

    @staticmethod
    def missing(check: CheckName, key: CommandKey) -> Finding:
        return check.skip(Said(f"no `{key.value}:` command in the stack profile"))

    @staticmethod
    def command(check: CheckName, run: CommandRun) -> Finding:
        """A command the stage's gate looks up and runs: it passes or it fails."""
        if run.code.value == 0:
            return check.ok(Said(f"`{run.command.value}` succeeded{run.reused.value}"))
        return check.fail(Said(f"`{run.command.value}` failed:\n{run.output.value}"))

    @staticmethod
    def suite(suite: SuiteRun, required: Presence, strict: Presence) -> SuiteJudged:
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
            found.append(red(TEST, Said(f"`{run.command.value}` ({key}) failed — {failed} failing case(s):\n"
                                        f"{run.output.value}"), required, strict))
        elif executed:
            found.append(TEST.ok(Said(f"`{run.command.value}` ({key}) ran {executed} case(s), none "
                                      f"failed{run.reused.value}")))
        elif suite.exit_code_only is Presence.PRESENT:
            found.append(TEST.skip(Said(f"`{run.command.value}` ({key}) exited 0 and writes no report "
                                        f"(`testEvidence: exit-code`) — nothing shows a test ran")))
        else:
            said = Said(f"`{run.command.value}` ({key}) exited 0, but no report written by this run shows an executed "
                        f"test — a runner that matched nothing exits 0 too")
            found.append(TEST.fail(said) if required is Presence.PRESENT else
                         TEST.note(said) if strict is Presence.PRESENT else TEST.skip(said))
        return SuiteJudged(tuple(found), tuple(r.test for r in suite.flaky))

    @staticmethod
    def required(commands: SuiteCommands) -> Findings:
        """The test commands the policy requires: a required key without its command fails — silently passed, the
        stage gate would certify a suite nobody can run."""
        if not commands.required:
            return ()
        found = [SUITE.fail(Said(f"no `{key.value}:` command in the stack profile — and `{key.value}` is required"))
                 for key, command in commands.declared if key in commands.required and command is None]
        if not any(key in commands.required for key, _command in commands.declared):
            found.append(SUITE.skip(Said("`required:` names no declared test command")))
        return tuple(found)

    @staticmethod
    def task(commands: SuiteCommands) -> Findings:
        """A task proves itself on the existing suite: the profile has to declare a test command."""
        if any(command is not None for _key, command in commands.declared):
            return ()
        return (SUITE.fail(Said("a task proves itself on the existing suite, and the stack profile declares no test "
                                "command — declare `test:` (and its siblings)")),)
