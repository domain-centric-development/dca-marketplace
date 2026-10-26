"""The published language, translated: a story's criteria and a plan's delta as delivery writes them, entries in and
out — and the model's rules (`LivingSpec`) in between."""

from __future__ import annotations

import re
import typing

from ..adapter.outgoing.files.spec_files import (
    CRITERION_HEADING, entry, feature_name, HAPPY, LINE_CRITERION, RULE_HEADING, trim)
from ...sharedkernel.adapter.outgoing.markdown.sections import section_of
from ..domain.model.criterion import Criterion, CriterionKey, FeatureName, Form, Line, Place, RuleText, Selector
from ..domain.model.delta import Delta, Move, Reason, Rename
from ..domain.model.living_spec import LivingSpec

#: A criterion in the published language: {key, rule, form, lines, tests} — `feature` where a context adds it.
Entry = typing.Dict[str, typing.Any]
Entries = typing.Sequence[Entry]
#: A delta in the published language, as `read_delta` reads it.
DeltaEntry = typing.Dict[str, typing.Any]
Tests = typing.Mapping[str, typing.Optional[typing.Sequence[str]]]

DELTA_LINE = re.compile(r"^[-*]\s*(adds|changes|removes|holds)\s+`?([a-z0-9][a-z0-9-]*)`?\s*(?::\s*(.*))?$", re.I)
MOVE_LINE = re.compile(r"^[-*]\s*moves\s+`?([a-z0-9][a-z0-9-]*)`?\s*:\s*`?([a-z0-9]+)`?\s*(?:→|->)\s*`?([a-z0-9]+)`?\s*$", re.I)
FEATURE_LINE = re.compile(r"^[-*]\s*adds\s+feature\s+`?([a-z0-9]+)`?\s*$", re.I)
RENAME_LINE = re.compile(r'^[-*]\s*rule\s+"(.+?)"\s*(?:→|->)\s*"(.+?)"\s*$', re.I)


# --- what delivery hands over ----------------------------------------------------------------------------------------
def story_entries(body: str) -> typing.List[Entry]:
    """The criteria of a story's `## Acceptance criteria` as spec entries, the happy-path mark taken out. Read
    leniently — the gate's `criteria_of` checks the shape."""
    found: typing.List[Entry] = []
    rule: typing.Optional[str] = None
    current: typing.Optional[Entry] = None
    collecting = False
    for raw in body.splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        if stripped.lower().startswith("## acceptance criteria"):
            collecting = True
            continue
        if collecting and line.startswith("## "):
            break
        if not collecting:
            continue
        heading = RULE_HEADING.match(line)
        if heading:
            current, rule = None, heading.group(1)
            continue
        scenario = CRITERION_HEADING.match(line)
        if scenario:
            current = entry(scenario.group(1), rule, "scenario", [f"#### {scenario.group(1)}"])
            found.append(current)
            continue
        criterion = LINE_CRITERION.match(line) if not line.startswith((" ", "\t")) else None
        if criterion:
            current = entry(criterion.group(1), rule, "line", [f"- {criterion.group(1)}: {criterion.group(2)}"])
            found.append(current)
            continue
        if current is not None and stripped:
            current["lines"].append(HAPPY.sub("", line) if current["form"] == "scenario" else line)
    for item in found:
        trim(item["lines"])
    return found


def read_delta(plan_text: str) -> DeltaEntry:
    """The plan's `## Spec delta`: {"adds"|"changes"|"holds": {key}, "removes": {key: reason}, "renames": [(old, new)],
    "moves": {key: (from, to)}, "features": {name}} — a move names the feature a criterion leaves and the one it goes
    to (`context` for none), `adds feature <name>` a feature the story brings into being."""
    adds: typing.Set[str] = set()
    changes: typing.Set[str] = set()
    holds: typing.Set[str] = set()
    removes: typing.Dict[str, str] = {}
    renames: typing.List[typing.Tuple[str, str]] = []
    moves: typing.Dict[str, typing.Tuple[str, str]] = {}
    features: typing.Set[str] = set()
    named = {"adds": adds, "changes": changes, "holds": holds}
    delta: DeltaEntry = {"adds": adds, "changes": changes, "holds": holds, "removes": removes, "renames": renames,
                         "moves": moves, "features": features}
    for raw in section_of(plan_text, "spec delta") or []:
        line = raw.strip()
        moved = MOVE_LINE.match(line)
        if moved:
            moves[moved.group(1)] = (moved.group(2).lower(), moved.group(3).lower())
            continue
        born = FEATURE_LINE.match(line)
        if born:
            features.add(feature_name(born.group(1)))
            continue
        rename = RENAME_LINE.match(line)
        if rename:
            renames.append((rename.group(1).strip(), rename.group(2).strip()))
            continue
        match = DELTA_LINE.match(line)
        if not match:
            continue
        verb, key = match.group(1).lower(), match.group(2)
        if verb == "removes":
            removes[key] = (match.group(3) or "").strip()
        else:
            named[verb].add(key)
    return delta


# --- entries and deltas into the model and back ----------------------------------------------------------------------
def criterion(item: Entry) -> Criterion:
    return Criterion(CriterionKey(item["key"]), RuleText(item["rule"]) if item["rule"] is not None else None,
                     Form(item["form"]), tuple(Line(line) for line in item["lines"]),
                     tuple(Selector(test) for test in item["tests"]), FeatureName(item.get("feature", "")))


def criteria(items: Entries) -> typing.List[Criterion]:
    return [criterion(item) for item in items]


def model_delta(delta: DeltaEntry) -> Delta:
    return Delta(adds=frozenset(CriterionKey(k) for k in delta["adds"]),
                 changes=frozenset(CriterionKey(k) for k in delta["changes"]),
                 holds=frozenset(CriterionKey(k) for k in delta["holds"]),
                 removes={CriterionKey(k): Reason(v) for k, v in delta["removes"].items()},
                 renames=tuple(Rename(RuleText(old), RuleText(new)) for old, new in delta["renames"]),
                 moves={CriterionKey(k): Move(Place(a), Place(b)) for k, (a, b) in delta["moves"].items()},
                 features=frozenset(FeatureName(name) for name in delta["features"]))


def tests_of(tests: Tests) -> typing.Dict[CriterionKey, typing.Tuple[Selector, ...]]:
    return {CriterionKey(key): tuple(Selector(s) for s in selectors or ()) for key, selectors in tests.items()}


def entries_of(merged: typing.Sequence[Criterion], story: Entries, held: Entries) -> typing.List[Entry]:
    """The merged criteria as entries: each the entry it came from — the story's where the story names its key, else
    the spec's — with its rule, lines and tests as merged; whatever else that entry carried stays."""
    from_story = {item["key"]: item for item in story}
    from_spec = {(item.get("feature", ""), item["key"]): item for item in held}
    out: typing.List[Entry] = []
    for item in merged:
        base = from_story.get(item.key.value) or from_spec.get((item.feature.value, item.key.value)) or {}
        out.append(dict(base, rule=item.rule.value if item.rule is not None else None,
                        lines=[line.value for line in item.lines], tests=[test.value for test in item.tests]))
    return out


# --- the rules -------------------------------------------------------------------------------------------------------
def derived(story: Entries, spec: Entries) -> typing.Dict[str, str]:
    """{key: "adds" | "holds" | "changes"} — what follows from comparing the story's criteria with the spec."""
    return {key.value: verdict.value for key, verdict in LivingSpec.derived(criteria(story), criteria(spec)).items()}


def delta_problems(story: Entries, spec: Entries, delta: DeltaEntry) -> typing.List[str]:
    """What is wrong with a delta against the story and the spec — each a sentence, empty when it holds."""
    return [p.value for p in LivingSpec.delta_problems(criteria(story), criteria(spec), model_delta(delta))]


def renamed_rules(story: Entries, spec: Entries, delta: DeltaEntry) -> typing.Dict[str, typing.List[str]]:
    """{old rule: [key]} — the criteria the spec holds under each rule the delta renames, which follow its new text."""
    return {old.value: [key.value for key in keys]
            for old, keys in LivingSpec.renamed_rules(criteria(spec), model_delta(delta)).items()}


def rule_problems(changed: typing.Sequence[str], story: Entries, spec: Entries,
                  delta: DeltaEntry) -> typing.List[str]:
    """A rule `## Changed expectations` quotes word for word that the story no longer writes and the delta neither
    renames nor takes away (#164). `changed` is the section's lines."""
    return [p.value for p in LivingSpec.rule_problems([Line(line) for line in changed], criteria(story),
                                                      criteria(spec), model_delta(delta))]


def place_name(feature: typing.Optional[str]) -> str:
    """A feature as the delta names it: its name, or `context` for what belongs to none."""
    return FeatureName(feature or "").place().value


def placement_problems(story: Entries, held: Entries, delta: DeltaEntry, feature: typing.Any,
                       features: typing.Iterable[str]) -> typing.List[str]:
    """What is wrong with where the story's criteria go (WP-105). `held` is the context's entries with their feature,
    `features` the context's feature folders."""
    return [p.value for p in LivingSpec.placement_problems(
        criteria(story), criteria(held), model_delta(delta), FeatureName(feature_name(feature)),
        {FeatureName(name) for name in features})]


def placement_lines(story: Entries, held: Entries, feature: typing.Any, features: typing.Iterable[str]) -> typing.List[str]:
    """The delta's lines for where the story's criteria go (WP-105): the feature born, then each criterion that moves —
    as the plan writes them and `placement_problems` holds them."""
    placed = LivingSpec.placement(criteria(story), criteria(held), FeatureName(feature_name(feature)),
                                  {FeatureName(name) for name in features})
    return [f"- adds feature {name.value}" for name in sorted(placed.features, key=lambda f: f.value)] + \
        [f"- moves {key.value}: {move.source.value} → {move.destination.value}" for key, move in placed.moves.items()]


def touches(story: Entries, spec: Entries, delta: DeltaEntry) -> typing.List[str]:
    """The keys whose behaviour the story changes or takes away — what a person's sentence has to back."""
    return [key.value for key in LivingSpec.touches(criteria(story), criteria(spec), model_delta(delta))]


def merge(spec: Entries, story: Entries, delta: DeltaEntry, tests: Tests) -> typing.List[Entry]:
    """The spec after the story (#136): a removed criterion gone, a renamed rule renamed, the story's criteria of each
    rule together in the story's order. `tests` is {key: [selector]} — the story's mapping."""
    merged = LivingSpec.merge(criteria(spec), criteria(story), model_delta(delta), tests_of(tests))
    return entries_of(merged, story, spec)


def merge_context(held: Entries, story: Entries, delta: DeltaEntry, tests: Tests,
                  feature: typing.Any) -> typing.Dict[str, typing.List[Entry]]:
    """{feature: [entry]} after the story — every file of the context; a file left without a criterion maps to []."""
    merged = LivingSpec.merge_context(criteria(held), criteria(story), model_delta(delta), tests_of(tests),
                                      FeatureName(feature_name(feature)))
    return {name.value: entries_of(items, story, held) for name, items in merged.items()}


def selectors_of(entries: Entries) -> typing.Dict[str, typing.Any]:
    return {item["key"]: item["tests"] for item in entries if item["tests"]}
