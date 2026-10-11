"""The living spec (WP-98): what holds, one file per bounded context, changed only by a delivery.

A story is a change; `<spec>/<context>/scenarios.md` is the truth it changes. The spec takes a story's criteria in
the story's own two forms — a scenario (`#### <key>` and its steps) under its `### Rule: <text>` where it has one, or
a line (`- <key>: <criterion>`) — without the happy-path mark and without any state; under each criterion one
`Test: <selector>` line, written by the gate alone. Criteria without a rule stand before the first rule. Journeys —
flows across contexts — stand in `<spec>/journeys.md`, the same shape without rules.

The plan derives the delta (`## Spec delta` in `plan.md`): what is added, changed, removed, and which rule is renamed.
What follows from comparing the story with the spec — a key the spec lacks is added, one it holds word for word holds
already, one it holds otherwise is changed — the gate derives itself; a removal and a renamed rule only the plan can
say. Every change and removal of what holds is backed by a sentence of a person: the story's `## Changed
expectations`, or an answered decision.
"""

import os
import re

from .contract import place, read_text, section_of

SCENARIOS_FILE = "scenarios.md"
JOURNEYS_FILE = "journeys.md"
GLOSSARY_FILE = "glossary.md"

HAPPY = re.compile(r"\s*\(happy path\)")
LINE_CRITERION = re.compile(r"^-\s+([a-z0-9][a-z0-9-]*)(?:\s*\(happy path\))?\s*:\s*(\S.*)$")
CRITERION_HEADING = re.compile(r"^####\s+([a-z0-9][a-z0-9-]*)(?:\s*\(happy path\))?\s*$")
RULE_HEADING = re.compile(r"^###\s+Rule:\s*(.*\S)\s*$", re.I)
TEST_LINE = re.compile(r"^Test:\s*(.*\S)\s*$")
DELTA_LINE = re.compile(r"^[-*]\s*(adds|changes|removes|holds)\s+`?([a-z0-9][a-z0-9-]*)`?\s*(?::\s*(.*))?$", re.I)
RENAME_LINE = re.compile(r'^[-*]\s*rule\s+"(.+?)"\s*(?:→|->)\s*"(.+?)"\s*$', re.I)


def context_folder(context):
    """The folder a context's spec lives in: its name lowercase, words joined by `-` — `Inventory` and
    `Product Catalog` read as `inventory` and `product-catalog`, whatever the story's spelling."""
    return re.sub(r"[^a-z0-9]+", "-", str(context or "").strip().lower()).strip("-")


def scenarios_path(context):
    return os.path.join(place("spec"), context_folder(context), SCENARIOS_FILE)


def journeys_path():
    return os.path.join(place("spec"), JOURNEYS_FILE)


def entry(key, rule, form, lines, tests=None):
    return {"key": key, "rule": rule, "form": form, "lines": list(lines), "tests": list(tests or [])}


def trim(lines):
    while lines and not lines[-1].strip():
        lines.pop()
    return lines


def story_entries(body):
    """The criteria of a story's `## Acceptance criteria` as spec entries, the happy-path mark taken out. Read
    leniently — the gate's `criteria_of` checks the shape."""
    found, rule, current, collecting = [], None, None, False
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


def parse_spec(text):
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


def read_spec(path):
    return parse_spec(read_text(path)) if os.path.isfile(path) else ([], [])


def render_spec(preamble, entries, title):
    """The spec file, deterministically: the preamble (or `# <title>`), the criteria without a rule, then each rule
    in the order it first appears, every criterion followed by its `Test:` line where it has one."""
    out = list(preamble) if preamble else [f"# {title}"]
    rules = []
    for item in entries:
        if item["rule"] is not None and item["rule"] not in rules:
            rules.append(item["rule"])

    def block(item):
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


def words(item):
    """A criterion as compared word for word: its lines, white space collapsed, its rule beside it."""
    return (item["rule"] or "", " ".join(" ".join(item["lines"]).split()))


def read_delta(plan_text):
    """The plan's `## Spec delta`: {"adds"|"changes"|"holds": {key}, "removes": {key: reason}, "renames": [(old, new)]}."""
    delta = {"adds": set(), "changes": set(), "holds": set(), "removes": {}, "renames": []}
    for raw in section_of(plan_text, "spec delta") or []:
        line = raw.strip()
        rename = RENAME_LINE.match(line)
        if rename:
            delta["renames"].append((rename.group(1).strip(), rename.group(2).strip()))
            continue
        match = DELTA_LINE.match(line)
        if not match:
            continue
        verb, key = match.group(1).lower(), match.group(2)
        if verb == "removes":
            delta["removes"][key] = (match.group(3) or "").strip()
        else:
            delta[verb].add(key)
    return delta


def derived(story, spec):
    """{key: "adds" | "holds" | "changes"} — what follows from comparing the story's criteria with the spec."""
    held = {item["key"]: item for item in spec}
    return {item["key"]: "adds" if item["key"] not in held
            else "holds" if words(item) == words(held[item["key"]]) else "changes" for item in story}


def delta_problems(story, spec, delta):
    """What is wrong with a delta against the story and the spec — each a sentence, empty when it holds."""
    problems = []
    held = {item["key"]: item for item in spec}
    found = derived(story, spec)
    for verb in ("adds", "changes", "holds"):
        for key in sorted(delta[verb]):
            if key not in found:
                problems.append(f"`{verb} {key}` — the story has no criterion `{key}`")
            elif found[key] != verb and not (verb == "adds" and found[key] == "holds"):
                problems.append(f"`{verb} {key}` — the spec {'has no' if key not in held else 'holds'} `{key}`"
                                + ("" if key not in held else
                                   " word for word" if found[key] == "holds" else " otherwise")
                                + f": it is `{found[key]} {key}`")
    for key in sorted(delta["removes"]):
        if key not in held:
            problems.append(f"`removes {key}` — the spec has no `{key}`")
        elif key in found:
            problems.append(f"`removes {key}` — the story still has `{key}` as a criterion")
    rules = {item["rule"] for item in spec}
    for old, new in delta["renames"]:
        if old not in rules:
            problems.append(f'rule "{old}" — the spec has no such rule')
            continue
        left = [item["key"] for item in spec if item["rule"] == old
                and item["key"] not in found and item["key"] not in delta["removes"]]
        if left:
            problems.append(f'rule "{old}" → "{new}" leaves {", ".join(left)} under the old text — name each as a '
                            f"criterion of the story under the new rule, or `removes` it")
    return problems


def touches(story, spec, delta):
    """The keys whose behaviour the story changes or takes away — what a person's sentence has to back."""
    found = derived(story, spec)
    return sorted([key for key, verb in found.items() if verb == "changes"] + list(delta["removes"]))


def merge(spec, story, delta, tests):
    """The spec after the story: a changed criterion replaced where it stood (or moved to its new rule), a new one
    appended under its rule (a new rule appended), a removed one gone, a renamed rule renamed; a rule left empty goes
    with it. `tests` is {key: [selector]} — the story's mapping; a criterion that holds keeps its test line unless
    the mapping names one."""
    renamed = dict(delta["renames"])
    merged = []
    for item in spec:
        if item["key"] in delta["removes"]:
            continue
        copy = dict(item, lines=list(item["lines"]), tests=list(item["tests"]))
        if copy["rule"] in renamed:
            copy["rule"] = renamed[copy["rule"]]
        merged.append(copy)
    index = {item["key"]: position for position, item in enumerate(merged)}
    for item in story:
        new = dict(item, lines=list(item["lines"]), tests=list(tests.get(item["key"]) or []))
        if item["key"] in index:
            old = merged[index[item["key"]]]
            new["tests"] = new["tests"] or old["tests"]
            if old["rule"] == new["rule"]:
                merged[index[item["key"]]] = new
                continue
            merged[index[item["key"]]] = None
        last = max((position for position, other in enumerate(merged)
                    if other is not None and other["rule"] == new["rule"]), default=None)
        if last is None:
            merged.append(new)
        else:
            merged.insert(last + 1, new)
        index = {other["key"]: position for position, other in enumerate(merged) if other is not None}
    return [item for item in merged if item is not None]


def selectors_of(entries):
    return {item["key"]: item["tests"] for item in entries if item["tests"]}
