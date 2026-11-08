"""The plan gate's backlog checks over the stories, said one line per finding — the backlog feature's command."""

from __future__ import annotations

import typing

from ....application.backlog.check_backlog import CheckBacklogCommand, CheckBacklogInputPort
from ....domain.model.story import StoryId
from ....domain.model.verdict import FindingState


def check_backlog(check: CheckBacklogInputPort, layout_note: typing.Optional[str], epics: str,
                  only: typing.Optional[str] = None) -> int:
    """The plan gate's backlog checks over every story that is not done, or over `only` (`CheckBacklogUseCase`),
    said one line per finding that did not pass; <layout_note> names an older layout first."""
    hint = layout_note
    if hint:
        print(f"gate:note layout — {hint}")
    checked = check.execute(CheckBacklogCommand(StoryId(only) if only else None))
    for verdict in checked.verdicts:
        for finding in verdict.findings:
            if finding.state is not FindingState.PASS:
                print(f"gate:{finding.state.value} {verdict.label.value} {finding.check.value} — {finding.said.value}")
    refused = [label.value for label in checked.refused]
    if not checked.checked and not refused:
        if only:
            print(f"backlog: no story {only} to check under {epics}/ (not there, delivered or superseded)")
            return 1
        print(f"backlog: no story to check under {epics}/")
        return 0
    print(f"backlog: {checked.checked} story(ies) checked" + (f", refused: {', '.join(refused)}" if refused
                                                             else " — every one holds for the plan gate"))
    return 1 if refused else 0
