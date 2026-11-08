"""The project description checked as the gate says its checks — the description feature's command."""

from __future__ import annotations

from ....application.delivery.check_stage import Verdict
from ....application.description.check_description import CheckDescriptionCommand, CheckDescriptionInputPort


def check_project(result: Verdict, check: CheckDescriptionInputPort) -> bool:
    """The two mandatory parts of the project description — the description feature's check, said as the gate
    says its checks."""
    checked = check.execute(CheckDescriptionCommand())
    for verdict in checked.verdicts:
        getattr(result, verdict.state)(verdict.part, verdict.said)
    return checked.complete
