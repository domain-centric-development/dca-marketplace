"""Discovery's open host service: what delivery and the views ask of discovery — a report checked, the reports
listed, the report of a topic and the work it proposes."""

from __future__ import annotations

import os
import typing

from ...infrastructure import discovery as wiring
from ...sharedkernel.adapter.outgoing.markdown.front_matter import read_text
from ..adapter.outgoing.files.report_files import discovery_items, ReportFiles
from ..application.check_report import CheckReportCommand, ReportChecked
from ..application.list_reports import ListReportsQuery
from ..domain.model.report import DESCRIPTION_CHANGES, PROPOSED_WORK, Topic

__all__ = ("check_report", "DESCRIPTION_CHANGES", "discovery_items", "list_reports", "proposals_in", "report_of",
           "ReportChecked")


def check_report(cwd: str, folder: str, topic: str) -> ReportChecked:
    """`<folder>/<topic>/discovery.md` checked: its sections, sources, proposals and changes."""
    return wiring.check_report(cwd, folder).execute(CheckReportCommand(Topic(topic)))


def list_reports(cwd: str, folder: str) -> typing.Dict[str, typing.Any]:
    """Every topic with its proposals — each with the epic that holds it — and its description changes."""
    return wiring.list_reports(cwd, folder).execute(ListReportsQuery())


def report_of(cwd: str, folder: str, topic: str) -> typing.Optional[str]:
    """The topic's report as a project path, None where the topic has none."""
    path = ReportFiles(cwd, folder).report_path(Topic(topic))
    return path if os.path.isfile(os.path.join(cwd, path)) else None


def proposals_in(cwd: str, report: str) -> typing.List[str]:
    """The names of the work the report at <report> proposes, in its order."""
    return [name for name, _fields in discovery_items(read_text(os.path.join(cwd, report)), PROPOSED_WORK)]
