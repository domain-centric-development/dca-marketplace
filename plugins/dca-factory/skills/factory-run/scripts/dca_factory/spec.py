"""The living spec (WP-98, WP-105): what holds, per bounded context and feature, changed only by a delivery.

A context's spec is `<spec>/<context>/scenarios.md` — what belongs to no feature — and one `<feature>/scenarios.md`
per feature below it (WP-105). A feature is a term of the context's language (its glossary entry, `Type: Feature`);
a criterion's key is unique across the whole context, so a criterion moves between features without changing its
key.

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
MOVE_LINE = re.compile(r"^[-*]\s*moves\s+`?([a-z0-9][a-z0-9-]*)`?\s*:\s*`?([a-z0-9]+)`?\s*(?:→|->)\s*`?([a-z0-9]+)`?\s*$", re.I)
FEATURE_LINE = re.compile(r"^[-*]\s*adds\s+feature\s+`?([a-z0-9]+)`?\s*$", re.I)

#: What the delta names as the place of what belongs to no feature: the context's own `scenarios.md`.
CONTEXT_WIDE = "context"
RENAME_LINE = re.compile(r'^[-*]\s*rule\s+"(.+?)"\s*(?:→|->)\s*"(.+?)"\s*$', re.I)


def context_folder(context):
    """The folder a context's spec lives in: its name lowercase, words joined by `-` — `Inventory` and
    `Product Catalog` read as `inventory` and `product-catalog`, whatever the story's spelling."""
    return re.sub(r"[^a-z0-9]+", "-", str(context or "").strip().lower()).strip("-")


def feature_name(feature):
    """A feature as its folder and the code's package spell it: lowercase letters and digits — `Product Details` and
    `productdetails` are one feature. "" for none."""
    return re.sub(r"[^a-z0-9]+", "", str(feature or "").strip().lower())


def scenarios_path(context, feature=None):
    """Where a context's criteria of this feature hold — the context's own file for none."""
    name = feature_name(feature)
    folder = os.path.join(place("spec"), context_folder(context))
    return os.path.join(folder, name, SCENARIOS_FILE) if name else os.path.join(folder, SCENARIOS_FILE)


def context_files(context):
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


def read_context(context):
    """Every criterion the context holds, across its files, each with the `feature` it stands under ("" — none)."""
    entries = []
    for feature, path in context_files(context):
        for item in read_spec(path)[1]:
            entries.append(dict(item, feature=feature))
    return entries


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
    """The plan's `## Spec delta`: {"adds"|"changes"|"holds": {key}, "removes": {key: reason}, "renames": [(old, new)],
    "moves": {key: (from, to)}, "features": {name}} — a move names the feature a criterion leaves and the one it goes
    to (`context` for none), `adds feature <name>` a feature the story brings into being."""
    delta = {"adds": set(), "changes": set(), "holds": set(), "removes": {}, "renames": [], "moves": {},
             "features": set()}
    for raw in section_of(plan_text, "spec delta") or []:
        line = raw.strip()
        moved = MOVE_LINE.match(line)
        if moved:
            delta["moves"][moved.group(1)] = (moved.group(2).lower(), moved.group(3).lower())
            continue
        born = FEATURE_LINE.match(line)
        if born:
            delta["features"].add(feature_name(born.group(1)))
            continue
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
    renamed = {old for old, _new in delta["renames"]}
    for verb in ("adds", "changes", "holds"):
        for key in sorted(delta[verb]):
            if key not in found and verb == "holds" and key in held and held[key]["rule"] in renamed:
                continue                     # it follows its rule's new text without being one of the story's (#164)
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
    for old, _new in delta["renames"]:
        if old not in rules:
            problems.append(f'rule "{old}" — the spec has no such rule')
    return problems


#: A rule's text as a person quotes it: straight, typographic or German quotation marks.
QUOTED = re.compile(r'"([^"]+)"|\u201c([^\u201d]+)\u201d|\u201e([^\u201c\u201d]+)[\u201c\u201d]')


def renamed_rules(story, spec, delta):
    """{old rule: [key]} — the criteria the spec holds under each rule the delta renames, which follow its new text."""
    return {old: [item["key"] for item in spec if item["rule"] == old and item["key"] not in delta["removes"]]
            for old, _new in delta["renames"]}


def rule_problems(changed, story, spec, delta):
    """A rule `## Changed expectations` quotes word for word, while the story no longer writes it and the delta neither
    renames it nor takes all of it away — a rewording the spec would not see: the old rule would keep its criteria and
    the story's new text would stand beside it as a second rule (#164). `changed` is the section's lines."""
    rules = {item["rule"] for item in spec if item["rule"]}
    kept = {item["rule"] for item in story}
    renamed = {old for old, _new in delta["renames"]}
    problems = []
    for line in changed:
        for match in QUOTED.finditer(line):
            text = " ".join(next(g for g in match.groups() if g).split())
            if text not in rules or text in kept or text in renamed:
                continue
            left = [item["key"] for item in spec if item["rule"] == text and item["key"] not in delta["removes"]]
            if left:
                problems.append(f'`## Changed expectations` names the rule "{text}", which the story no longer writes '
                                f'— `rule "{text}" → "<its new text>"` where it is reworded ({", ".join(left)} follow '
                                f"it), or `removes` what it takes away")
    return list(dict.fromkeys(problems))


def place_name(feature):
    """A feature as the delta names it: its name, or `context` for what belongs to none."""
    return feature or CONTEXT_WIDE


def placement_problems(story, held, delta, feature, features):
    """What is wrong with where the story's criteria go (WP-105): a criterion the context holds under another
    feature moves — the delta says `moves <key>: <from> → <to>` —, a move names what the spec and the story say, and
    a feature the context does not have yet is born with `adds feature <name>`. `held` is the context's entries with
    their feature, `features` the context's feature folders."""
    problems, keys = [], {item["key"] for item in story}
    where = {item["key"]: item["feature"] for item in held}
    target = feature_name(feature)
    for item in story:
        was = where.get(item["key"])
        if was is not None and was != target and item["key"] not in delta["moves"]:
            problems.append(f"`{item['key']}` stands under {place_name(was)} and the story puts it under "
                            f"{place_name(target)} — `moves {item['key']}: {place_name(was)} → {place_name(target)}`")
    for key, (source, destination) in sorted(delta["moves"].items()):
        if key not in where:
            problems.append(f"`moves {key}` — the spec has no `{key}`")
        elif key not in keys:
            problems.append(f"`moves {key}` — the story has no criterion `{key}`")
        elif source != place_name(where[key]) or destination != place_name(target):
            problems.append(f"`moves {key}: {source} → {destination}` — it stands under {place_name(where[key])}, and the "
                            f"story's feature is {place_name(target)}")
    if target and story and target not in features and target not in delta["features"]:
        problems.append(f"feature `{target}` is new to the context — `adds feature {target}`")
    for name in sorted(delta["features"]):
        if name in features:
            problems.append(f"`adds feature {name}` — the context has it already")
        elif name != target:
            problems.append(f"`adds feature {name}` — the story's feature is {place_name(target)}")
    return problems


def merge_context(held, story, delta, tests, feature):
    """{feature: [entry]} after the story — every file of the context: a removed criterion gone wherever it stood, a
    moved one out of its old file, a renamed rule renamed everywhere, the story's criteria merged into the file of its
    feature. A file left without a criterion maps to []."""
    target = feature_name(feature)
    leaving = set(delta["moves"]) | {item["key"] for item in story}
    files = {}
    for item in held:
        files.setdefault(item["feature"], []).append(item)
    files.setdefault(target, [])
    merged = {}
    for name, entries in files.items():
        if name == target:
            merged[name] = merge(entries, story, delta, tests)
        else:
            kept = [item for item in entries if item["key"] not in leaving]
            merged[name] = merge(kept, [], delta, {})
    return merged


def touches(story, spec, delta):
    """The keys whose behaviour the story changes or takes away — what a person's sentence has to back."""
    found = derived(story, spec)
    return sorted([key for key, verb in found.items() if verb == "changes"] + list(delta["removes"]))


def merge(spec, story, delta, tests):
    """The spec after the story: a removed criterion gone, a renamed rule renamed, and the story's criteria of each
    rule standing together in the order the story lists them, held ones included (#136) — where the first of them
    stood under that rule, or at the rule's end when none stood there (a new rule appended). So a rule's order
    follows the story that delivered it last, not the order its criteria happened to arrive in; a criterion the story
    does not list keeps its place, and a criterion that moves to another rule leaves its old one. `tests` is
    {key: [selector]} — the story's mapping; a criterion that holds keeps its test line unless the mapping names
    one."""
    renamed = dict(delta["renames"])
    merged = []
    for item in spec:
        if item["key"] in delta["removes"]:
            continue
        copy = dict(item, lines=list(item["lines"]), tests=list(item["tests"]))
        if copy["rule"] in renamed:
            copy["rule"] = renamed[copy["rule"]]
        merged.append(copy)
    held = {item["key"]: item for item in merged}
    rules = []
    for item in story:
        if item["rule"] not in rules:
            rules.append(item["rule"])
    for rule in rules:
        block = []
        for item in story:
            if item["rule"] == rule:
                new = dict(item, lines=list(item["lines"]), tests=list(tests.get(item["key"]) or []))
                new["tests"] = new["tests"] or (held[item["key"]]["tests"] if item["key"] in held else [])
                block.append(new)
        keys = {item["key"] for item in block}
        anchor = next((position for position, other in enumerate(merged)
                       if other["key"] in keys and other["rule"] == rule), None)
        if anchor is not None:
            merged[anchor] = None
        merged = [other for other in merged if other is None or other["key"] not in keys]
        if anchor is not None:
            anchor = merged.index(None)
            merged[anchor:anchor + 1] = block
            continue
        last = max((position for position, other in enumerate(merged) if other["rule"] == rule), default=None)
        if last is None:
            merged.extend(block)
        else:
            merged[last + 1:last + 1] = block
    return merged


def selectors_of(entries):
    return {item["key"]: item["tests"] for item in entries if item["tests"]}


GLOSSARY_HEADING = re.compile(r"^###\s+(.+?)\s*(?:\((.+?)\))?\s*$")
TYPE_LINE = re.compile(r"^\*\*Type:\*\*\s*(.+?)\s*$")


def glossary_features(context):
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


def lint_text(text):
    """What is wrong with one spec file's shape (WP-105): prose before the first criterion or rule (the title is the
    one line allowed), a rule without a criterion, a scenario without its `When` or its `Then`, a key twice."""
    problems, seen, rule, rule_has, scenario, steps = [], set(), None, False, None, set()

    def close_scenario():
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
            key = (criterion or line_form).group(1)
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


def lint_context(context, files=None):
    """Every problem of a context's spec, each naming its file: the shape of each file, a key that stands in two
    files, a feature folder without a glossary entry of `Type: Feature`. `files` is {feature: text} to check instead
    of what is on disk — a merge before it is written."""
    if files is None:
        files = {name: read_text(path) for name, path in context_files(context)}
    problems, where = [], {}
    named = glossary_features(context)
    for name, text in sorted(files.items()):
        shown_as = f"{context_folder(context)}/{name + '/' if name else ''}{SCENARIOS_FILE}"
        problems += [f"{shown_as}: {problem}" for problem in lint_text(text)]
        for item in parse_spec(text)[1]:
            if item["key"] in where and where[item["key"]] != name:
                problems.append(f"{shown_as}: `{item['key']}` stands in {place_name(where[item['key']])} as well")
            where.setdefault(item["key"], name)
        if name and name not in named:
            problems.append(f"{shown_as}: the feature `{name}` has no glossary entry of `Type: Feature` in "
                            f"{context_folder(context)}/{GLOSSARY_FILE}")
    return problems
