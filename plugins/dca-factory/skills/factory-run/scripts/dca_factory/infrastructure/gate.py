"""The gate's use cases, wired to the project's files — the project <cwd>, its epics under <epics>, its profile — and
a gate run over one story with every check the stage table registers."""

from __future__ import annotations

import typing

from ..delivery.adapter.outgoing.build.stage_runs import StageRunFiles
from ..delivery.adapter.outgoing.files.backlog_entry_files import BacklogEntryFiles
from ..delivery.adapter.outgoing.files.stage_delivery_files import StageDeliveryFiles
from ..delivery.adapter.outgoing.files.stage_evidence_files import (
    DecisionStampFiles, MainLineEvidence, StageEvidenceFiles, stage_story)
from ..delivery.adapter.outgoing.files.stage_marks_files import StageMarkFiles
from ..delivery.adapter.outgoing.files.story_layout import story_kind
from ..delivery.adapter.outgoing.files.test_files import StageTestFiles
from ..delivery.adapter.outgoing.git.change import ChangeIndexFiles, ParityReportFiles
from ..delivery.application.backlog.check_backlog import CheckBacklogUseCase
from ..delivery.application.delivery import pass_actions  # noqa: F401 — registers what a passing gate does
from ..delivery.application.delivery import process_checks  # noqa: F401 — registers the checks that run processes
from ..delivery.application.delivery import stage_checks  # noqa: F401 — registers the checks over the evidence alone
from ..delivery.application.delivery.check_change import CheckChangeUseCase
from ..delivery.application.delivery.check_parity import CheckParityUseCase
from ..delivery.application.delivery.check_stage import StageRun
from ..delivery.domain.service.profile_checks import ProfileChecks
from .description import check_description


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
