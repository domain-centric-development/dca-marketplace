"""What an agent tool's run left to read — its usage, the parts of a shared process, the calls it was denied, the
lines `follow` shows — through one reader per output format, and the session logs a session's usage is read from.
"""

from __future__ import annotations

import glob
import json
import os
import re
import typing
from datetime import datetime, timezone

from ..pipeline.stage_rows import STAGE_ORDER
from .....sharedkernel.adapter.outgoing.profile.profile_files import read_profile, resolve_profile
from .....sharedkernel.adapter.outgoing.markdown.front_matter import MarkdownError as GateError, read_text
from ....application.status.texts import parse_time
from ....domain.model.usage import USAGE_FIELDS

#: An event, an entry, a usage as a tool writes it: JSON.
Json = typing.Dict[str, typing.Any]
#: A usage read, and the final message the output carries.
Read = typing.Tuple[typing.Optional[Json], str]


# What a stage cost, as the tool itself reports it. The runner saves each invocation's raw output and
# asks this script to read it; the numbers land in the story's journal next to the stage's start and
# end, so they survive restarts, second sessions and new runs like everything else there. A tool that
# reports nothing is `unknown` — never zero, because a zero would look like a cheap stage.


def _claude_usage(raw: str) -> Read:
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


def _codex_usage(raw: str) -> Read:
    usage: Json = {k: 0 for k in USAGE_FIELDS}
    seen, text = False, ""
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


def _opencode_usage(raw: str) -> Read:
    # `opencode run --format json`: one event per line; every model step ends in a `step_finish`
    # whose part carries that step's tokens, and the answer arrives as `text` parts. A local model
    # has no price (cost 0), which is reported as no price rather than as free.
    usage: Json = {k: 0 for k in USAGE_FIELDS}
    seen, cost = False, 0.0
    text: typing.List[str] = []
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


def parse_usage(fmt: str, path: str) -> Read:
    """({model, input, cache_read, cache_write, output, cost} or None, the final message text) — the reader of the
    format answers."""
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            raw = handle.read()
    except OSError:
        return None, ""
    reader = READERS.get(fmt)
    return reader.usage(raw) if reader else (None, raw)


def claude_session_logs(session_id: typing.Optional[str] = None) -> typing.List[str]:
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


def codex_session_log(session_id: typing.Optional[str] = None) -> typing.Optional[str]:
    """The Codex session log of CODEX_SESSION_ID (or the given id) — found by its file name, which ends
    in the id, so no other session's log is opened."""
    session_id = session_id or os.environ.get("CODEX_SESSION_ID") or os.environ.get("CODEX_THREAD_ID", "")
    if not session_id or not re.fullmatch(r"[\w-]+", session_id):
        return None
    home = os.environ.get("CODEX_HOME") or os.path.join(os.path.expanduser("~"), ".codex")
    found = glob.glob(os.path.join(home, "sessions", "**", f"rollout-*{session_id}.jsonl"), recursive=True)
    return found[0] if found else None


def session_usage_allowed(cwd: str) -> bool:
    """Reading a tool's session log can be switched off: per person (FACTORY_SESSION_USAGE=off) or for
    the project (`sessionUsage: off` in the stack profile). In-session stages are then unknown."""
    if os.environ.get("FACTORY_SESSION_USAGE", "").strip().lower() in ("off", "0", "no", "false"):
        return False
    profile = read_profile(resolve_profile(None, cwd))
    return str(profile.get("sessionUsage", "on")).strip().lower() not in ("off", "0", "no", "false")


def session_usage(kind: str, paths: typing.Iterable[str], start: typing.Optional[datetime] = None,
                  end: typing.Optional[datetime] = None) -> typing.Optional[Json]:
    """{model, input, cache_read, cache_write, output} over the window, or None when nothing is read."""
    def inside(stamp: typing.Optional[datetime]) -> bool:
        return stamp is not None and (start is None or stamp >= start) and (end is None or stamp <= end)
    if kind == "claude-session":
        # One API response is written as several log entries — one per content block — that share its
        # message id. The entries repeat the input and cache counts, and the output count grows until
        # the last one: counting the first entry alone undercounts output many times over. So each
        # field is the largest any entry of that message states.
        seen: typing.Set[typing.Any] = set()
        models: typing.Set[str] = set()
        per_message: typing.Dict[typing.Any, typing.Dict[str, int]] = {}
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
        usage: Json = {k: sum(c[k] for c in per_message.values()) for k in USAGE_FIELDS}
        usage["model"] = ",".join(sorted(models)) or "unknown"
        return usage
    if kind == "codex-session":
        before: typing.Optional[Json] = None
        after: typing.Optional[Json] = None
        models = set()
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


def usage_fields(usage: Json) -> str:
    return "\t".join(f"{k}={usage[k]}" for k in ("model",) + USAGE_FIELDS + (("cost",) if "cost" in usage else ()))


def current_session() -> typing.Tuple[str, str]:
    """(kind, id) of the session this command runs in, from the tool's own environment variable — each reader says
    which variable is its tool's."""
    for reader in READERS.values():
        session_id = reader.session_kind and reader.session_of_env()
        if session_id:
            return reader.session_kind, session_id
    return "in-session", ""


def session_reader(kind: str) -> typing.Optional[Reader]:
    """The reader whose session logs a journal's `tool=<kind>` names."""
    return next((r for r in READERS.values() if r.session_kind and r.session_kind == kind), None)


def log_kind(path: str) -> str:
    """The session kind of a log a person names by path."""
    return next((r.session_kind for r in READERS.values() if r.session_kind and r.owns_log(path)), "in-session")


#: Work on a story outside its stages: writing it (the backlog skill) and answering its questions (the
#: decisions skill). Measured like a stage — a window over the session log — but it is not a stage: it
#: claims no checkout and makes no story "running", so a runner working another story is not held up.
WINDOWS = ("backlog", "decisions")


def usage_lines(fmt: str, path: str, model: typing.Optional[str] = None) -> typing.List[str]:
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


def usage_from(fmt: str, path: str, model: typing.Optional[str] = None) -> int:
    print("\n".join(usage_lines(fmt, path, model)))
    return 0


def tokens_of(entry: typing.Mapping[str, typing.Any]) -> int:
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


def part_of_call(block: Json) -> typing.Optional[str]:
    """The stage a tool call begins — by the Skill tool or by reading the stage's SKILL.md — or None."""
    name, given = block.get("name"), block.get("input") or {}
    if name == "Skill":
        found = PART_SKILL.search(str(given.get("skill", "")))
    elif name in ("Read", "Bash"):
        found = PART_SKILL_FILE.search(str(given.get("file_path") or given.get("command") or ""))
    else:
        return None
    return found.group(1) if found else None


#: A shared process that loads no stage's skill — a builder resumed after a question goes straight to the skeletons
#: and the gates — still shows where a stage begins: its skeleton (`--plan-skeleton`, `--files-skeleton <story>
#: <stage>`) and its gate (`story-gate.py … --stage <stage>`).
PART_SKELETON = re.compile(r"factory-cli\.py\b.*?--(?:plan-skeleton\b|files-skeleton\s+\S+\s+(plan|test|build|tidy|judge|document)\b)")
PART_GATE = re.compile(r"story-gate\.py\b.*?--stage\s+(plan|test|build|tidy|judge|document)\b")


def part_marker(block: Json) -> typing.Tuple[typing.Optional[str], str]:
    """(stage, how) a tool call marks: `skill` — the stage's skill loaded —, `skeleton` or `gate`; (None, '')."""
    stage = part_of_call(block)
    if stage:
        return stage, "skill"
    if block.get("name") != "Bash":
        return None, ""
    command = str((block.get("input") or {}).get("command") or "")
    found = PART_SKELETON.search(command)
    if found:
        return found.group(1) or "plan", "skeleton"
    found = PART_GATE.search(command)
    return (found.group(1), "gate") if found else (None, "")


def next_part(current: typing.Optional[str], block: Json) -> typing.Optional[str]:
    """The stage a call moves a shared process into, None where it stays. A gate call never moves it back: a later
    stage that runs an earlier stage's gate again checks its ground, it does not return to that stage."""
    stage, how = part_marker(block)
    if not stage or stage == current:
        return None
    if how == "gate" and current in STAGE_ORDER and stage in STAGE_ORDER and STAGE_ORDER.index(stage) < STAGE_ORDER.index(current):
        return None
    return stage


def stream_parts(path: str, fmt: typing.Optional[str] = None) -> typing.Tuple[typing.List[Json], typing.Optional[float]]:
    """[{stage, start, end, input, cache_read, cache_write, output, weight}] of one shared process's stream,
    in the order its stages began (`next_part`: a stage's skill, skeleton or gate), and the process's reported cost (None when the stream has no result) — read from
    the common events, so every tool's stream gives its parts.

    An answer's own usage carries its input and cache tokens, but its output only as counted when the answer
    began; the final output is the process's alone. So the process's output is split over the parts by what each
    part wrote — its text, its tool calls' input and its thinking — an estimate, like the cost."""
    parts: typing.List[Json] = []
    current: typing.Optional[Json] = None
    answers: typing.Dict[typing.Any, Json] = {}
    cost: typing.Any = None
    output_total: typing.Any = None
    for event in stream_events(path, fmt):
        moment = event.get("at")
        if event["kind"] == "result":
            cost = event.get("cost") if event.get("cost") is not None else cost
            output_total = event.get("output") if event.get("output") is not None else output_total
            continue
        if event["kind"] == "call":
            stage = next_part(current["stage"] if current else None, event)
            if stage:
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


def stream_denials(path: str, fmt: typing.Optional[str] = None) -> typing.List[Json]:
    """[{stage, tool, command}] — the calls a stream's result names as denied permission, in the order they were
    made, each with the shared stage it fell in ('' outside one). A headless stage has nobody to grant a permission:
    the tool refuses the call, and the stage spends a turn on another way. A format that reports no denials gives
    none."""
    where, current, denied = {}, "", []
    for event in stream_events(path, fmt):
        if event["kind"] == "call":
            current = next_part(current or None, event) or current
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


def _short(text: typing.Any, width: int = 110) -> str:
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


def _json_lines(raw: str) -> typing.List[Json]:
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


def _at(event: Json) -> typing.Optional[datetime]:
    return parse_time(str(event.get("timestamp", ""))) if event.get("timestamp") else None


class Reader:
    """One output format. `usage(raw)` → (usage or None, final text); `events(raw)` → the common events;
    `session_logs(id)` and `session_of_env()` for a hand session — a tool without session logs answers none."""
    fmt = ""
    session_kind = ""

    def usage(self, raw: str) -> Read:
        return None, raw

    def events(self, raw: str) -> typing.List[Json]:
        return []

    def session_logs(self, session_id: typing.Optional[str] = None) -> typing.List[str]:
        return []

    def session_of_env(self) -> str:
        return ""

    def owns_log(self, path: str) -> bool:
        return False

    def session_usage(self, paths: typing.Iterable[str], start: typing.Optional[datetime] = None,
                      end: typing.Optional[datetime] = None) -> typing.Optional[Json]:
        return None

    def project_logs(self, cwd: str, since: typing.Optional[datetime] = None) -> typing.List[str]:
        """The logs a stage process of this tool writes for the project, changed since `since` — where the tool keeps
        them per project folder; [] otherwise."""
        return []

    def limit(self, raw: str) -> typing.Optional[Json]:
        """Where the process stopped at the tool's usage limit: {"until": the reset as epoch seconds, or None where the
        output names none; "text": what the tool said} — else None. Only a tool whose output at the limit was recorded
        is read; any other answers None, and the runner treats its exit as any other."""
        return None


class ClaudeReader(Reader):
    fmt, session_kind = "claude-json", "claude-session"

    def usage(self, raw: str) -> Read:
        return _claude_usage(raw)

    def events(self, raw: str) -> typing.List[Json]:
        out: typing.List[Json] = []
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
                usage: typing.Dict[str, int] = {}
                raw_usage = message.get("usage") or {}
                for field, name in (("input", "input_tokens"), ("cache_read", "cache_read_input_tokens"),
                                    ("cache_write", "cache_creation_input_tokens"), ("output", "output_tokens")):
                    if isinstance(raw_usage.get(name), (int, float)):
                        usage[field] = int(raw_usage[name])
                creation: typing.Any = raw_usage.get("cache_creation") if isinstance(raw_usage.get("cache_creation"), dict) else {}
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

    def limit(self, raw: str) -> typing.Optional[Json]:
        # Recorded 2026-10-13 (`claude -p --output-format stream-json`): the result carries `api_error:
        # usage_limit_reached` (status 429) and "You've hit your session limit · resets 7:10am (Europe/Berlin)"; the
        # `rate_limit_event` before it, `status: rejected`, names the reset as `resetsAt` in epoch seconds.
        events = _json_lines(raw)
        result = next((e for e in reversed(events) if e.get("type") == "result"), None)
        if not result or not (result.get("api_error") == "usage_limit_reached"
                              or result.get("is_error") and result.get("api_error_status") == 429):
            return None
        until = None
        for event in events:
            info = event.get("rate_limit_info") if event.get("type") == "rate_limit_event" else None
            if isinstance(info, dict) and info.get("status") == "rejected" \
                    and isinstance(info.get("resetsAt"), (int, float)):
                until = int(info["resetsAt"])
        return {"until": until, "text": str(result.get("result", "")).strip()}

    def session_logs(self, session_id: typing.Optional[str] = None) -> typing.List[str]:
        return claude_session_logs(session_id)

    def session_of_env(self) -> str:
        return os.environ.get("CLAUDE_CODE_SESSION_ID", "")

    def owns_log(self, path: str) -> bool:
        return "/.claude/" in path.replace(os.sep, "/") or bool(os.environ.get("CLAUDE_CONFIG_DIR")) \
            and os.path.abspath(path).startswith(os.path.abspath(os.environ["CLAUDE_CONFIG_DIR"]))

    def session_usage(self, paths: typing.Iterable[str], start: typing.Optional[datetime] = None,
                      end: typing.Optional[datetime] = None) -> typing.Optional[Json]:
        return session_usage("claude-session", paths, start, end)

    def project_logs(self, cwd: str, since: typing.Optional[datetime] = None) -> typing.List[str]:
        home = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")
        folder = os.path.join(home, "projects", re.sub(r"[^A-Za-z0-9]", "-", os.path.abspath(cwd)))
        floor = since.timestamp() if since else 0
        return [path for path in glob.glob(os.path.join(folder, "**", "*.jsonl"), recursive=True)
                if os.path.getmtime(path) >= floor]


class CodexReader(Reader):
    fmt, session_kind = "codex-jsonl", "codex-session"

    def usage(self, raw: str) -> Read:
        return _codex_usage(raw)

    def events(self, raw: str) -> typing.List[Json]:
        out: typing.List[Json] = []
        turn = 0
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

    def session_logs(self, session_id: typing.Optional[str] = None) -> typing.List[str]:
        found = codex_session_log(session_id)
        return [found] if found else []

    def session_of_env(self) -> str:
        return os.environ.get("CODEX_SESSION_ID") or os.environ.get("CODEX_THREAD_ID", "")

    def owns_log(self, path: str) -> bool:
        return "/.codex/" in path.replace(os.sep, "/")

    def session_usage(self, paths: typing.Iterable[str], start: typing.Optional[datetime] = None,
                      end: typing.Optional[datetime] = None) -> typing.Optional[Json]:
        return session_usage("codex-session", paths, start, end)


#: OpenCode names its tools in lower case and its arguments in camel case; the common events use the Claude
#: spelling, so one rule — a part begins at a Skill or a read of `stage-<x>/SKILL.md` — holds for every tool.
OPENCODE_TOOLS = {"read": "Read", "bash": "Bash", "edit": "Edit", "write": "Write", "glob": "Glob", "grep": "Grep",
                  "skill": "Skill", "list": "Glob", "webfetch": "WebFetch", "todowrite": "TodoWrite"}


class OpencodeReader(Reader):
    fmt = "opencode-json"

    def usage(self, raw: str) -> Read:
        return _opencode_usage(raw)

    def events(self, raw: str) -> typing.List[Json]:
        out: typing.List[Json] = []
        steps, cost, seen = 0, 0.0, False
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


def reader_of(raw: str, fmt: typing.Optional[str] = None) -> Reader:
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


def stream_events(path: str, fmt: typing.Optional[str] = None) -> typing.List[Json]:
    try:
        raw = read_text(path)
    except (OSError, GateError):
        return []
    return reader_of(raw, fmt).events(raw)


def stream_limit(path: str, fmt: typing.Optional[str] = None) -> typing.Optional[Json]:
    """The tool's usage limit in one process's output, as `Reader.limit` reads it — None where it ran into none."""
    try:
        raw = read_text(path)
    except (OSError, GateError):
        return None
    return reader_of(raw, fmt).limit(raw)


def follow_render(event: Json, denied: typing.AbstractSet[str] = frozenset()) -> typing.List[str]:
    """The lines one common event stands for — [] for an event that shows nothing. `denied` holds the ids of the
    calls the stream's result names as denied permission: known once the process ended, so a running one shows such
    a call as any failed call, by the reason the tool gave. One rendering for every tool: the readers turn each
    format into the same events."""
    kind = event.get("kind")
    if kind == "session":
        return [f"· session started{(' — ' + event['model']) if event.get('model') else ''}"]
    if kind == "call":
        given = event.get("input") or {}
        lines = []
        stage = part_of_call(event)
        if stage:
            lines.append(f"── {stage}")                             # a shared process begins this stage
            if event.get("name") == "Skill":
                return lines
        arg = next((given[k] for k in FOLLOW_ARGS if isinstance(given, dict) and given.get(k)), "")
        return lines + [f"▸ {event.get('name', 'tool')} {_short(arg, 100)}".rstrip()]
    if kind == "error":
        said = " — ".join([line.strip() for line in str(event.get("text") or "").splitlines() if line.strip()][:2]) \
            or "failed"
        return [f"✗ {'denied: ' if event.get('id') in denied else ''}{_short(said, 120)}"]
    if kind == "text" and str(event.get("text", "")).strip():
        return [f"  {_short(event['text'])}"]
    if kind == "result":
        bits = [f"{event['turns']} turns" if event.get("turns") is not None else "",
                f"${float(event['cost']):.2f}" if event.get("cost") is not None else "",
                f"{int(event['duration_ms']) // 1000}s" if event.get("duration_ms") else "",
                f"{len(event['denied'])} denied" if event.get("denied") else ""]
        state = "stopped: " + event["failed"] if event.get("failed") else "done"
        return [f"■ {state}" + (" — " + ", ".join(b for b in bits if b) if any(bits) else "")]
    return []


def follow_lines(text: str, fmt: typing.Optional[str] = None) -> typing.Tuple[typing.List[str], bool]:
    events = reader_of(text, fmt).events(text)
    ended = any(e["kind"] == "result" for e in events)
    denied = {call_id for e in events if e["kind"] == "result" for call_id, _n, _i in e.get("denied") or []}
    lines = []
    for event in events:
        lines += follow_render(event, denied)
    return lines, ended
