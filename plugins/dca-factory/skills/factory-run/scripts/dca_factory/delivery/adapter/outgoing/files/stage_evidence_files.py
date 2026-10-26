"""The evidence a stage's gate reads for its checks, as files: the profile, the run folder, the backlog around the
story."""

from __future__ import annotations

import contextlib
import os
import re
import typing

from .....contract import CONTRACT, VERSION
from .....sharedkernel.adapter.outgoing.markdown.front_matter import GateError
from .hand_over_patterns import HAPPY_MARK, SELECTOR
from ..pipeline.stage_rows import order_for, SHARED_WINDOWS, STAGE_FILES, STAGES
from .....sharedkernel.adapter.outgoing.markdown.sections import section_of
from .....sharedkernel.adapter.outgoing.markdown.front_matter import read_front_matter, read_text
from .....sharedkernel.adapter.outgoing.profile.profile_files import (
    evidence_dir, factory_home, HOME_VARIABLE, in_worktree, places_in, location, METHOD_PROFILE, place, read_flat, shown, unknown_profile_keys)
from ....application.profile.profile_rules import perspectives_of
from ....application.shared.front import is_acceptance
from ....domain.model.decision_record import (
    ANSWERED_WORDS, AnswerField, DecisionState, RecordId, RecordKind, WAITING_WORDS)
from ....domain.model.epic import EpicId
from ....domain.model.schedule import ContextName
from ....domain.model.stage import StageName, StoryKind
from ....domain.model.stage_story import (
    AssertionAt, ChangedTest, DocumentFacts, Integration, MainTestLines, MainTests, MappedTest, OutcomeEvent, OutcomeFacts, PassGap,
    PipelineFacts, PlannedDigest, ProposalFacts, ReviewFacts, StoryPass, SpecDelta, SpecTests, StoryCommit, DecidedRecord, KeptTests, PlannedTestChange, RedProof, StageChanges,
    TestChange, TestEdit, Unobserved, AssertionFact, ByteSize, Clause, ClauseRow, CommandKey, Count,
    ElementName, ElementRules, FileChange, InvariantFacts, InvariantRow, PlannedFile, PortName, Presence, Rule,
    ScenarioClauses, Selector, ContextMapFacts, HandOverName, HandOverSize, PlanLevels, DecisionFacts, DecisionsFacts, HandOverAsk, ContractNumber, EpicFacts, EpicField, EventName, GateRelease, InstructionFile,
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
import glob
from .delivery_files import (
    glossary_files, IMPORT_LINE, PATHLIKE, PIPELINE_DIR, plan_proposals, production_files,
    proposal_words, REVIEW_RANKS)
from .decision_record_files import NOTHING
from .kept_files import bare_path, row_cells
from .run_marks import current_stage_files, STORY_DIGEST, verdict_in
from .snapshots import NOT_OBSERVED
from .story_layout import journeys_hold, story_digest
from ..claims.remote_claims import claim_config_here
from ..git.integration import (
    CONFLICT_MARKER, integration_target, lost_text, MAIN_TESTS, main_tests_adapted, main_tests_lost, main_tests_waiver,
    merge_target)
from .test_files import locate_tests, plan_levels, stage_bytes, unfinished_levels
from .....spec.api import delta_problems, derived, placement_problems, read_delta, rule_problems, story_entries, touches
from ..spec.story_spec_files import moved_tests, spec_backing, story_spec
from ....domain.model.verdict import FindingState
from ....domain.service.test_checks import TestChecks
from ..git.repository import git, git_blob
from .decision_record_files import answered_decisions, records_of
from .kept_files import (
    assertions_kept, changed_tests_in_plan, committed_by_a_stage, human_line, meaningful_lines, read_red_digests,
    red_tree, switched_off, TESTS_BASELINE, tidy_moves, unproven_tests)
from .run_marks import last_ended, stage_open, window_open
from .snapshots import git_tree, listed_files, snapshot_reason, tree_changes
from .story_layout import file_digest
from .design_files import (
    adapter_level_keys, asserts_at, locate_selector, MOCK_MARKERS, mocked_ports, PLAN_FILE_LINE, plan_domain_elements,
    plan_invariants, read_clause_rows, read_invariant_rows, scenario_clauses)
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


def contract_of(profile: typing.Mapping[str, typing.Any]) -> int:
    """The contract the profile declares, else the gate's own."""
    declared = str(profile.get("contract", "")).strip()
    return int(declared) if declared.isdigit() else CONTRACT


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
        tuple(EventName(e) for e in publishes_of(front)),
        tuple(ScenarioClauses(ScenarioKey(key), tuple(Clause(Count(n), Detail(text)) for n, text in clauses))
              for key, clauses in scenario_clauses(body).items()),
        Count(sum(1 for line in section_of(body, "changed expectations") or []
                  if line.strip().startswith(("-", "*")) and human_line(line.strip()[1:].strip()))),
        Detail(str(front.get("feature") or "").strip()))


def spec_front(story: StageStory) -> typing.Dict[str, typing.Any]:
    """The fields of the story's front matter that place it in the spec."""
    return {"context": story.context.value, "feature": story.feature.value or None, "status": story.status.value,
            "kind": story.kind.value if story.kind in (StoryKind.JOURNEY, StoryKind.TASK) else ""}


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
        try:
            epic_path, epic_name = epic_of(story.place.value, read_front_matter(story.place.value)[0], self._epics)
        except GateError as error:
            return EpicFacts(story.place, EpicId(""), (), None, None, Metric(""), Detail(str(error)))
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
        try:
            place_of = story.place.value or find_story(place("epics"), story_id)
            store = decisions_store(place_of)
            read = read_decisions(store, story_id)
        except GateError as error:
            return DecisionsFacts(Place(""), (), (), Detail(str(error)))
        records = []
        for path, front, body, state, answer in read:
            asked = state in WAITING_WORDS
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
                          frozenset(ScenarioKey(k) for k in plan_levels(self._runs, story.value)),
                          frozenset(ScenarioKey(k) for k in adapter_level_keys(self._runs, story.value)))

    def hand_over_sizes(self, story: StoryId,
                        names: typing.Tuple[HandOverName, ...]) -> typing.Tuple[HandOverSize, ...]:
        found = []
        for name in names:
            path = os.path.join(self._runs, story.value, name.value)
            if os.path.isfile(path):
                found.append(HandOverSize(name, ByteSize(stage_bytes(path, name.value))))
        return tuple(found)

    def _run_file(self, story: StoryId, name: str) -> typing.Optional[str]:
        path = os.path.join(self._runs, story.value, name)
        return read_text(path) if os.path.isfile(path) else None

    def invariants(self, story: StageStory) -> typing.Optional[InvariantFacts]:
        plan = self._run_file(story.story, "plan.md")
        if plan is None:
            return None
        tests = self._run_file(story.story, "tests.md")
        named = plan_invariants(plan) or {}
        listed = sum(1 for line in section_of(plan, "invariants") or [] if line.strip().startswith("-"))
        rows = read_invariant_rows(tests) if tests is not None else None
        return InvariantFacts(
            Count(listed), tuple(ElementName(e) for e in plan_domain_elements(plan)),
            tuple(ElementRules(ElementName(e), tuple(Rule(r) for r in rules)) for e, rules in named.items()),
            tuple(InvariantRow(ElementName(element), tuple(Count(n) for n in numbers),
                               Selector(selector) if selector and SELECTOR.match(selector) else None,
                               Detail(selector) if selector and not SELECTOR.match(selector) else None)
                  for element, numbers, selector in rows) if rows is not None else None)

    def test_place(self, selector: Selector) -> typing.Optional[Place]:
        found = locate_selector(self._cwd, selector.value)
        return Place(found) if found else None

    def clause_rows(self, story: StoryId) -> typing.Optional[typing.Tuple[ClauseRow, ...]]:
        tests = self._run_file(story, "tests.md")
        rows = read_clause_rows(tests) if tests is not None else None
        return tuple(ClauseRow(ScenarioKey(key), Count(n), Detail(location), Detail(level))
                     for key, n, location, level in rows) if rows is not None else None

    def assertion_at(self, file: Place, line: Count, among: typing.Tuple[Place, ...]) -> AssertionFact:
        path = os.path.join(self._cwd, file.value)
        own = {os.path.normpath(place.value) for place in among}
        presence = Presence.PRESENT if os.path.normpath(path) in own else Presence.ABSENT
        if not os.path.isfile(path):
            return AssertionFact(AssertionAt.NO_FILE, presence)
        return AssertionFact(AssertionAt.ASSERTS if asserts_at(path, line.value) else AssertionAt.NOTHING, presence)

    def doubles(self, test: Place) -> typing.Tuple[PortName, ...]:
        named = str(self._profile.get("mockMarkers", "")).strip()
        markers = [m.strip() for m in named.split(",") if m.strip()] if named else list(MOCK_MARKERS)
        method = read_flat(os.path.join(factory_home() or self._cwd, METHOD_PROFILE))
        suffixes = {str(method.get("input_port_suffix", "")).strip() or "InputPort", "UseCase"}
        try:
            with open(os.path.join(self._cwd, test.value), encoding="utf-8") as handle:
                return tuple(PortName(name) for name in mocked_ports(handle.read(), markers, suffixes))
        except (OSError, UnicodeDecodeError):
            return ()

    def plan_files(self, story: StoryId) -> typing.Optional[typing.Tuple[PlannedFile, ...]]:
        plan = self._run_file(story, "plan.md")
        lines = section_of(plan, "files") if plan is not None else None
        if lines is None:
            return None
        planned = []
        for line in lines:
            match = PLAN_FILE_LINE.match(line)
            if not match or any(c in match.group(1) for c in "*<>{}"):
                continue
            rel = match.group(1).strip()
            planned.append(PlannedFile(
                Place(rel), FileChange(match.group(2).lower()),
                Presence.PRESENT if os.path.lexists(os.path.join(self._cwd, rel)) else Presence.ABSENT))
        return tuple(planned)

    def stage_changes(self, story: StoryId, stage: StageName,
                      tests: typing.Tuple[MappedTest, ...]) -> StageChanges:
        runs, story_id, name = self._runs, story.value, stage.value
        record: typing.Optional[str] = os.path.join(evidence_dir(runs, story_id), f"changed-{name}.txt")
        handovers = [STAGE_FILES[name]]
        listing = [s.file for s in STAGES if s.lists if os.path.isfile(os.path.join(runs, story_id, s.file))]
        if last_ended(runs, story_id, (name, "builder")) == "builder":
            # A shared builder ran plan to tidy in one window: its record is the one that holds, and a file it
            # changed is listed by whichever of its hand-overs belongs to the stage that changed it.
            record, handovers = os.path.join(evidence_dir(runs, story_id), "changed-builder.txt"), listing
        changed_now: typing.List[str] = []
        base_file = os.path.join(evidence_dir(runs, story_id), "base-tree")
        if window_open(runs, story_id, "builder") and name in SHARED_WINDOWS["builder"] and os.path.isfile(base_file):
            # A shared builder runs its own gates inside its window, before any changed-files record exists. What the
            # story changed so far is the tree against its base: checked now, the builder can still list a file it
            # forgot — found only by the runner afterwards, it costs a round.
            base = read_text(base_file).strip()
            now = git_tree(self._cwd) if base and base != "none" else None
            rows = tree_changes(self._cwd, base, now, runs) if now else None
            if rows is not None:
                record, handovers, changed_now = None, listing, [path for _kind, path in rows]

        def unobserved(why: Unobserved, reason: str = "") -> StageChanges:
            return StageChanges(why, Detail(reason), (), (), None, frozenset())

        if record is not None and (not os.path.isfile(record) or stage_open(runs, story_id, name)):
            # A stage that runs its own gate does so inside its window: its record is written at the stage's end,
            # and the gate after `--stage-end` checks it.
            return unobserved(Unobserved.STAGE_OPEN if stage_open(runs, story_id, name) else Unobserved.NO_RECORD)
        if record is None:
            changed = changed_now
        else:
            reason = snapshot_reason(record)
            if reason:
                return unobserved(Unobserved.NOT_OBSERVED, reason)
            changed = [line.split("\t", 1)[1] for line in read_text(record).splitlines() if "\t" in line]
        found = [listed_files(os.path.join(runs, story_id, h)) for h in handovers]
        listed = set().union(*[names for names in found if names is not None]) if any(n is not None for n in found) \
            else None
        # A test file restored to the version the test stage saw red: the red ledger holds that version's digest.
        digests = read_red_digests(runs, story_id)
        by_file = {t.place.value: digests.get(t.selector.value) for t in tests if t.place is not None}
        restored = frozenset(Place(path) for path in changed if by_file.get(path)
                             and os.path.isfile(os.path.join(self._cwd, path))
                             and file_digest(os.path.join(self._cwd, path)) == by_file[path])
        return StageChanges(None, Detail(""), tuple(Place(p) for p in changed), tuple(HandOverName(h) for h in handovers),
                            frozenset(Place(n) for n in listed) if listed is not None else None, restored)

    def kept_tests(self, story: StoryId) -> typing.Optional[KeptTests]:
        cwd, runs, story_id = self._cwd, self._runs, story.value
        path = os.path.join(evidence_dir(runs, story_id), TESTS_BASELINE)
        if not os.path.isfile(path):
            return None
        changed: typing.List[ChangedTest] = []
        lost: typing.List[Place] = []
        arranged: typing.List[Place] = []
        for line in read_text(path).splitlines():
            if "  " not in line:
                continue
            blob, rel = line.split("  ", 1)
            full = os.path.join(cwd, rel)
            if not os.path.isfile(full):
                changed.append(ChangedTest(Place(rel), TestChange.REMOVED))
                continue
            # A run commits nothing while a story is open: a test committed since the baseline changed outside this
            # story. The story is held to its own changes — against what is committed now. Not in a story's
            # worktree: every commit on its branch is the runner's, holding the story's own change, and what the
            # main line brought in is in the baseline already (`rebase_tests_baseline`).
            head_code, head_blob = git(cwd, "rev-parse", f"HEAD:{rel}")
            if not head_code and not in_worktree(cwd) and head_blob.strip() and head_blob.strip() != blob \
                    and not git(cwd, "cat-file", "-e", blob)[0] and not committed_by_a_stage(cwd, runs, story_id, rel):
                blob = head_blob.strip()
            code, before = git_blob(cwd, blob)
            if code:
                lost.append(Place(rel))
                continue
            with open(full, encoding="utf-8", errors="replace") as handle:
                now = meaningful_lines(handle.read(), rel)
            was = meaningful_lines(before, rel)
            # Additions only: every line the test had is still there, in the same order, outside a comment — and no
            # added line switches it off.
            remaining = iter(now)
            off = switched_off(was, now)
            kept = not off and all(any(old == new for new in remaining) for old in was)
            held = not off and not kept and assertions_kept("\n".join(was), "\n".join(now))
            edit = TestEdit.of(*(Presence.PRESENT if fact else Presence.ABSENT for fact in (off, kept, held)))
            if edit is TestEdit.SWITCHED_OFF:
                changed.append(ChangedTest(Place(rel), TestChange.SWITCHED_OFF))
            elif edit is TestEdit.ARRANGED:
                arranged.append(Place(rel))
            elif edit is TestEdit.CHANGED:
                changed.append(ChangedTest(Place(rel), TestChange.CHANGED))
        return KeptTests(tuple(changed), tuple(lost), tuple(arranged))

    def decided_tests(self, story: StoryId) -> typing.Tuple[DecidedRecord, ...]:
        ids = answered_decisions(self._cwd, story.value, "test")
        try:
            records = {str(front["id"]).strip(): (front, body) for _p, front, body, _s, _a
                       in records_of(story.value, cwd=self._cwd)}
        except GateError:
            records = {}
        found = []
        for rid in ids:
            front, body = records.get(rid, ({}, ""))
            stage = str(front.get("stage", "")).strip()
            found.append(DecidedRecord(RecordId(rid), StageName(stage) if stage else None, Detail(body)))
        return tuple(found)

    def planned_test_changes(self, story: StoryId) -> typing.Tuple[PlannedTestChange, ...]:
        return tuple(PlannedTestChange(Place(rel), Detail(str(cites)))
                     for rel, cites in changed_tests_in_plan(self._runs, story.value).items())

    def answered_records(self, story: StoryId) -> typing.FrozenSet[RecordId]:
        try:
            return frozenset(RecordId(str(front["id"]).strip()) for _p, front, _b, state, _a in records_of(story.value)
                             if state in ANSWERED_WORDS)
        except GateError:
            return frozenset()

    def red_proof(self, story: StoryId, stage: StageName,
                  tests: typing.Tuple[MappedTest, ...]) -> typing.Optional[RedProof]:
        ledger = os.path.join(evidence_dir(self._runs, story.value), ".tests-red")
        if not os.path.isfile(ledger):
            return None
        located = {t.selector.value: t.place.value for t in tests if t.place is not None}
        if stage.value == "tidy" and red_tree(self._runs, story.value) \
                and tidy_moves(self._cwd, self._runs, story.value, located):
            return RedProof(Count(0), Count(0), (), Presence.PRESENT)
        digests = read_red_digests(self._runs, story.value)
        return RedProof(Count(len(digests)), Count(sum(1 for d in digests.values() if d is None)),
                        tuple(Detail(m) for m in unproven_tests(self._cwd, located, digests)), Presence.ABSENT)

    def _absent(self, cwd: str, wanted: typing.Mapping[str, typing.Sequence[str]]) -> typing.List[str]:
        """`<selector>: …` for each wanted test that is not there."""
        looked = locate_tests(cwd, wanted)[1]
        return [f.said.value.split(" — ")[0] for f in TestChecks.exist(looked) if f.state is FindingState.FAIL]

    def spec_delta(self, story: StageStory) -> typing.Optional[SpecDelta]:
        plan_path = os.path.join(self._runs, story.story.value, "plan.md")
        if not os.path.isfile(plan_path):
            return None
        front, body = spec_front(story), read_front_matter(story.place.value)[1]
        target, spec, features, feature = story_spec(front)
        if not target:
            return None
        entries = story_entries(body)
        delta = read_delta(read_text(plan_path))
        problems = delta_problems(entries, spec, delta) \
            + rule_problems(section_of(body, "changed expectations") or [], entries, spec, delta)
        if not journeys_hold(front):
            problems += placement_problems(entries, spec, delta, feature, features)
        found = derived(entries, spec)
        return SpecDelta(Place(shown(plan_path)), Place(shown(target)), tuple(Detail(p) for p in problems),
                         tuple(ScenarioKey(k) for k in (touches(entries, spec, delta) if not problems else [])),
                         Count(sum(v == "adds" for v in found.values())), Count(sum(v == "holds" for v in found.values())))

    def spec_backing(self, story: StageStory) -> typing.Optional[Detail]:
        body = read_front_matter(story.place.value)[1]
        backing = spec_backing(self._cwd, story.story.value, body, story.place.value or None)
        return Detail(backing) if backing else None

    def spec_tests(self, story: StageStory, tests: typing.Tuple[MappedTest, ...]) -> typing.Optional[SpecTests]:
        target, spec, _features, _feature = story_spec(spec_front(story))
        if not target:
            return None
        plan = os.path.join(self._runs, story.story.value, "plan.md")
        # a criterion the story takes away takes its test with it (WP-106 B): the delta's removals are not asked for
        removed = set(read_delta(read_text(plan))["removes"]) if os.path.isfile(plan) else set()
        moved = moved_tests(self._runs, story.story.value)
        # a row names the test as it is now: the old one is gone, and the delivery writes the row into the spec
        absent = self._absent(self._cwd, moved) if moved else []
        if absent:
            return SpecTests(Place(shown(target)), tuple(Detail(a) for a in absent), Count(0), ())
        own = {t.key.value for t in tests} | set(moved) | removed
        wanted = {item["key"]: item["tests"] for item in spec if item["tests"] and item["key"] not in own}
        missing = self._absent(self._cwd, wanted) if wanted else []
        if missing and in_worktree(self._cwd):
            # The spec is the main checkout's; a story delivered there meanwhile names tests this worktree, branched
            # before it, does not have yet. They are not gone: the integrate gate checks again on the main line.
            gone_there = {m.split(":")[0] for m in self._absent(factory_home() or self._cwd, wanted)}
            missing = [m for m in missing if m.split(":")[0] in gone_there]
        return SpecTests(Place(shown(target)), (), Count(len(wanted)), tuple(Detail(m) for m in missing))

    def story_commit(self, story: StageStory, tests: typing.Tuple[MappedTest, ...]) -> typing.Optional[StoryCommit]:
        cwd = self._cwd
        target, spec, _features, _feature = story_spec(spec_front(story))
        wanted: typing.Dict[str, typing.List[str]] = {}
        for test in tests:
            wanted.setdefault(test.key.value, []).append(test.selector.value)
        for item in spec if target else []:
            if item["tests"]:
                wanted.setdefault(item["key"], [])
                wanted[item["key"]] += [t for t in item["tests"] if t not in wanted[item["key"]]]
        if not wanted:
            return None
        located = locate_tests(cwd, wanted)[0]
        files = sorted(set(located.values()))
        if not files:
            return None
        held = set(git(cwd, "ls-tree", "-r", "--name-only", "HEAD", "--", *files)[1].split("\n"))
        prefix = git(cwd, "rev-parse", "--show-prefix")[1].strip()
        # `git` strips its answer, so the first line's leading status column may be gone: the path is what follows the
        # code
        dirty = {line.split(None, 1)[1].split(" -> ")[-1] for line in
                 git(cwd, "status", "--porcelain", "--ignored", "--", *files)[1].split("\n")
                 if len(line.split(None, 1)) == 2}
        head = git(cwd, "rev-parse", "--short", "HEAD")[1].strip()
        missing = []
        for rel in files:
            if rel not in held:
                selectors = sorted(sel for sel, path in located.items() if path == rel)
                missing.append(f"{rel} ({', '.join(selectors)}) is not in it")
            elif prefix + rel in dirty or rel in dirty:
                missing.append(f"{rel} differs from it")
        return StoryCommit(Detail(head), Count(len(files)), tuple(Detail(m) for m in missing))

    def story_pass(self, story: StageStory) -> StoryPass:
        runs, story_id = self._runs, story.story.value
        order = order_for(story.kind.value)
        folder = os.path.join(runs, story_id)
        texts = current_stage_files(runs, story_id, order)
        gaps = tuple(PassGap(HandOverName(STAGE_FILES[s]),
                             Presence.PRESENT if os.path.isfile(os.path.join(folder, STAGE_FILES[s])) else Presence.ABSENT)
                     for s in order if s not in texts)
        planned = os.path.join(evidence_dir(runs, story_id), STORY_DIGEST)
        digest = PlannedDigest.MISSING if not os.path.isfile(planned) else \
            PlannedDigest.SAME if read_text(planned).strip() == story_digest(story.place.value) else PlannedDigest.CHANGED
        return StoryPass(gaps, Detail(verdict_in(texts["judge"]) or "" if "judge" in texts else ""), digest)

    def outcome(self, story: StageStory) -> OutcomeFacts:
        cwd = self._cwd
        texts = {rel: read_text(os.path.join(cwd, rel)) for rel in production_files(cwd)}
        record = os.path.join(evidence_dir(self._runs, story.story.value), "changed.txt")
        changed: typing.Optional[typing.FrozenSet[Place]] = None
        if os.path.isfile(record) and not read_text(record).startswith(NOT_OBSERVED):
            changed = frozenset(Place(parts[1]) for parts in (line.split("\t", 1) for line in read_text(record).splitlines())
                                if len(parts) == 2 and parts[0] in ("added", "modified"))
        events = []
        for name in story.publishes:
            event = name.value
            declares = re.compile(rf"\b(?:class|record|interface|struct|enum|object|type)\s+{re.escape(event)}\b")
            declared = [rel for rel, text in texts.items() if declares.search(text)]
            mention = re.compile(rf"(?<!\w){re.escape(event)}(?!\w)")
            constructs = re.compile(rf"\bnew\s+{re.escape(event)}\b|(?<!\w){re.escape(event)}\s*\.\s*\w+\s*\(")

            def raises(rel: str, text: str) -> bool:
                # The event's own file (`TaskCompleted.java`) never raises it: its factory names it, nothing else does.
                # An import, using or package line names it without raising it. A declaring file raises it where the
                # event is nested in it (the aggregate) and constructed there — `new TaskCompleted(…)`,
                # `TaskCompleted.of(…)`.
                if os.path.splitext(os.path.basename(rel))[0] == event.rsplit(".", 1)[-1]:
                    return False
                body = IMPORT_LINE.sub("", text)
                return bool(constructs.search(body)) if rel in declared else bool(mention.search(body))
            raising = [rel for rel, text in texts.items() if raises(rel, text)] if declared else []
            events.append(OutcomeEvent(name, tuple(Place(d) for d in declared), tuple(Place(r) for r in raising)))
        return OutcomeFacts(tuple(events), changed)

    def document(self, story: StoryId) -> DocumentFacts:
        path = os.path.join(self._runs, story.value, "document.md")
        try:
            text = read_text(path)
        except GateError as error:
            return DocumentFacts(Place(path), Detail(str(error)), Presence.ABSENT, Count(0), (), ())
        if needs_human_ids(text) is not None:
            return DocumentFacts(Place(path), None, Presence.PRESENT, Count(0), (), ())
        section: typing.Optional[str] = None
        missing: typing.List[str] = []
        unsourced: typing.List[str] = []
        files = 0
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("## "):
                section = stripped[3:].strip().lower()
                continue
            cells = row_cells(stripped)
            if len(cells) < 3 or cells[0].lower() in ("term", "file") or set(cells[0]) <= {"-", " "}:
                continue
            name, source = cells[0].strip("`"), cells[-1]
            if section == "documents updated" and name.strip().lower() in NOTHING:
                if not source:
                    unsourced.append("the row saying nothing was updated (no `Verified by`)")
                continue
            if section == "documents updated":
                files += 1
                target = bare_path(name)
                if target and not os.path.exists(os.path.join(self._cwd, target)):
                    missing.append(name)
                if not source:
                    unsourced.append(f"{name} (no `Verified by`)")
            elif section == "glossary" and not source:
                unsourced.append(f"glossary term {name!r}")
        for name in PATHLIKE.findall(text):
            target = bare_path(name)
            # A path, or a bare file name with a line (`BookId.java:8`) — that is a citation, and a citation resolves
            # from the project root or sends the reader nowhere.
            if ("/" in target or target != name) and not os.path.exists(os.path.join(self._cwd, target)):
                missing.append(name)
        return DocumentFacts(Place(path), None, Presence.ABSENT, Count(files), tuple(Detail(m) for m in missing),
                             tuple(Detail(u) for u in unsourced))

    def proposals(self, story: StoryId) -> typing.Optional[ProposalFacts]:
        plan = self._run_file(story, "plan.md")
        proposals = plan_proposals(plan) if plan is not None else []
        if not proposals:
            return None
        files = glossary_files(self._cwd, self._profile)
        if not files:
            return ProposalFacts(Count(len(proposals)), Presence.ABSENT, ())
        corpus = "\n".join(read_text(f).lower() for f in files)
        # a term is named open only under `## Not documented` of document.md — a row the pipeline pre-filled under
        # `## Glossary` names it, it does not account for it
        open_section = ""
        document = self._run_file(story, "document.md")
        collecting = False
        for line in (document or "").splitlines():
            if line.startswith("## "):
                collecting = line[3:].strip().lower() == "not documented"
                continue
            if collecting:
                open_section += line.lower() + "\n"
        missing = [term for term in proposals
                   if not any(word in corpus for word in proposal_words(term))
                   and not any(word in open_section for word in proposal_words(term))]
        return ProposalFacts(Count(len(proposals)), Presence.PRESENT, tuple(Detail(m) for m in missing))

    def reviews(self, story: StoryId) -> ReviewFacts:
        folder = os.path.join(self._runs, story.value, "reviews")
        read: typing.List[str] = []
        missing: typing.List[str] = []
        malformed: typing.List[str] = []
        for name, _carrier in perspectives_of(self._profile):
            path = os.path.join(folder, f"{name}.md")
            if not os.path.isfile(path):
                missing.append(name)
                continue
            text = read_text(path).lower()
            if not any(rank in text for rank in REVIEW_RANKS) and "nothing found" not in text \
                    and "no finding" not in text:
                malformed.append(name)
                continue
            read.append(name)
        return ReviewFacts(tuple(Detail(r) for r in read), tuple(Detail(m) for m in missing),
                           tuple(Detail(m) for m in malformed))

    def pipeline(self, story: StoryId) -> PipelineFacts:
        records = sorted(glob.glob(os.path.join(evidence_dir(self._runs, story.value), "changed-*.txt")))
        if not records:
            return PipelineFacts(Place(PIPELINE_DIR), None)
        touched = sorted({line.split("\t", 1)[1] for record in records for line in read_text(record).splitlines()
                          if "\t" in line and line.split("\t", 1)[1].startswith(PIPELINE_DIR)})
        return PipelineFacts(Place(PIPELINE_DIR), tuple(Place(t) for t in touched))

    def integration(self, story: StoryId) -> Integration:
        cwd, runs, story_id = self._cwd, self._runs, story.value
        home = Detail(HOME_VARIABLE)
        if not in_worktree(cwd):
            return Integration(Presence.ABSENT, home, Presence.ABSENT, Detail(""), (), (), Presence.ABSENT)
        if not integration_target(runs, story_id):
            return Integration(Presence.PRESENT, home, Presence.ABSENT, Detail(""), (), (), Presence.ABSENT)
        target = merge_target(runs, story_id, cwd)
        _code, unmerged = git(cwd, "diff", "--name-only", "--diff-filter=U")
        if unmerged.strip():
            return Integration(Presence.PRESENT, home, Presence.PRESENT, Detail(target),
                               tuple(Place(p) for p in unmerged.split()), (), Presence.ABSENT)
        code, changed = git(cwd, "diff", "--name-only", f"{target}...HEAD")
        marked = []
        for rel in changed.split("\n") if code == 0 else []:
            full = os.path.join(cwd, rel.strip())
            if rel.strip() and os.path.isfile(full):
                with contextlib.suppress(OSError, UnicodeDecodeError):
                    with open(full, encoding="utf-8") as handle:
                        if CONFLICT_MARKER.search(handle.read()):
                            marked.append(Place(rel.strip()))
        tip = git(cwd, "rev-parse", target)[1].strip()
        parent = git(cwd, "rev-parse", "HEAD~1")[1].strip() if git(cwd, "rev-parse", "HEAD")[1].strip() != tip else tip
        moved = Presence.PRESENT if tip and parent and tip != parent else Presence.ABSENT
        return Integration(Presence.PRESENT, home, Presence.PRESENT, Detail(target), (), tuple(marked), moved)

    def main_tests(self, story: StoryId) -> typing.Optional[MainTests]:
        cwd, runs, story_id = self._cwd, self._runs, story.value
        if not os.path.isfile(os.path.join(evidence_dir(runs, story_id), MAIN_TESTS)):
            return None
        lost = main_tests_lost(cwd, runs, story_id)
        adapted = tuple(MainTestLines(Place(rel), tuple(Detail(line) for line in lines))
                        for rel, lines in main_tests_adapted(cwd, runs, story_id))
        waived = []
        for rel, _lines in main_tests_lost(cwd, runs, story_id, waive=False):
            ids = main_tests_waiver(cwd, story_id, rel)
            if ids:
                waived.append((Place(rel), tuple(RecordId(i) for i in ids)))
        return MainTests(adapted, tuple(waived), Detail(lost_text(lost) if lost else ""),
                         Detail(integration_target(runs, story_id) or "the main line"))

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


class MainLineEvidence(StageEvidenceFiles):
    """The evidence at the integrate gate: the spec as the main line holds it now. With claims on a remote the main
    line is the remote's, merged into this worktree — its epics and spec read from the worktree (WP-93 D)."""

    def _main_line(self) -> typing.ContextManager[None]:
        return places_in(self._cwd) if claim_config_here(factory_home() or self._cwd) else contextlib.nullcontext()

    def spec_delta(self, story: StageStory) -> typing.Optional[SpecDelta]:
        with self._main_line():
            return super().spec_delta(story)

    def spec_backing(self, story: StageStory) -> typing.Optional[Detail]:
        with self._main_line():
            return super().spec_backing(story)
