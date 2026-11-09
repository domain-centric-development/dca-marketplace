"""The gate's composition root: the record-keeping commands the runner gives the gate many times per story — a
window's start and end, the tree a story's diff is taken against, what a stage changed — wired here and light, and
every command that checks something wired in `gate_checks`, loaded on first use: a gate process that only keeps a
record never imports the checks."""

from __future__ import annotations

import typing

from ..delivery.adapter.outgoing.files.owned_files import owned_end, record_owned
from ..delivery.adapter.outgoing.files.snapshots import record_base, record_changes
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


def gate_story(result: Verdict, args: typing.Any, cwd: str, profile: Profile, report: Report) -> int:
    from . import gate_checks
    return gate_checks.gate_story(result, args, cwd, profile, report)


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


def story_base(cwd: str, runs: str, story_id: str) -> None:
    """The tree a story's diff is taken against."""
    record_base(cwd, runs, story_id)


def stage_changes(cwd: str, runs: str, story_id: str, stage: str) -> None:
    """What a stage changed, from the snapshots."""
    record_changes(cwd, runs, story_id, stage)


def main(argv: typing.Sequence[str]) -> int:
    """The gate's command line, given the composition root it builds its use cases from."""
    from ..delivery.adapter.incoming.gate import gate_command
    from . import gate as root
    gate_command.wire(root)
    return gate_command.main(argv)
