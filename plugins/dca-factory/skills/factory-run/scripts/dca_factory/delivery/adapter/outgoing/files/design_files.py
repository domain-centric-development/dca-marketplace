"""The plan's and the tests' design tables, as files: the domain types a plan changes and their invariants, the
scenarios' clauses and the lines that assert them, the plan's files, the doubles a test declares."""

from __future__ import annotations

import os
import re
import typing
from .hand_over_patterns import SELECTOR
from .....sharedkernel.adapter.outgoing.markdown.sections import section_of
from .....sharedkernel.adapter.outgoing.markdown.front_matter import read_text
from ....domain.service.design_checks import CLAUSES_MARKER, INVARIANTS_MARKER
from .test_files import contains, in_package


STEP = re.compile(r"^-\s+(Given|When|Then|And|But)\b\s*(.*)$")


def adapter_level_keys(runs: str, story_id: str) -> typing.Set[str]:
    """The keys the plan gave `integration (adapter: …)` — an incoming adapter's translation, tested against a stubbed
    input port by design (stage-test)."""
    text = read_text(os.path.join(runs, story_id, "plan.md")) if os.path.isfile(os.path.join(runs, story_id, "plan.md")) else ""
    return {m.group(1) for m in re.finditer(r"^\s*-\s+([a-z0-9][a-z0-9-]*)\b[^\n]*level:\s*integration\s*\(\s*adapter",
                                            text, re.M)}


#: The kinds of a plan's `## Changes` row that carry invariants: the domain's own types. A use case, a port, an
#: adapter or a read model has none of its own — its rules are the domain's, reached through the use case.
DOMAIN_KINDS = re.compile(r"\b(aggregate|entity|value object|value|domain service)\b", re.I)


def first_identifier(cell: str) -> str:
    """The name a table cell or a list item starts with — `Task`, `` `TaskCompleted(eventId, …)` ``, `Task — field
    state` all start with their element's name; what follows it is description, never part of the name."""
    match = re.search(r"[A-Za-z_][\w.]*", cell)
    return match.group(0) if match else ""


def plan_domain_elements(plan: str) -> typing.List[str]:
    """The elements of the plan's `## Changes` table whose kind is a domain type, in the table's order."""
    elements = []
    for line in section_of(plan, "changes") or []:
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 2 or set(cells[0]) <= set("-: ") or cells[0].strip("` ").lower() == "element":
            continue
        name = first_identifier(cells[0])
        if name and DOMAIN_KINDS.search(cells[1]) and not re.search(r"\bevent\b", cells[1], re.I):
            elements.append(name)
    return elements


def split_rules(text: str) -> typing.List[str]:
    """A plan invariant line's rules, split at `;` outside parentheses and backticks — `complete() (open → done;
    done → no change)` is one rule."""
    rules: typing.List[str] = []
    depth, tick, current = 0, False, ""
    for char in text:
        if char == "`":
            tick = not tick
        elif not tick and char in "([":
            depth += 1
        elif not tick and char in ")]" and depth:
            depth -= 1
        if char == ";" and depth == 0 and not tick:
            rules.append(current.strip())
            current = ""
        else:
            current += char
    if current.strip():
        rules.append(current.strip())
    return [r for r in rules if r]


def plan_invariants(plan: str) -> typing.Optional[typing.Dict[str, typing.List[str]]]:
    """`## Invariants` as {element: [rule, …]}: one line per domain type, `- <Element>: <rule>; <rule>`, or
    `- <Element>: none — <why>` (an empty list). None when the section is absent."""
    lines = section_of(plan, "invariants")
    if lines is None:
        return None
    found: typing.Dict[str, typing.List[str]] = {}
    for line in lines:
        match = re.match(r"^\s*-\s+(.+?)\s*:\s*(.+?)\s*$", line)
        if not match:
            continue
        name = first_identifier(match.group(1))
        # The part before the `:` is one element's name — bare, in backticks, or followed by a dash and a
        # description. A sentence there (`- The aggregate Task: …`, `- Note on the rules: …`) names no element.
        if not name or not re.fullmatch(rf"[`*]*{re.escape(name)}[`*]*(\s*\([^)]*\))?(\s+[—–-].*)?",
                                        match.group(1).strip()):
            continue
        rules = match.group(2)
        found[name] = [] if re.match(r"^none\b", rules, re.I) else split_rules(rules)
    return found


def read_invariant_rows(text: str) -> typing.Optional[typing.List[typing.Tuple[str, typing.List[int], str]]]:
    """The `gate:invariants` table of tests.md: [(element, [rule numbers], selector)] — `| TaskTitle | 1 | <rule> |
    <Class>#<method> |`, several numbers as `1, 2`; the selector is the last cell. None when the table is absent."""
    if INVARIANTS_MARKER not in text:
        return None
    rows: typing.List[typing.Any] = []
    for line in text.split(INVARIANTS_MARKER, 1)[1].splitlines():
        stripped = line.strip()
        if stripped.startswith("##"):
            break
        cells = [c.strip().strip("`") for c in stripped.strip("|").split("|")] if stripped.startswith("|") else []
        if len(cells) < 3 or cells[0].lower() == "element" or set(cells[0]) <= set("-: "):
            continue
        numbers = [int(n) for n in re.findall(r"\d+", cells[1])]
        rows.append((first_identifier(cells[0]), numbers, cells[-1]))
    return rows


def locate_selector(cwd: str, selector: str) -> typing.Optional[str]:
    """The file that holds `<Class>#<method>`: a file named after the class, in its package, that mentions the method."""
    match = SELECTOR.match(selector)
    if not match:
        return None
    cls, method = match.groups()
    simple = cls.rsplit(".", 1)[-1]
    candidates: typing.List[str] = []
    for root, dirs, files in os.walk(cwd):
        dirs[:] = [d for d in dirs if d not in BREAK_IGNORE and not d.startswith(".")]
        candidates += [os.path.join(root, f) for f in files if os.path.splitext(f)[0] == simple]
    found = [path for path in in_package(candidates, cls) if contains(path, method)]
    return found[0] if found else None


def scenario_clauses(body: str) -> typing.Dict[str, typing.List[typing.Tuple[int, str]]]:
    """{scenario key: [(n, "Then …" / "And …")]} — what each scenario says is observed: its `Then` and every `And` or
    `But` after it, numbered from 1. The `Given` and `When` steps are the arrangement, not an expectation."""
    clauses: typing.Dict[str, typing.List[typing.Tuple[int, str]]] = {}
    key: typing.Optional[str] = None
    phase: typing.Optional[str] = None
    collecting = False
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("## acceptance criteria"):
            collecting = True
            continue
        if collecting and line.startswith("## "):
            break
        if not collecting:
            continue
        if line.startswith("#### "):
            key, phase = re.sub(r"\s*\(happy path\)$", "", line[5:].strip()), None
            continue
        step = STEP.match(stripped)
        if not step or key is None:
            continue
        word, text = step.groups()
        if word in ("Given", "When", "Then"):
            phase = word
        if phase == "Then" and word in ("Then", "And", "But"):
            entries = clauses.setdefault(key, [])
            entries.append((len(entries) + 1, f"{word} {text}".strip()))
    return clauses


def read_clause_rows(text: str) -> typing.Optional[typing.List[typing.Tuple[str, int, str, str]]]:
    """The `gate:clauses` table of tests.md: [(key, n, location, level)] — `| <key> | <n> | <clause> | <File>:<line> |
    <level> |`. None when the table is absent."""
    if CLAUSES_MARKER not in text:
        return None
    rows: typing.List[typing.Any] = []
    for line in text.split(CLAUSES_MARKER, 1)[1].splitlines():
        stripped = line.strip()
        if stripped.startswith("##"):
            break
        cells = [c.strip().strip("`") for c in stripped.strip("|").split("|")] if stripped.startswith("|") else []
        if len(cells) < 5 or cells[0].lower() == "criterion" or set(cells[0]) <= set("-: "):
            continue
        number = re.match(r"\d+", cells[1])
        rows.append((cells[0], int(number.group()) if number else 0, cells[3], cells[4].lower()))
    return rows


def asserts_at(path: str, number: int) -> bool:
    """Whether the statement at line `number` of `path` asserts: the line or the three before it (a call chain's
    start) carry an assertion library's call, a framework's expectation or a mock's verification."""
    try:
        lines = read_text(path).splitlines()
    except OSError:
        return False
    if not 1 <= number <= len(lines):
        return False
    return bool(ASSERTION_STATEMENT.search(" ".join(lines[max(number - 4, 0):number])))


#: How a test declares a test double, across the common stacks — the profile's `mockMarkers:` (comma-separated)
#: replaces the list for a stack it does not cover.
MOCK_MARKERS = ("@MockitoBean", "@MockBean", "@Mock", "Mockito.mock(", "mock(", "new Mock<", "Substitute.For<",
                "A.Fake<", "MagicMock(", "create_autospec(", "jest.mock(", "vi.mock(")


def mocked_ports(text: str, markers: typing.Sequence[str], suffixes: typing.Iterable[str]) -> typing.List[str]:
    """The port types a test file declares as doubles: a marker followed, within the same declaration, by a type
    whose name ends in one of `suffixes`."""
    found: typing.Set[str] = set()
    for marker in markers:
        for match in re.finditer(re.escape(marker), text):
            window = text[match.end():match.end() + 160].split(";", 1)[0].split("{", 1)[0]
            for name in re.findall(r"\b([A-Z]\w*)\b", window):
                if name.endswith(tuple(suffixes)):
                    found.add(name)
    return sorted(found)


#: A plan's `## Files` line that says what becomes of the file: `- `<path>` — changes: new …` or `… changes: removed …`.
PLAN_FILE_LINE = re.compile(r"^\s*[-*]\s*`([^`]+)`\s*[—–-]+\s*changes:\s*(new|removed)\b", re.I)


BREAK_IGNORE = (".git", "build", "bin", "obj", "target", "node_modules", ".gradle", "TestResults", "out")


#: A statement that checks: an assertion library's call, a framework's expectation, a mock's verification.
ASSERTION_STATEMENT = re.compile(r"\b(?:assert\w*|expect\w*|andExpect\w*|verify\w*|should\w*)\b", re.IGNORECASE)
