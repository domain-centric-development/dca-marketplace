"""The decision records as files: `<story>/decisions/<nn>.md` beside each story, `<product>/decisions/<name>.md` for
the project's own."""

from __future__ import annotations

import os
import re
import time
import typing

from .journal_files import mark_questioned
from .story_layout import DECISIONS_DIR, find_story, story_digest, story_files, story_folder, story_id_of
from .....sharedkernel.adapter.outgoing.profile.profile_files import DEFAULTS, place, PLACES_REL, shown
from .....sharedkernel.adapter.outgoing.markdown.front_matter import Front, MarkdownError, read_front_matter, read_text
from .....sharedkernel.adapter.outgoing.markdown.sections import fields_of, section_of, sections_of
from ....application.shared.decision_record_repository import RecordNotFound
from ....application.shared.front import is_acceptance
from ....application.shared.story_repository import StoryNotFound
from ....domain.model.decision_record import (
    ANSWER_FIELDS as DOMAIN_ANSWER_FIELDS, ANSWERED_WORDS, AnswerField, Asker, DecisionRecord, DecisionState, OptionKey,
    Given, RecordId, RecordKind, Section, WAITING_WORDS)
from ....domain.model.stage import StageName
from ....domain.model.story_state import AcceptanceVerdict
from ....domain.model.story import StoryId
from ....domain.service.story_route import StoryRoute
from ....domain.model.stage_story import Presence
from ....domain.service.acceptance_rules import AcceptanceMode, AcceptanceRules

GateError = MarkdownError


#: Records as they are read: one tuple each.
Records = typing.List[typing.Tuple[typing.Any, ...]]

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


def answer_appended(given: str, by: str, at: str) -> str:
    return f"\n## Answer\nanswer: {given}\nby: {by}\nat: {at}\n"


class DecisionRecordFiles:
    """The decision record repository as files, under the project the process works in."""

    def __init__(self, cwd: str) -> None:
        self._cwd = cwd
        self._epics = os.path.join(cwd, place("epics"))

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
                handle.write(answer_appended(answer.given.value, answer.by.value, answer.at.value))
        return aggregate

    def delete_by_id(self, aggregate_id: RecordId) -> None:
        os.remove(self.path_of(aggregate_id))

    def open_acceptance_of(self, story: StoryId) -> typing.Optional[DecisionRecord]:
        try:
            path = find_story(self._epics, story.value)
        except GateError as error:
            raise StoryNotFound(f"no story {story.value} under {place('epics')}/ — {error}") from None
        found = [rid for rid, _front, state, _a, _b in acceptance_records(self._cwd, story.value, path)
                 if state in WAITING_WORDS]
        return self.get(RecordId(found[-1])) if found else None

    def open_records_of(self, story: StoryId) -> typing.Sequence[DecisionRecord]:
        return [self.record(name, front, body, state) for name, front, body, state, error, _path
                in decision_files(self._cwd)
                if not error and str(front.get("story", "")).strip() == story.value and state in WAITING_WORDS]

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


# --- the records as the gate, the runner and the views read them -------------------------------------------------


#: The project's own decision records — a question that belongs to no story yet: the description, a discovery, an
#: epic not written (WP-91) — beside the epics: `<product>/decisions/<name>.md`, the shape of a story's record with
#: `id: <name>` and no `story:`. A skill run for a request asks there when it may not decide alone.
PROJECT_DECISIONS = "decisions"


def project_decisions_dir() -> str:
    """The project's decision records beside the epics: `product/decisions` for `product/epics`."""
    epics = place("epics").rstrip("/")
    return os.path.join(os.path.dirname(epics) or ".", PROJECT_DECISIONS)


def project_decisions_rel() -> str:
    """The project's decision records relative to the project, as the profile places the epics."""
    epics = (PLACES_REL.get("epics") or DEFAULTS["epics"]).rstrip("/")
    return os.path.join(os.path.dirname(epics) or ".", PROJECT_DECISIONS).replace("\\", "/")


#: What a table row writes when there is nothing to list: a document stage that changed nothing says
#: so in one row and why, and that row names no file.
NOTHING = {"", "—", "–", "-", "none", "n/a", "nothing"}


# --- decisions: the question a stage may not answer, kept where the answer can land ------------
#
# A stage that cannot decide writes `## needs-human` and the run stops. The question itself lives
# in a record of its own in the story's folder, `<story>/decisions/<nn>.md` with `id: <story>-<nn>` —
# markdown with front matter, committed with the project, in the people's place because the answer
# is a person's — since the stage file has no place for an answer and no second session would find
# one there. State is read from the record, never stored in it: no `## Answer` is open; an
# `## Answer` with `answer:`, `by:` and `at:` is answered; a gate-written `## Applied` is applied.
# A draft that lacks the actor or the time is not an answer — an unconfirmed draft unblocks nothing.
def decisions_store(story_path: str) -> str:
    """The records in the story's folder: `<story>/decisions/` beside its `story.md`."""
    return os.path.join(story_folder(story_path), DECISIONS_DIR)


def records_of(story_id: str, story_path: typing.Optional[str] = None,
               cwd: typing.Optional[str] = None) -> Records:
    """This story's records, read from the folder beside it — the story found by its id where no path is given,
    under `cwd` where the project is not the working directory (a scratch copy)."""
    if not story_id:
        return []
    epics = os.path.join(cwd, place("epics")) if cwd else place("epics")
    return read_decisions(decisions_store(story_path or find_story(epics, story_id)), story_id)


def record_path(story_id: str, rid: str, story_path: typing.Optional[str] = None) -> str:
    """Where a record with this id lives (or would): `<story>/decisions/<nn>.md` for `id: <story>-<nn>`."""
    store = decisions_store(story_path or find_story(place("epics"), story_id))
    return os.path.join(store, rid[len(story_id) + 1:] + ".md") if rid.startswith(story_id + "-") else os.path.join(store, rid + ".md")


ANSWER_FIELDS = tuple(field.value for field in DOMAIN_ANSWER_FIELDS)


def decision_state(text: str) -> typing.Tuple[str, typing.Dict[str, str]]:
    """('open' | 'draft' | 'answered' | 'applied', answer fields) — the state as the domain reads it off the sections."""
    answer = fields_of(section_of(text, "answer"))
    sections = {section for section in Section if section_of(text, section.value) is not None}
    return DecisionState.of(sections, {AnswerField(f) for f, value in answer.items() if value}).value, answer


#: One option of a record's `## Options`, in every form a stage writes it: an optional list marker, optional bold,
#: the label (`a`, `B`, `1`, `(a)`), then `.` `)` `:` or a dash (` — ` ` – ` ` - `) before the text — `- a: …`,
#: `- **a — …** …`, `- **b.** …`, `1) …`. The canonical form, the one the template and the stages write, is `- a: …`.
OPTION_LINE = re.compile(r"^(?:-\s*|[*+]\s+)?(?:\*\*)?\(?([A-Za-z0-9]{1,3})(?:\*\*)?(?:[.):]|\s+[\u2014\u2013-](?=\s|$))\s*(.*)$")


def plain(text: str) -> str:
    """Markdown bold taken out and runs of white space made one: how an option reads outside its record."""
    return " ".join(text.replace("**", "").split())


def decision_options(text: str) -> typing.List[typing.Dict[str, str]]:
    """[{key, line, text}] — the options of a record's `## Options`, the one reader every view and the gate use:
    `key` the label as written, `line` the option's first line, `text` with its continuation lines, both plain."""
    options = []
    for raw in section_of(text, "options") or []:
        match = OPTION_LINE.match(raw.strip())
        if match:
            options.append(dict(key=match.group(1), line=plain(match.group(2)), text=plain(match.group(2))))
        elif options and raw.strip():
            options[-1]["text"] = plain(options[-1]["text"] + " " + raw)
    return options


def recommended_option(text: str, options: typing.Optional[typing.List[typing.Dict[str, str]]] = None) -> typing.Optional[str]:
    """The key of the option the record's `## Recommendation` opens with (`a — …`, `**b.**`, `Option 1.`), when it
    names one of its options; else None."""
    options = decision_options(text) if options is None else options
    lines = [line.strip() for line in section_of(text, "recommendation") or [] if line.strip()]
    first = re.match(r"^[*`\s]*(?:option\s+)?\(?([A-Za-z0-9]{1,3})\b", lines[0], re.I) if lines else None
    if not first:
        return None
    return next((o["key"] for o in options if o["key"].lower() == first.group(1).lower()), None)


def read_decisions(store: str, story_id: str) -> Records:
    """[(path, front, body, state, answer)] for every record that names this story, in id order.

    A record the gate cannot read is a refusal, not a skip: a broken record hides a question."""
    if not os.path.isdir(store):
        return []
    records = []
    for name in sorted(os.listdir(store)):
        if not name.endswith(".md"):
            continue
        path = os.path.join(store, name)
        front, body = read_front_matter(path)
        if str(front.get("story", "")).strip() != story_id:
            raise GateError(
                f"{shown(path)}: names story {front.get('story')!r}, but it lies beside {story_id} — a record "
                f"lives in its own story's `{DECISIONS_DIR}/` folder")
        if str(front.get("id", "")).strip() != f"{story_id}-{name[:-3]}":
            raise GateError(
                f"{shown(path)}: `id:` is {front.get('id')!r}, the file is named {name[:-3]!r} — a "
                f"record is found by its file name: `<story>/{DECISIONS_DIR}/<nn>.md` carries `id: <story>-<nn>`")
        state, answer = decision_state(body)
        records.append((path, front, body, state, answer))
    return records


def applying_stage(front: Front, answer: typing.Mapping[str, str]) -> str:
    """The stage that applies an answer: the one the answer names (`applies: test` — an answer that changes a
    test goes back to the test stage, whoever asked), else the record's `stage:`, the stage that asked."""
    return StoryRoute.applying(StageName(str(front.get("stage", "")).strip()),
                               StageName(str((answer or {}).get("applies", "")).strip().lower())).value


def resume_stage(front: Front, answer: typing.Mapping[str, str]) -> typing.Optional[str]:
    """Where the story resumes for an answer: the earlier of the stage that asked and the one the answer
    names. A plan's question answered `applies: test` still re-plans — the plan lists the tests that change —
    and the test stage after it takes the changed expectation."""
    return StoryRoute.resumes_at(StageName(str(front.get("stage", "")).strip()),
                                 StageName(str((answer or {}).get("applies", "")).strip().lower())).value


def answered_decisions(cwd: str, story_id: str, stage: str) -> typing.List[str]:
    """Ids of this story's answered or applied records the given stage applies."""
    try:
        records = records_of(story_id, cwd=cwd)
    except GateError:
        return []
    return [str(front["id"]).strip() for _p, front, _b, state, answer in records
            if state in ANSWERED_WORDS and applying_stage(front, answer) == stage]


def nothing_line(line: str) -> bool:
    """`(none)`, `- None.`, `_None._`, `—` and the like: a line that says there is nothing."""
    text = line.strip().lstrip("-*").strip().strip("_*()").strip().rstrip(".").strip()
    return text.lower() in NOTHING


def needs_human_ids(text: str) -> typing.Optional[typing.List[str]]:
    """The decision ids a `## needs-human` section names (`decision: <id>`), or [] without one;
    None when the file has no such section at all — or only the heading, left empty or filled with
    `(none)` from the file template: that asks nobody anything, and reading it as a stop halts a
    finished stage."""
    section = section_of(text, "needs-human")
    if section is None or all(nothing_line(line) for line in section):
        return None
    # the id alone: a stage may go on writing after it on the same line ("decision: s-01. The browser …")
    ids = []
    for key, value in fields_of(section).items():
        match = re.match(r"`?([A-Za-z0-9][\w-]*)", value) if key == "decision" and value else None
        if match:
            ids.append(match.group(1))
    return ids


def stamp_applied(path: str, stage: str) -> None:
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(f"\n## Applied\nat: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}\n"
                     f"stage: {stage}\n")


def decision_files(cwd: str) -> typing.Iterator[typing.Tuple[typing.Any, ...]]:
    """(id from the file name, front, body, state, error, path) for every record of every story, story by
    story in the order of the files."""
    for story_path in story_files(os.path.join(cwd, place("epics"))):
        store = decisions_store(story_path)
        if not os.path.isdir(store):
            continue
        story_id = story_id_of(story_path)
        for name in sorted(os.listdir(store)):
            if not name.endswith(".md"):
                continue
            path = os.path.join(store, name)
            try:
                front, body = read_front_matter(path)
            except GateError as error:
                yield f"{story_id}-{name[:-3]}", {}, "", "unreadable", error, path
                continue
            yield f"{story_id}-{name[:-3]}", front, body, decision_state(body)[0], None, path
    yield from project_decision_files(cwd)


def project_decision_files(cwd: str) -> typing.Iterator[typing.Tuple[typing.Any, ...]]:
    """The same six fields for every record of the project's own (`<product>/decisions/<name>.md`): its id is its
    file's name, and a record that names a story belongs beside that story instead — read as unreadable here."""
    epics = place("epics")
    store = os.path.join(os.path.dirname(os.path.join(cwd, epics).rstrip("/")) or ".", PROJECT_DECISIONS)
    if not os.path.isdir(store):
        return
    for name in sorted(os.listdir(store)):
        if not name.endswith(".md"):
            continue
        path = os.path.join(store, name)
        try:
            front, body = read_front_matter(path)
            if str(front.get("story", "")).strip():
                raise GateError(f"{shown(path)}: names story {front.get('story')!r} — a story's record lives in its "
                                f"own `{DECISIONS_DIR}/` folder, a project record names no story")
            if str(front.get("id", "")).strip() != name[:-3]:
                raise GateError(f"{shown(path)}: `id:` is {front.get('id')!r}, the file is named {name[:-3]!r} — a "
                                f"project record is found by its file name")
        except GateError as error:
            yield name[:-3], {}, "", "unreadable", error, path
            continue
        yield name[:-3], front, body, decision_state(body)[0], None, path


def answer_section(text: str) -> typing.Optional[str]:
    """A record's `## Answer` section as written, up to the next `## ` heading — the person's part of it."""
    lines, inside = [], False
    for line in text.splitlines():
        if line.strip().lower() == "## answer":
            inside = True
        elif inside and line.startswith("## "):
            break
        if inside:
            lines.append(line)
    return "\n".join(lines).rstrip() if lines else None      # a section appended after it leaves it as it was


def answer_sentence(body: str, answer: typing.Mapping[str, typing.Any]) -> str:
    """The sentence an answered record leaves in its story — deterministic: where the answer names an option of the
    record's `## Options` by its label (`a`, `B`, `option b`), that option's first line; else the answer itself.
    One line, markup and runs of white space taken out."""
    given = " ".join(str(answer.get("answer", "")).split())
    label = re.sub(r"^(?:option\s+)", "", given, flags=re.I).strip(" .):*")
    if re.fullmatch(r"[A-Za-z0-9]{1,3}", label or ""):
        given = next((o["line"] for o in decision_options(body) if o["key"].lower() == label.lower()), given)
    return plain(given)


#: A story delivered only once a human looked at it: the record kind, the modes of `acceptance:`.
ACCEPTANCE_KIND = "acceptance"


ACCEPTANCE_MODES = tuple(mode.value for mode in AcceptanceMode)


def acceptance_mode(profile: typing.Mapping[str, typing.Any]) -> str:
    mode = str(profile.get("acceptance", "none")).strip().lower() or "none"
    if mode not in ACCEPTANCE_MODES:
        raise GateError(f"`acceptance: {mode}` is none of {', '.join(ACCEPTANCE_MODES)}")
    return mode


def acceptance_records(cwd: str, story_id: str, story_path: typing.Optional[str] = None) -> Records:
    """This story's acceptance records, oldest first: [(id, front, state, answer, body)]."""
    records = records_of(story_id, story_path)
    found = [(str(f["id"]).strip(), f, state, answer, body) for _p, f, body, state, answer in records if is_acceptance(f)]
    def number(rid: str) -> int:
        trailing = re.search(r"(\d+)$", rid)
        return int(trailing.group(1)) if trailing else 0
    return sorted(found, key=lambda r: number(r[0]))



def acceptance_state(cwd: str, story_id: str,
                     story_path: typing.Optional[str]) -> typing.Tuple[str, typing.Optional[str]]:
    """('ask' | 'open' | 'accepted' | 'correction', id or None) for the story as it is now.

    An answer holds for the story it was given for: the record carries the story's digest, and a
    story changed since — a correction written in — is asked again once it has run."""
    records = acceptance_records(cwd, story_id, story_path)
    if not records:
        return AcceptanceRules.verdict(None, Given(""), Presence.ABSENT).value, None
    rid, front, state, answer, _body = records[-1]
    same = Presence.PRESENT if str(front.get("digest", "")).strip() == story_digest(story_path or "") else Presence.ABSENT
    return AcceptanceRules.verdict(DecisionState(state), Given(str(answer.get("answer", ""))), same).value, rid


def latest_verdict(records: Records) -> AcceptanceVerdict:
    """What the latest of a story's acceptance records says, the story's digest left aside."""
    _rid, _front, state, answer, _body = records[-1]
    return AcceptanceRules.verdict(DecisionState(state), Given(str(answer.get("answer", ""))), Presence.PRESENT)


def record_sections(body: str) -> typing.List[typing.Dict[str, str]]:
    """What a record says beyond its title, as a view shows it beside the options: the question and its evidence,
    or what an acceptance asks to look at — never the options, the recommendation or the answer, which the view
    draws as the actions they are."""
    return [s for s in sections_of(body, "options")[0]
            if s["heading"].split("(")[0].strip().lower() not in ("recommendation", "answer")]


class DecisionInboxFiles:
    """The decision inbox as files, under the project the process works in."""

    def __init__(self, cwd: str) -> None:
        self._cwd = cwd

    def records(self) -> typing.List[typing.Dict[str, typing.Any]]:
        found: typing.List[typing.Dict[str, typing.Any]] = []
        for name, front, body, state, error, path in decision_files(self._cwd):
            if error:
                found.append(dict(name=name, error=str(error), path=shown(path)))
                continue
            acceptance = is_acceptance(front)
            options = [] if acceptance else decision_options(body)
            found.append(dict(name=name, error=None, path=shown(path), id=str(front.get("id", name)).strip(),
                              state=state, kind="acceptance" if acceptance else "question",
                              story=str(front.get("story", "")).strip(), stage=str(front.get("stage", "?")).strip(),
                              asked=str(front.get("asked", "")),
                              title=(body.strip().splitlines() or ["(no title)"])[0].lstrip("# ").strip(),
                              answer=decision_state(body)[1],
                              options=[dict(key=o["key"], text=o["text"]) for o in options],
                              recommended=recommended_option(body, options), sections=record_sections(body)))
        return found

    def project_name(self) -> str:
        return os.path.basename(os.path.abspath(self._cwd))

    def where(self) -> str:
        return f"{place('epics')}/<epic>/<story>/{DECISIONS_DIR}/"


class RequestRecordFiles:
    """The records the requests of the project <cwd> wrote, beside the stories and the project's own."""

    def __init__(self, cwd: str) -> None:
        self._cwd = cwd

    def asked(self, request: str) -> typing.List[typing.Tuple[str, str, str]]:
        return [(str(shown(path)), rid, state) for path, rid, state in request_records(self._cwd, request)]

    def applied(self, request: str) -> None:
        for path, _rid, state in request_records(self._cwd, request):
            if state == "answered":
                stamp_applied(path, "request")

    def questioned(self, paths: typing.Sequence[str], request: str) -> None:
        mark_questioned(self._cwd, place("runs"), paths, request)
