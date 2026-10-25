"""The decision records as files: `<story>/decisions/<nn>.md` beside each story, `<product>/decisions/<name>.md` for
the project's own."""

from __future__ import annotations

import os
import re
import time
import typing

from .....contract import (
    decision_files, decision_options, decision_state, project_decisions_dir, shown)
from .....sharedkernel.adapter.outgoing.markdown.front_matter import Front, read_text
from .....state import acceptance_records
from ....application.shared.front import is_acceptance
from ....application.shared.decision_record_repository import RecordNotFound
from ....domain.model.decision_record import Asker, DecisionRecord, DecisionState, OptionKey, RecordId, RecordKind
from ....domain.model.story import StoryId
from .story_files import StoryFiles

#: (path, id, state) of one record.
Located = typing.Tuple[str, str, str]


def request_records(cwd: str, request_id: str) -> typing.List[Located]:
    """Every decision record a request's skill wrote to ask a person — `request: <id>` in its front matter, beside a
    story or the project's own: [(path, id, state)]."""
    found = []
    for name, front, _body, state, error, path in decision_files(cwd):
        if not error and str(front.get("request", "")).strip() == request_id:
            found.append((path, str(front.get("id", name)).strip(), state))
    return found


def project_record_path(request_id: str, topic: str) -> str:
    """Where a request's question with no story is kept: `<product>/decisions/<stamp>-<topic>.md`."""
    word = re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")[:40] or "question"
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    return os.path.join(project_decisions_dir(), f"{stamp}-{word}.md")


def answer_section(given: str, by: str, at: str) -> str:
    return f"\n## Answer\nanswer: {given}\nby: {by}\nat: {at}\n"


class DecisionRecordFiles:
    """The decision record repository as files, under the project the process works in."""

    def __init__(self, cwd: str) -> None:
        self._cwd = cwd
        self._stories = StoryFiles(cwd)

    def path_of(self, record_id: RecordId) -> str:
        """The record's file; RecordNotFound with the reason where none has the id, or it cannot be read."""
        for name, front, _body, _state, error, path in decision_files(self._cwd):
            rid = str(front.get("id", name)).strip() if not error else name
            if rid.lower() == record_id.value.lower():
                if error:
                    raise RecordNotFound(f"{shown(path)} cannot be read — {error}")
                return str(path)
        raise RecordNotFound(f"no decision record {record_id.value} — `factory.sh decisions` lists them")

    def get(self, record_id: RecordId) -> DecisionRecord:
        path = self.path_of(record_id)
        for name, front, body, state, _error, at in decision_files(self._cwd):
            if at == path:
                return self.record(name, front, body, state)
        raise RecordNotFound(f"no decision record {record_id.value} — `factory.sh decisions` lists them")

    def find_by_id(self, aggregate_id: RecordId) -> typing.Optional[DecisionRecord]:
        try:
            return self.get(aggregate_id)
        except RecordNotFound:
            return None

    def save(self, aggregate: DecisionRecord) -> DecisionRecord:
        """The answer the record took, appended as its `## Answer` — the one write a record takes here."""
        answer = aggregate.answer_given
        path = self.path_of(aggregate.id)
        if answer is not None and decision_state(read_text(path))[1].get("answer") != answer.given.value:
            with open(path, "a", encoding="utf-8") as handle:
                handle.write(answer_section(answer.given.value, answer.by.value, answer.at.value))
        return aggregate

    def delete_by_id(self, aggregate_id: RecordId) -> None:
        os.remove(self.path_of(aggregate_id))

    def open_acceptance_of(self, story: StoryId) -> typing.Optional[DecisionRecord]:
        path = self._stories.path_of(story)
        found = [rid for rid, _front, state, _a, _b in acceptance_records(self._cwd, story.value, path)
                 if state in ("open", "draft")]
        return self.get(RecordId(found[-1])) if found else None

    def open_records_of(self, story: StoryId) -> typing.Sequence[DecisionRecord]:
        return [self.record(name, front, body, state) for name, front, body, state, error, _path
                in decision_files(self._cwd)
                if not error and str(front.get("story", "")).strip() == story.value and state in ("open", "draft")]

    @staticmethod
    def record(name: str, front: Front, body: str, state: str) -> DecisionRecord:
        story = str(front.get("story", "")).strip()
        return DecisionRecord(
            RecordId(str(front.get("id", name)).strip()),
            RecordKind.ACCEPTANCE if is_acceptance(front) else RecordKind.QUESTION,
            Asker.REQUEST if str(front.get("request", "")).strip() else Asker.STAGE,
            DecisionState(state),
            [OptionKey(option["key"]) for option in decision_options(body)],
            StoryId(story) if story else None)
