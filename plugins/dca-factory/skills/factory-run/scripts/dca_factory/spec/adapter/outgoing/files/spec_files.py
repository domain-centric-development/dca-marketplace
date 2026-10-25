"""The living spec as files (WP-98, WP-105): `<spec>/<context>/scenarios.md` — what belongs to no feature — and one
`<feature>/scenarios.md` per feature below it; journeys — flows across contexts — in `<spec>/journeys.md`, the same
shape without rules; a context's glossary beside its scenarios. A criterion is a scenario (`#### <key>` and its steps)
under its `### Rule: <text>` where it has one, or a line (`- <key>: <criterion>`); under each criterion one
`Test: <selector>` line, written by the gate alone. Criteria without a rule stand before the first rule.

Read and written here as entries — {key, rule, form, lines, tests}, `feature` where a context's reading adds it — the
published language `api` translates into the model."""

from __future__ import annotations

import os
import re
import typing

from .....sharedkernel.adapter.outgoing.profile.profile_files import place
from .....sharedkernel.adapter.outgoing.markdown.front_matter import read_text
from ....domain.model.criterion import FeatureName, Line


#: A criterion as the files read and write it: {key, rule, form, lines, tests} — `feature` where a context adds it.
Entry = typing.Dict[str, typing.Any]


SCENARIOS_FILE = "scenarios.md"


JOURNEYS_FILE = "journeys.md"


GLOSSARY_FILE = "glossary.md"


HAPPY = re.compile(r"\s*\(happy path\)")


LINE_CRITERION = re.compile(r"^-\s+([a-z0-9][a-z0-9-]*)(?:\s*\(happy path\))?\s*:\s*(\S.*)$")


CRITERION_HEADING = re.compile(r"^####\s+([a-z0-9][a-z0-9-]*)(?:\s*\(happy path\))?\s*$")


RULE_HEADING = re.compile(r"^###\s+Rule:\s*(.*\S)\s*$", re.I)


TEST_LINE = re.compile(r"^Test:\s*(.*\S)\s*$")


def context_folder(context: typing.Any) -> str:
    """The folder a context's spec lives in: its name lowercase, words joined by `-` — `Inventory` and
    `Product Catalog` read as `inventory` and `product-catalog`, whatever the story's spelling."""
    return re.sub(r"[^a-z0-9]+", "-", str(context or "").strip().lower()).strip("-")


def feature_name(feature: typing.Any) -> str:
    """A feature as its folder and the code's package spell it: lowercase letters and digits. "" for none."""
    return FeatureName.spelled(Line(str(feature or ""))).value


def scenarios_path(context: typing.Any, feature: typing.Any = None) -> str:
    """Where a context's criteria of this feature hold — the context's own file for none."""
    name = feature_name(feature)
    folder = os.path.join(place("spec"), context_folder(context))
    return os.path.join(folder, name, SCENARIOS_FILE) if name else os.path.join(folder, SCENARIOS_FILE)


def context_files(context: typing.Any) -> typing.List[typing.Tuple[str, str]]:
    """[(feature, path)] of every spec file of the context that exists: the context's own first ("" — no feature),
    then each feature folder by name."""
    folder = os.path.join(place("spec"), context_folder(context))
    found = [("", os.path.join(folder, SCENARIOS_FILE))] if os.path.isfile(os.path.join(folder, SCENARIOS_FILE)) else []
    if os.path.isdir(folder):
        for name in sorted(os.listdir(folder)):
            path = os.path.join(folder, name, SCENARIOS_FILE)
            if os.path.isfile(path):
                found.append((name, path))
    return found


def read_context(context: typing.Any) -> typing.List[Entry]:
    """Every criterion the context holds, across its files, each with the `feature` it stands under ("" — none)."""
    entries = []
    for feature, path in context_files(context):
        for item in read_spec(path)[1]:
            entries.append(dict(item, feature=feature))
    return entries


def journeys_path() -> str:
    return os.path.join(place("spec"), JOURNEYS_FILE)


def entry(key: str, rule: typing.Optional[str], form: str, lines: typing.Iterable[str],
          tests: typing.Optional[typing.Iterable[str]] = None) -> Entry:
    return {"key": key, "rule": rule, "form": form, "lines": list(lines), "tests": list(tests or [])}


def trim(lines: typing.List[str]) -> typing.List[str]:
    while lines and not lines[-1].strip():
        lines.pop()
    return lines


def parse_spec(text: str) -> typing.Tuple[typing.List[str], typing.List[Entry]]:
    """(preamble lines, [entry]) of a spec file — the preamble is everything before the first criterion or rule."""
    preamble, entries, rule, current, started = [], [], None, None, False
    for raw in text.splitlines():
        line = raw.rstrip()
        heading = RULE_HEADING.match(line)
        if heading:
            started, current, rule = True, None, heading.group(1)
            continue
        scenario = CRITERION_HEADING.match(line)
        if scenario:
            started = True
            current = entry(scenario.group(1), rule, "scenario", [f"#### {scenario.group(1)}"])
            entries.append(current)
            continue
        # A step begins with a capital word (`- Given`), a key never: an unindented `- <key>: …` is a criterion.
        criterion = LINE_CRITERION.match(line) if not line.startswith((" ", "\t")) else None
        if criterion:
            started = True
            current = entry(criterion.group(1), rule, "line", [f"- {criterion.group(1)}: {criterion.group(2)}"])
            entries.append(current)
            continue
        test = TEST_LINE.match(line.strip())
        if test and current is not None:
            current["tests"] = [part.strip() for part in test.group(1).split(",") if part.strip()]
            continue
        if not started:
            preamble.append(line)
        elif current is not None and line.strip():
            current["lines"].append(line)
    for item in entries:
        trim(item["lines"])
    return trim(preamble), entries


def read_spec(path: str) -> typing.Tuple[typing.List[str], typing.List[Entry]]:
    return parse_spec(read_text(path)) if os.path.isfile(path) else ([], [])


def render_spec(preamble: typing.List[str], entries: typing.List[Entry], title: str) -> str:
    """The spec file, deterministically: the preamble (or `# <title>`), the criteria without a rule, then each rule
    in the order it first appears, every criterion followed by its `Test:` line where it has one."""
    out = list(preamble) if preamble else [f"# {title}"]
    rules = []
    for item in entries:
        if item["rule"] is not None and item["rule"] not in rules:
            rules.append(item["rule"])

    def block(item: Entry) -> typing.List[str]:
        lines = [""] + item["lines"]
        if item["tests"]:
            lines.append(f"Test: {', '.join(item['tests'])}")
        return lines

    for item in entries:
        if item["rule"] is None:
            out += block(item)
    for rule in rules:
        out += ["", f"### Rule: {rule}"]
        for item in entries:
            if item["rule"] == rule:
                out += block(item)
    return "\n".join(out) + "\n"


GLOSSARY_HEADING = re.compile(r"^###\s+(.+?)\s*(?:\((.+?)\))?\s*$")


TYPE_LINE = re.compile(r"^\*\*Type:\*\*\s*(.+?)\s*$")


def glossary_features(context: typing.Any) -> typing.Set[str]:
    """The features a context's glossary names: every entry whose `**Type:**` is `Feature`, by the name its folder
    takes — from the code's word in parentheses where there is one, else from the term."""
    path = os.path.join(place("spec"), context_folder(context), GLOSSARY_FILE)
    found, heading = set(), None
    for line in read_text(path).splitlines() if os.path.isfile(path) else []:
        match = GLOSSARY_HEADING.match(line)
        if match:
            heading = match
            continue
        kind = TYPE_LINE.match(line.strip())
        if kind and heading and kind.group(1).strip().lower().startswith("feature"):
            found.add(feature_name(heading.group(2) or heading.group(1)))
    return found


def lint_text(text: str) -> typing.List[str]:
    """What is wrong with one spec file's shape (WP-105): prose before the first criterion or rule (the title is the
    one line allowed), a rule without a criterion, a scenario without its `When` or its `Then`, a key twice."""
    problems: typing.List[str] = []
    seen: typing.Set[str] = set()
    rule: typing.Optional[str] = None
    rule_has = False
    scenario: typing.Optional[str] = None
    steps: typing.Set[str] = set()

    def close_scenario() -> None:
        if scenario and not {"when", "then"} <= steps:
            missing = " and ".join(word.capitalize() for word in ("when", "then") if word not in steps)
            problems.append(f"scenario `{scenario}` has no `{missing}`")

    started = False
    for raw in text.splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        heading = RULE_HEADING.match(line)
        criterion = CRITERION_HEADING.match(line)
        line_form = LINE_CRITERION.match(line) if not line.startswith((" ", "\t")) else None
        if heading:
            close_scenario()
            if rule is not None and not rule_has:
                problems.append(f'rule "{rule}" has no criterion')
            started, rule, rule_has, scenario, steps = True, heading.group(1), False, None, set()
            continue
        if criterion or line_form:
            close_scenario()
            found = criterion or line_form
            assert found is not None
            key = found.group(1)
            if key in seen:
                problems.append(f"`{key}` twice")
            seen.add(key)
            started, rule_has = True, True
            scenario, steps = (key, set()) if criterion else (None, set())
            continue
        if not started:
            if stripped and not stripped.startswith("# "):
                problems.append(f"text before the first criterion or rule: {stripped[:60]!r}")
            continue
        if scenario and stripped.startswith("- "):
            steps.add(stripped[2:].split(" ", 1)[0].lower())
    close_scenario()
    if rule is not None and not rule_has:
        problems.append(f'rule "{rule}" has no criterion')
    return problems


def lint_context(context: typing.Any, files: typing.Optional[typing.Dict[str, str]] = None) -> typing.List[str]:
    """Every problem of a context's spec, each naming its file: the shape of each file, a key that stands in two
    files, a feature folder without a glossary entry of `Type: Feature`. `files` is {feature: text} to check instead
    of what is on disk — a merge before it is written."""
    if files is None:
        files = {name: read_text(path) for name, path in context_files(context)}
    problems: typing.List[str] = []
    where: typing.Dict[str, str] = {}
    named = glossary_features(context)
    for name, text in sorted(files.items()):
        shown_as = f"{context_folder(context)}/{name + '/' if name else ''}{SCENARIOS_FILE}"
        problems += [f"{shown_as}: {problem}" for problem in lint_text(text)]
        for item in parse_spec(text)[1]:
            if item["key"] in where and where[item["key"]] != name:
                problems.append(f"{shown_as}: `{item['key']}` stands in {FeatureName(where[item['key']]).place().value} as well")
            where.setdefault(item["key"], name)
        if name and name not in named:
            problems.append(f"{shown_as}: the feature `{name}` has no glossary entry of `Type: Feature` in "
                            f"{context_folder(context)}/{GLOSSARY_FILE}")
    return problems
