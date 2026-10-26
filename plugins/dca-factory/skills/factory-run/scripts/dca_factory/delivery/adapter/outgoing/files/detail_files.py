"""What a story's or an epic's detail reads, from the project's files: the file taken apart, the journal's parts and
denials, the newest stream of a shared window still running."""

from __future__ import annotations

import contextlib
import glob
import os
import re
import typing

from ..pipeline.stage_rows import SHARED_WINDOWS
from .criteria_files import criteria_of, scenarios_of
from .....sharedkernel.adapter.outgoing.markdown.front_matter import MarkdownError, read_front_matter
from .....sharedkernel.adapter.outgoing.markdown.sections import section_of, sections_of
from .....sharedkernel.adapter.outgoing.profile.profile_files import evidence_dir
from ..tools.streams import stream_parts
from .epic_files import epic_files
from .journal_files import Event, journal_events
from .story_layout import EPIC_FILE, story_kind
from .stream_records import journal_parts, parts_incomplete
from .usage_files import journal_denials

Facts = typing.Dict[str, typing.Any]

#: The sections a detail shows in a block of its own instead of as text: a story's criteria (as scenarios), an
#: epic's stories (with their state). Their place among the sections is kept as an index.
STORY_OWN_BLOCK, EPIC_OWN_BLOCK = "acceptance criteria", "stories"

#: A section a detail puts first, whatever its place in the file: why a story is not built.
FIRST_SECTIONS = ("superseded",)


def story_description(body: str) -> str:
    """What a story is about, in its own words: its `## Story` section — or, for a task, which has none, the prose
    between its title and its first section. Comments left out."""
    lines = section_of(body, "story")
    if lines is None:
        lines = []
        for line in body.splitlines():
            if line.startswith("## "):
                break
            if not line.startswith("# "):
                lines.append(line)
    text = re.sub(r"<!--.*?-->", "", "\n".join(lines), flags=re.S)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def story_sections(body: str) -> Facts:
    """A story's sections for its detail, its criteria's place among them, and why it is not built where it says."""
    sections, at = sections_of(body, STORY_OWN_BLOCK, FIRST_SECTIONS)
    return dict(sections=sections, criteria_at=at)


def window_parts(events: typing.List[Event], window: str) -> typing.List[Facts]:
    """The parts of every run of one shared window of a story, summed per stage, in the stages' order — from the
    journal's `part` lines (WP-150): [{stage, runs, seconds, input, cache_read, cache_write, output, tokens, cost (or
    None), denied}]."""
    order = SHARED_WINDOWS.get(window, ())
    rows = journal_parts(events, window)
    return sorted(rows, key=lambda r: order.index(r["stage"]) if r["stage"] in order else len(order))


class DetailFactFiles:
    """The detail's facts, read from the project's epics and run folder."""

    def __init__(self, epics: str, runs: str) -> None:
        self._epics, self._runs = epics, runs

    def story_text(self, path: str, body: str, front: Facts) -> Facts:
        try:
            criteria = len(criteria_of(path, body, front))
        except MarkdownError:
            criteria = 0
        return dict(description=story_description(body), scenarios=scenarios_of(body), criteria=criteria,
                    kind=story_kind(front), **story_sections(body))

    def story_journal(self, story_id: str, windows: typing.Iterable[str], stages: typing.Iterable[str]) -> Facts:
        events = journal_events(self._runs, story_id)
        shared = [w for w in windows if w in SHARED_WINDOWS]
        return dict(parts={w: window_parts(events, w) for w in shared},
                    incomplete={w: parts_incomplete(events, w) for w in shared},
                    denied={stage: journal_denials(events, stage) for stage in stages})

    def stream_now(self, story_id: str, window: str) -> typing.List[Facts]:
        outs = glob.glob(os.path.join(evidence_dir(self._runs, story_id), f"{window}.*.out"))
        return list(stream_parts(max(outs, key=os.path.getmtime))[0]) if outs else []

    def epic_folders(self) -> typing.Dict[str, str]:
        return {f["folder"].lower(): f["epic"] for f in epic_files(self._epics)}

    def epic_text(self, epic: str) -> Facts:
        own = next((f for f in epic_files(self._epics) if epic in (f["epic"], f["folder"])), None)
        front: Facts = {}
        body = ""
        if own:
            with contextlib.suppress(MarkdownError, OSError):
                front, body = read_front_matter(os.path.join(self._epics, own["folder"], EPIC_FILE))
        sections, at = sections_of(body, EPIC_OWN_BLOCK, FIRST_SECTIONS)
        return dict(front=front, body=body, sections=sections, stories_at=at)
