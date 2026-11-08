"""The runner's exit codes and the run's outcomes, one table both ways — a process's exit read as an outcome, an
outcome given back as the runner's exit."""

from __future__ import annotations

import typing

from ....application.shared.run_outcome import GateOutcome, MergeOutcome, RunOutcome

#: The runner's exit for each outcome (`run_command.py` documents them).
EXITS: typing.Dict[RunOutcome, int] = {
    RunOutcome.RAN_THROUGH: 0,
    RunOutcome.FAILED: 1,
    RunOutcome.NOT_SET_UP: 2,
    RunOutcome.WAITS_FOR_PERSON: 3,
    RunOutcome.AT_LIMIT: 4,
    RunOutcome.CHECKOUT_TAKEN: 5,
    RunOutcome.CHANGED_UNDER_IT: 7,
}
OUTCOMES: typing.Dict[int, RunOutcome] = {code: outcome for outcome, code in EXITS.items()}


def exit_of(outcome: RunOutcome) -> int:
    return EXITS[outcome]


def outcome_of(code: int) -> RunOutcome:
    """A process's exit as an outcome — any exit the table does not name is a failure."""
    return OUTCOMES.get(code, RunOutcome.FAILED)


def maybe_outcome_of(code: typing.Optional[int]) -> typing.Optional[RunOutcome]:
    return None if code is None else outcome_of(code)


def maybe_exit_of(outcome: typing.Optional[RunOutcome]) -> typing.Optional[int]:
    return None if outcome is None else exit_of(outcome)


def gate_outcome_of(code: int) -> GateOutcome:
    """A gate's exit: 0 passed, 3 waits for a person's acceptance, anything else refused — a gate that is not there
    refuses too."""
    if code == 0:
        return GateOutcome.PASSED
    return GateOutcome.WAITS_FOR_PERSON if code == 3 else GateOutcome.REFUSED


def merge_outcome_of(code: int) -> MergeOutcome:
    """A merge's exit: 0 merged, 3 stopped on conflicts, anything else failed."""
    if code == 0:
        return MergeOutcome.MERGED
    return MergeOutcome.CONFLICTS if code == 3 else MergeOutcome.FAILED
