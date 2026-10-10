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
            for candidate in reversed(lines[max(0, index - 6):index + 1]):
                for pattern in DISPLAY_NAME:
                    match = pattern.search(candidate)
                    if match:
                        return unescape_literal(match.group(1))
                if candidate.strip().endswith("}") and candidate is not lines[index]:
                    break                     # left this method's declaration
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


def parse_usage(fmt, path):
    """({model, input, cache_read, cache_write, output, cost} or None, the final message text)."""
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            raw = handle.read()
    except OSError:
        return None, ""
    if fmt == "claude-json":
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
    if fmt == "codex-jsonl":
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
    if fmt == "opencode-json":
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
    return None, raw


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
    """(kind, id) of the session this command runs in, from the tool's own environment variable."""
    if os.environ.get("CLAUDE_CODE_SESSION_ID"):
        return "claude-session", os.environ["CLAUDE_CODE_SESSION_ID"]
    codex = os.environ.get("CODEX_SESSION_ID") or os.environ.get("CODEX_THREAD_ID")
    if codex:
        return "codex-session", codex
    return "in-session", ""


#: Work on a story outside its stages: writing it (the backlog skill) and answering its questions (the
#: decisions skill). Measured like a stage — a window over the session log — but it is not a stage: it
#: claims no checkout and makes no story "running", so a runner working another story is not held up.
WINDOWS = ("backlog", "decisions")


def usage_from(fmt, path, model=None):
    if fmt in ("claude-session", "codex-session"):
        usage = session_usage(fmt, [path])
        print(usage_fields(usage) if usage else "unknown")
        return 0
    usage, text = parse_usage(fmt, path)
    if usage is None:
        print("unknown")
    else:
        if model and not usage.get("model"):
            usage["model"] = model
        usage.setdefault("model", "unknown")
        print("\t".join(f"{k}={usage[k]}" for k in ("model",) + USAGE_FIELDS + (("cost",) if "cost" in usage else ())))
    if text.strip():
        print(text.strip())
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


def stream_parts(path):
    """[{stage, start, end, input, cache_read, cache_write, output, weight}] of one shared process's stream,
    in the order its stages began, and the process's reported cost (None when the stream has no result).

    An answer's own usage in the stream carries its input and cache tokens, but its output only as counted when
    the answer began; the final output is the process's alone. So the process's output is split over the parts
    by what each part wrote — its text, its tool calls' input and its thinking — an estimate, like the cost."""
    parts, current, answers, cost, output_total = [], None, {}, None, None
    try:
        lines = read_text(path).splitlines()
    except (OSError, GateError):
        return [], None
    for raw in lines:
        try:
            event = json.loads(raw)
        except ValueError:
            continue
        if not isinstance(event, dict):
            continue
        moment = parse_time(str(event.get("timestamp", ""))) if event.get("timestamp") else None
        if event.get("type") == "result":
            if event.get("total_cost_usd") is not None:
                cost = float(event["total_cost_usd"])
            models = event.get("modelUsage") or {}
            if models:
                output_total = sum(int(m.get("outputTokens", 0)) for m in models.values() if isinstance(m, dict))
            elif isinstance(event.get("usage"), dict):
                output_total = int(event["usage"].get("output_tokens", 0))
            continue
        if event.get("type") != "assistant":
            continue
        message = event.get("message") or {}
        for block in message.get("content") or []:
            if isinstance(block, dict) and block.get("type") == "tool_use" and block.get("name") == "Skill":
                found = PART_SKILL.search(str((block.get("input") or {}).get("skill", "")))
                if found and (current is None or current["stage"] != found.group(1)):
                    if current is not None and moment:
                        current["end"] = moment          # a part lasts until the next one begins
                    current = dict(stage=found.group(1), start=moment, end=moment, answers=set())
                    parts.append(current)
        if moment and current is not None:
            current["end"] = moment
        usage = message.get("usage") or {}
        key = message.get("id") or f"anon-{len(answers)}"
        seen = answers.setdefault(key, {"part": current, "usage": {}, "written": 0})
        for block in message.get("content") or []:
            if isinstance(block, dict):
                seen["written"] += len(str(block.get("text", ""))) + len(str(block.get("thinking", ""))) \
                    + (len(json.dumps(block.get("input"))) if block.get("type") == "tool_use" else 0)
        for field, value in usage.items():
            if isinstance(value, (int, float)):
                seen["usage"][field] = max(seen["usage"].get(field, 0), value)
        if isinstance(usage.get("cache_creation"), dict):
            for field, value in usage["cache_creation"].items():
                if isinstance(value, (int, float)):
                    seen["usage"][field] = max(seen["usage"].get(field, 0), value)
    if not parts:
        return [], cost
    for part in parts:
        part.update(input=0, cache_read=0, cache_write=0, output=0, weight=0.0, written=0)
    for seen in answers.values():
        part = seen["part"] or parts[0]          # what the process did before it loaded the first stage
        u = seen["usage"]
        write = int(u.get("cache_creation_input_tokens", 0))
        write_1h = int(u.get("ephemeral_1h_input_tokens", 0))
        write_5m = max(write - write_1h, 0)
        part["input"] += int(u.get("input_tokens", 0))
        part["cache_read"] += int(u.get("cache_read_input_tokens", 0))
        part["cache_write"] += write
        part["output"] += int(u.get("output_tokens", 0))
        part["written"] += seen["written"]
        part["weight"] += (PART_WEIGHTS["input"] * int(u.get("input_tokens", 0))
                           + PART_WEIGHTS["cache_read"] * int(u.get("cache_read_input_tokens", 0))
                           + PART_WEIGHTS["cache_write_5m"] * write_5m + PART_WEIGHTS["cache_write_1h"] * write_1h)
    written = sum(p["written"] for p in parts)
    reported = output_total if output_total is not None else sum(p["output"] for p in parts)
    for part in parts:
        if written and reported >= sum(p["output"] for p in parts):
            part["output"] = round(reported * part["written"] / written)
        part["weight"] += PART_WEIGHTS["output"] * part["output"]
        part.pop("answers", None)
        part.pop("written", None)
    return parts, cost


def stream_denials(path):
    """[{stage, tool, command}] — the calls a Claude stream's result names as denied permission, in the order they
    were made, each with the shared stage it fell in ('' outside one). A headless stage has nobody to grant a
    permission: the tool refuses the call, and the stage spends a turn on another way."""
    try:
        text = read_text(path)
    except (OSError, GateError):
        return []
    events = []
    try:
        whole = json.loads(text)                   # `--output-format json`: the result event alone
        events = [whole] if isinstance(whole, dict) else []
    except ValueError:
        for raw in text.splitlines():
            try:
                event = json.loads(raw)
            except ValueError:
                continue
            if isinstance(event, dict):
                events.append(event)
    where, current, denied = {}, "", []
    for event in events:
        if event.get("type") == "assistant":
            for block in (event.get("message") or {}).get("content") or []:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    found = PART_SKILL.search(str((block.get("input") or {}).get("skill", ""))) \
                        if block.get("name") == "Skill" and isinstance(block.get("input"), dict) else None
                    if found:
                        current = found.group(1)
                    where[block.get("id")] = current
        elif event.get("type") == "result":
            for one in event.get("permission_denials") or []:
                if not isinstance(one, dict):
                    continue
                given = one.get("tool_input") or {}
                arg = next((given[k] for k in FOLLOW_ARGS if isinstance(given, dict) and given.get(k)), "")
                denied.append(dict(stage=where.get(one.get("tool_use_id"), ""), tool=str(one.get("tool_name", "")),
                                   command=_short(str(arg), 160)))
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
