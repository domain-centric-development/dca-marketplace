"""The gate's checking half, wired to the project's files — the project <cwd>, its epics under <epics>, its profile
—: a gate run over one story with every check the stage table registers, the backlog's, the change's and the
profile's checks. Loaded only when a command checks something (`gate.__getattr__`); the record-keeping commands the
runner gives many times per story stay in `gate` and never load it."""

from __future__ import annotations

import os
import time
import typing

from ..delivery.adapter.outgoing.stack.commands import MISSING_TOOLS
from ..delivery.adapter.outgoing.git.checkout import Checkouts
from ..delivery.adapter.outgoing.stack.stage_runs import StageRunFiles
from ..delivery.adapter.outgoing.files.criteria_files import criteria_of
from ..delivery.adapter.outgoing.files.gate_journal import close_record, journal_gate
from ..delivery.adapter.outgoing.files.migrations import layout_hint
from ..delivery.adapter.outgoing.files.owned_files import observe_writes
from ..delivery.adapter.outgoing.files.backlog_entry_files import BacklogEntryFiles
from ..delivery.adapter.outgoing.files.delivery_writes import checkout_epics
from ..delivery.adapter.outgoing.files.journal_events import FileTransactions, JournalEventPublisher
from ..delivery.adapter.outgoing.files.stage_delivery_files import StageDeliveryFiles
from ..delivery.adapter.outgoing.files.story_files import StoryFiles
from ..delivery.adapter.outgoing.files.stage_evidence_files import (
    DecisionStampFiles, MainLineEvidence, StageEvidenceFiles)
from ..delivery.adapter.outgoing.files.story_files import story_of
from ..delivery.adapter.outgoing.files.stage_marks_files import StageMarkFiles
from ..delivery.adapter.outgoing.files.story_layout import find_story, story_folder, story_kind
from ..delivery.adapter.outgoing.files.test_files import StageTestFiles
from ..delivery.adapter.outgoing.git.change import ChangeIndexFiles, ParityReportFiles
from ..delivery.adapter.outgoing.pipeline.stage_rows import stage_named
from ..delivery.application.backlog.check_backlog import CheckBacklogUseCase
from ..delivery.application.delivery import pass_actions  # noqa: F401 — registers what a passing gate does
from ..delivery.application.delivery import process_checks  # noqa: F401 — registers the checks that run processes
from ..delivery.application.delivery import stage_checks  # noqa: F401 — registers the checks over the evidence alone
from ..delivery.application.delivery.check_change import CheckChangeUseCase
from ..delivery.application.delivery.check_parity import CheckParityUseCase
from ..delivery.application.delivery.check_stage import run_checks, run_passed, StageRun, Verdict
from ..delivery.adapter.outgoing.files.acceptance_record_files import AcceptanceRecordFiles
from ..delivery.adapter.outgoing.files.decision_record_files import DecisionRecordFiles
from ..delivery.application.delivery.adopt_on_plan import AdoptOnPlanUseCase
from ..delivery.application.delivery.apply_answer import ApplyAnswerUseCase
from ..delivery.application.delivery.ask_acceptance import AskAcceptanceUseCase
from ..delivery.application.delivery.deliver_story import DeliverStoryUseCase
from ..delivery.application.delivery.split_off_on_plan import SplitOffOnPlanUseCase
from ..delivery.application.shared.stage_delivery import Landing
from ..delivery.domain.model.moment import Moment
from ..discovery.api import check_report
from ..sharedkernel.adapter.outgoing.markdown.front_matter import GateError, read_front_matter
from .workflow import load_workflow

# the stages and the rules, from their repositories — once per process, held against every binding
load_workflow()
from .description import check_description as check_description

Profile = typing.Mapping[str, typing.Any]
#: The gate's report of a run over a story, said for the story's id; its exit.
Report = typing.Callable[[typing.Optional[str]], int]


def check_backlog(cwd: str, epics: str, profile: typing.Mapping[str, typing.Any]) -> CheckBacklogUseCase:
    return CheckBacklogUseCase(BacklogEntryFiles(epics), StageEvidenceFiles(cwd, "", epics, profile))


def check_change(cwd: str, profile: typing.Mapping[str, typing.Any]) -> CheckChangeUseCase:
    return CheckChangeUseCase(profile, ChangeIndexFiles(cwd), StageRunFiles(cwd, "", profile))


def check_parity() -> CheckParityUseCase:
    return CheckParityUseCase(ParityReportFiles())


def stage_run(close: typing.Callable[[StageRun], None], checkouts: typing.Optional[Checkouts] = None,
              **fields: typing.Any) -> StageRun:
    """What one gate run over a story knows: the fields the gate read, the story, its evidence and its contract from
    them, and the ports its checks reach the project through — those that ask git where the checkout is through the
    call's `checkouts`; `close` journals a delivery's last events."""
    checkouts = checkouts if checkouts is not None else Checkouts()
    run: typing.Any = StageRun(**fields)
    run.kind = story_kind(run.front)
    run.evidence = StageEvidenceFiles(run.cwd, run.runs, run.args.epics, run.profile, checkouts)
    run.tests = StageTestFiles(run.cwd, run.runs, run.profile)
    run.main_line = MainLineEvidence(run.cwd, run.runs, run.args.epics, run.profile)
    run.marks = StageMarkFiles(run.cwd, run.runs, run.kind, checkouts)
    run.describe = check_description(run.cwd, run.profile)
    run.runs_port = StageRunFiles(run.cwd, run.runs, run.profile)
    wire_delivery(run, checkouts)
    run.close = lambda: close(run)
    run.story = story_of(run.story_path, run.front, run.body, run.criteria)
    run.contract = run.evidence.gate().reads(run.evidence.declared_contract())
    # a journey is a guard over what is delivered: green at its test gate, the inverse of a story
    run.expected = "red" if run.stage.red and run.kind == "story" else "green"
    return typing.cast(StageRun, run)


def now() -> Moment:
    """This moment, as the factory stamps it."""
    return Moment(time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))


def wire_delivery(run: typing.Any, checkouts: typing.Optional[Checkouts] = None) -> None:
    """The ports a passing gate delivers through: its writes, the story delivered by the gate — where the gate read
    it, and in the story's own checkout for a published delivery —, the clock."""
    run.delivery = StageDeliveryFiles(run.cwd, run.runs, run.profile, checkouts)
    events, transactions = JournalEventPublisher(run.runs), FileTransactions()
    run.deliveries = {
        Landing.STORY: DeliverStoryUseCase(StoryFiles(run.cwd, run.args.epics), events, transactions),
        Landing.CHECKOUT: DeliverStoryUseCase(StoryFiles(run.cwd, checkout_epics(run.cwd, run.args.epics)), events, transactions),
    }
    run.adoptions = AdoptOnPlanUseCase(StoryFiles(run.cwd, run.args.epics), events, transactions)
    run.splits = SplitOffOnPlanUseCase(StoryFiles(run.cwd, run.args.epics), events, transactions)
    run.answers = ApplyAnswerUseCase(DecisionRecordFiles(run.cwd, run.args.epics), StoryFiles(run.cwd, run.args.epics),
                                     DecisionStampFiles(run.runs, run.args.epics), events, transactions)
    run.acceptances = AskAcceptanceUseCase(AcceptanceRecordFiles(run.cwd, run.args.epics, run.runs, run.profile),
                                           events, transactions)
    run.now = now


def check_discovery(cwd: str, folder: str, topic: str) -> typing.Tuple[bool, str]:
    """The discovery report of one topic checked, in discovery's words: whether it passed, and what it says."""
    checked = check_report(cwd, folder, topic)
    return checked.passed, checked.said


def layout_note(cwd: str, profile: Profile) -> typing.Optional[str]:
    """An older layout, named: `factory.sh update` migrates it."""
    return layout_hint(cwd, profile)


def missing_tools() -> typing.List[typing.Tuple[str, str]]:
    """The tools a command of this gate run found missing on the PATH, each with the command that missed it."""
    return list(MISSING_TOOLS)










def gate_story(result: Verdict, args: typing.Any, cwd: str, profile: Profile, report: Report,
               checkouts: typing.Optional[Checkouts] = None) -> int:
    """One gate run over a story: its file read, the stage's checks over it, a passing gate's actions, the run
    journaled — a file the gate cannot read refused as `gate`."""
    story_path = story_id = None
    try:
        story_path = find_story(args.epics, args.story)
        front, body = read_front_matter(story_path)
        story_id = str(front.get("id") or os.path.basename(story_folder(story_path)))
        observe_writes(args.runs, story_id)
        criteria = criteria_of(story_path, body, front)
        run = stage_run(close_record, result=result, args=args, cwd=cwd, runs=args.runs, stage=stage_named()[args.stage],
                        story_id=story_id, story_path=story_path, front=front, body=body, criteria=criteria,
                        profile=profile, checkouts=checkouts)
        run_checks(run)
    except GateError as error:
        result.fail("gate", str(error))
        return journal_gate(result, args, story_id, story_path, report(args.story))
    if not result.failed:
        run_passed(run)
    return journal_gate(result, args, story_id, story_path, report(story_id))
