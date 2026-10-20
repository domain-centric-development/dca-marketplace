"""What a run left to read — test reports, a tool's usage, a command's outcome.

JUnit, TRX and Playwright reports and the tests they name; a command run with its output and its missing-tool
reading; the suites record; the tree snapshots a stage's changes are taken from; the usage a tool writes (its
`--format json` stream, a session log). Each reader says "unknown" where the format says nothing, never a guess.
"""

import glob
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from xml.etree import ElementTree
from .contract import (
    GateError, read_profile, read_text, resolve_profile, SHARED_WINDOWS)


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


def fill(fmt, cls, method, test_path=None):
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


def normalise(output, cwd):
    text = output.replace(cwd, ".")
    return NOISE.sub("<time>", text).strip()


def report_state(cwd, profile):
    """{path: (digest, mtime)} of every candidate report file right now."""
    patterns = [profile["testReport"]] if profile.get("testReport") else list(REPORT_GLOBS)
    state = {}
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


def clock_marker(cwd):
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


def reports_from_this_run(before, after, marker):
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


def executed_tests(paths):
    """{(class, method): outcome} for every test a report says ran. Outcome is 'passed' or 'failed'.

    Two formats, because two are enough to cover the runners this is used with. A report is the
    only artefact that states what was *executed*: an exit code says how a process ended, and a
    message says what a process printed — neither says a test ran.
    """
    ran = {}

    def record(cls, method, outcome):
        key = (cls, re.split(r"[(\[]", method, maxsplit=1)[0])
        if OUTCOME_RANK[outcome] >= OUTCOME_RANK.get(ran.get(key), -1):
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


def unescape_literal(text):
    """A Java or C# string literal's content as the runtime sees it: `\\"` is `"`, `\\\\` is `\\`.
    A report carries the name unescaped, so a title with a quote in it would otherwise never match."""
    return re.sub(r"\\(.)", lambda m: {"n": "\n", "t": "\t"}.get(m.group(1), m.group(1)), text)


def display_name_of(test_path, method):
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


def outcome_for(ran, cls, method, display=None):
    """What a report says about this selector: (outcome, how it was matched) or (None, "").

    The method name is the better key, but it is not always in the report — a JUnit XML writer puts
    the *display* name in `name`, so a test with a readable title loses its method name there; the
    display name declared on the method is the second key. The class narrows both: a run carries
    every selector its command covers, or the whole suite, so a case of the right class under another
    name is a sibling, not this test — the answer then names the cases it saw rather than guessing.
    """
    simple = cls.rsplit(".", 1)[-1]

    def same_class(report_class):
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


def read_scenarios(path):
    scenarios, current = [], None
    for line in read_text(path).splitlines():
        match = SCENARIO_HEADING.match(line)
        if match:
            current = {"id": match.group(1), "title": "", "runs": "always"}
            scenarios.append(current)
        elif current is not None and ":" in line and line.split(":", 1)[0].strip().lower() in ("title", "runs"):
            key, value = line.split(":", 1)
            current[key.strip().lower()] = value.strip()
    return scenarios


def reported_names(paths):
    """{test name: outcome} as the report states the name — whole, because a title may hold dots."""
    names = {}
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
            if name and OUTCOME_RANK[outcome] >= OUTCOME_RANK.get(names.get(name), -1):
                names[name] = outcome
    return names


# What a stage cost, as the tool itself reports it. The runner saves each invocation's raw output and
# asks this script to read it; the numbers land in the story's journal next to the stage's start and
# end, so they survive restarts, second sessions and new runs like everything else there. A tool that
# reports nothing is `unknown` — never zero, because a zero would look like a cheap stage.
USAGE_FIELDS = ("input", "cache_read", "cache_write", "output")


def _claude_usage(raw):
    # `--output-format stream-json` writes one event per line and ends with a `result` event; the
    # older `--output-format json` wrote that event alone. Either way the result event is read.
    data = None
    try:
        data = json.loads(raw)
    except ValueError:
        text, events = "", 0
        for line in raw.splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if not isinstance(event, dict):
                continue
            events += 1
            if event.get("type") == "result":
                data = event
            elif event.get("type") == "assistant":
                parts = (event.get("message") or {}).get("content") or []
                said = "".join(str(p.get("text", "")) for p in parts if isinstance(p, dict) and p.get("type") == "text")
                text = said or text
        if data is None:
            # a stream cut off before its result: its last answer, never the stream itself on screen;
            # output that is no stream at all (a tool that failed to start) is shown as it is
            return None, text if events else raw
    if not isinstance(data, dict):
        return None, raw
    models = data.get("modelUsage") or {}
    if not models:
        return None, str(data.get("result", ""))
    usage = {"model": ",".join(sorted(models)),
             "input": sum(int(m.get("inputTokens", 0)) for m in models.values()),
             "cache_read": sum(int(m.get("cacheReadInputTokens", 0)) for m in models.values()),
             "cache_write": sum(int(m.get("cacheCreationInputTokens", 0)) for m in models.values()),
             "output": sum(int(m.get("outputTokens", 0)) for m in models.values())}
    if data.get("total_cost_usd") is not None:
        usage["cost"] = f"{float(data['total_cost_usd']):.4f}"
    return usage, str(data.get("result", ""))


def _codex_usage(raw):
    usage, seen, text = {k: 0 for k in USAGE_FIELDS}, False, ""
    for line in raw.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get("type") == "turn.completed" and isinstance(event.get("usage"), dict):
            seen = True
            u = event["usage"]
            cached = int(u.get("cached_input_tokens", 0))
            usage["input"] += int(u.get("input_tokens", 0)) - cached       # input counts the cached part
            usage["cache_read"] += cached
            usage["cache_write"] += int(u.get("cache_write_input_tokens", 0))
            usage["output"] += int(u.get("output_tokens", 0))
        item = event.get("item") or {}
        if event.get("type") == "item.completed" and item.get("type") in ("agent_message", "assistant_message"):
            text = str(item.get("text", text))
    return (usage if seen else None), text


def _opencode_usage(raw):
    # `opencode run --format json`: one event per line; every model step ends in a `step_finish`
    # whose part carries that step's tokens, and the answer arrives as `text` parts. A local model
    # has no price (cost 0), which is reported as no price rather than as free.
    usage, seen, text, cost = {k: 0 for k in USAGE_FIELDS}, False, [], 0.0
    for line in raw.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        part = event.get("part") or {}
        if event.get("type") == "text" and part.get("text"):
            text.append(str(part["text"]))
        if event.get("type") == "step_finish" and isinstance(part.get("tokens"), dict):
            seen = True
            t = part["tokens"]
            cache = t.get("cache") or {}
            usage["input"] += int(t.get("input", 0) or 0)
            usage["cache_read"] += int(cache.get("read", 0) or 0)
            usage["cache_write"] += int(cache.get("write", 0) or 0)
            usage["output"] += int(t.get("output", 0) or 0) + int(t.get("reasoning", 0) or 0)
            cost += float(part.get("cost", 0) or 0)
    if seen and cost > 0:
        usage["cost"] = f"{cost:.4f}"
    return (usage if seen else None), "".join(text).strip()


def parse_usage(fmt, path):
    """({model, input, cache_read, cache_write, output, cost} or None, the final message text) — the reader of the
    format answers."""
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            raw = handle.read()
    except OSError:
        return None, ""
    reader = READERS.get(fmt)
    return reader.usage(raw) if reader else (None, raw)


def parse_time(text):
    text = str(text or "").strip()
    if not text:
        return None
    try:
        stamp = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return stamp if stamp.tzinfo else stamp.replace(tzinfo=timezone.utc)


def claude_session_logs(session_id=None):
    """The session's log and its subagents' logs, for CLAUDE_CODE_SESSION_ID or the given id."""
    session_id = session_id or os.environ.get("CLAUDE_CODE_SESSION_ID", "")
    # The id may come from the journal, which is a file in the project: as a glob pattern, `*` would
    # open every session's log.
    if not session_id or not re.fullmatch(r"[\w-]+", session_id):
        return []
    home = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")
    main = glob.glob(os.path.join(home, "projects", "*", f"{session_id}.jsonl"))
    if not main:
        return []
    return main[:1] + sorted(glob.glob(os.path.join(os.path.dirname(main[0]), session_id, "subagents", "*.jsonl")))


def codex_session_log(session_id=None):
    """The Codex session log of CODEX_SESSION_ID (or the given id) — found by its file name, which ends
    in the id, so no other session's log is opened."""
    session_id = session_id or os.environ.get("CODEX_SESSION_ID") or os.environ.get("CODEX_THREAD_ID", "")
    if not session_id or not re.fullmatch(r"[\w-]+", session_id):
        return None
    home = os.environ.get("CODEX_HOME") or os.path.join(os.path.expanduser("~"), ".codex")
    found = glob.glob(os.path.join(home, "sessions", "**", f"rollout-*{session_id}.jsonl"), recursive=True)
    return found[0] if found else None


def session_usage_allowed(cwd):
    """Reading a tool's session log can be switched off: per person (FACTORY_SESSION_USAGE=off) or for
    the project (`sessionUsage: off` in the stack profile). In-session stages are then unknown."""
    if os.environ.get("FACTORY_SESSION_USAGE", "").strip().lower() in ("off", "0", "no", "false"):
        return False
    profile = read_profile(resolve_profile(None, cwd))
    return str(profile.get("sessionUsage", "on")).strip().lower() not in ("off", "0", "no", "false")


def session_usage(kind, paths, start=None, end=None):
    """{model, input, cache_read, cache_write, output} over the window, or None when nothing is read."""
    def inside(stamp):
        return stamp is not None and (start is None or stamp >= start) and (end is None or stamp <= end)
    if kind == "claude-session":
        # One API response is written as several log entries — one per content block — that share its
        # message id. The entries repeat the input and cache counts, and the output count grows until
        # the last one: counting the first entry alone undercounts output many times over. So each
        # field is the largest any entry of that message states.
        seen, models, per_message = set(), set(), {}
        for path in paths:
            try:
                handle = open(path, encoding="utf-8", errors="replace")
            except OSError:
                continue
            with handle:
                for line in handle:
                    try:
                        entry = json.loads(line)
                    except ValueError:
                        continue
                    message = entry.get("message")
                    if not isinstance(message, dict) or not isinstance(message.get("usage"), dict) \
                            or str(message.get("model", "")).startswith("<"):   # `<synthetic>`: no model call
                        continue
                    key = message.get("id") or entry.get("requestId") or entry.get("uuid")
                    if key not in seen and not inside(parse_time(entry.get("timestamp"))):
                        continue
                    seen.add(key)
                    u = message["usage"]
                    counts = per_message.setdefault(key, {k: 0 for k in USAGE_FIELDS})
                    for field, name in (("input", "input_tokens"), ("cache_read", "cache_read_input_tokens"),
                                        ("cache_write", "cache_creation_input_tokens"),
                                        ("output", "output_tokens")):
                        counts[field] = max(counts[field], int(u.get(name, 0) or 0))
                    if message.get("model"):
                        models.add(str(message["model"]))
        if not seen:
            return None
        usage = {k: sum(c[k] for c in per_message.values()) for k in USAGE_FIELDS}
        usage["model"] = ",".join(sorted(models)) or "unknown"
        return usage
    if kind == "codex-session":
        before, after, models = None, None, set()
        for path in paths:
            try:
                handle = open(path, encoding="utf-8", errors="replace")
            except OSError:
                continue
            with handle:
                for line in handle:
                    try:
                        entry = json.loads(line)
                    except ValueError:
                        continue
                    payload = entry.get("payload") or {}
                    if entry.get("type") == "turn_context" and isinstance(payload, dict) and payload.get("model"):
                        models.add(str(payload["model"]))
                    if entry.get("type") != "event_msg" or not isinstance(payload, dict) \
                            or payload.get("type") != "token_count" or not payload.get("info"):
                        continue
                    total = (payload["info"] or {}).get("total_token_usage") or {}
                    stamp = parse_time(entry.get("timestamp"))
                    if start is not None and stamp is not None and stamp < start:
                        before = total
                    elif inside(stamp):
                        after = total
        if after is None:
            return None
        base = before or {}
        diff = lambda k: int(after.get(k, 0) or 0) - int(base.get(k, 0) or 0)
        return {"model": ",".join(sorted(models)) or "unknown",
                "input": diff("input_tokens") - diff("cached_input_tokens"),
                "cache_read": diff("cached_input_tokens"), "cache_write": diff("cache_write_input_tokens"),
                "output": diff("output_tokens")}
    return None


def usage_fields(usage):
    return "\t".join(f"{k}={usage[k]}" for k in ("model",) + USAGE_FIELDS + (("cost",) if "cost" in usage else ()))


def current_session():
    """(kind, id) of the session this command runs in, from the tool's own environment variable — each reader says
    which variable is its tool's."""
    for reader in READERS.values():
        session_id = reader.session_kind and reader.session_of_env()
        if session_id:
            return reader.session_kind, session_id
    return "in-session", ""


def session_reader(kind):
    """The reader whose session logs a journal's `tool=<kind>` names."""
    return next((r for r in READERS.values() if r.session_kind and r.session_kind == kind), None)


def log_kind(path):
    """The session kind of a log a person names by path."""
    return next((r.session_kind for r in READERS.values() if r.session_kind and r.owns_log(path)), "in-session")


#: Work on a story outside its stages: writing it (the backlog skill) and answering its questions (the
#: decisions skill). Measured like a stage — a window over the session log — but it is not a stage: it
#: claims no checkout and makes no story "running", so a runner working another story is not held up.
WINDOWS = ("backlog", "decisions")


def usage_lines(fmt, path, model=None):
    """One invocation's usage from a tool's raw output: the `model=… input=…` fields (or `unknown`), then the
    final message the output carries, if any."""
    if fmt in ("claude-session", "codex-session"):
        usage = session_usage(fmt, [path])
        return [usage_fields(usage) if usage else "unknown"]
    usage, text = parse_usage(fmt, path)
    if usage is None:
        lines = ["unknown"]
    else:
        if model and not usage.get("model"):
            usage["model"] = model
        usage.setdefault("model", "unknown")
        lines = ["\t".join(f"{k}={usage[k]}" for k in ("model",) + USAGE_FIELDS + (("cost",) if "cost" in usage else ()))]
    return lines + ([text.strip()] if text.strip() else [])


def usage_from(fmt, path, model=None):
    print("\n".join(usage_lines(fmt, path, model)))
    return 0


#: Where a process that is no stage of the table sits among the stages in a report: beside a stage of a shared
#: window, by an offset — the shared builder after the last stage it carries, the reviews just before the verifier's
#: first stage, which converges them, the shared verifier after that stage; the backlog before every stage, the
#: decisions after them.
PROCESS_RANKS = {"builder": (SHARED_WINDOWS["builder"][-1], 0.5), "review:": (SHARED_WINDOWS["verifier"][0], -0.2),
                 "verifier": (SHARED_WINDOWS["verifier"][0], 0.5)}


def tokens_of(entry):
    return sum(entry[k] for k in USAGE_FIELDS)


# --- the parts of a shared window ------------------------------------------------------------------------
# A shared builder (plan … tidy) or verifier (judge, document) is one process with one usage report. Its
# stream shows where each stage begins — the process loads the stage's skill — and every answer carries its
# own tokens, so a part's time and tokens are read, not guessed. The process's cost is reported once; it is
# split over the parts in the proportion of their tokens priced relative to input (output 5, cache write
# 1.25 for five minutes or 2 for an hour, cache read 0.1 — the same ratios on every Claude model). The parts
# add up to the process's cost; each part's share is an estimate and is shown as one.

PART_WEIGHTS = {"input": 1.0, "output": 5.0, "cache_read": 0.1, "cache_write_5m": 1.25, "cache_write_1h": 2.0}


PART_SKILL = re.compile(r"(?:^|:)stage-(plan|test|build|tidy|judge|document)$")

#: The same skill read as a file — a process that opens `stage-<x>/SKILL.md` with Read or the shell instead of the
#: Skill tool has begun that stage just the same.
PART_SKILL_FILE = re.compile(r"(?:^|[/\s])stage-(plan|test|build|tidy|judge|document)/SKILL\.md\b")


def part_of_call(block):
    """The stage a tool call begins — by the Skill tool or by reading the stage's SKILL.md — or None."""
    name, given = block.get("name"), block.get("input") or {}
    if name == "Skill":
        found = PART_SKILL.search(str(given.get("skill", "")))
    elif name in ("Read", "Bash"):
        found = PART_SKILL_FILE.search(str(given.get("file_path") or given.get("command") or ""))
    else:
        return None
    return found.group(1) if found else None


def stream_parts(path, fmt=None):
    """[{stage, start, end, input, cache_read, cache_write, output, weight}] of one shared process's stream,
    in the order its stages began, and the process's reported cost (None when the stream has no result) — read from
    the common events, so every tool's stream gives its parts.

    An answer's own usage carries its input and cache tokens, but its output only as counted when the answer
    began; the final output is the process's alone. So the process's output is split over the parts by what each
    part wrote — its text, its tool calls' input and its thinking — an estimate, like the cost."""
    parts, current, answers, cost, output_total = [], None, {}, None, None
    for event in stream_events(path, fmt):
        moment = event.get("at")
        if event["kind"] == "result":
            cost = event.get("cost") if event.get("cost") is not None else cost
            output_total = event.get("output") if event.get("output") is not None else output_total
            continue
        if event["kind"] == "call":
            stage = part_of_call(event)
            if stage and (current is None or current["stage"] != stage):
                if current is not None and moment:
                    current["end"] = moment              # a part lasts until the next one begins
                current = dict(stage=stage, start=moment, end=moment)
                parts.append(current)
        if moment and current is not None:
            current["end"] = moment
        if event["kind"] == "answer":
            key = event.get("id") or f"anon-{len(answers)}"
            seen = answers.setdefault(key, {"part": current, "usage": {}, "written": 0})
            seen["written"] += int(event.get("written") or 0)
            for field, value in (event.get("usage") or {}).items():
                seen["usage"][field] = max(seen["usage"].get(field, 0), value)
    if not parts:
        return [], cost
    for part in parts:
        part.update(input=0, cache_read=0, cache_write=0, output=0, weight=0.0, written=0)
    for seen in answers.values():
        part = seen["part"] or parts[0]          # what the process did before it loaded the first stage
        u = seen["usage"]
        write = int(u.get("cache_write", 0))
        write_1h = int(u.get("cache_write_1h", 0))
        write_5m = max(write - write_1h, 0)
        part["input"] += int(u.get("input", 0))
        part["cache_read"] += int(u.get("cache_read", 0))
        part["cache_write"] += write
        part["output"] += int(u.get("output", 0))
        part["written"] += seen["written"]
        part["weight"] += (PART_WEIGHTS["input"] * int(u.get("input", 0))
                           + PART_WEIGHTS["cache_read"] * int(u.get("cache_read", 0))
                           + PART_WEIGHTS["cache_write_5m"] * write_5m + PART_WEIGHTS["cache_write_1h"] * write_1h)
    written = sum(p["written"] for p in parts)
    reported = output_total if output_total is not None else sum(p["output"] for p in parts)
    for part in parts:
        if written and reported >= sum(p["output"] for p in parts):
            part["output"] = round(reported * part["written"] / written)
        part["weight"] += PART_WEIGHTS["output"] * part["output"]
        part.pop("written", None)
    return parts, cost


def stream_denials(path, fmt=None):
    """[{stage, tool, command}] — the calls a stream's result names as denied permission, in the order they were
    made, each with the shared stage it fell in ('' outside one). A headless stage has nobody to grant a permission:
    the tool refuses the call, and the stage spends a turn on another way. A format that reports no denials gives
    none."""
    where, current, denied = {}, "", []
    for event in stream_events(path, fmt):
        if event["kind"] == "call":
            stage = part_of_call(event)
            current = stage or current
            where[event.get("id")] = current
        elif event["kind"] == "result":
            for call_id, name, given in event.get("denied") or []:
                arg = next((given[k] for k in FOLLOW_ARGS if isinstance(given, dict) and given.get(k)), "")
                denied.append(dict(stage=where.get(call_id, ""), tool=name, command=_short(str(arg), 160)))
    return denied


# --- follow: a stage you can watch --------------------------------------------------------------------
# Every stage writes its tool's output to `<evidence>/<story>/<stage>.<HHMMSS>.out` as the tool writes it: Claude's
# `stream-json`, Codex's `exec --json`, OpenCode's `run --format json` — one event per line. `follow`
# reads the newest of them and prints one line per thing the tool did, so a person can see what a stage
# does while it runs, whoever started it (a session, a shell, a worker, a bench). It starts nothing.

FOLLOW_ARGS = ("file_path", "notebook_path", "pattern", "command", "skill", "url", "path", "description", "prompt")


def _short(text, width=110):
    text = " ".join(str(text).split())
    here = os.getcwd() + os.sep
    text = text.replace(here, "")                     # a path inside the project, as the project names it
    return text if len(text) <= width else text[: width - 1] + "…"


# --- readers: one per tool output format ------------------------------------------------------------------
# A tool is a record to start (tools.py) and a reader to read: what one invocation used, what it did as common
# events, and — for a stage run by hand inside a session — where that session's log is. Everything that shows a
# stage (its parts, its denials, `follow`, the usage line) reads the events, never a format. A new tool is its
# record, its reader and the recorded streams that hold both to a real output.
#
# The common events, one dict each, `kind` first:
#   session  model                                   the process began
#   call     name, input, id                         a tool call — `name` in the Claude spelling (Read, Bash, Edit,
#                                                    Write, Skill, …), `input` with `file_path` / `command` / `skill`
#   error    id, text                                a call that failed
#   text     text                                    what the model said
#   answer   id, usage, written                      one model answer's tokens (input, cache_read, cache_write,
#                                                    cache_write_1h, output) and how much it wrote
#   result   cost, turns, duration_ms, output, denied, failed
#                                                    the process ended; `denied` [(id, name, input)]
# Every event may carry `at` (a datetime) where the format has a time.


def _json_lines(raw):
    try:
        whole = json.loads(raw)                    # a single JSON document: the result event alone
        return [whole] if isinstance(whole, dict) else []
    except ValueError:
        pass
    events = []
    for line in raw.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


def _at(event):
    return parse_time(str(event.get("timestamp", ""))) if event.get("timestamp") else None


class Reader:
    """One output format. `usage(raw)` → (usage or None, final text); `events(raw)` → the common events;
    `session_logs(id)` and `session_of_env()` for a hand session — a tool without session logs answers none."""
    fmt = ""
    session_kind = ""

    def usage(self, raw):
        return None, raw

    def events(self, raw):
        return []

    def session_logs(self, session_id=None):
        return []

    def session_of_env(self):
        return ""

    def owns_log(self, path):
        return False

    def session_usage(self, paths, start=None, end=None):
        return None

    def project_logs(self, cwd, since=None):
        """The logs a stage process of this tool writes for the project, changed since `since` — where the tool keeps
        them per project folder; [] otherwise."""
        return []


class ClaudeReader(Reader):
    fmt, session_kind = "claude-json", "claude-session"

    def usage(self, raw):
        return _claude_usage(raw)

    def events(self, raw):
        out = []
        for event in _json_lines(raw):
            kind, at = event.get("type"), _at(event)
            if kind == "system" and event.get("subtype") == "init":
                out.append({"kind": "session", "model": str(event.get("model", "")), "at": at})
            elif kind == "assistant":
                message = event.get("message") or {}
                written = 0
                for block in message.get("content") or []:
                    if not isinstance(block, dict):
                        continue
                    written += len(str(block.get("text", ""))) + len(str(block.get("thinking", ""))) \
                        + (len(json.dumps(block.get("input"))) if block.get("type") == "tool_use" else 0)
                    if block.get("type") == "tool_use":
                        given = block.get("input") if isinstance(block.get("input"), dict) else {}
                        out.append({"kind": "call", "name": str(block.get("name", "tool")), "input": given,
                                    "id": block.get("id"), "at": at})
                    elif block.get("type") == "text" and str(block.get("text", "")).strip():
                        out.append({"kind": "text", "text": str(block["text"]), "at": at})
                usage, raw_usage = {}, message.get("usage") or {}
                for field, name in (("input", "input_tokens"), ("cache_read", "cache_read_input_tokens"),
                                    ("cache_write", "cache_creation_input_tokens"), ("output", "output_tokens")):
                    if isinstance(raw_usage.get(name), (int, float)):
                        usage[field] = int(raw_usage[name])
                creation = raw_usage.get("cache_creation") if isinstance(raw_usage.get("cache_creation"), dict) else {}
                if isinstance(creation.get("ephemeral_1h_input_tokens"), (int, float)):
                    usage["cache_write_1h"] = int(creation["ephemeral_1h_input_tokens"])
                out.append({"kind": "answer", "id": message.get("id"), "usage": usage, "written": written, "at": at})
            elif kind == "user":
                for part in (event.get("message") or {}).get("content") or []:
                    if isinstance(part, dict) and part.get("type") == "tool_result" and part.get("is_error"):
                        said = part.get("content")
                        if isinstance(said, list):
                            said = " ".join(str(p.get("text", "")) for p in said if isinstance(p, dict))
                        out.append({"kind": "error", "id": part.get("tool_use_id"), "text": str(said or ""), "at": at})
            elif kind == "result":
                models = event.get("modelUsage") or {}
                output = sum(int(m.get("outputTokens", 0)) for m in models.values() if isinstance(m, dict)) if models \
                    else (int(event["usage"].get("output_tokens", 0)) if isinstance(event.get("usage"), dict) else None)
                denied = [(d.get("tool_use_id"), str(d.get("tool_name", "")), d.get("tool_input") or {})
                          for d in event.get("permission_denials") or [] if isinstance(d, dict)]
                out.append({"kind": "result", "cost": float(event["total_cost_usd"])
                            if event.get("total_cost_usd") is not None else None, "turns": event.get("num_turns"),
                            "duration_ms": event.get("duration_ms"), "output": output, "denied": denied,
                            "failed": str(event.get("subtype")) if event.get("is_error") else "", "at": at})
        return out

    def session_logs(self, session_id=None):
        return claude_session_logs(session_id)

    def session_of_env(self):
        return os.environ.get("CLAUDE_CODE_SESSION_ID", "")

    def owns_log(self, path):
        return "/.claude/" in path.replace(os.sep, "/") or bool(os.environ.get("CLAUDE_CONFIG_DIR")) \
            and os.path.abspath(path).startswith(os.path.abspath(os.environ["CLAUDE_CONFIG_DIR"]))

    def session_usage(self, paths, start=None, end=None):
        return session_usage("claude-session", paths, start, end)

    def project_logs(self, cwd, since=None):
        home = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")
        folder = os.path.join(home, "projects", re.sub(r"[^A-Za-z0-9]", "-", os.path.abspath(cwd)))
        floor = since.timestamp() if since else 0
        return [path for path in glob.glob(os.path.join(folder, "**", "*.jsonl"), recursive=True)
                if os.path.getmtime(path) >= floor]


class CodexReader(Reader):
    fmt, session_kind = "codex-jsonl", "codex-session"

    def usage(self, raw):
        return _codex_usage(raw)

    def events(self, raw):
        out, turn = [], 0
        for event in _json_lines(raw):
            kind, item, at = event.get("type"), event.get("item") or {}, _at(event)
            if kind == "thread.started":
                out.append({"kind": "session", "model": "", "at": at})
            elif kind == "item.started" and item.get("type") == "command_execution":
                out.append({"kind": "call", "name": "Bash", "input": {"command": str(item.get("command", ""))},
                            "id": item.get("id"), "at": at})
            elif kind == "item.completed" and item.get("type") == "command_execution" \
                    and item.get("exit_code") not in (None, 0):
                out.append({"kind": "error", "id": item.get("id"),
                            "text": str(item.get("aggregated_output", "") or f"exit {item.get('exit_code')}"), "at": at})
            elif kind == "item.completed" and item.get("type") == "file_change":
                names = ", ".join(str(c.get("path", "")) for c in item.get("changes") or [] if isinstance(c, dict))
                out.append({"kind": "call", "name": "Edit", "input": {"file_path": names}, "id": item.get("id"), "at": at})
            elif kind == "item.completed" and item.get("type") in ("agent_message", "assistant_message"):
                out.append({"kind": "text", "text": str(item.get("text", "")), "at": at})
            elif kind == "turn.completed" and isinstance(event.get("usage"), dict):
                u = event["usage"]
                cached = int(u.get("cached_input_tokens", 0))
                turn += 1
                out.append({"kind": "answer", "id": f"turn-{turn}", "at": at, "written": 0,
                            "usage": {"input": int(u.get("input_tokens", 0)) - cached, "cache_read": cached,
                                      "cache_write": int(u.get("cache_write_input_tokens", 0)),
                                      "output": int(u.get("output_tokens", 0))}})
            elif kind == "turn.failed":
                out.append({"kind": "result", "cost": None, "turns": turn, "duration_ms": None, "output": None,
                            "denied": [], "failed": str((event.get("error") or {}).get("message", "failed")), "at": at})
        if out and out[-1]["kind"] != "result" and any(e["kind"] == "answer" for e in out):
            out.append({"kind": "result", "cost": None, "turns": turn, "duration_ms": None, "output": None,
                        "denied": [], "failed": "", "at": None})
        return out

    def session_logs(self, session_id=None):
        found = codex_session_log(session_id)
        return [found] if found else []

    def session_of_env(self):
        return os.environ.get("CODEX_SESSION_ID") or os.environ.get("CODEX_THREAD_ID", "")

    def owns_log(self, path):
        return "/.codex/" in path.replace(os.sep, "/")

    def session_usage(self, paths, start=None, end=None):
        return session_usage("codex-session", paths, start, end)


#: OpenCode names its tools in lower case and its arguments in camel case; the common events use the Claude
#: spelling, so one rule — a part begins at a Skill or a read of `stage-<x>/SKILL.md` — holds for every tool.
OPENCODE_TOOLS = {"read": "Read", "bash": "Bash", "edit": "Edit", "write": "Write", "glob": "Glob", "grep": "Grep",
                  "skill": "Skill", "list": "Glob", "webfetch": "WebFetch", "todowrite": "TodoWrite"}


class OpencodeReader(Reader):
    fmt = "opencode-json"

    def usage(self, raw):
        return _opencode_usage(raw)

    def events(self, raw):
        out, steps, cost, seen = [], 0, 0.0, False
        for event in _json_lines(raw):
            kind, part = event.get("type"), event.get("part") or {}
            at = datetime.fromtimestamp(event["timestamp"] / 1000, timezone.utc) \
                if isinstance(event.get("timestamp"), (int, float)) else _at(event)
            if kind == "step_start" and steps == 0:
                out.append({"kind": "session", "model": "", "at": at})
            if kind == "tool_use" or part.get("type") == "tool":
                state = part.get("state") or {}
                given = dict(state.get("input") or {}) if isinstance(state.get("input"), dict) else {}
                for spelling in ("filePath", "path"):        # OpenCode 2.0 reads `path`, earlier `filePath`
                    if spelling in given and "file_path" not in given:
                        given["file_path"] = given.pop(spelling)
                name = str(part.get("tool", "tool"))
                out.append({"kind": "call", "name": OPENCODE_TOOLS.get(name.lower(), name), "input": given,
                            "id": part.get("callID") or part.get("id"), "at": at})
                if state.get("status") == "error":
                    out.append({"kind": "error", "id": part.get("callID") or part.get("id"),
                                "text": str(state.get("error", "failed")), "at": at})
            elif kind == "text" and str(part.get("text", "")).strip():
                out.append({"kind": "text", "text": str(part["text"]), "at": at})
            elif kind == "step_finish" and isinstance(part.get("tokens"), dict):
                seen, steps = True, steps + 1
                tokens, cache = part["tokens"], part["tokens"].get("cache") or {}
                cost += float(part.get("cost", 0) or 0)
                out.append({"kind": "answer", "id": f"step-{steps}", "at": at, "written": 0,
                            "usage": {"input": int(tokens.get("input", 0) or 0),
                                      "cache_read": int(cache.get("read", 0) or 0),
                                      "cache_write": int(cache.get("write", 0) or 0),
                                      "output": int(tokens.get("output", 0) or 0) + int(tokens.get("reasoning", 0) or 0)}})
        if seen:
            out.append({"kind": "result", "cost": cost if cost > 0 else None, "turns": steps, "duration_ms": None,
                        "output": None, "denied": [], "failed": "", "at": None})
        return out


#: The readers by the format a tool record names (`Tool.usage`).
READERS = {reader.fmt: reader for reader in (ClaudeReader(), CodexReader(), OpencodeReader())}


def reader_of(raw, fmt=None):
    """The reader of a stream: the one named, else the one whose events the first lines look like."""
    if fmt in READERS:
        return READERS[fmt]
    for event in _json_lines(raw)[:20]:
        kind = str(event.get("type", ""))
        if kind in ("system", "assistant", "user", "result"):
            return READERS["claude-json"]
        if kind.startswith(("thread.", "item.", "turn.")):
            return READERS["codex-jsonl"]
        if "part" in event or kind in ("step_start", "step_finish", "tool_use", "text"):
            return READERS["opencode-json"]
    return READERS["claude-json"]


def stream_events(path, fmt=None):
    try:
        raw = read_text(path)
    except (OSError, GateError):
        return []
    return reader_of(raw, fmt).events(raw)
