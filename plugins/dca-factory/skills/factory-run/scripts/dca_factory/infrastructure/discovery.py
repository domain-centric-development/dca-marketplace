"""Discovery's use cases, wired to the project's files and to delivery's open host service."""

from __future__ import annotations

from ..discovery.adapter.outgoing.delivery.backlog import DeliveryBacklog
from ..discovery.adapter.outgoing.files.report_files import ReportFiles
from ..discovery.application.check_report import CheckReportUseCase
from ..discovery.application.list_reports import ListReportsUseCase


def check_report(cwd: str, folder: str) -> CheckReportUseCase:
    return CheckReportUseCase(ReportFiles(cwd, folder))


def list_reports(cwd: str, folder: str) -> ListReportsUseCase:
    return ListReportsUseCase(ReportFiles(cwd, folder), DeliveryBacklog(cwd))
