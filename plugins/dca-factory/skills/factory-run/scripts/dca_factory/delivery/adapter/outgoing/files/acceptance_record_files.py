"""The decision records as files, with the acceptance a delivering gate asks for: its next id, and its file written
when it is new — the criteria it lists are the ones accepted, a reopen after an acceptance compares against them."""

from __future__ import annotations

import os
import typing

from .....sharedkernel.adapter.outgoing.markdown.front_matter import GateError, read_front_matter
from ....domain.model.decision_record import DecisionRecord
from .criteria_files import criteria_of
from .decision_record_files import ACCEPTANCE_KIND, DecisionRecordFiles, decisions_store
from .story_layout import find_story, story_digest
from .test_files import read_mapping


class AcceptanceRecordFiles(DecisionRecordFiles):
    """The records of the project <cwd> under <epics>, an acceptance's question drawn from the run folder <runs> and
    the profile."""

    def __init__(self, cwd: str, epics: str, runs: str, profile: typing.Mapping[str, typing.Any]) -> None:
        super().__init__(cwd, epics)
        self._runs = runs
        self._profile = profile

    def save(self, aggregate: DecisionRecord) -> DecisionRecord:
        if aggregate.asked is not None and aggregate.story is not None:
            self._write_asked(aggregate.story.value, aggregate.id.value, aggregate.asked.value,
                              aggregate.content.stage.value if aggregate.content.stage else "")
        return super().save(aggregate)

    def _write_asked(self, story_id: str, rid: str, asked: str, stage: str) -> None:
        story_path = find_story(self._epics, story_id)
        store = decisions_store(story_path)
        path = os.path.join(store, rid[len(story_id) + 1:] + ".md")
        if os.path.isfile(path):
            return
        front, body = read_front_matter(story_path)
        try:
            _where, mapping = read_mapping(self._runs, story_id)
        except GateError:
            mapping = {}
        run = str(self._profile.get("run", "")).strip()
        lines = [f"- {key}: {text}" + (f" — `{', '.join(mapping[key])}`" if mapping.get(key) else "")
                 for key, text in criteria_of(story_path, body, front)]
        os.makedirs(store, exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(
                f"---\nid: {rid}\nstory: {story_id}\nstage: {stage}\nkind: {ACCEPTANCE_KIND}\n"
                f"asked: {asked}\ndigest: {story_digest(story_path)}\n---\n\n"
                f"# Accept {story_id}?\n\n## Question\n"
                f"Every gate passed. Look at what the story delivers before it counts as delivered:\n\n"
                + "\n".join(lines) + "\n\n"
                + (f"Start the application with `{run}`.\n\n" if run else
                   "Start the application the way the project runs it (the profile names no `run:`).\n\n")
                + "## Options\n"
                  "- accepted: the story is delivered.\n"
                  "- a correction: what should be different, written into the story (criteria and an "
                  "`answered:` line naming this record); the story runs again from plan.\n")
