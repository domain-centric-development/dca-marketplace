"""The evidence a stage's gate reads for its checks, as files: the profile, the run folder, the backlog around the
story."""

from __future__ import annotations

import os
import re
import typing

from .....contract import CONTRACT, GateError, HAPPY_MARK, STAGE_FILES, VERSION
from .....sharedkernel.adapter.outgoing.markdown.front_matter import read_front_matter, read_text
from .....sharedkernel.adapter.outgoing.profile.profile_files import (
    evidence_dir, location, place, shown, unknown_profile_keys)
from ....application.shared.front import is_acceptance
from ....domain.model.decision_record import DecisionState, RecordId, RecordKind
from ....domain.model.epic import EpicId
from ....domain.model.schedule import ContextName
from ....domain.model.stage import StageName, StoryKind
from ....domain.model.stage_story import (
    AnswerField, ByteSize, CommandKey, ContextMapFacts, HandOverName, HandOverSize, PlanLevels, DecisionFacts, DecisionsFacts, HandOverAsk, ContractNumber, EpicFacts, EpicField, EventName, GateRelease, InstructionFile,
    Metric, ModelKey, OwnedFacts, OwnedPart, Place, ProfileKey, ProfileText, RoundsRecord, RowId, RowState,
    ScenarioKey, StageStory, UnknownKey)
from ....domain.model.story import DeliveredOn, StoryId
from ....domain.model.story_state import Detail, HandOverText, Rounds, StatusWord
from ....domain.service.backlog_checks import EPIC_FIELDS, normal_name
from ....domain.service.decision_checks import Applying
from .decision_record_files import (
    ANSWER_FIELDS, answer_sentence, decisions_store, needs_human_ids, read_decisions, record_path, resume_stage,
    stamp_applied)
from .epic_files import epic_dependency_problem
from .findings_files import findings_path, findings_rows, project_findings_path
from .owned_files import owned_changes, write_answered
from .test_files import plan_levels, stage_bytes, unfinished_levels
from .run_marks import OWNED_CHANGED
from .story_layout import delivered_on, EPIC_FILE, epic_folder, find_story, story_kind

Front = typing.Mapping[str, typing.Any]

#: Where a project keeps its context map when the profile names none.
CONTEXT_MAP_CANDIDATES = (
    "product/domain.md",
    "docs/context-map.md",
    "docs/architecture/context-map.md",
    "context-map.md",
)

#: The instruction files a tool loads first, in the order they are looked for.
INSTRUCTION_FILES = ("AGENTS.md", "CLAUDE.md")


def happy_paths(body: str) -> typing.List[str]:
    """The keys marked `(happy path)` under the acceptance criteria."""
    section = body.split("## Acceptance criteria", 1)[-1].split("\n## ", 1)[0] if "## Acceptance criteria" in body else ""
    return [m.group(1) for m in (HAPPY_MARK.match(line.strip()) for line in section.splitlines()) if m]


#: A finding row a task closes: `<story>#<n>`, the row's number in that story's findings.md.
CLOSES_ROW = re.compile(r"^([A-Za-z0-9][\w.-]*)#(\d+)$")


def closes_of(front: Front) -> typing.List[str]:
    """The finding rows a task names under `closes:` — a list, or one line of comma-separated rows."""
    value = front.get("closes") or []
    items = value if isinstance(value, list) else str(value).strip("[] ").split(",")
    return [str(item).strip() for item in items if str(item).strip()]


def closed_rows(row_id: str) -> typing.Tuple[typing.Optional[str], typing.Optional[typing.Sequence[str]]]:
    """(findings file, row) for `<story>#<n>`, or `<name>#<n>` of a project finding file (`<product>/findings/<name>.md`,
    where no story has that id) — the file None where neither or the row is not there."""
    match = CLOSES_ROW.match(row_id)
    if not match:
        return None, None
    try:
        path = findings_path(find_story(place("epics"), match.group(1)))
    except GateError:
        path = project_findings_path(match.group(1))
    row = next((r for r in findings_rows(path) if r[0] == match.group(2)), None)
    return (path if row else None), row


def epic_of(story_path: str, front: Front, epics: str) -> typing.Tuple[str, str]:
    named = front.get("epic")
    if isinstance(named, list) or not named:
        raise GateError(f"{story_path}: front matter has no `epic:`")
    for candidate in (
        os.path.join(epic_folder(story_path), EPIC_FILE),
        os.path.join(epics, str(named), EPIC_FILE),
    ):
        if os.path.isfile(candidate):
            return candidate, str(named)
    raise GateError(
        f"{story_path}: epic {named!r} has no epic.md — create "
        f"{os.path.join(epics, str(named), 'epic.md')}"
    )


def find_first(cwd: str, candidates: typing.Sequence[str]) -> typing.Optional[str]:
    for candidate in candidates:
        if os.path.isfile(os.path.join(cwd, candidate)):
            return candidate
    return None


def map_names(text: str) -> typing.Set[str]:
    """The names a context map gives: whole table cells, headings, bold names, list items and the nodes of a
    Mermaid diagram. A context is on the map when it is one of them — not when its name is part of another's
    (`order` inside `order-fulfilment`) or of a sentence."""
    def normal(name: str) -> str:
        return normal_name(ContextName(name)).value

    names: typing.Set[str] = set()
    in_diagram = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_diagram = stripped.lower().startswith("```mermaid") and not in_diagram
            continue
        if in_diagram:
            names |= {normal(t) for t in re.findall(r"[\w-]+", stripped)}
            names |= {normal(t) for t in re.findall(r"[\[(\"]([^\])\"]+)[\])\"]", stripped)}
            continue
        if stripped.startswith("|"):
            names |= {normal(cell) for cell in stripped.strip("|").split("|")}
        elif stripped.startswith("#"):
            names.add(normal(stripped.lstrip("#")))
        elif re.match(r"[-*+]\s", stripped):
            names.add(normal(re.split(r"\s[—–:-]\s|:", stripped[2:], maxsplit=1)[0]))
        names |= {normal(m) for m in re.findall(r"\*\*([^*]+)\*\*", stripped)}
    return names - {""}


def split_list(value: typing.Any) -> typing.List[str]:
    return [part for part in re.split(r"[\s,]+", str(value or "").strip()) if part]


def publishes_of(front: Front) -> typing.List[str]:
    """The outcome events a story's `publishes:` names — one, or a list."""
    value = front.get("publishes")
    items = value if isinstance(value, list) else split_list(value)
    return [str(item).strip().strip("`") for item in items if str(item).strip().strip("`")]


def depends_on_of(front: Front) -> typing.List[str]:
    """The stories a journey walks, under `depends_on:` — a list, or one line of comma-separated ids."""
    needs = front.get("depends_on")
    if isinstance(needs, str):
        return [n.strip() for n in needs.strip("[] ").split(",") if n.strip()]
    return [str(n) for n in needs] if isinstance(needs, list) else []


def stage_story(story_id: str, story_path: str, front: Front, body: str,
                criteria: typing.Sequence[typing.Tuple[str, str]]) -> StageStory:
    """The story under a gate, read off its front matter and its criteria."""
    named = front.get("epic")
    return StageStory(
        StoryId(story_id), Place(story_path),
        EpicId(str(named)) if named and not isinstance(named, list) else None,
        ContextName(str(front.get("context", "")).strip()), StoryKind(story_kind(front)),
        StatusWord(str(front.get("status", "")).strip().lower()), DeliveredOn(delivered_on(front)),
        tuple(ScenarioKey(key) for key, _text in criteria), tuple(ScenarioKey(k) for k in happy_paths(body)),
        tuple(StoryId(s) for s in depends_on_of(front)), tuple(RowId(r) for r in closes_of(front)),
        tuple(EventName(e) for e in publishes_of(front)))


class StageEvidenceFiles:
    """The evidence of the project <cwd> with its run folder <runs>, its epics under <epics> and its profile, read
    once."""

    def __init__(self, cwd: str, runs: str, epics: str, profile: Front) -> None:
        self._cwd = cwd
        self._runs = runs
        self._epics = epics
        self._profile = profile

    def gate(self) -> GateRelease:
        return GateRelease(ContractNumber(CONTRACT), Detail(VERSION))

    def declared_contract(self) -> ProfileText:
        return ProfileText(str(self._profile.get("contract", "")))

    def unknown_keys(self) -> typing.Tuple[UnknownKey, ...]:
        return tuple(UnknownKey(ProfileKey(key), ProfileKey(near) if near else None)
                     for key, near in unknown_profile_keys(self._profile))

    def model_keys(self) -> typing.Tuple[ModelKey, ...]:
        return tuple(ModelKey(ProfileKey(key), ProfileText(str(self._profile[key])))
                     for key in self._profile if key == "model" or key.startswith("model."))

    def rounds(self, story: StoryId) -> typing.Optional[RoundsRecord]:
        path = os.path.join(evidence_dir(self._runs, story.value), ".rounds")
        if not os.path.isfile(path):
            return None
        try:
            return RoundsRecord(Place(path), Rounds(int(read_text(path).strip() or "0")))
        except (ValueError, GateError):
            return RoundsRecord(Place(path), None)

    def owned(self, story: StageStory) -> OwnedFacts:
        marked = os.path.join(evidence_dir(self._runs, story.story.value), OWNED_CHANGED)
        if os.path.isfile(marked):
            parts = [line.split(":", 1)[1].strip() for line in read_text(marked).splitlines()
                     if line.startswith("changed:")]
            return OwnedFacts(tuple(OwnedPart(p) for p in parts), None)
        changed = owned_changes(self._runs, story.story.value, story.place.value)
        return OwnedFacts((), tuple(OwnedPart(p) for p in changed) if changed is not None else None)

    def context_map(self) -> ContextMapFacts:
        """The designed map (`domain:`) is read first, so a story for a context that is designed but not built yet
        passes; then the one generated from the code (`contextMap:`), then the conventional places."""
        named_domain = str(self._profile.get("domain", "")).strip()
        if named_domain and not os.path.isfile(os.path.join(self._cwd, named_domain)):
            return ContextMapFacts(Place(named_domain), None, frozenset())
        candidates = [location(self._profile, "domain")]
        named = self._profile.get("contextMap")
        if named and os.path.isfile(os.path.join(self._cwd, named)):
            candidates.append(named)
        path = find_first(self._cwd, candidates + list(CONTEXT_MAP_CANDIDATES))
        if not path:
            return ContextMapFacts(None, None, frozenset())
        return ContextMapFacts(None, Place(path), frozenset(
            ContextName(n) for n in map_names(read_text(os.path.join(self._cwd, path)))))

    def instruction_file(self) -> typing.Optional[InstructionFile]:
        for name in INSTRUCTION_FILES:
            path = os.path.join(self._cwd, name)
            if os.path.isfile(path):
                return InstructionFile(Place(name), ByteSize(os.path.getsize(path)))
        return None

    def epic(self, story: StageStory) -> EpicFacts:
        epic_path, epic_name = epic_of(story.place.value, read_front_matter(story.place.value)[0], self._epics)
        front = read_front_matter(epic_path)[0]
        # A key with no value parses as an empty list, and `str([])` is "[]" — non-empty, so the field would count as
        # filled. A mandatory field is a sentence, so only a non-empty string counts.
        filled = {f for f in EPIC_FIELDS for value in (front.get(f),) if isinstance(value, str) and value.strip()}
        missing = [f for f in EPIC_FIELDS if f not in filled]
        discovery = str(front.get("discovery") or "").strip()
        problem = epic_dependency_problem(self._epics, epic_name)
        return EpicFacts(
            Place(epic_path), EpicId(epic_name), tuple(EpicField(f) for f in missing),
            ProfileText(discovery) if discovery and not os.path.isfile(discovery.strip("`")) else None,
            Detail(problem) if problem else None, Metric(str(front.get("metric", ""))))

    def finding_row(self, row: RowId) -> typing.Optional[RowState]:
        path, found = closed_rows(row.value)
        return RowState(found[6]) if path and found else None

    def decisions(self, story: StageStory) -> DecisionsFacts:
        story_id = story.story.value
        store = decisions_store(story.place.value)
        records = []
        for path, front, body, state, answer in read_decisions(store, story_id):
            asked = state in ("open", "draft")
            stage = str(front.get("stage", "")).strip() if asked else resume_stage(front, answer)
            records.append(DecisionFacts(
                RecordId(str(front["id"]).strip()), RecordKind.ACCEPTANCE if is_acceptance(front) else RecordKind.QUESTION,
                DecisionState(state), StageName(stage) if stage else None,
                Detail((body.strip().splitlines() or ["(no title)"])[0].lstrip("# ").strip()),
                Place(os.path.relpath(path, self._cwd).replace(os.sep, "/")),     # one spelling on every platform
                Detail(str(answer.get("answer"))), Detail(str(answer.get("by"))),
                tuple(AnswerField(f) for f in ANSWER_FIELDS if not answer.get(f))))
        hand_overs = []
        for stage_name, name in STAGE_FILES.items():
            path = os.path.join(self._runs, story_id, name)
            if os.path.isfile(path):
                text = read_text(path)
                ids = needs_human_ids(text)
                hand_overs.append(HandOverAsk(StageName(stage_name), Place(path), HandOverText(text),
                                              tuple(RecordId(i) for i in ids) if ids is not None else None))
        return DecisionsFacts(Place(shown(store)), tuple(records), tuple(hand_overs))

    def record_place(self, story: StageStory, record: RecordId) -> Place:
        return Place(shown(record_path(story.story.value, record.value, story.place.value)))


    def command(self, key: CommandKey) -> typing.Optional[ProfileText]:
        command = self._profile.get(key.value)
        return ProfileText(str(command)) if command else None

    def plan_levels(self, story: StoryId) -> typing.Optional[PlanLevels]:
        if not os.path.isfile(os.path.join(self._runs, story.value, "plan.md")):
            return None
        return PlanLevels(tuple(ScenarioKey(k) for k in unfinished_levels(self._runs, story.value)),
                          frozenset(ScenarioKey(k) for k in plan_levels(self._runs, story.value)))

    def hand_over_sizes(self, story: StoryId,
                        names: typing.Tuple[HandOverName, ...]) -> typing.Tuple[HandOverSize, ...]:
        found = []
        for name in names:
            path = os.path.join(self._runs, story.value, name.value)
            if os.path.isfile(path):
                found.append(HandOverSize(name, ByteSize(stage_bytes(path, name.value))))
        return tuple(found)

class DecisionStampFiles:
    """The decision records beside the story and its `## Assumptions`, the journal under the run folder <runs>."""

    def __init__(self, runs: str) -> None:
        self._runs = runs

    def apply(self, story: StageStory, applying: Applying) -> typing.Optional[Place]:
        rid = applying.record.record.value
        found = next(((path, body, answer) for path, front, body, _state, answer
                      in read_decisions(decisions_store(story.place.value), story.story.value)
                      if str(front["id"]).strip() == rid), None)
        if found is None:
            return None
        path, body, answer = found
        stamp_applied(path, applying.stage.value)
        written = write_answered(story.place.value, self._runs, rid, answer_sentence(body, answer))
        return Place(shown(story.place.value)) if written else None
