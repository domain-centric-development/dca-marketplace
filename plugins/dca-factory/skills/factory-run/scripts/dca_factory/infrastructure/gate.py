"""The gate's use cases, wired to the project's files — the project <cwd>, its epics under <epics>, its profile —, a
gate run over one story with every check the stage table registers, and the record-keeping commands the runner gives
the gate (a window's start and end, the tree a story's diff is taken against, what a stage changed)."""

from __future__ import annotations

import os
import typing

from ..delivery.adapter.outgoing.stack.commands import MISSING_TOOLS
from ..delivery.adapter.outgoing.stack.stage_runs import StageRunFiles
from ..delivery.adapter.outgoing.files.criteria_files import criteria_of
from ..delivery.adapter.outgoing.files.gate_journal import close_record, journal_gate
from ..delivery.adapter.outgoing.files.migrations import layout_hint
from ..delivery.adapter.outgoing.files.owned_files import observe_writes, owned_end, record_owned
from ..delivery.adapter.outgoing.files.snapshots import record_base, record_changes
from ..delivery.adapter.outgoing.files.backlog_entry_files import BacklogEntryFiles
from ..delivery.adapter.outgoing.files.stage_delivery_files import StageDeliveryFiles
from ..delivery.adapter.outgoing.files.stage_evidence_files import (
    DecisionStampFiles, MainLineEvidence, StageEvidenceFiles, stage_story)
from ..delivery.adapter.outgoing.files.stage_marks_files import StageMarkFiles
from ..delivery.adapter.outgoing.files.story_layout import find_story, story_folder, story_kind
from ..delivery.adapter.outgoing.files.test_files import StageTestFiles
from ..delivery.adapter.outgoing.git.change import ChangeIndexFiles, ParityReportFiles
from ..delivery.adapter.outgoing.pipeline.stage_rows import STAGE
from ..delivery.application.backlog.check_backlog import CheckBacklogUseCase
from ..delivery.application.delivery import pass_actions  # noqa: F401 — registers what a passing gate does
from ..delivery.application.delivery import process_checks  # noqa: F401 — registers the checks that run processes
from ..delivery.application.delivery import stage_checks  # noqa: F401 — registers the checks over the evidence alone
from ..delivery.application.delivery.check_change import CheckChangeUseCase
from ..delivery.application.delivery.check_parity import CheckParityUseCase
from ..delivery.application.delivery.check_stage import run_checks, run_passed, StageRun, Verdict
from ..delivery.domain.model.verdict import Findings
from ..delivery.domain.service.profile_checks import ProfileChecks
from ..sharedkernel.adapter.outgoing.markdown.front_matter import GateError, read_front_matter
from .description import check_description

Profile = typing.Mapping[str, typing.Any]
#: The gate's report of a run over a story, said for the story's id; its exit.
Report = typing.Callable[[typing.Optional[str]], int]


def check_backlog(cwd: str, epics: str, profile: typing.Mapping[str, typing.Any]) -> CheckBacklogUseCase:
    return CheckBacklogUseCase(BacklogEntryFiles(epics), StageEvidenceFiles(cwd, "", epics, profile))


def check_change(cwd: str, profile: typing.Mapping[str, typing.Any]) -> CheckChangeUseCase:
    return CheckChangeUseCase(profile, ChangeIndexFiles(cwd), StageRunFiles(cwd, "", profile))


def check_parity() -> CheckParityUseCase:
    return CheckParityUseCase(ParityReportFiles())


def stage_run(close: typing.Callable[[StageRun], None], **fields: typing.Any) -> StageRun:
    """What one gate run over a story knows: the fields the gate read, the story, its evidence and its contract from
    them, and the ports its checks reach the project through; `close` journals a delivery's last events."""
    run: typing.Any = StageRun(**fields)
    run.kind = story_kind(run.front)
    run.evidence = StageEvidenceFiles(run.cwd, run.runs, run.args.epics, run.profile)
    run.tests = StageTestFiles(run.cwd, run.runs, run.profile)
    run.main_line = MainLineEvidence(run.cwd, run.runs, run.args.epics, run.profile)
    run.marks = StageMarkFiles(run.cwd, run.runs, run.kind)
    run.stamps = DecisionStampFiles(run.runs)
    run.describe = check_description(run.cwd, run.profile)
    run.runs_port = StageRunFiles(run.cwd, run.runs, run.profile)
    run.delivery = StageDeliveryFiles(run.cwd, run.runs, run.profile)
    run.close = lambda: close(run)
    run.story = stage_story(run.story_id, run.story_path, run.front, run.body, run.criteria)
    run.contract = ProfileChecks.contract_number(run.evidence)
    # a journey is a guard over what is delivered: green at its test gate, the inverse of a story
    run.expected = "red" if run.stage.red and run.kind == "story" else "green"
    return typing.cast(StageRun, run)


def contract_findings(profile: Profile) -> Findings:
    """The profile's contract and its unknown keys (`ProfileChecks.contract`)."""
    return ProfileChecks.contract(StageEvidenceFiles(".", "", "", profile))


def model_findings(profile: Profile) -> Findings:
    """The profile's model keys, each bound to a tool (`ProfileChecks.models`)."""
    return ProfileChecks.models(StageEvidenceFiles(".", "", "", profile))


def layout_note(cwd: str, profile: Profile) -> typing.Optional[str]:
    """An older layout, named: `factory.sh update` migrates it."""
    return layout_hint(cwd, profile)


def missing_tools() -> typing.List[typing.Tuple[str, str]]:
    """The tools a command of this gate run found missing on the PATH, each with the command that missed it."""
    return list(MISSING_TOOLS)


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


def gate_story(result: Verdict, args: typing.Any, cwd: str, profile: Profile, report: Report) -> int:
    """One gate run over a story: its file read, the stage's checks over it, a passing gate's actions, the run
    journaled — a file the gate cannot read refused as `gate`."""
    story_path = story_id = None
    try:
        story_path = find_story(args.epics, args.story)
        front, body = read_front_matter(story_path)
        story_id = str(front.get("id") or os.path.basename(story_folder(story_path)))
        observe_writes(args.runs, story_id)
        criteria = criteria_of(story_path, body, front)
        run = stage_run(close_record, result=result, args=args, cwd=cwd, runs=args.runs, stage=STAGE[args.stage],
                        story_id=story_id, story_path=story_path, front=front, body=body, criteria=criteria,
                        profile=profile)
        run_checks(run)
    except GateError as error:
        result.fail("gate", str(error))
        return journal_gate(result, args, story_id, story_path, report(args.story))
    if not result.failed:
        run_passed(run)
    return journal_gate(result, args, story_id, story_path, report(story_id))
