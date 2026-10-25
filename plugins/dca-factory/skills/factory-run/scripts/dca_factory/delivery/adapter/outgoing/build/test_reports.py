"""What a build left to read — the test reports and the tests they name, a command's outcome.

JUnit, TRX and Playwright reports; a command's output normalised for comparison and its reports taken from this run
alone; the scenarios a report names. Each reader says "unknown" where the format says nothing, never a guess.
"""

from __future__ import annotations

import glob
import hashlib
import os
import re
import typing
from xml.etree import ElementTree

from .....sharedkernel.adapter.outgoing.markdown.front_matter import read_text


#: Where test runners leave a report of what they actually executed. These are file-format
#: conventions rather than knowledge about any one tool: JUnit XML (Gradle, Maven, most JVM
#: runners) and TRX (the .NET test platform). A project whose reports live elsewhere says so with
#: `testReport: <glob>`.
REPORT_GLOBS = (
    "**/build/test-results/**/*.xml",
    "**/target/surefire-reports/*.xml",
    "**/target/failsafe-reports/*.xml",
    "**/test-results/**/*.xml",
    "**/TestResults/**/*.trx",
    "**/*.trx",
)


#: A selector no project can contain — the control run's subject (see `discriminates`): the class,
#: the method, and the file a `{file}` placeholder would name for it.
SENTINEL = ("dev.dca.factory.NoSuchTestClass", "noSuchTestMethod", "dev/dca/factory/NoSuchTest.py")


def fill(fmt: str, cls: str, method: str, test_path: typing.Optional[str] = None) -> str:
    """The runner's filter argument for one selector.

    `{class}` and `{method}` are the selector's two halves. `{file}` is the source file the selector
    was located in, relative to the project root and with forward slashes — the handle runners
    that select by path want (`pytest tests/test_x.py::test_y`), which no dotted name gives them.
    """
    text = fmt.replace("{class}", cls).replace("{method}", method)
    if test_path is not None:
        text = text.replace("{file}", test_path.replace(os.sep, "/"))
    return text


NOISE = re.compile(r"\b\d+(\.\d+)?\s*(ms|s|sec|seconds|minutes)\b|\b\d{2}:\d{2}:\d{2}\b")


def normalise(output: str, cwd: str) -> str:
    text = output.replace(cwd, ".")
    return NOISE.sub("<time>", text).strip()


def report_state(cwd: str, profile: typing.Mapping[str, typing.Any]) -> typing.Dict[str, typing.Tuple[str, float]]:
    """{path: (digest, mtime)} of every candidate report file right now."""
    patterns = [profile["testReport"]] if profile.get("testReport") else list(REPORT_GLOBS)
    state: typing.Dict[str, typing.Tuple[str, float]] = {}
    for pattern in patterns:
        for path in glob.glob(os.path.join(cwd, pattern), recursive=True):
            if not os.path.isfile(path):
                continue
            try:
                with open(path, "rb") as handle:
                    state[path] = (hashlib.sha256(handle.read()).hexdigest(),
                                   os.path.getmtime(path))
            except OSError:
                continue
    return state


def clock_marker(cwd: str) -> typing.Optional[float]:
    """A file written now, to read the *filesystem's* clock rather than this process's.

    Comparing report timestamps against `time.time()` imports clock skew and the filesystem's
    granularity into the check; comparing them against a file written at the same moment does not.
    """
    path = os.path.join(cwd, ".factory-gate-marker")
    try:
        with open(path, "w") as handle:
            handle.write("")
        stamp = os.path.getmtime(path)
        os.remove(path)
        return stamp
    except OSError:
        return None


def reports_from_this_run(before: typing.Dict[str, typing.Tuple[str, float]], after: typing.Dict[str, typing.Tuple[str, float]],
                          marker: typing.Optional[float]) -> typing.List[str]:
    """The report files this invocation created or rewrote.

    Two signals, because neither alone is enough. Content: a report whose bytes changed is new
    evidence — but a deterministic runner can write the same bytes twice. Time against the marker:
    a report touched after the invocation began is this run's — while a report left by an earlier
    run keeps its older timestamp and stays out, which is the case this check exists for.
    """
    fresh = []
    for path, (digest, mtime) in after.items():
        was = before.get(path)
        if was is None or was[0] != digest:
            fresh.append(path)
        elif marker is not None and mtime >= marker:
            fresh.append(path)
    return fresh


#: One test, several report cases: a parametrised test reports `test_x[a]`, `test_x[b]`, …, and a
#: JUnit writer may append the signature, `test_x(int)`. All of them are the mapped test, and one
#: failing case fails it — so the outcomes merge, and failed wins.
OUTCOME_RANK = {"failed": 2, "passed": 1, "skipped": 0}


def executed_tests(paths: typing.Iterable[str]) -> typing.Dict[typing.Tuple[str, str], str]:
    """{(class, method): outcome} for every test a report says ran. Outcome is 'passed' or 'failed'.

    Two formats, because two are enough to cover the runners this is used with. A report is the
    only artefact that states what was *executed*: an exit code says how a process ended, and a
    message says what a process printed — neither says a test ran.
    """
    ran: typing.Dict[typing.Tuple[str, str], str] = {}

    def record(cls: str, method: str, outcome: str) -> None:
        key = (cls, re.split(r"[(\[]", method, maxsplit=1)[0])
        if OUTCOME_RANK[outcome] >= OUTCOME_RANK.get(ran.get(key, ""), -1):
            ran[key] = outcome
    for path in paths:
        try:
            root = ElementTree.parse(path).getroot()
        except (ElementTree.ParseError, OSError):
            continue
        for case in root.iter():
            tag = case.tag.rsplit("}", 1)[-1]
            if tag == "testcase":                                   # JUnit XML
                cls = (case.get("classname") or "").strip()
                method = (case.get("name") or "").strip()
                outcome = "passed"
                for child in case:
                    if child.tag.rsplit("}", 1)[-1] in ("failure", "error"):
                        outcome = "failed"
                    elif child.tag.rsplit("}", 1)[-1] == "skipped":
                        outcome = "skipped"
                if method:
                    record(cls, method, outcome)
            elif tag == "UnitTestResult":                           # TRX
                name = (case.get("testName") or "").strip()
                outcome = (case.get("outcome") or "").strip().lower()
                if name:
                    cls, _, method = name.rpartition(".")
                    record(cls, method,
                           "passed" if outcome == "passed" else
                           "skipped" if outcome in ("notexecuted", "skipped") else "failed")
    return ran


#: How a test's *reported* name is declared in code where it differs from the method name. Two
#: forms cover the runners whose reports drop the method name; every other stack reports the method
#: and never reaches this.
DISPLAY_NAME = (
    re.compile(r'@DisplayName\s*\(\s*"((?:[^"\\]|\\.)*)"'),           # JUnit 5
    re.compile(r'DisplayName\s*=\s*"((?:[^"\\]|\\.)*)"'),              # xUnit [Fact(DisplayName=…)]
    re.compile(r'Description\s*=\s*"((?:[^"\\]|\\.)*)"'),              # NUnit [Test(Description=…)]
)


def unescape_literal(text: str) -> str:
    """A Java or C# string literal's content as the runtime sees it: `\\"` is `"`, `\\\\` is `\\`.
    A report carries the name unescaped, so a title with a quote in it would otherwise never match."""
    return re.sub(r"\\(.)", lambda m: {"n": "\n", "t": "\t"}.get(m.group(1), m.group(1)), text)


def display_name_of(test_path: typing.Optional[str], method: str) -> typing.Optional[str]:
    """The name this method is reported under, read from the code that declares it.

    A report that carries a display name instead of a method name needs a mapping, and the only
    honest place to get one is the declaration: the annotation sits on the method. Guessing from
    class membership instead would let a sibling's result stand in for this test.
    """
    text = read_text(test_path) if test_path and os.path.isfile(test_path) else ""
    if not text:
        return None
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if re.search(rf"\b{re.escape(method)}\s*\(", line):
            start = index
            while start > max(0, index - 8) and not lines[start - 1].strip().endswith("}"):
                start -= 1                    # stop where the declaration before this one ends
            # One text, not one line at a time: a formatter wraps a long title onto the line after the annotation
            block = "\n".join(lines[start:index + 1])
            found = [m for pattern in DISPLAY_NAME for m in pattern.finditer(block)]
            if found:
                return unescape_literal(max(found, key=lambda m: m.start()).group(1))
    return None


def outcome_for(ran: typing.Dict[typing.Tuple[str, str], str], cls: str, method: str,
                display: typing.Optional[str] = None) -> typing.Tuple[typing.Optional[str], str]:
    """What a report says about this selector: (outcome, how it was matched) or (None, "").

    The method name is the better key, but it is not always in the report — a JUnit XML writer puts
    the *display* name in `name`, so a test with a readable title loses its method name there; the
    display name declared on the method is the second key. The class narrows both: a run carries
    every selector its command covers, or the whole suite, so a case of the right class under another
    name is a sibling, not this test — the answer then names the cases it saw rather than guessing.
    """
    simple = cls.rsplit(".", 1)[-1]

    def same_class(report_class: str) -> bool:
        # both qualified, and the report's class is another package's class of the same simple name
        if "." in cls and "." in (report_class or "") and report_class.rsplit(".", 1)[-1] == simple \
                and report_class.rsplit(".", 1)[0] != cls.rsplit(".", 1)[0]:
            return False
        return (not report_class or report_class == cls
                or report_class.rsplit(".", 1)[-1] == simple
                or report_class.endswith("." + simple)
                or simple in report_class.split("."))

    for (report_class, report_method), outcome in ran.items():
        if report_method == method and same_class(report_class):
            return outcome, "by name"
    if display:
        for (report_class, report_method), outcome in ran.items():
            if report_method == display and same_class(report_class):
                return outcome, f"by the display name declared in the code ({display!r})"
    # Nothing below the name. Membership of the same class is not a mapping: a runner that ignores
    # the filter, or a filter that matches a sibling, produces exactly one case for the class that
    # is *not* this test — and counting it would let one test's outcome decide another's criterion.
    # A report without this test's name, or without the display name its declaration sets, is no
    # evidence, and the names it did carry are worth printing.
    in_class = sorted(m for (report_class, m), _o in ran.items() if same_class(report_class))
    if not in_class:
        return None, ""
    return None, (f"the report holds {len(in_class)} case(s) for that class "
                  f"({', '.join(in_class[:4])}) and none is named {method!r}"
                  + (f" or {display!r}" if display else "")
                  + (", and no display name is declared on it" if not display else ""))


# Several implementations of one behaviour, each proving the same scenarios. The scenario contract is
# markdown: `## <id>`, then `Title:` and `Runs:` lines. A report names a scenario by carrying its
# title as the test's name. Each implementation is checked against the contract — never against the
# other one, because two implementations agreeing on a wrong result is not parity.
SCENARIO_HEADING = re.compile(r"^##\s+(\S+)\s*$")


def read_scenarios(path: str) -> typing.List[typing.Dict[str, str]]:
    scenarios: typing.List[typing.Dict[str, str]] = []
    current: typing.Optional[typing.Dict[str, str]] = None
    for line in read_text(path).splitlines():
        match = SCENARIO_HEADING.match(line)
        if match:
            current = {"id": match.group(1), "title": "", "runs": "always"}
            scenarios.append(current)
        elif current is not None and ":" in line and line.split(":", 1)[0].strip().lower() in ("title", "runs"):
            key, value = line.split(":", 1)
            current[key.strip().lower()] = value.strip()
    return scenarios


def reported_names(paths: typing.Iterable[str]) -> typing.Dict[str, str]:
    """{test name: outcome} as the report states the name — whole, because a title may hold dots."""
    names: typing.Dict[str, str] = {}
    for path in paths:
        try:
            root = ElementTree.parse(path).getroot()
        except (ElementTree.ParseError, OSError):
            continue
        for case in root.iter():
            tag = case.tag.rsplit("}", 1)[-1]
            if tag == "testcase":
                name, outcome = (case.get("name") or "").strip(), "passed"
                for child in case:
                    child_tag = child.tag.rsplit("}", 1)[-1]
                    if child_tag in ("failure", "error"):
                        outcome = "failed"
                    elif child_tag == "skipped" and outcome != "failed":
                        outcome = "skipped"
            elif tag == "UnitTestResult":
                name = (case.get("testName") or "").strip()
                raw = (case.get("outcome") or "").strip().lower()
                outcome = "passed" if raw == "passed" else \
                    "skipped" if raw in ("notexecuted", "skipped", "inconclusive") else "failed"
            else:
                continue
            if name and OUTCOME_RANK[outcome] >= OUTCOME_RANK.get(names.get(name, ""), -1):
                names[name] = outcome
    return names
