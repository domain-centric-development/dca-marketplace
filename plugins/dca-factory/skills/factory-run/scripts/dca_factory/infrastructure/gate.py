"""The gate's composition root: the record-keeping commands the runner gives the gate many times per story — a
window's start and end, the tree a story's diff is taken against, what a stage changed — wired here and light, and
every command that checks something wired in `gate_checks`, loaded on first use: a gate process that only keeps a
record never imports the checks."""

from __future__ import annotations

import typing

from ..delivery.adapter.outgoing.files.owned_files import owned_end, record_owned
from ..delivery.adapter.outgoing.files.snapshots import record_base, record_changes
from ..delivery.adapter.outgoing.git.checkout import Checkouts
from .workflow import load_workflow

# the stages and the rules, from their repositories — once per process, held against every binding
load_workflow()


if typing.TYPE_CHECKING:
    from ..delivery.application.backlog.check_backlog import CheckBacklogInputPort
    from ..delivery.application.delivery.check_change import CheckChangeInputPort
    from ..delivery.application.delivery.check_parity import CheckParityInputPort
    from ..delivery.application.delivery.check_stage import Verdict
    from ..delivery.application.description.check_description import CheckDescriptionInputPort
    from ..delivery.application.profile.check_profile import CheckProfileInputPort

Profile = typing.Mapping[str, typing.Any]
#: The gate's report of a run over a story, said for the story's id; its exit.
Report = typing.Callable[[typing.Optional[str]], int]


# --- what checks something: the checking half, imported on first use ---------------------------------------------


def gate_story(result: Verdict, args: typing.Any, cwd: str, profile: Profile, report: Report,
               checkouts: typing.Optional[Checkouts] = None) -> int:
    from . import gate_checks
    return gate_checks.gate_story(result, args, cwd, profile, report, checkouts)


def check_backlog(cwd: str, epics: str, profile: Profile) -> CheckBacklogInputPort:
    from . import gate_checks
    return gate_checks.check_backlog(cwd, epics, profile)


def check_change(cwd: str, profile: Profile) -> CheckChangeInputPort:
    from . import gate_checks
    return gate_checks.check_change(cwd, profile)


def check_parity() -> CheckParityInputPort:
    from . import gate_checks
    return gate_checks.check_parity()


def check_profile(profile: Profile) -> CheckProfileInputPort:
    """The profile checked on its own — the evidence's reader of it alone, not the checks' whole wiring: `factory.sh`
    asks it before every run."""
    from ..delivery.adapter.outgoing.files.stage_evidence_files import StageEvidenceFiles
    from ..delivery.application.profile.check_profile import CheckProfileUseCase
    return CheckProfileUseCase(StageEvidenceFiles(".", "", "", profile))


def check_description(cwd: str, profile: typing.Mapping[str, str]) -> CheckDescriptionInputPort:
    from . import gate_checks
    return gate_checks.check_description(cwd, profile)


def check_discovery(cwd: str, folder: str, topic: str) -> typing.Tuple[bool, str]:
    from . import gate_checks
    return gate_checks.check_discovery(cwd, folder, topic)


def layout_note(cwd: str, profile: Profile) -> typing.Optional[str]:
    from . import gate_checks
    return gate_checks.layout_note(cwd, profile)


def missing_tools() -> typing.List[typing.Tuple[str, str]]:
    from . import gate_checks
    return gate_checks.missing_tools()


def __getattr__(name: str) -> typing.Any:
    """What a test or a sibling root asks of the checking half by name (`wire_delivery`, `stage_run`, `now`) — never
    what the import machinery asks a module (`__path__`, `__spec__`), which would load the checks for every import."""
    if name.startswith("__"):
        raise AttributeError(name)
    from . import gate_checks
    return getattr(gate_checks, name)


# --- what keeps a record: light, many times per story ---------------------------------------------------------


def window_start(runs: str, story_id: str) -> None:
    """A stage window starts: the person's parts recorded."""
    record_owned(runs, story_id)


def window_end(runs: str, story_id: str, window: str, ran: str) -> int:
    """A stage window ends: the person's parts compared, the hand-overs it wrote journaled."""
    return owned_end(runs, story_id, window, ran)


def story_base(cwd: str, runs: str, story_id: str, checkouts: typing.Optional[Checkouts] = None) -> None:
    """The tree a story's diff is taken against."""
    record_base(cwd, runs, story_id, checkouts)


def stage_changes(cwd: str, runs: str, story_id: str, stage: str) -> None:
    """What a stage changed, from the snapshots."""
    record_changes(cwd, runs, story_id, stage)


class GateCall:
    """The composition root of one gate call: the root's commands, with the checkouts the call stands in — its own,
    or the run's where the runner calls the gate in its process (WP-202). Dropped with the call."""

    def __init__(self, checkouts: Checkouts) -> None:
        self._checkouts = checkouts

    def check_backlog(self, cwd: str, epics: str, profile: Profile) -> CheckBacklogInputPort:
        return check_backlog(cwd, epics, profile)

    def check_change(self, cwd: str, profile: Profile) -> CheckChangeInputPort:
        return check_change(cwd, profile)

    def check_parity(self) -> CheckParityInputPort:
        return check_parity()

    def check_profile(self, profile: Profile) -> CheckProfileInputPort:
        return check_profile(profile)

    def check_description(self, cwd: str, profile: typing.Mapping[str, str]) -> CheckDescriptionInputPort:
        return check_description(cwd, profile)

    def check_discovery(self, cwd: str, folder: str, topic: str) -> typing.Tuple[bool, str]:
        return check_discovery(cwd, folder, topic)

    def gate_story(self, result: Verdict, args: typing.Any, cwd: str, profile: Profile, report: Report) -> int:
        return gate_story(result, args, cwd, profile, report, self._checkouts)

    def layout_note(self, cwd: str, profile: Profile) -> typing.Optional[str]:
        return layout_note(cwd, profile)

    def missing_tools(self) -> typing.List[typing.Tuple[str, str]]:
        return missing_tools()

    def stage_changes(self, cwd: str, runs: str, story_id: str, stage: str) -> None:
        stage_changes(cwd, runs, story_id, stage)

    def story_base(self, cwd: str, runs: str, story_id: str) -> None:
        story_base(cwd, runs, story_id, self._checkouts)

    def window_end(self, runs: str, story_id: str, window: str, ran: str) -> int:
        return window_end(runs, story_id, window, ran)

    def window_start(self, runs: str, story_id: str) -> None:
        window_start(runs, story_id)


def main(argv: typing.Sequence[str], checkouts: typing.Optional[Checkouts] = None) -> int:
    """The gate's command line, given the composition root it builds its use cases from — one per call, with the
    run's checkouts where a run calls it in its process, else the call's own."""
    from ..delivery.adapter.incoming.gate import gate_command
    gate_command.wire(GateCall(checkouts if checkouts is not None else Checkouts()))
    return gate_command.main(argv)
