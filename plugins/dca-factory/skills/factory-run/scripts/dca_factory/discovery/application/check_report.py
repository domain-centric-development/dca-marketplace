"""Check a discovery report."""

from __future__ import annotations

import dataclasses
import re
import typing

from ...building_blocks import UseCase
from ..domain.model.report import ReportRules, SECTIONS, Topic
from .shared.report_store import ReportStore

#: A URL in a source's entry.
URL = re.compile(r"https?://\S+")
#: The date a web source was read.
READ_ON = re.compile(r"\bread \d{4}-\d{2}-\d{2}\b")
#: A location after a path (`:12`, `:L3-8`, `#anchor`): not part of the file's name.
LOCATION_SUFFIX = re.compile(r"(?::L?\d+(?:[-–:]\d+)?|#[\w.-]+)$")
#: A path written bare in a source's entry.
BARE_PATH = re.compile(r"(?<!\S)([\w.-]+/[\w./-]+\.[A-Za-z0-9]{1,6}(?::L?\d+(?:[-–:]\d+)?)?)")


@dataclasses.dataclass(frozen=True)
class CheckReportCommand:
    topic: Topic


@dataclasses.dataclass(frozen=True)
class ReportChecked:
    """`passed`, and the sentence the gate prints for it."""

    passed: bool
    said: str


class CheckReportInputPort(UseCase[CheckReportCommand, ReportChecked], typing.Protocol):
    """Check a report."""


class CheckReportUseCase:
    """The report's sections in order, every citation a listed source, every source resolving — an excerpt under the
    topic's folder, a project file, or a URL with the date it was read —, every proposed body of work with intent,
    goal and metric, and the topic's `originals/` ignored by git."""

    def __init__(self, reports: ReportStore) -> None:
        self._reports = reports

    def execute(self, command: CheckReportCommand) -> ReportChecked:
        topic = command.topic
        path = self._reports.report_path(topic)
        report = self._reports.read(topic)
        if report is None:
            return ReportChecked(False, f"no {path} — `factory-discover {topic.value}` writes it")
        folder = path.rsplit("/", 1)[0]
        problems = [p.value for p in ReportRules.sections(report)]
        for sid, entry in report.sources.items():
            if URL.search(entry.value):
                if not READ_ON.search(entry.value):
                    problems.append(f"{sid.value}: a web source names the date it was read (`read YYYY-MM-DD`)")
                continue
            paths = [bare(p) for p in re.findall(r"`([^`]+)`", entry.value)] or \
                [bare(p) for p in BARE_PATH.findall(entry.value)]
            if not paths:
                problems.append(f"{sid.value}: names no file and no URL")
                continue
            for name in paths:
                if not self._reports.resolves(topic, name):
                    problems.append(f"{sid.value}: {name} is not there — an excerpt lives under {folder}/sources/")
        problems += [p.value for p in ReportRules.proposals(report)]
        if not self._reports.ignores_originals(topic):
            problems.append(f"{folder}/.gitignore does not ignore `originals/` — the handed-over originals stay out "
                            "of git")
        if problems:
            return ReportChecked(False, f"{path}: " + "; ".join(problems))
        changes = len(report.changes)
        return ReportChecked(True, f"{path}: {len(SECTIONS)} sections, {len(report.sources)} source(s) resolving, "
                                   f"{len(report.proposals)} proposed body(ies) of work"
                                   + (f", {changes} proposed description change(s)" if changes else ""))


def bare(name: str) -> str:
    """A path as a file's name: without the backticks and the location after it."""
    return LOCATION_SUFFIX.sub("", name.strip().strip("`")).strip()
