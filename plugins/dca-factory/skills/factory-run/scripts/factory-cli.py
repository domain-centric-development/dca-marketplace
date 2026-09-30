#!/usr/bin/env python3
"""Factory CLI — what shows and coordinates a factory run, beside the gate that decides.

The gate (`story-gate.py`, in this folder) reads the project's files and refuses or lets a stage
through. This file is everything a person or a runner asks *about* the pipeline, and the one place
the runner asks a project file's content from — so the profile, a stage file and a decision record
have one reader, the gate's, and two callers can never disagree about what they say.

    factory-cli.py --status [--story <id>] [--format text|md|json] [--live] [--part all|backlog]
    factory-cli.py --status --brief [--session-start]   two lines for a session's start
    factory-cli.py --help-view [--format text|md|json]  the factory explained, with this project's place in it
    factory-cli.py --list-decisions [--story <id>]      the decision inbox, one line per record
    factory-cli.py --schedule                           every story's state and the next one to run
    factory-cli.py --story <id> --start | --kind        where a run begins | `story`, `journey` or `adopt`
    factory-cli.py --resolve "<argument>"               what /factory-run <argument> means
    factory-cli.py --reopen <story>                     take a delivered story back for a correction
    factory-cli.py --usage [--story <id>] [--total]     tokens per story and stage, from the journals
    factory-cli.py --usage-from <format> <file>         one invocation's usage from a tool's raw output
    factory-cli.py --stage-start|--stage-end <stage> --story <id>    a stage run inside a session
    factory-cli.py --window-start|--window-end <work> --story <id>   writing or answering, measured
    factory-cli.py --claim <owner> | --release [<owner>] | --listening   one worker per checkout

What the runner reads through here instead of parsing a file itself:

    factory-cli.py --get <key>                the profile's value for one key ("" when absent)
    factory-cli.py --command-heads            the first word of every command the profile declares
    factory-cli.py --carriers                 the skills the profile names as carriers, reviewers, knowledge
    factory-cli.py --carrier-lines            those keys with their values, one `key value` per line
    factory-cli.py --model <tool> <stage>     `model.<tool>.<stage>`, else `model.<tool>`, else ""
    factory-cli.py --verdict <story>          the judge's verdict of that story, or ""
    factory-cli.py --needs-human <file>       the decision ids a stage file's `## needs-human` names,
                                              `<id>\\t<stage>` per line; exit 1 when it asks nobody
    factory-cli.py --open-decisions <story>   the records that name the story and carry no answer

Options as the gate's: --epics, --runs, --profile (else FACTORY_PROFILE, else the gate's place),
--root, --format, --color, --json.
"""

import argparse
import importlib.util
import json
import os
import re
import sys
import time

# The lines carry `—` and `→`; a Windows console's code page cannot encode `→`, and the print raises.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

# The gate beside this file is the one reader of every project file. It is loaded from its path (the
# name carries a hyphen) and its names are taken over, so every reader, check and constant used below
# is the gate's own — nothing here parses a file the gate parses.
_HERE = os.path.dirname(os.path.abspath(__file__))
GATE_PATH = os.path.join(_HERE, "story-gate.py")
if not os.path.isfile(GATE_PATH):
    sys.stderr.write(f"factory-cli: no gate beside this file ({GATE_PATH}) — 'factory.sh update' puts both there\n")
    sys.exit(2)
# No bytecode beside the gate: a `__pycache__` in the project is an untracked file the commit check would
# refuse, and a cache is nothing a project should carry.
sys.dont_write_bytecode = True
_spec = importlib.util.spec_from_file_location("story_gate", GATE_PATH)
_gate = importlib.util.module_from_spec(_spec)
sys.modules["story_gate"] = _gate
_spec.loader.exec_module(_gate)
globals().update({_name: _value for _name, _value in vars(_gate).items() if not _name.startswith("__")})
# Every CLI file is that gate's: the runner compares the two before a run and refuses a pair whose
# versions differ, because a status that reads the journal with yesterday's rules would show a wrong
# state with a straight face.
VERSION = _gate.VERSION
CONTRACT = _gate.CONTRACT


def resolve(epics, argument):
    """What `/factory-run <argument>` means — decided here, not by a model: one word naming a story is that
    story; one word naming none is an unknown id, never a new story (a typo stays a typo); more than one
    word is a wish, for the backlog skill to turn into a story; nothing is the backlog."""
    words = argument.split()
    if not words:
        print("backlog")
        return 0
    if len(words) > 1:
        print("wish")
        return 0
    try:
        path = find_story(epics, words[0])
    except GateError:
        known = story_ids(epics) if os.path.isdir(epics) else []
        print(f"unknown {words[0]} — no story by that id under {epics.replace(os.sep, '/')}/"
              + (f"; the backlog has: {', '.join(known)}" if known else "; the backlog has no story yet")
              + ". A wish takes more than one word.")
        return 2
    front, _ = read_front_matter(path)
    print(f"story {str(front.get('id', '')).strip() or os.path.splitext(os.path.basename(path))[0]}")
    return 0


def list_decisions(cwd, story_id=None, fmt="text", colour="auto"):
    """The inbox: every record, what waits for a person first — open, drafts, answered, applied — read
    from the files alone; the same view as the status, in text, Markdown or JSON."""
    records = []
    for name, front, body, state, error, path in decision_files(cwd):
        if error:
            records.append(dict(rank=-1, id=name, state="unreadable", kind="question", story="?", stage="?",
                                asked=None, text=str(error), path=shown(path)))
            continue
        story = str(front.get("story", "")).strip()
        if story_id and story != story_id:
            continue
        answer = decision_state(body)[1]
        question = (body.strip().splitlines() or ["(no title)"])[0].lstrip("# ").strip()
        given = f" → {answer.get('answer')} ({answer.get('by')})" if state in ("answered", "applied") else ""
        records.append(dict(rank={"open": 0, "draft": 1, "answered": 2, "applied": 3}[state],
                            id=str(front.get("id", name)).strip(), state=state,
                            kind="acceptance" if is_acceptance(front) else "question", story=story,
                            stage=str(front.get("stage", "?")).strip(),
                            asked=parse_time(str(front.get("asked", ""))), text=question + given,
                            path=shown(path)))
    records.sort(key=lambda r: (r["rank"], r["id"]))
    waiting = [r for r in records if r["state"] in ("open", "draft", "unreadable")]
    model = dict(project=os.path.basename(os.path.abspath(cwd)), story=story_id, records=records,
                 waiting=len(waiting), store=f"{place('epics')}/<epic>/<story>{DECISIONS_SUFFIX}/")
    mark = lambda r: "look" if r["kind"] == "acceptance" and r["state"] in ("open", "draft") else \
        "stopped" if r["state"] == "unreadable" else decision_mark(r)
    headers = ["record", "state", "story / stage", "asked (UTC)", "question → answer"]
    cells = lambda marks: [[f"{marks[mark(r)]} {r['id']}", r["state"], f"{r['story']} / {r['stage']}",
                            stamp_text(r["asked"]), r["text"]] for r in records]
    summary = f"{len(records)} record" + ("" if len(records) == 1 else "s") + " · " + \
        (f"{len(waiting)} wait" + ("s" if len(waiting) == 1 else "") + " for you" if waiting else "nothing waits for you")
    if fmt == "json":
        print(json.dumps(json_ready(model), indent=2, ensure_ascii=False))
        return 0
    first = next((r for r in records if r in waiting), None)
    how = make_action(skill="/factory-decisions",
                      shell=f"write the answer into {first['path']} under `## Answer`") if first else None
    if fmt == "md":
        lead = "look" if first and first["kind"] == "acceptance" else "question" if waiting else "done"
        out = [f"### Decisions — {model['project']}" + (f" · {story_id}" if story_id else ""), "",
               f"{MARKS_MD[lead]} {summary}", ""]
        if records:
            # the question beside the record would make the table too wide to read: a list below it
            out += table_md(headers[:-1], [c[:-1] for c in cells(MARKS_MD)], first_bold=True)
            out += ["", "**Questions and answers**", ""] + [f"- **{r['id']}** — {r['text']}" for r in records]
        out += ["", f"**Next:** answer {first['id']} — {how_md(how)}" if how else "**Next:** Nothing waits for you."]
        print("\n".join(out))
        return 0
    use = use_colour(colour)
    out = [""] + heading(f"Decisions — {model['project']}" + (f" · {story_id}" if story_id else ""), use, "═")
    lead = "question" if waiting else "done"
    if first and first["kind"] == "acceptance":
        lead = "look"
    out += ["", "  " + paint(f"{MARKS_TEXT[lead]} {summary}", lead, use), ""]
    if records:
        # the question and its answer under each record, over the full width — a column would crush it
        lines = table_text(headers[:-1], [c[:-1] for c in cells(MARKS_TEXT)], colour=use,
                           marks=[mark(r) for r in records], first_bold=True)
        out += lines[:2]
        for row_line, r in zip(lines[2:], records):
            out.append(row_line)
            out += [f"        {piece}" for piece in textwrap.wrap(r["text"], view_width() - 8)]
            out.append("")
        out = out[:-1]
    else:
        out.append(f"    No decision record beside any story ({model['store']}).")
    out += ["", "─" * 72]
    if how:
        out += [f"  {bold('Next', use)}   answer {first['id']}."] + how_lines(how, use, "         ")
    else:
        out.append(f"  {bold('Next', use)}   Nothing waits for you.")
    print("\n".join(out + [""]))
    return 0


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
        try:
            data = json.loads(raw)
        except ValueError:
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


def mark_window(cwd, runs, story_id, name, edge, session_log=None):
    """`--window-start`/`--window-end`: the session's tokens and time spent on a story outside a stage."""
    if name not in WINDOWS:
        print(f"window: {name!r} is none of {', '.join(WINDOWS)}")
        return 2
    journal = os.path.join(runs, story_id, ".verify", "journal.tsv")
    os.makedirs(os.path.dirname(journal), exist_ok=True)
    now = datetime.now(timezone.utc)
    stamp = now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"
    kind, session_id = current_session()
    if session_log:
        kind = "claude-session" if "/.claude/" in session_log.replace(os.sep, "/") else "codex-session"
    freeze_all(runs)
    with open(journal, "a", encoding="utf-8") as handle:
        if edge == "start":
            handle.write(f"{stamp}\twindow-start\t{name}\ttool={kind}\n")
            print(f"window: {name} of {story_id} started ({kind})")
            return 0
        started = None
        for line in read_text(journal).splitlines():
            parts = line.split("\t")
            if len(parts) >= 3 and parts[1] == "window-start" and parts[2] == name:
                started = parse_time(parts[0])
        source = f"log={session_log}" if session_log else \
            f"session={kind.split('-')[0]}:{session_id}" if session_id and kind != "in-session" else ""
        handle.write(f"{stamp}\twindow-end\t{name}\n")
        if not session_usage_allowed(cwd) or not started or not source:
            handle.write(f"{stamp}\tusage\t{name}\ttool={kind}\tunknown\n")
            print(f"window: {name} of {story_id} ended — its usage is unknown")
        else:
            begun = started.strftime("%Y-%m-%dT%H:%M:%S.") + f"{started.microsecond // 1000:03d}Z"
            handle.write(f"{stamp}\tusage\t{name}\ttool={kind}\twindow={begun}/{stamp}\t{source}\n")
            print(f"window: {name} of {story_id} ended — its usage is read from the session log")
    return 0


def mark_stage(cwd, runs, story_id, stage, edge, session_log=None):
    """`--stage-start`/`--stage-end` for a stage run inside a session: the same journal the runner writes."""
    journal = os.path.join(runs, story_id, ".verify", "journal.tsv")
    os.makedirs(os.path.dirname(journal), exist_ok=True)
    now = datetime.now(timezone.utc)
    stamp = now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"
    kind, session_id = current_session()
    owner = session_owner()
    if owner and claim(cwd, owner) == 3:
        return 3                               # another worker holds the checkout: this stage does not start
    freeze_all(runs)                          # the earlier stages' logs have caught up by now
    if session_log:
        kind = "claude-session" if "/.claude/" in session_log.replace(os.sep, "/") else "codex-session"
    allowed = session_usage_allowed(cwd)
    with open(journal, "a", encoding="utf-8") as handle:
        if edge == "start":
            # The model the profile asks this tool to run the stage on. A session cannot switch its own
            # model; a subagent may run on it. Which model the window actually used is read from the
            # session log later, and the status shows a request that did not reach the stage.
            profile = read_profile(resolve_profile(None, cwd))
            tool = kind.split("-")[0]
            requested = str(profile.get(f"model.{tool}.{stage}") or profile.get(f"model.{tool}") or "").strip()
            extra = f"\tmodel_requested={requested}" if requested else ""
            handle.write(f"{stamp}\tstage-start\t{stage}\ttool={kind}{extra}\n")
            if requested:
                print(f"model: the profile asks for {requested} — run this stage as a subagent on it where the "
                      f"tool allows; in this session's own context it cannot take effect")
            record_base(cwd, runs, story_id)
            write_snapshot(cwd, runs, story_id, f"before-{stage}")
            # A repeat judge round reads the verdict before it — the runner moves it aside the same way.
            verdict = os.path.join(runs, story_id, "judge.md")
            if stage == "judge" and os.path.isfile(verdict):
                os.replace(verdict, os.path.join(runs, story_id, ".judge-previous.md"))
                print(f"judge: the previous verdict is {runs}/{story_id}/.judge-previous.md — account for it")
            print(f"usage: stage {stage} of {story_id} started ({kind})")
            return 0
        started = None
        for line in read_text(journal).splitlines():
            parts = line.split("\t")
            if len(parts) >= 3 and parts[1] == "stage-start" and parts[2] == stage:
                started = parse_time(parts[0])
        # The window is recorded, not summed: a session log lags behind the session — Claude Code writes
        # a response after the tool call it made returns, so the response running this very command is
        # not in the log yet. `--usage` reads the window when the log has caught up.
        # Only the session's id goes into the journal, never a path: the journal is committed with the
        # project, and a path names the machine and the person. The log is found again when it is read.
        source = f"log={session_log}" if session_log else \
            f"session={kind.split('-')[0]}:{session_id}" if session_id and kind != "in-session" else ""
        handle.write(f"{stamp}\tstage-end\t{stage}\texit=0\n")
        write_snapshot(cwd, runs, story_id, f"after-{stage}")
        record_changes(cwd, runs, story_id, stage)
        if not allowed:
            handle.write(f"{stamp}\tusage\t{stage}\ttool={kind}\tunknown\n")
            print(f"usage: stage {stage} of {story_id} — unknown (session usage is switched off)")
        elif started and source:
            begun = started.strftime("%Y-%m-%dT%H:%M:%S.") + f"{started.microsecond // 1000:03d}Z"
            handle.write(f"{stamp}\tusage\t{stage}\ttool={kind}\twindow={begun}/{stamp}\t{source}\n")
            print(f"usage: stage {stage} of {story_id} ended — its usage is read from the session log by --usage")
        else:
            handle.write(f"{stamp}\tusage\t{stage}\ttool={kind}\tunknown\n")
            print(f"usage: stage {stage} of {story_id} — unknown (no stage start, or no session log this tool writes)")
    return 0


#: Seconds after a window's end before its numbers are written into the journal: a session log is
#: written after the tool call that marked the end returns, so a younger window may still grow.
FREEZE_AFTER = 300


def freeze_windows(journal):
    """Write the numbers of every session window that can be read now into the journal itself.

    The window points at a session log on this machine, which a clone does not have and the tool
    deletes after a while. Once read, the journal carries the numbers and no path, so the history
    stays with the project."""
    if not os.path.isfile(journal):
        return
    text = read_text(journal)
    lines, changed = text.splitlines(), False
    settled = datetime.now(timezone.utc).timestamp() - FREEZE_AFTER
    for i, line in enumerate(lines):
        parts = line.split("\t")
        if len(parts) < 4 or parts[1] != "usage" or not any(p.startswith("window=") for p in parts):
            continue
        fields = dict(p.split("=", 1) for p in parts[3:] if "=" in p)
        end = parse_time(fields.get("window", "").partition("/")[2])
        if end is None or end.timestamp() > settled:
            continue                            # the log may still lag behind this window
        read = resolve_window(fields)
        if read is None:
            continue
        lines[i] = "\t".join(parts[:3] + [f"tool={fields.get('tool', '')}", usage_fields(read),
                                            f"window={fields['window']}"])
        changed = True
    if changed:
        # Written aside and moved into place, with whatever was appended while the logs were read —
        # the runner or a stage mark may write a line at any moment.
        grown = read_text(journal)
        tail = grown[len(text):] if grown.startswith(text) else ""
        temporary = f"{journal}.{os.getpid()}"
        with open(temporary, "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n" + tail)
        os.replace(temporary, journal)


def freeze_all(runs):
    """`freeze_windows` over every story's journal. A story's last stages end its run, so no stage
    start of its own ever comes back to freeze them; the next command that writes anyway — a stage
    of another story, a claim, a release, a listening loop's look — does it for them. Never fails
    the command it rides on."""
    for journal in glob.glob(os.path.join(runs, "*", ".verify", "journal.tsv")):
        with contextlib.suppress(OSError, GateError, ValueError):
            freeze_windows(journal)


def resolve_window(fields):
    """A recorded session window, read now: {usage fields} or None."""
    if not session_usage_allowed(os.getcwd()):
        return None
    kind = fields.get("tool", "")
    start, _, end = fields.get("window", "").partition("/")
    paths = [p for p in fields.get("log", "").split(",") if p]
    tool, _, session_id = fields.get("session", "").partition(":")
    if session_id and tool == "claude":
        paths = claude_session_logs(session_id)
    elif session_id and tool == "codex":
        paths = [p for p in [codex_session_log(session_id)] if p]
    return session_usage(kind, paths, parse_time(start), parse_time(end)) if paths else None


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


def journal_usage(runs, story_id, resolve=True):
    """{stage: {invocations, measured, input, cache_read, cache_write, output, cost}} from the journal.

    `resolve=False` counts only what the journal carries itself, without opening a session log."""
    journal = os.path.join(runs, story_id, ".verify", "journal.tsv")
    stages = {}
    if not os.path.isfile(journal):
        return stages
    # A journal merged with `merge=union` can hold one session window twice — read on one branch,
    # still pending on the other. A window is one stage run, so it is counted once, the read one first.
    counted_windows = set()
    lines = sorted(read_text(journal).splitlines(), key=lambda l: ("log=" in l, l))
    for line in lines:
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        window = next((p for p in parts if p.startswith("window=")), None)
        if parts[1] == "usage" and window:
            if (parts[2], window) in counted_windows:
                continue
            counted_windows.add((parts[2], window))
        entry = stages.setdefault(parts[2], {"invocations": 0, "measured": 0, "cost": 0.0, "priced": 0,
                                             "seconds": 0, **{k: 0 for k in USAGE_FIELDS}})
        if parts[1] == "usage":
            # wall-clock time of the invocation, recorded by the runner — known even when its tokens
            # are not, and the only cost a local model has
            entry["seconds"] += sum(int(p[8:]) for p in parts[3:] if p.startswith("seconds=") and p[8:].isdigit())
        if parts[1] == "stage-start":
            entry["invocations"] += 1
            for p in parts[3:]:
                if p.startswith("model_requested="):
                    entry.setdefault("requested", set()).add(p.split("=", 1)[1])
                if p.startswith("model_applied=no"):
                    entry["not_applied"] = entry.get("not_applied", 0) + 1
        elif parts[1] == "usage" and "unknown" not in parts[3:]:
            fields = dict(p.split("=", 1) for p in parts[3:] if "=" in p)
            if "window" in fields and ("log" in fields or "session" in fields):
                read = resolve_window(fields) if resolve else None
                if read is None:
                    continue
                fields.update({k: str(v) for k, v in read.items()})
            entry["measured"] += 1
            if fields.get("model") and fields["model"] != "unknown":
                entry.setdefault("models", set()).update(fields["model"].split(","))
            for k in USAGE_FIELDS:
                entry[k] += int(fields.get(k, 0) or 0)
            if fields.get("cost"):
                entry["cost"] += float(fields["cost"])
                entry["priced"] += 1
    return {s: e for s, e in stages.items() if e["invocations"] or e["measured"]}


def stage_rank(stage):
    """Stage order for reports; the shared builder process (plan to tidy in one) sits before the judge, the
    shared verifier (judge, then document) after it."""
    return STAGE_ORDER.index(stage) if stage in STAGE_ORDER else 3.5 if stage == "builder" \
        else 4.5 if stage == "verifier" else -1 if stage == "backlog" else 98 if stage == "decisions" else 99


def tokens_of(entry):
    return sum(entry[k] for k in USAGE_FIELDS)


def money(entry):
    """The cost where the tool reported one — a session log has none, and that is not free."""
    if not entry["priced"]:
        return "—"
    return f"{entry['cost']:.2f}" + ("" if entry["priced"] == entry["measured"] else "+")


def facts_model(cwd, runs, story_id):
    """A story's stage figures from its journal alone — for a journal whose story is not in the backlog."""
    facts = story_facts(cwd, runs, story_id)
    return dict(stages=facts["stages"], models=sorted({m for e in facts["stages"].values() for m in e["models"]}),
                not_applied=sorted({r for e in facts["stages"].values() if e["not_applied"] for r in e["requested"]}),
                priced=facts["priced"] > 0)


def usage_report(runs, story_filter=None, total_only=False, cwd=".", epics=None, fmt="text"):
    """Tokens by class, as the status shows them: one story's stages, or every story by epic."""
    epics = epics or place("epics")
    stories = sorted(d for d in os.listdir(runs) if os.path.isdir(os.path.join(runs, d))) \
        if os.path.isdir(runs) else []
    if story_filter:
        stories = [s for s in stories if s == story_filter]
    if total_only:
        print(sum(tokens_of(e) for s in stories for e in journal_usage(runs, s).values()))
        return 0
    colour = use_colour("auto")
    if story_filter:
        try:
            model = story_model(cwd, epics, runs, story_filter)
        except GateError:
            model = facts_model(cwd, runs, story_filter)
        if fmt == "json":
            print(json.dumps(json_ready(model["stages"]), indent=2, ensure_ascii=False))
            return 0
        if not model["stages"]:
            print(f"usage: no stage recorded for {story_filter}")
            return 0
        headers, rows, right = stage_cells(model)
        print("\n".join(section(stage_caption(model), colour) + table_text(headers, rows, right, total=True,
                                                                           colour=colour, first_bold=True) + [""]))
        return 0
    model = status_model(cwd, epics, runs)
    if not model["rows"]:
        print("usage: no story yet")
        return 0
    headers, rows, kinds, right = token_rows(model)
    caption = "Tokens" + ("" if model["priced"] or not model["measured"] else " — no price in a session log")
    print("\n".join(section(caption, colour) + table_text(headers, rows, right, total=True, colour=colour) + [""]))
    return 0


# Two workers on one checkout build on each other's unfinished code. The claim is a file created
# exclusively — of two workers asking at the same moment, one gets it — in the git directory, so it is
# per checkout (a worktree has its own), never committed and never an untracked file the commit check
# would call drift. A holder renews it before every stage; one that stops renewing is stale after
# FACTORY_STALE_AFTER seconds (default two hours) and may be taken over, which is said out loud.
def stale_after():
    try:
        return max(0, int(os.environ.get("FACTORY_STALE_AFTER", "7200")))
    except ValueError:
        return 7200


def claim_path(cwd):
    code, git_dir = git(cwd, "rev-parse", "--git-dir")
    if code == 0 and git_dir:
        return os.path.join(cwd, git_dir, "dca-factory-worker.lock")
    return os.path.join(cwd, ".agents", "factory", "worker.lock")


def session_owner():
    kind, session_id = current_session()
    return f"{kind}:{session_id}" if session_id else ""


def read_claim(path):
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return None


def write_claim(path, owner, since):
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    temporary = f"{path}.{os.getpid()}"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump({"owner": owner, "since": since or stamp, "beat": stamp}, handle)
    os.replace(temporary, path)


def claim(cwd, owner):
    """0 when `owner` holds the checkout now (claimed, renewed or taken over), 3 when another does."""
    path = claim_path(cwd)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    # Written aside, then linked into place: a link fails when the claim exists, so the file appears
    # with its content or not at all — an empty claim between create and write would read as unreadable.
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    temporary = f"{path}.{os.getpid()}.new"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump({"owner": owner, "since": stamp, "beat": stamp}, handle)
    try:
        os.link(temporary, path)
        print(f"claim: {owner} holds the checkout")
        return 0
    except FileExistsError:
        pass
    except OSError:                              # a file system without hard links
        try:
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(read_text(temporary))
            print(f"claim: {owner} holds the checkout")
            return 0
        except FileExistsError:
            pass
    finally:
        with contextlib.suppress(OSError):
            os.remove(temporary)
    held = read_claim(path) or {}
    if held.get("owner") == owner:
        write_claim(path, owner, held.get("since"))
        return 0
    beat = parse_time(held.get("beat"))
    if beat is None:                             # unreadable: aged by the file, not taken on sight
        with contextlib.suppress(OSError):
            beat = datetime.fromtimestamp(os.path.getmtime(path), timezone.utc)
    age = (datetime.now(timezone.utc) - beat).total_seconds() if beat else None
    if age is None or age > stale_after():
        write_claim(path, owner, None)
        print(f"claim: took over from {held.get('owner', 'an unreadable claim')} — no sign of life for "
              f"{int(age // 60) if age is not None else '?'} min, so it was stopped or crashed")
        return 0
    print(f"claim: the checkout is held by {held.get('owner')} since {held.get('since')} (last sign of life "
          f"{int(age // 60)} min ago) — one worker per checkout; this one does not start")
    return 3


# A session that listens on the backlog (`/loop /factory-run`) holds no claim while nothing is ready,
# so from outside a waiting listener and an ended one look the same. Each look leaves a mark next to
# the claim — who looked, and when — which `--status` shows. It only informs; it locks nothing.
def listener_path(cwd):
    return claim_path(cwd).replace("dca-factory-worker.lock", "dca-factory-listener.json") \
        if claim_path(cwd).endswith("dca-factory-worker.lock") else \
        os.path.join(cwd, ".agents", "factory", "listener.json")


def listen_stale_after():
    try:
        return max(60, int(os.environ.get("FACTORY_LISTEN_STALE", "3600")))
    except ValueError:
        return 3600


def mark_listening(cwd):
    owner = session_owner() or "a session without an id"
    path = listener_path(cwd)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    write_claim(path, owner, None)
    print(f"listening: {owner} looked at the backlog")
    return 0


def listener_line(cwd):
    """`listening: …` for the status, or None when no session has looked."""
    held = read_claim(listener_path(cwd))
    if not held:
        return None
    beat = parse_time(held.get("beat"))
    if not beat:
        return None
    minutes = int((datetime.now(timezone.utc) - beat).total_seconds() // 60)
    ended = minutes * 60 > listen_stale_after()
    return (f"listening: {held.get('owner')}, last look {minutes} min ago"
            + (" — no look for longer than a loop waits, probably ended" if ended else ""))


def release(cwd, owner):
    path = claim_path(cwd)
    held = read_claim(path)
    if held and held.get("owner") == owner:
        os.remove(path)
        print(f"claim: {owner} released the checkout")
    return 0


def running_stages(runs):
    """[(story, stage, started)] for every stage whose journal shows a start and no end yet.

    The journal knows that a stage began, not whether its process is still alive: a stage whose
    runner was killed reads the same, which is why the start time is shown with it."""
    found = []
    if not os.path.isdir(runs):
        return found
    for story in sorted(os.listdir(runs)):
        journal = os.path.join(runs, story, ".verify", "journal.tsv")
        if not os.path.isfile(journal):
            continue
        open_stage = None
        # By time, not by position: a union merge interleaves two branches' lines.
        for line in sorted(read_text(journal).splitlines(), key=lambda l: parse_time(l.split("\t")[0])
                           or datetime.min.replace(tzinfo=timezone.utc)):
            parts = line.split("\t")
            if len(parts) < 3:
                continue
            if parts[1] == "stage-start":
                open_stage = (parts[2], parts[0])
            elif parts[1] == "stage-end" and open_stage and parts[2] == open_stage[0]:
                open_stage = None
        if open_stage:
            found.append((story, open_stage[0], open_stage[1]))
    return found


def dangling_skill_links(cwd):
    """The entries of the tools' skill directories that are links to nothing, as relative paths."""
    found = []
    for folder in (".claude/skills", ".codex/skills", ".opencode/skills"):
        path = os.path.join(cwd, folder)
        if os.path.islink(path) and not os.path.exists(path):
            found.append(folder)
            continue
        if not os.path.isdir(path):
            continue
        for name in sorted(os.listdir(path)):
            entry = os.path.join(path, name)
            if os.path.islink(entry) and not os.path.exists(entry):
                found.append(f"{folder}/{name}")
    return found


def status_brief(cwd, epics, runs, session_start=False):
    """Two lines: what is ready, what waits, who works, what it cost — for a session's start."""
    import contextlib
    import io
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        schedule(cwd, epics, runs)
    rows = [l for l in buffer.getvalue().splitlines() if l and not l.startswith(("schedule:", "wait:", "layout:"))]
    nxt = next((l[6:] for l in rows if l.startswith("next: ")), "none")
    states = {}
    for line in rows:
        if line.startswith("next: "):
            continue
        parts = line.split()
        if len(parts) >= 2:
            states.setdefault(parts[1], []).append(parts[0])
    held = read_claim(claim_path(cwd))
    view = status_model(cwd, epics, runs)
    words = {}
    for row in view["rows"]:
        words.setdefault(row["state"], []).append(row["story"])
    summary = " · ".join(f"{len(v)} {k}" for k, v in sorted(words.items())) or "no stories yet"
    print(f"factory: {summary}" + (f" · {view['tokens']:,} tokens so far" if view["measured"] else ""))
    waiting = "; ".join(f"{MARKS_TEXT[w['mark']]} {w['story']} {w['what']}" for w in view["waiting"])
    print("factory: " + (f"waiting for you: {waiting} · " if waiting else "nothing waits for you · ")
          + (f"worker {held.get('owner')} holds the checkout · " if held else "no worker running · ")
          + f"next: {view['next']['text']}")
    listening = listener_line(cwd)
    if listening:
        print(f"factory: {listening}")
    # A skill link that points nowhere — its plugin version pruned from the cache, a checkout moved: the
    # skills are then missing for a session and a runner stage alike, and only the update relinks them.
    dangling = dangling_skill_links(cwd)
    if dangling:
        more = f" and {len(dangling) - 1} more" if len(dangling) > 1 else ""
        print(f"factory: skill link {dangling[0]} points nowhere{more} — /factory-update relinks them (or copies, with --copy)")
    # The part of the factory that is missing, where the files show it: the description, the backlog.
    profile = read_profile(resolve_profile(None, cwd))
    undescribed = [key for key in ("product", "tech") if not os.path.isfile(os.path.join(cwd, location(profile, key)))]
    if layout_hint(cwd, profile):
        print(f"factory: {layout_hint(cwd, profile)}")
    elif undescribed:
        print(f"factory: no project description ({', '.join(location(profile, k) for k in undescribed)}) — /factory-setup")
    elif not states:
        print("factory: the backlog is empty — /factory-backlog writes the first epic and story")
    drift = conventions_drift(cwd, profile)
    if drift:
        print(f"factory: {drift}")
    if session_start and os.environ.get("FACTORY_WORKER"):
        # A stage the runner started: the hook runs in its session too, and the claim it names is the
        # runner's — this session's own. Said plainly, or a careful model takes itself for a second writer.
        print(f"dca-factory: this session is stage {os.environ.get('FACTORY_STAGE') or '?'} of story "
              f"{os.environ.get('FACTORY_STORY') or '?'}, started by the worker {os.environ['FACTORY_WORKER']} "
              "that holds the checkout — the claim is this session's own, not a second writer's. Carry out the "
              "stage as the prompt says, write its file under the run folder, and ask nothing: the runner reads "
              "the file when this session ends.")
    elif session_start:
        print("dca-factory: this project delivers stories through the factory. At the person's first message, "
              "unless they already name a task, show the two lines above and ask what they want to do: write or "
              "release a story (/factory-backlog), answer a waiting question (/factory-decisions), start working "
              "the backlog (/factory-run, which keeps asking the schedule; in Claude Code also /loop /factory-run), "
              "look closer (/factory-status), or learn how the factory works (/factory-help). An instruction that "
              "changes what an actor can see or do is a story: ask once, \"As a story through the factory — to an "
              "existing epic, a new epic — or directly by hand?\", and for the factory run /factory-run with the "
              "person's words. A session never runs `factory.sh run` — it starts a tool "
              "process per stage. A managing session writes backlog and decision files only; the worker is the "
              "one writer in the checkout.")
    return 0


def duplicate_pipeline_note(cwd):
    """A session sees the person's plugins as well as the project's skills. With the dca-factory plugin
    enabled and a project copy installed, a stage run in the session may pick either copy — the
    runner's stage processes see only the project, a session does not."""
    if not os.path.isfile(os.path.join(cwd, ".claude", "skills", "factory-run", "SKILL.md")):
        return None
    home = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")
    for settings in (os.path.join(home, "settings.json"), os.path.join(cwd, ".claude", "settings.json"),
                     os.path.join(cwd, ".claude", "settings.local.json")):
        try:
            with open(settings, encoding="utf-8") as handle:
                enabled = (json.load(handle) or {}).get("enabledPlugins") or {}
        except (OSError, ValueError):
            continue
        if any(str(key).startswith("dca-factory@") and value for key, value in enabled.items()):
            return ("note: the dca-factory plugin is enabled and the project has its own copy — a stage run in a "
                    "session may pick the plugin's skills; the runner's stages see only the project's")
    return None


def activity_logs(cwd, owner, since):
    """The session logs a running stage writes into while it works: the worker's own session and its
    subagents where the claim names a session, else the tool's logs for this project directory that
    changed since the stage started (a runner's stage process has a session of its own)."""
    kind, _, session_id = (owner or "").partition(":")
    if kind == "claude-session":
        return claude_session_logs(session_id)
    if kind == "codex-session":
        found = codex_session_log(session_id)
        return [found] if found else []
    home = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")
    folder = os.path.join(home, "projects", re.sub(r"[^A-Za-z0-9]", "-", os.path.abspath(cwd)))
    floor = since.timestamp() if since else 0
    return [path for path in glob.glob(os.path.join(folder, "**", "*.jsonl"), recursive=True)
            if os.path.getmtime(path) >= floor]


def last_tool_call(path):
    """`Name: first words of its input` of the newest tool call in a Claude or Codex session log."""
    try:
        with open(path, "rb") as handle:
            handle.seek(max(0, os.path.getsize(path) - 262144))
            lines = handle.read().decode("utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    for line in reversed(lines):
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        content = (entry.get("message") or {}).get("content") if isinstance(entry.get("message"), dict) else None
        for block in reversed(content if isinstance(content, list) else []):
            if isinstance(block, dict) and block.get("type") == "tool_use":
                given = block.get("input") or {}
                detail = next((str(given[k]) for k in ("command", "description", "skill", "file_path", "pattern")
                               if isinstance(given, dict) and given.get(k)), "")
                detail = " ".join(detail.split())
                return f"{block.get('name')}" + (f": {detail[:70]}" + ("…" if len(detail) > 70 else "") if detail else "")
        payload = entry.get("payload") if isinstance(entry.get("payload"), dict) else {}
        if payload.get("type") in ("function_call", "local_shell_call"):
            return str(payload.get("name") or payload.get("type"))
    return ""


def activity_line(cwd, owner, started, now):
    """The sign of life inside a stage: a stage writes to the journal only at its start and its end,
    while its session log grows with every tool call. Read only where session logs may be read."""
    if not session_usage_allowed(cwd):
        return "activity: not read — session logs are switched off (sessionUsage)"
    logs = [path for path in activity_logs(cwd, owner, parse_time(started)) if os.path.isfile(path)]
    if not logs:
        return "activity: unknown — no session log of this stage found on this machine"
    newest = max(logs, key=os.path.getmtime)
    age = int(now.timestamp() - os.path.getmtime(newest))
    ago = f"{age} s ago" if age < 120 else f"{age // 60} min ago"
    call = last_tool_call(newest)
    return f"activity: {ago}" + (f" — last tool call {call}" if call else "")


def status(cwd, epics, runs, story_filter=None, fmt="text", colour="auto", live=False, part="all"):
    """The person's view: what waits for them, what runs, the backlog by epic with times and tokens —
    or one story's details. The same files give the same text; `--live` adds what the clock says."""
    try:
        if story_filter:
            model = story_model(cwd, epics, runs, story_filter, live)
            text = render_story_md(model) if fmt == "md" else render_story_text(model, use_colour(colour))
        else:
            model = status_model(cwd, epics, runs, live)
            model["part"] = part
            text = render_status_md(model) if fmt == "md" else render_status_text(model, use_colour(colour))
    except GateError as error:
        print(f"status: {error}")
        return 1
    if fmt == "json":
        print(json.dumps(json_ready(model), indent=2, ensure_ascii=False))
    else:
        print(text)
    return 0


def factory_help(cwd, epics, runs, fmt="text", colour="auto"):
    """The factory explained in one fixed view: the flow with where this project stands in it, every
    command in its agent and its shell form, the marks, the files. The text is the same everywhere;
    only the marks in the flow and the Next line come from the project's files."""
    try:
        model = help_model(cwd, epics, runs)
    except GateError as error:
        print(f"help: {error}")
        return 1
    if fmt == "json":
        print(json.dumps(json_ready(model), indent=2, ensure_ascii=False))
    else:
        print(render_help_md(model) if fmt == "md" else render_help_text(model, use_colour(colour)))
    return 0


BUILD_FILES = ("build.gradle", "build.gradle.kts", "pom.xml", "package.json", "pyproject.toml", "go.mod", "Cargo.toml")


SHELL_NAME = "factory.sh"          # the help's tables name the runner short; the view says its full path once


HELP_COMMANDS = (
    ("deliver a wish", "your words become a backlog story — which epic, the criteria — and it runs at once",
     "/factory-run <your words>", ""),
    ("where it stands", "what runs, what waits for you, every story with its times and tokens",
     "/factory-status", "status"),
    ("one story", "its stages, passes and tokens", "/factory-status <story>", "status --story <story>"),
    ("the backlog", "the epics and stories, their state, the next one", "/factory-backlog", "backlog"),
    ("check the backlog", "the plan gate's checks over every open story, writing nothing", "/factory-backlog",
     "backlog --check"),
    ("the inbox", "the open questions and acceptances, and how to answer them", "/factory-decisions", "decisions"),
    ("the profile", "what detection finds against the stack profile", "/factory-setup", "setup --check"),
    ("observe a story", "what a delivered story changed, measured from its files", "/factory-verify <story>",
     "verify --story <story>"),
    ("the machinery", "the pipeline's own suite against fixtures — for whoever changes the pipeline",
     "/factory-verify --fixtures", "verify --fixtures"),
    ("one stage by hand", "stage-plan … stage-document are the six stages the run calls; by hand only to redo one "
                          "stage of a story that has the ones before", "/stage-<stage> <story>", ""),
    ("update the pipeline", "the newest pipeline found, same tools", "/factory-update", "update"),
    ("this help", "the flow, the commands, the marks, the files", "/factory-help", "help"),
)


NOW_WORDS = {"done": "done", "next": "you are here", "look": "waits for your look", "question": "waits for your answer",
             "running": "running"}


HELP_MARKS = (("look", "waits for your look — an acceptance"), ("question", "waits for your answer"),
              ("stopped", "stopped — read why before it runs again"), ("running", "running"),
              ("done", "done — a story, an epic, a decision"), ("none", "nothing to do there now"))


def help_model(cwd, epics, runs):
    profile_path = resolve_profile(None, cwd)
    profile = read_profile(profile_path)
    status_view = status_model(cwd, epics, runs)
    described = all(os.path.isfile(os.path.join(cwd, location(profile, k))) for k in ("product", "tech"))
    has_build = any(os.path.isfile(os.path.join(cwd, name)) for name in BUILD_FILES) \
        or any(name.endswith((".sln", ".slnx", ".csproj")) for name in os.listdir(cwd))
    marks = {m["mark"] for m in status_view["waiting"]}
    rows = status_view["rows"]
    delivered = bool(rows) and all(r["state"] in ("delivered", "superseded") for r in rows)
    has_stories = bool(rows) and not delivered
    waiting_mark = "look" if "look" in marks else ("question" if "question" in marks else "")
    started = described and has_build
    # what waits for a person comes first: nothing of theirs moves until it is answered
    if waiting_mark:
        here = "answer or accept"
    elif not started:
        here = "start"
    elif not profile_path:
        here = "set up"
    elif not has_stories:
        here = "write stories"
    else:
        here = "run"
    # The first two steps happen once, so they can be done. The last three repeat with every story and
    # never are: there the flow marks only where the project is now (waiting, running, next).
    flow = [
        dict(step="start", what="the description and a runnable skeleton in one pass — an existing project: "
                                "/dca-describe", skill="/dca-new project", shell="", once=True, done=started),
        dict(step="set up", what="the stack profile: build, test, format and browser commands, the carriers",
             skill="/factory-setup", shell="setup --check" if profile_path else "setup", once=True,
             done=bool(profile_path)),
        dict(step="write stories", what="epics and stories with acceptance criteria; a story runs once released",
             skill="/factory-backlog", shell=""),
        dict(step="run", what="plan → test → build → tidy → judge → document, a gate between the stages",
             skill="/factory-run [<story>]", shell="run [--story <story>]"),
        dict(step="answer or accept", what="a question a stage may not decide alone, or a result to look at: "
                                           "accepted delivers it, a correction goes back into the story",
             skill="/factory-decisions", shell="decisions"),
    ]
    for n, f in enumerate(flow, 1):
        f["number"] = n
        if f["step"] == here:
            f["mark"] = waiting_mark if here == "answer or accept" else \
                "running" if here == "run" and status_view["running"] else "next"
        else:
            f["mark"] = "done" if f.pop("done", False) else "none"
        f.pop("done", None)
        f.pop("once", None)
    if waiting_mark:
        nxt = status_view["next"]
    elif not described and has_build:
        nxt = dict(text="Describe the project — drafted from its code, confirmed by you.",
                   action=make_action(skill="/dca-describe", shell=""))
    elif not has_build:
        nxt = dict(text="Start the project — the description and a skeleton from a generator, in one pass.",
                   action=make_action(skill="/dca-new project", shell=""))
    elif not profile_path:
        nxt = dict(text="Set the factory up — the stack profile is missing.",
                   action=make_action(skill="/factory-setup", shell=f"{RUNNER} setup"))
    else:
        nxt = status_view["next"]
    files = [("description", ", ".join(location(profile, k) for k in ("product", "tech", "domain")),
              "what is built, on which stack, in which contexts"),
             ("epics", epics.replace(os.sep, "/") + "/", "one file per epic and per story; a delivered story says so itself"),
             ("stack profile", (profile_path or PROFILE_FILE).replace(os.sep, "/"),
              "the project's commands and the skills each stage uses"),
             ("decisions", f"{epics.replace(os.sep, '/')}/<epic>/<story>{DECISIONS_SUFFIX}/",
              "one record per question or acceptance, beside its story"),
             ("a story's run", f"{runs}/<story>/", "hand-overs, marks, the journal — protocol, disposable")]
    return dict(project=status_view["project"], flow=flow, commands=[dict(zip(("name", "what", "skill", "shell"), c))
                                                                    for c in HELP_COMMANDS],
                marks=[dict(mark=m, meaning=t) for m, t in HELP_MARKS],
                files=[dict(name=n, where=w, holds=h) for n, w, h in files],
                runner=RUNNER, next=nxt)


def shell_form(command):
    return f"{SHELL_NAME} {command}" if command else ""


def render_help_text(model, colour=False):
    out = [""] + heading(f"Factory help — {model['project']}", colour, "═")
    out += section("The flow — and where this project is now", colour)
    rows = [[f"{f['number']}  {f['step']}", NOW_WORDS.get(f["mark"], ""), f["skill"],
             shell_form(f["shell"]) or "— needs an agent session", f["what"]] for f in model["flow"]]
    out += table_text(["step", "now", "agent", "shell", "what it is"], rows,
                      marks=[f["mark"] if f["mark"] != "none" else None for f in model["flow"]], colour=colour, painted=2)
    out += section("Commands", colour)
    out += table_text(["to see", "agent", "shell", "what it shows"],
                      [[c["name"], c["skill"], shell_form(c["shell"]) or "— needs an agent session", c["what"]]
                       for c in model["commands"]],
                      colour=colour, first_bold=True)
    note = f"{SHELL_NAME} is {model['runner']}, in a terminal of its own; a session uses the agent form."
    out += ["", "    " + dim(note, colour)]
    out += section("Marks", colour)
    out += table_text(["mark", "means"], [[MARKS_TEXT[m["mark"]], m["meaning"]] for m in model["marks"]],
                      marks=[m["mark"] for m in model["marks"]], colour=colour, painted=1)
    out += section("Files", colour)
    out += table_text(["what", "where", "holds"], [[f["name"], f["where"], f["holds"]] for f in model["files"]],
                      colour=colour, first_bold=True)
    return "\n".join(out + ["", "─" * 72] + next_text(model, colour) + [""])


def render_help_md(model):
    out = [f"### Factory help — {model['project']}", "", "**The flow — and where this project is now**", ""]
    out += table_md(["step", "now", "agent", "shell", "what it is"],
                    [[f"{f['number']} {f['step']}", f"**{NOW_WORDS[f['mark']]}**" if f["mark"] in NOW_WORDS else "",
                      f"`{f['skill']}`",
                      f"`{shell_form(f['shell'])}`" if f["shell"] else "— needs an agent session", commands(f["what"], False, md=True)]
                     for f in model["flow"]])
    out += ["", "**Commands**", ""]
    out += table_md(["to see", "agent", "shell", "what it shows"],
                    [[c["name"], f"`{c['skill']}`", f"`{shell_form(c['shell'])}`" if c["shell"] else "— needs an agent session",
                      c["what"]] for c in model["commands"]],
                    first_bold=True)
    out += ["", f"`{SHELL_NAME}` is `{model['runner']}`, in a terminal of its own; a session uses the agent form.",
            "", "**Marks**", ""]
    out += table_md(["session", "terminal", "means"], [[MARKS_MD[m["mark"]], f"`{MARKS_TEXT[m['mark']]}`", m["meaning"]]
                                                      for m in model["marks"]])
    out += ["", "**Files**", ""]
    out += table_md(["what", "where", "holds"], [[f["name"], f"`{f['where']}`", f["holds"]] for f in model["files"]],
                    first_bold=True)
    return "\n".join(out + ["", next_md(model)])


MARKS_TEXT = {"look": "!", "question": "?", "stopped": "✗", "running": "▶", "done": "✓", "none": "·", "next": "→"}


MARKS_MD = {"look": "👀", "question": "❓", "stopped": "⛔", "running": "⏳", "done": "✅", "none": "➖", "next": "👉"}


COLOURS = {"look": "33", "question": "33", "stopped": "31", "running": "34", "done": "32", "none": "2", "next": "36"}


def stamp_text(value):
    """`2026-09-25 14:31` in UTC, or `—`."""
    moment = parse_time(value) if isinstance(value, str) else value
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M") if moment else "—"


def took_text(seconds):
    if not seconds:
        return "—"
    seconds = int(round(seconds))
    if seconds < 60:
        return f"{seconds} s"
    minutes = seconds // 60
    return f"{minutes // 60} h {minutes % 60} min" if minutes >= 60 else f"{minutes} min"


def tokens_text(tokens, measured=True):
    return f"{tokens:,}" if measured and tokens else "not measured"


def journal_events(runs, story_id):
    """[(time, kind, stage, fields)] of a story's journal, by time — a union merge interleaves lines."""
    journal = os.path.join(runs, story_id, ".verify", "journal.tsv")
    if not os.path.isfile(journal):
        return []
    events = []
    # A union merge can hold one window twice — read on one branch, still pending on the other: the read
    # one first, so the pending one is the duplicate that is skipped.
    for line in sorted(read_text(journal).splitlines(), key=lambda l: ("log=" in l or "session=" in l)):
        parts = line.split("\t")
        if len(parts) < 3 or parse_time(parts[0]) is None:
            continue
        fields = dict(p.split("=", 1) for p in parts[3:] if "=" in p)
        if "unknown" in parts[3:]:
            fields["unknown"] = "1"
        events.append((parse_time(parts[0]), parts[1], parts[2], fields))
    return sorted(events, key=lambda e: e[0])


def usage_tokens(fields, resolve=True):
    """(tokens, new tokens, model) of one usage line, or None where nothing was measured."""
    if fields.get("unknown"):
        return None
    if "window" in fields and ("log" in fields or "session" in fields) and "input" not in fields:
        read = resolve_window(fields) if resolve else None
        if read is None:
            return None
        fields = dict(fields, **{k: str(v) for k, v in read.items()})
    counts = {k: int(fields.get(k, 0) or 0) for k in USAGE_FIELDS}
    return (sum(counts.values()), counts, fields.get("model", ""),
            float(fields["cost"]) if fields.get("cost") else None)


def story_facts(cwd, runs, story_id, front=None):
    """What a story's journal says: when it started and ended, how long its stages took, its passes
    (a pass begins at every plan start), and its tokens — per stage and per pass. When it was delivered
    is the story's own line, `delivered:`, not the journal's."""
    events = journal_events(runs, story_id)
    stages, passes, open_starts, counted = {}, [], {}, set()
    for moment, kind, stage, fields in events:
        if kind == "usage" and fields.get("window"):
            if (stage, fields["window"]) in counted:
                continue
            counted.add((stage, fields["window"]))
        if kind == "stage-start":
            if stage == "plan" or not passes:
                passes.append(dict(start=moment, end=None, seconds=0, tokens=0, measured=0, runs=0, stages=set()))
            passes[-1]["stages"].add(stage)
            open_starts[stage] = moment
            entry = stages.setdefault(stage, dict(runs=0, seconds=0, tokens=0, measured=0, models=set(), **{k: 0 for k in USAGE_FIELDS},
                                                  cost=0.0, priced=0, requested=set(), not_applied=0))
            entry["runs"] += 1
            passes[-1]["runs"] += 1
            if fields.get("model_requested"):
                entry["requested"].add(fields["model_requested"])
            if str(fields.get("model_applied", "")).startswith("no"):
                entry["not_applied"] += 1
        elif kind == "window-start":
            open_starts[stage] = moment
            stages.setdefault(stage, dict(runs=0, seconds=0, tokens=0, measured=0, models=set(), **{k: 0 for k in USAGE_FIELDS},
                                          cost=0.0, priced=0, requested=set(), not_applied=0))["runs"] += 1
        elif kind == "window-end" and stage in open_starts:
            stages[stage]["seconds"] += (moment - open_starts.pop(stage)).total_seconds()
        elif kind == "stage-end" and stage in open_starts:
            took = (moment - open_starts.pop(stage)).total_seconds()
            stages.setdefault(stage, dict(runs=0, seconds=0, tokens=0, measured=0, models=set(), **{k: 0 for k in USAGE_FIELDS}, cost=0.0,
                                          priced=0, requested=set(), not_applied=0))["seconds"] += took
            if passes:
                passes[-1]["seconds"] += took
                passes[-1]["end"] = moment
        elif kind == "usage":
            read = usage_tokens(fields)
            entry = stages.setdefault(stage, dict(runs=0, seconds=0, tokens=0, measured=0, models=set(), **{k: 0 for k in USAGE_FIELDS},
                                                  cost=0.0, priced=0, requested=set(), not_applied=0))
            if read is None:
                continue
            tokens, counts, model, cost = read
            entry["tokens"] += tokens
            for k in USAGE_FIELDS:
                entry[k] = entry.get(k, 0) + counts[k]
            entry["measured"] += 1
            if model and model != "unknown":
                entry["models"].update(model.split(","))
            if cost is not None:
                entry["cost"] += cost
                entry["priced"] += 1
            if passes and stage not in WINDOWS:
                passes[-1]["tokens"] += tokens
                passes[-1]["measured"] += 1
    started = events[0][0] if events else None
    tokens = sum(e["tokens"] for e in stages.values())
    invocations = sum(e["runs"] for e in stages.values())
    measured = sum(e["measured"] for e in stages.values())
    return dict(started=started, delivered=parse_time(delivered_on(front or {})), stages=stages,
                passes=passes, tokens=tokens, runs=invocations, measured=measured,
                seconds=sum(e["seconds"] for e in stages.values()),
                cost=sum(e["cost"] for e in stages.values()), priced=sum(e["priced"] for e in stages.values()))


def story_records(cwd, story_id, story_path=None):
    try:
        return records_of(story_id, story_path)
    except GateError:
        return []


RUNNER = "bash .agents/factory/factory.sh"


def make_action(text="", skill="", shell="", look=""):
    """What to do, both ways: `skill` in an agent session, `shell` in a terminal — empty where a
    terminal cannot do it (writing a story needs an agent)."""
    return dict(text=text, skill=skill, shell=shell, look=look)


def story_attention(cwd, story_id, story, profile):
    """(mark, state words, action) for one story — the words a person uses."""
    state, detail = story["state"], story.get("detail", "")
    records = story_records(cwd, story_id, story.get("path"))
    open_records = [(path, front) for path, front, _body, st, _a in records if st in ("open", "draft")]
    record = shown(open_records[0][0]) if open_records else ""
    by_hand = f"write the answer into {record} under `## Answer`" if record else ""
    if state == "waiting" and any(is_acceptance(f) for _p, f in open_records):
        record = next(shown(p) for p, f in open_records if is_acceptance(f))
        return "look", "waiting for your acceptance", make_action(
            skill="/factory-decisions", look=str(profile.get("run", "")).strip() or "start the application",
            shell=f"write accepted or your correction into {record} under `## Answer`")
    if state == "waiting":
        return "question", "waiting for your answer", make_action(skill="/factory-decisions", shell=by_hand)
    if state == "unreleased":
        return "question", "draft — waits for your release", make_action(
            text="release it", skill="/factory-backlog",
            shell=f"set `status: approved` in {str(story.get('path', 'the story')).replace(os.sep, '/')}")
    if state == "stopped":
        return "stopped", "stopped", make_action(text=detail, skill=f"/factory-status {story_id}",
                                            shell=f"{RUNNER} status --story {story_id}")
    if "possibly interrupted" in detail:
        return "stopped", "interrupted?", make_action(text=detail, skill=f"/factory-run {story_id}",
                                                 shell=f"{RUNNER} run --story {story_id}")
    if state == "running":
        return "running", "running", make_action()
    if state == "delivered":
        return "done", "delivered (adopted)" if detail == "adopted" else "delivered", make_action()
    if str(story.get("kind", "")) == "adopt" and state in ("ready", "in-progress", "resumable"):
        return "none", "to adopt", make_action(text=detail)
    if state == "blocked":
        return "none", "blocked", make_action(text=detail)
    if state in ("ready", "in-progress", "resumable"):
        words = {"ready": "ready", "in-progress": "in progress", "resumable": "can continue"}[state]
        return "none", words, make_action(text=detail)
    return "none", state, make_action(text=detail)


def status_model(cwd, epics, runs, live=False):
    profile = read_profile(resolve_profile(None, cwd))
    data = schedule_data(cwd, epics, runs)
    stories, order = data["stories"], data["order"]
    now = datetime.now(timezone.utc)
    rows, waiting = [], []
    for story_id in order:
        story = stories[story_id]
        facts = story_facts(cwd, runs, story_id, story.get("front"))
        mark, words, action = story_attention(cwd, story_id, story, profile)
        done = story["state"] == "delivered"
        stage = "" if done else next((st for sid, st, _t in running_stages(runs) if sid == story_id),
                                     story.get("start") or "")
        journal = os.path.isfile(os.path.join(runs, story_id, ".verify", "journal.tsv"))
        rows.append(dict(journal=journal, done=done, epic=story.get("epic", ""), story=story_id,
                         title=story.get("title", ""), mark=mark,
                         state=words, stage=stage or "—", passes=len(facts["passes"]) or 0,
                         started=facts["started"], delivered=facts["delivered"], seconds=facts["seconds"],
                         tokens=facts["tokens"], measured=facts["measured"], runs=facts["runs"],
                         **{k: sum(e.get(k, 0) for e in facts["stages"].values()) for k in USAGE_FIELDS},
                         cost=facts["cost"], priced=facts["priced"]))
        if mark in ("look", "question", "stopped"):
            waiting.append(dict(mark=mark, story=story_id, what=words, action=action))
    for name, front, body, state, error, path in decision_files(cwd):
        story_id = str(front.get("story", "")).strip() if not error else ""
        if story_id in stories:
            continue                                  # its story's row already says so
        if error or state in ("open", "draft"):
            waiting.append(dict(mark="question", story=story_id or name, what="an open question",
                                action=make_action(skill="/factory-decisions",
                                              shell=f"write the answer into {shown(path)} under `## Answer`")))
    running = []
    held = read_claim(claim_path(cwd)) if live else None
    for story_id, stage, started in running_stages(runs):
        if story_id in stories and stories[story_id]["state"] in ("delivered", "superseded"):
            continue
        interrupted = story_id in stories and stories[story_id]["state"] != "running"
        entry = dict(story=story_id, stage=stage, since=parse_time(started), interrupted=interrupted)
        if live:
            since = parse_time(started)
            entry["ago"] = took_text((now - since).total_seconds()) + " ago" if since else ""
            entry["activity"] = activity_line(cwd, (held or {}).get("owner", ""), started, now).split(": ", 1)[-1]
        running.append(entry)
    epics = []
    for row in rows:
        if not epics or epics[-1]["epic"] != row["epic"]:
            found = next((e for e in epics if e["epic"] == row["epic"]), None)
            if found is None:
                epics.append(dict(epic=row["epic"], rows=[]))
            else:
                epics.append(epics.pop(epics.index(found)))
        epics[-1]["rows"].append(row)
    for epic in epics:
        epic["rows"].sort(key=lambda r: order.index(r["story"]))
        epic.update(delivered=sum(r["done"] for r in epic["rows"]), total=len(epic["rows"]),
                    tokens=sum(r["tokens"] for r in epic["rows"]), measured=sum(r["measured"] for r in epic["rows"]),
                    seconds=sum(r["seconds"] for r in epic["rows"]))
    epics.sort(key=lambda e: min(order.index(r["story"]) for r in e["rows"]))
    journeys = journey_hints(stories, epics)
    nxt = data["next"]
    if nxt:
        next_line = dict(text=f"{nxt} can start from {stories[nxt]['start'] or 'plan'} — run it.",
                         action=make_action(skill=f"/factory-run {nxt}", shell=f"{RUNNER} run --story {nxt}"))
    elif not rows:
        next_line = dict(text="The backlog is empty — write the first story.",
                         action=make_action(skill="/factory-backlog", shell=""))
    elif all(r["state"] in ("delivered", "superseded") for r in rows):
        next_line = dict(text="Every story is delivered — write the next one.",
                         action=make_action(skill="/factory-backlog", shell=""))
    else:
        holder = next((r for r in rows if r["mark"] in ("look", "question", "stopped")), None)
        busy = next((r for r in rows if r["mark"] == "running"), None)
        if holder:
            until = {"look": "is accepted", "question": "has its answer", "stopped": "is unblocked"}[holder["mark"]]
            text = f"Nothing else starts until {holder['story']} {until} — see Waiting for you."
        elif busy:
            text = f"{busy['story']} is running — one story at a time; nothing to do but wait."
        else:
            text = data["reason"] + "."
        next_line = dict(text=text, action=make_action())
    extra = []
    if live:
        if held:
            extra.append(f"worker: {held.get('owner')} since {stamp_text(held.get('since'))} UTC")
        listening = listener_line(cwd)
        extra.append(listening or "listening: no session has looked at the backlog")
        note = duplicate_pipeline_note(cwd)
        if note:
            extra.append(note)
    return dict(project=os.path.basename(os.path.abspath(cwd)), waiting=waiting, running=running, epics=epics,
                rows=rows, next=next_line, journeys=journeys,
                priced=any(r["priced"] for r in rows), extra=extra, hint=data["hint"],
                delivered=sum(r["done"] for r in rows), total=len(rows),
                tokens=sum(r["tokens"] for r in rows), measured=sum(r["measured"] for r in rows),
                seconds=sum(r["seconds"] for r in rows))


def journey_hints(stories, epics):
    """An epic whose stories are all delivered and whose `## Journey` is still open, or named without a
    `kind: journey` item — a hint, never a stop. An epic without the section has decided against one."""
    hints = []
    for epic in epics:
        paths = [stories[r["story"]].get("path", "") for r in epic["rows"]]
        kinds = []
        for path in paths:
            try:
                kinds.append(story_kind(read_front_matter(path)[0]) if path else "story")
            except GateError:
                kinds.append("story")
        built = [r for r, k in zip(epic["rows"], kinds) if k == "story"]
        if not built or any(r["state"] != "delivered" for r in built) or "journey" in kinds or not paths[0]:
            continue
        text = read_text(os.path.join(os.path.dirname(paths[0]), "epic.md")) \
            if os.path.isfile(os.path.join(os.path.dirname(paths[0]), "epic.md")) else ""
        section = text.split("## Journey", 1)[1].split("\n## ", 1)[0] if "## Journey" in text else None
        if section is None:
            continue
        said = "is still open" if re.search(r"^\s*-\s*open:", section, re.M) or not section.strip() \
            else "has no journey test yet"
        hints.append(dict(epic=epic["epic"], text=f"every story is delivered and its journey {said}",
                          action=make_action(skill="/factory-backlog", shell="")))
    return hints


def paint(text, mark, colour):
    return f"\x1b[{COLOURS[mark]}m{text}\x1b[0m" if colour and mark in COLOURS else text


def bold(text, colour):
    return f"\x1b[1m{text}\x1b[0m" if colour else text


def dim(text, colour):
    return f"\x1b[2m{text}\x1b[0m" if colour else text


COMMAND = re.compile(r"(/(?:factory|dca)-[a-z-]+(?: [A-Za-z0-9][\w.-]*)?)")


def commands(text, colour, md=False):
    """The skills a line names, set apart: cyan on a terminal, `code` in Markdown."""
    if md:
        return COMMAND.sub(r"`\1`", text)
    return COMMAND.sub(lambda m: f"\x1b[36m{m.group(1)}\x1b[0m", text) if colour else text


def how_lines(act, colour, indent):
    """The action as labelled lines: look at it, in an agent session, in a shell."""
    lines = []
    if act.get("text"):
        lines.append(f"{indent}{act['text']}")
    rows = []
    if act.get("look"):
        rows.append(("look at it", act["look"]))
    if act.get("skill"):
        rows.append(("agent", commands(act["skill"], colour)))
        rows.append(("shell", act["shell"] if act.get("shell") else dim("— needs an agent session", colour)))
    for label, value in rows:
        lines.append(f"{indent}{dim(label.ljust(10), colour)}   {value}")
    return lines


def how_md(act):
    parts = []
    if act.get("text"):
        parts.append(act["text"])
    if act.get("look"):
        parts.append(f"look at it: `{act['look']}`")
    if act.get("skill"):
        parts.append(f"`{act['skill']}`" + (f" (in a shell: {act['shell']})" if act.get("shell") else ""))
    return " · ".join(parts)


def next_text(model, colour):
    nxt = model["next"]
    return [f"  {bold('Next', colour)}   {nxt['text']}"] + how_lines(nxt["action"], colour, "         ")


def next_md(model):
    """The session's form: the skill to use; the shell's command beside it where there is one."""
    nxt, act = model["next"], model["next"]["action"]
    line = f"**Next:** {nxt['text']}"
    if act.get("skill"):
        line += f" → `{act['skill']}`" + (f" (in a shell: `{act['shell']}`)" if act.get("shell") else "")
    return line


def table_text(headers, rows, right=(), indent="    ", marks=None, colour=False, widths=None, total=False,
               first_bold=False, painted=2):
    """Aligned columns with a rule under the header; `marks[i]` colours row i's first `painted` cells.
    `widths` makes several tables line up — the backlog's, one per epic; `total` sets the last row
    apart with a rule of its own."""
    widths = list(widths or column_widths(headers, rows))
    # The last column wraps inside its own column rather than being cut: nothing a reader needs is lost.
    # The width is the terminal's where there is one, else a fixed 120 — the same text in a pipe.
    room = view_width() - len(indent) - sum(widths[:-1]) - 3 * (len(widths) - 1)
    wrap_last = len(widths) > 1 and (len(widths) - 1) not in right and widths[-1] > max(room, 30)
    if wrap_last:
        widths[-1] = max(room, 30)
    fmt = lambda cells: "   ".join((str(c).rjust(widths[i]) if i in right else str(c).ljust(widths[i]))
                                   for i, c in enumerate(cells)).rstrip()
    if wrap_last:
        wrapped = []
        for row in rows:
            pieces = textwrap.wrap(str(row[-1]), widths[-1]) or [""]
            wrapped.append(list(row[:-1]) + [pieces[0]])
            wrapped += [[""] * (len(row) - 1) + [piece] for piece in pieces[1:]]
        if marks is not None:
            expanded = []
            for mark, row in zip(marks, rows):
                expanded += [mark] + [None] * (len(textwrap.wrap(str(row[-1]), widths[-1]) or [""]) - 1)
            marks = expanded
        rows = wrapped
    lines = [indent + (bold(fmt(headers), True) if colour else fmt(headers)),
             indent + "   ".join("─" * w for w in widths)]
    for n, row in enumerate(rows):
        is_total = total and n == len(rows) - 1
        if is_total:
            lines.append(indent + "   ".join("─" * w for w in widths))
        line = bold(fmt(row), colour) if is_total else fmt(row)
        if first_bold and colour and not is_total:
            first = str(row[0]).ljust(widths[0])
            line = bold(first, True) + line[len(first):]
        if marks and colour and marks[n]:
            head = "   ".join(str(c).ljust(widths[i]) for i, c in enumerate(row[:painted]))
            line = paint(head, marks[n], True) + line[len(head):]
        lines.append(indent + line)
    return lines


def view_width():
    return shutil.get_terminal_size((120, 24)).columns if sys.stdout.isatty() else 120


def column_widths(headers, rows):
    return [max([len(str(h))] + [len(str(r[i])) for r in rows]) for i, h in enumerate(headers)]


def table_md(headers, rows, right=(), first_bold=False):
    """A Markdown table with its headers in bold; `first_bold` sets the first column apart too."""
    strong = lambda c: f"**{c}**" if str(c) and not str(c).startswith("**") else str(c)
    rows = [[strong(r[0])] + list(r[1:]) for r in rows] if first_bold else rows
    lines = ["| " + " | ".join(strong(h) for h in headers) + " |",
             "|" + "|".join("--:" if i in right else "---" for i in range(len(headers))) + "|"]
    lines += ["| " + " | ".join(str(c).replace("|", "\\|") for c in row) + " |" for row in rows]
    return lines


def epic_mark(epic):
    """The epic's own mark, from its stories: what needs you wins, then what stopped, what runs; ✓ when all
    are delivered."""
    marks = [r["mark"] for r in epic["rows"]]
    for wanted in ("look", "question", "stopped", "running"):
        if wanted in marks:
            return wanted
    return "done" if marks and all(m == "done" for m in marks) else "none"


def epic_summary(item):
    parts = [f"{item['delivered']} of {item['total']} delivered",
             tokens_text(item["tokens"], item["measured"]) + (" tokens" if item["measured"] else "")]
    if item["seconds"]:
        parts.append(took_text(item["seconds"]))
    return " · ".join(parts)


def backlog_columns(model):
    headers = ["story", "state", "stage", "passes", "started (UTC)", "delivered (UTC)", "worked"]
    return headers, {3, 6}


def backlog_cells(row, model, marks):
    if not row.get("journal", True) and row["mark"] == "done":
        # delivered before the pipeline kept a journal: said once, not in five empty cells
        return [f"{marks[row['mark']]} {row['story']}", row["state"], "", "", "no journal",
                stamp_text(row["delivered"]), ""]
    return [f"{marks[row['mark']]} {row['story']}", row["state"], row["stage"], row["passes"] or "—",
            stamp_text(row["started"]), stamp_text(row["delivered"]), took_text(row["seconds"])]


def token_rows(model):
    """The tokens per story, grouped by epic with a subtotal each and the total over every story — the
    four classes as the tool reports them."""
    classes = ("input", "output", "cache_write", "cache_read")
    def cells(label, item, runs):
        if not item["measured"]:
            return [label, runs or "—", "—", "—", "—", "—", "not measured"] + (["—"] if model["priced"] else [])
        row = [label, runs] + [f"{item.get(k, 0):,}" for k in classes] + [f"{item['tokens']:,}"]
        return row + ([f"{item.get('cost', 0):.2f}" if item.get("priced") else "—"] if model["priced"] else [])
    rows, kinds = [], []
    for epic in model["epics"]:
        subtotal = {k: sum(r.get(k, 0) for r in epic["rows"]) for k in classes + ("tokens", "measured", "runs", "cost", "priced")}
        rows.append(cells(epic["epic"] or "(no epic)", subtotal, subtotal["runs"]))
        kinds.append("epic")
        for r in epic["rows"]:
            rows.append(cells("  ↳ " + r["story"], r, r["runs"]))
            kinds.append("story")
    grand = {k: sum(r.get(k, 0) for r in model["rows"]) for k in classes + ("tokens", "measured", "runs", "cost", "priced")}
    rows.append(cells("total", grand, grand["runs"]))
    kinds.append("total")
    headers = ["epic / story", "runs", "input", "output", "cache write", "cache read", "total"] \
        + (["cost $"] if model["priced"] else [])
    return headers, rows, kinds, set(range(1, len(headers)))


def heading(text, colour, underline="─"):
    """A title the eye finds: bold where there is colour, underlined always."""
    return [bold(text, colour), underline * len(text)]


def section(text, colour):
    return ["", "  " + bold(text, colour), ""]


def render_status_text(model, colour=False):
    only_backlog = model.get("part") == "backlog"
    out = [""] + heading(f"{'Backlog' if only_backlog else 'Factory'} — {model['project']}", colour, "═")
    if not only_backlog:
        out += waiting_running_text(model, colour)
    return "\n".join(out + backlog_text(model, colour, heading_line=not only_backlog) + [""])


def waiting_running_text(model, colour):
    out = section("Waiting for you", colour)
    if model["waiting"]:
        width = max(len(w["story"]) for w in model["waiting"])
        what = max(len(w["what"]) for w in model["waiting"])
        for n, w in enumerate(model["waiting"]):
            head = f"{MARKS_TEXT[w['mark']]} {w['story'].ljust(width)}   {w['what']}"
            out += ([""] if n else []) + ["    " + paint(head, w["mark"], colour)]
            out += how_lines(w["action"], colour, "        ")
    else:
        out.append("    Nothing waits for you.")
    out += section("Running", colour)
    if model["running"]:
        for r in model["running"]:
            mark = "stopped" if r.get("interrupted") else "running"
            line = f"{MARKS_TEXT[mark]} {r['story']}   {r['stage']}   since {stamp_text(r['since'])} UTC"
            if r.get("interrupted"):
                line += " · never ended — possibly interrupted"
            if r.get("ago"):
                line += f" · {r['ago']}"
            out.append("    " + paint(line, mark, colour))
            if r.get("activity"):
                out.append(f"        activity: {r['activity']}")
    else:
        out.append("    Nothing is running.")
    return out


def backlog_text(model, colour, heading_line=True):
    whole = epic_mark({"rows": model["rows"]})
    summary = paint(f"{MARKS_TEXT[whole]} {epic_summary(model)}", whole, colour) if model["rows"] else ""
    out = section("Backlog" + (f" — {epic_summary(model)}" if model["rows"] else ""), colour) if heading_line \
        else ["", "  " + summary, ""]
    if not model["rows"]:
        out.append("    No story yet.")
    headers, right = backlog_columns(model)
    widths = column_widths(headers, [backlog_cells(r, model, MARKS_TEXT) for r in model["rows"]])
    for n, epic in enumerate(model["epics"]):
        mark = epic_mark(epic)
        out += ([""] if n else []) + ["    " + paint(bold(f"{MARKS_TEXT[mark]} {epic['epic'] or '(no epic)'}", colour), mark, colour)
                                      + f"   {dim(epic_summary(epic), colour)}"]
        cells = [backlog_cells(r, model, MARKS_TEXT) for r in epic["rows"]]
        out += table_text(headers, cells, right, indent="      ", marks=[r["mark"] for r in epic["rows"]],
                          colour=colour, widths=widths)
    for hint in model.get("journeys", []):
        out += ["", f"    {dim('journey', colour)}   {hint['epic']}: {hint['text']} — {commands(hint['action']['skill'], colour)}"]
    if model["rows"]:
        headers, rows, kinds, right = token_rows(model)
        caption = "Tokens" + ("" if model["priced"] or not model["measured"] else " — no price in a session log")
        out += section(caption, colour)
        lines = table_text(headers, rows, right, total=True, colour=colour)
        # epic rows and the total in bold: the sums stand out
        for n, kind in enumerate(kinds):
            index = 2 + n + (1 if kind == "total" else 0)
            if kind == "epic" and colour:
                lines[index] = bold(lines[index], True)
        out += lines
    out += ["", "─" * 72] + next_text(model, colour)
    if model["extra"]:
        out += [""] + ["  " + line for line in model["extra"]]
    if model["hint"]:
        out += ["", f"  layout: {model['hint']}"]
    return out


def render_status_md(model):
    if model.get("part") == "backlog":
        return render_backlog_md(model)
    out = [f"### Factory — {model['project']}", "", "**Waiting for you**", ""]
    if model["waiting"]:
        out += table_md(["", "story", "what", "how"],
                        [[MARKS_MD[w["mark"]], w["story"], w["what"], how_md(w["action"])] for w in model["waiting"]])
    else:
        out.append("Nothing waits for you.")
    out += ["", "**Running**", ""]
    if model["running"]:
        out += table_md(["", "story", "stage", "since"] + (["activity"] if any(r.get("activity") for r in model["running"]) else []),
                        [[MARKS_MD["stopped" if r.get("interrupted") else "running"], r["story"], r["stage"],
                          stamp_text(r["since"]) + " UTC" + (" · never ended — possibly interrupted" if r.get("interrupted") else "")
                          + (f" · {r['ago']}" if r.get("ago") else "")]
                         + ([r.get("activity", "")] if any(x.get("activity") for x in model["running"]) else [])
                         for r in model["running"]])
    else:
        out.append("Nothing is running.")
    return "\n".join(out + backlog_md_lines(model))


def render_backlog_md(model):
    return "\n".join([f"### Backlog — {model['project']}"] + backlog_md_lines(model))


def backlog_md_lines(model):
    out = ["", "**Backlog**" + (f" — {epic_summary(model)}" if model["rows"] else "")]
    if not model["rows"]:
        out += ["", "No story yet."]
    headers, right = backlog_columns(model)
    for epic in model["epics"]:
        out += ["", f"{MARKS_MD[epic_mark(epic)]} *{epic['epic'] or '(no epic)'}* — {epic_summary(epic)}", ""]
        out += table_md(headers, [backlog_cells(r, model, MARKS_MD) for r in epic["rows"]], right)
    for hint in model.get("journeys", []):
        out += ["", f"*journey* — {hint['epic']}: {hint['text']} → `{hint['action']['skill']}`"]
    if model["rows"]:
        headers, rows, kinds, right = token_rows(model)
        rows = [[f"**{c}**" if kind in ("epic", "total") and str(c) else c for c in row] if kind != "story"
                else [row[0].strip()] + row[1:] for row, kind in zip(rows, kinds)]  # "↳ story" in Markdown
        caption = "Tokens" + ("" if model["priced"] or not model["measured"] else " — no price in a session log")
        out += ["", f"**{caption}**", ""] + table_md(headers, rows, right)
    out += ["", next_md(model)]
    if model["extra"]:
        out += [""] + [f"- {line}" for line in model["extra"]]
    return out


def pass_label(index, pass_, records):
    """First delivery, then what started each later pass: a human's correction, or a re-plan."""
    if index == 0:
        return "first delivery"
    corrections = [str(f["id"]).strip() for _p, f, _b, st, a in records
                   if is_acceptance(f) and st in ("answered", "applied") and not accepted(a)
                   and parse_time(str(a.get("at", ""))) and parse_time(str(a.get("at", ""))) <= pass_["start"]]
    return "correction" if corrections else "again from plan"


def decision_mark(decision):
    """Open or a draft needs you; answered waits for the stage that applies it; applied is done — and
    an answered acceptance is done too: it was applied by the gate or by the re-plan."""
    if decision["state"] in ("open", "draft"):
        return "question"
    if decision["state"] == "applied" or decision["kind"] == "acceptance":
        return "done"
    return "running"


def story_model(cwd, epics, runs, story_id, live=False):
    overview = status_model(cwd, epics, runs, live)
    row = next((r for r in overview["rows"] if r["story"] == story_id), None)
    if row is None:
        raise GateError(f"no story {story_id} under {epics}/")
    data = schedule_data(cwd, epics, runs)["stories"][story_id]
    facts = story_facts(cwd, runs, story_id, data.get("front"))
    records = story_records(cwd, story_id, data.get("path"))
    try:
        criteria = len(criteria_of(data["path"], data["body"]))
    except GateError:
        criteria = 0
    accepted_by = next((str(f["id"]).strip() for _p, f, _b, st, a in reversed(records)
                        if is_acceptance(f) and st in ("answered", "applied") and accepted(a)), None)
    passes = []
    for i, p in enumerate(facts["passes"]):
        before = facts["passes"][i - 1]["end"] if i else None
        passes.append(dict(p, label=pass_label(i, p, records),
                           waited=(p["start"] - before).total_seconds() if before and p["start"] else 0))
    # why a stage ran more than once per pass: the questions it asked, else a repeat (a gate refused it)
    questions = {}
    for _p, front, _b, _st, _a in records:
        if not is_acceptance(front):
            questions.setdefault(str(front.get("stage", "")).strip(), []).append(str(front["id"]).strip())
    for stage, entry in facts["stages"].items():
        if stage in WINDOWS:
            entry["why"] = {"backlog": "writing the story", "decisions": "answering its questions"}[stage] \
                + (f" · {entry['runs']} sessions" if entry["runs"] > 1 else "")
            continue
        extra = entry["runs"] - sum(1 for p in facts["passes"] if stage in p["stages"])
        # a shared window carries several stages: a question any of those stages asked is its
        covered = SHARED_WINDOWS.get(stage, (stage,))
        asked = [rid for name in covered for rid in questions.get(name, [])][:max(extra, 0)]
        repeats = max(extra, 0) - len(asked)
        why = [f"{len(asked)} question" + ("s" if len(asked) > 1 else "") + f" ({', '.join(asked)})"] if asked else []
        if repeats:
            why.append(f"{repeats} repeat" + ("s" if repeats > 1 else "") + " (a gate refused)")
        entry["why"] = " · ".join(why)
    decisions = []
    for _p, front, body, state, answer in records:
        question = (body.strip().splitlines() or ["(no title)"])[0].lstrip("# ").strip()
        given = str(answer.get("answer", "")).strip() if state in ("answered", "applied") else ""
        text = (f"{given}" if is_acceptance(front) and given else
                f"{given} — {question}" if given else f"open — {question}")
        decisions.append(dict(id=str(front["id"]).strip(), state=state,
                              kind="acceptance" if is_acceptance(front) else "question", text=text))
    models = sorted({m for e in facts["stages"].values() for m in e["models"]})
    not_applied = sorted({r for e in facts["stages"].values() if e["not_applied"] for r in e["requested"]})
    return dict(row=row, story=story_id, title=data.get("title", ""), epic=data.get("epic", ""),
                context=str(data["front"].get("context", "")).strip(), criteria=criteria, accepted_by=accepted_by,
                passes=passes, stages=facts["stages"], decisions=decisions, models=models, not_applied=not_applied,
                priced=facts["priced"] > 0, waiting=[w for w in overview["waiting"] if w["story"] == story_id],
                next=overview["next"])


def token_cells(entry, measured):
    """The four token classes as Claude Code reports them (and ccusage shows them), and their total."""
    if not measured:
        return ["—", "—", "—", "—", "not measured"]
    return [f"{entry.get(k, 0):,}" for k in ("input", "output", "cache_write", "cache_read")] + [f"{entry['tokens']:,}"]


def stage_cells(model):
    """One row per stage and a total. A model column only where the stages ran on different models or a
    requested one did not reach a stage — otherwise the one model is named in the caption."""
    per_stage = len(model["models"]) > 1 or bool(model["not_applied"])
    any_why = any(e.get("why") for e in model["stages"].values())
    rows = []
    for stage in sorted(model["stages"], key=stage_rank):
        e = model["stages"][stage]
        cells = [stage, e["runs"], took_text(e["seconds"])] + token_cells(e, e["measured"])
        if e["measured"] < e["runs"]:
            cells[1] = f"{e['runs']} ({e['runs'] - e['measured']} not measured)"
        if model["priced"]:
            cells.append(f"{e['cost']:.2f}" if e["priced"] else "—")
        if per_stage:
            ran = ", ".join(sorted(e["models"])) or "—"
            if e["not_applied"]:
                ran += f" (requested {', '.join(sorted(e['requested']))}: not applied)"
            cells.append(ran)
        if any_why:
            cells.append(e.get("why", ""))
        rows.append(cells)
    total = {k: sum(e.get(k, 0) for e in model["stages"].values())
             for k in ("runs", "seconds", "tokens", "measured", "cost") + USAGE_FIELDS}
    cells = ["total", total["runs"], took_text(total["seconds"])] + token_cells(total, total["measured"])
    if model["priced"]:
        cells.append(f"{total['cost']:.2f}")
    if per_stage:
        cells.append("")
    if any_why:
        cells.append("")
    rows.append(cells)
    headers = ["stage", "runs", "worked", "input", "output", "cache write", "cache read", "total"] \
        + (["cost $"] if model["priced"] else []) + (["model"] if per_stage else []) + (["notes"] if any_why else [])
    right = {1, 2, 3, 4, 5, 6, 7} | ({8} if model["priced"] else set())
    return headers, rows, right


def story_header(model):
    """(title line, [(label, value)]): what the story is, where it stands, how often it ran."""
    row = model["row"]
    title = f"{model['story']} — {model['title']}" if model["title"] else model["story"]
    state = row["state"]
    if row["delivered"]:
        state = f"delivered {stamp_text(row['delivered'])} UTC"
    if model["accepted_by"]:
        state += " · accepted by a human"
    passes = model["passes"]
    corrections = sum(1 for p in passes[1:] if p["label"].startswith("correction"))
    again = len(passes) - 1 - corrections
    why = []
    if corrections:
        why.append("one correction" if corrections == 1 else f"{corrections} corrections")
    if again:
        why.append("planned again once" if again == 1 else f"planned again {again} times")
    pass_text = ("no journal — delivered before the pipeline measured"
                 if not model["row"].get("journal", True) and model["row"]["mark"] == "done"
                 else "not run yet") if not passes else "1 pass — the first delivery" if len(passes) == 1 else \
        f"{len(passes)} passes — the first delivery, then " + " and ".join(why)
    facts = [("Epic", model["epic"] or "—")]
    if model["context"]:
        facts.append(("Context", model["context"]))
    facts += [("Criteria", str(model["criteria"])), ("State", state), ("History", pass_text)]
    return title, facts


def stage_caption(model):
    caption = "Stages"
    parts = []
    if len(model["models"]) == 1 and not model["not_applied"]:
        parts.append(model["models"][0])
    if model["not_applied"]:
        parts.append(f"requested {', '.join(model['not_applied'])}: not applied")
    if not model["priced"] and any(e["measured"] for e in model["stages"].values()):
        parts.append("no price in a session log")
    return caption + (" — " + " · ".join(parts) if parts else "")


def render_story_text(model, colour=False):
    row = model["row"]
    title, facts = story_header(model)
    width = max(len(label) for label, _v in facts)
    out = [""] + heading(title, colour, "═") + [""]
    for label, value in facts:
        if label == "State":
            value = paint(f"{MARKS_TEXT[row['mark']]} {value}", row["mark"], colour)
        out.append(f"  {bold(label.ljust(width), colour)}   {value}")
    for w in model["waiting"]:
        out += ["", "  " + paint(f"{MARKS_TEXT[w['mark']]} {w['what']}", w["mark"], colour)]
        out += how_lines(w["action"], colour, "      ")
    if model["passes"]:
        out += section("Passes", colour)
        out += table_text(["pass", "started (UTC)", "ended (UTC)", "worked", "waited before", "tokens"],
                          [[f"{i + 1}  {p['label']}", stamp_text(p["start"]), stamp_text(p["end"]),
                            took_text(p["seconds"]), took_text(p["waited"]), tokens_text(p["tokens"], p["measured"])]
                           for i, p in enumerate(model["passes"])], {3, 4, 5}, colour=colour, first_bold=True)
    if model["stages"]:
        headers, rows, right = stage_cells(model)
        out += section(stage_caption(model), colour) + table_text(headers, rows, right, total=True, colour=colour,
                                                                    first_bold=True)
    if model["decisions"]:
        out += section("Decisions", colour)
        out += table_text(["record", "state", "answer or question"],
                          [[d["id"], d["state"], d["text"]] for d in model["decisions"]], colour=colour,
                          marks=[decision_mark(d) for d in model["decisions"]], first_bold=True)
    out += ["", "─" * 72] + next_text(model, colour) + [""]
    return "\n".join(out)


def render_story_md(model):
    title, facts = story_header(model)
    out = [f"**{title}**", ""]
    out += [f"- **{label}:** " + (f"{MARKS_MD[model['row']['mark']]} " if label == "State" else "") + value
            for label, value in facts]
    for w in model["waiting"]:
        out += ["", f"{MARKS_MD[w['mark']]} **{w['what']}** — {how_md(w['action'])}"]
    if model["passes"]:
        out += ["", "**Passes**", ""]
        out += table_md(["pass", "started (UTC)", "ended (UTC)", "worked", "waited before", "tokens"],
                        [[f"{i + 1} {p['label']}", stamp_text(p["start"]), stamp_text(p["end"]),
                          took_text(p["seconds"]), took_text(p["waited"]), tokens_text(p["tokens"], p["measured"])]
                         for i, p in enumerate(model["passes"])], {3, 4, 5}, first_bold=True)
    if model["stages"]:
        headers, rows, right = stage_cells(model)
        rows = rows[:-1] + [[f"**{c}**" if str(c) else c for c in rows[-1]]]
        out += ["", f"**{stage_caption(model)}**", ""] + table_md(headers, rows, right, first_bold=True)
    if model["decisions"]:
        out += ["", "**Decisions**", ""]
        out += table_md(["", "record", "state", "answer or question"],
                        [[MARKS_MD[decision_mark(d)], f"**{d['id']}**", d["state"], d["text"]] for d in model["decisions"]])
    out += ["", next_md(model)]
    return "\n".join(out)


def json_ready(value):
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if isinstance(value, set):
        return sorted(value)
    if isinstance(value, dict):
        return {k: json_ready(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_ready(v) for v in value]
    return value


def use_colour(choice):
    if choice == "always":
        return True
    if choice == "never" or os.environ.get("NO_COLOR"):
        return False
    return sys.stdout.isatty()


def checkout_holders(cwd, epics, runs, exclude=None):
    """The stories with unfinished code in the checkout — past their test stage, not delivered — as
    the schedule counts them."""
    holders = []
    for root, _dirs, files in os.walk(epics):
        if os.path.normpath(root) == os.path.normpath(epics):
            continue
        for name in sorted(files):
            if not name.endswith(".md") or name == "epic.md":
                continue
            path = os.path.join(root, name)
            try:
                front, _body = read_front_matter(path)
            except GateError:
                continue
            story_id = str(front.get("id") or name[:-3]).strip()
            if story_id == exclude or not os.path.isfile(os.path.join(runs, story_id, STAGE_FILES["test"])):
                continue
            if story_state(cwd, runs, story_id, front, path)[0] not in ("delivered", "superseded"):
                holders.append(story_id)
    return sorted(holders)


def reopen(cwd, runs, epics, story_id):
    """Take a delivered story back for a correction a human gave on looking at it.

    Only with an answered acceptance record the story cites — the answer is in the story, not in a
    prompt. Before a story was accepted every answer is a correction; after an acceptance, one that
    changes or takes back a criterion is a new wish, and that is a new story, not this one."""
    story_path = find_story(epics, story_id)
    front, _body = read_front_matter(story_path)
    if not is_delivered(front):
        print(f"reopen: {story_id} is not delivered — a correction before delivery goes into the story, "
              f"and the schedule runs it from plan")
        return 1
    records = acceptance_records(cwd, story_id, story_path)
    if not records or records[-1][2] not in ("answered", "applied") or accepted(records[-1][3]):
        print(f"reopen: {story_id} has no answered correction — /factory-decisions records the human's "
              f"correction as an acceptance record first")
        return 1
    rid = records[-1][0]
    holders = checkout_holders(cwd, epics, runs, exclude=story_id)
    if holders:
        print(f"reopen: {', '.join(holders)} holds the checkout with unfinished code — one story at a time; "
              f"reopen {story_id} once it is delivered")
        return 1
    text = read_text(story_path)
    if rid not in text:
        print(f"reopen: the story does not cite {rid} — write the correction into it first (criteria and "
              f"an `answered:` line naming {rid})")
        return 1
    # After an acceptance, the criteria as accepted are the record's list: a correction that changes one of
    # them is a new wish.
    earlier = [record for record in records[:-1] if accepted(record[3])]
    if earlier:
        before = dict(accepted_criteria(earlier[-1][4]))
        now = dict(criteria_of(story_path, read_front_matter(story_path)[1]))
        changed = sorted(key for key, value in before.items() if now.get(key) != value)
        if changed:
            print(f"reopen: after its acceptance the correction changes {', '.join(changed)} — that is a new "
                  f"wish: a new story with `## Changed expectations`, not this one reopened")
            return 1
    kept = keep_pass(os.path.join(runs, story_id))
    write_story_fields(story_path, status="approved", delivered=None)
    print(f"reopen: {story_id} taken back for {rid} — it runs again from plan; the delivered pass is kept as "
          f"{shown(kept) if kept else 'nothing (no run folder)'}, and the story no longer says delivered")
    return 0


def keep_pass(folder):
    """Before a story runs again from plan: its hand-overs, marks and refusals go to `.verify/pass-<n>/`, with the
    base tree the pass's diff was taken against — the next pass records its own. The journal and the tree
    snapshots stay where they are; the history continues. Returns the folder, or None without a run folder."""
    if not os.path.isdir(folder):
        return None
    verify = os.path.join(folder, ".verify")
    os.makedirs(verify, exist_ok=True)
    number = 1 + sum(1 for name in os.listdir(verify) if name.startswith("pass-"))
    target = os.path.join(verify, f"pass-{number}")
    os.makedirs(target)
    for name in sorted(os.listdir(folder)):
        if name != ".verify":
            os.replace(os.path.join(folder, name), os.path.join(target, name))
    base = os.path.join(verify, "base-tree")
    if os.path.isfile(base):
        os.replace(base, os.path.join(target, "base-tree"))
    return target


def schedule_data(cwd, epics, runs):
    """Every story's state, the order and the next one to run — read off the files, printed by
    `schedule` for the runner and by `status` for a person.

    One story with unfinished code at a time: a story past its plan stage that is not delivered
    holds the checkout, because its tests and code are in the working tree and a second story
    would build on them. Such a story is next if it can run, and nothing else starts while it
    cannot. A story that stopped at its plan stage wrote no code, so independent work runs past it."""
    stories, order = {}, []
    hint = layout_hint(cwd, read_profile(resolve_profile(None, cwd)))
    twice = duplicate_ids(epics)
    for path in story_files(epics):
        name = os.path.basename(path)
        epic = os.path.basename(os.path.dirname(path))
        try:
            front, story_body = read_front_matter(path)
        except GateError as error:
            stories[name[:-3]] = dict(state="stopped", start=None, detail=str(error), deps=[], path=path,
                                      epic=epic, title="", front={}, body="")
            continue
        story_id = str(front.get("id") or name[:-3]).strip()
        if story_id.lower() in twice:
            # Two stories under one id would share a run folder and a row here: both stop, both are named.
            others = [shown(p) for p in twice[story_id.lower()] if os.path.normpath(p) != os.path.normpath(path)]
            stories[f"{story_id} ({shown(path)})"] = dict(
                state="stopped", start=None, deps=[], path=path, epic=epic, front=front, body=story_body,
                title=story_title(front, story_body), kind=story_kind(front), holds=False,
                detail=f"id {story_id!r} is not unique — also {', '.join(others)}; give one of them another")
            continue
        state, start, detail = story_state(cwd, runs, story_id, front, path)
        stories[story_id] = dict(state=state, start=start, detail=detail, deps=depends_on(front),
                                 kind=story_kind(front),
                                 holds=state not in ("delivered", "superseded") and os.path.isfile(
                                     os.path.join(runs, story_id, STAGE_FILES["test"])),
                                 path=path, epic=str(front.get("epic") or epic).strip(), front=front,
                                 body=story_body, title=story_title(front, story_body))

    # dependency order, ties by id; whatever is left after that sits on a cycle
    placed, remaining = set(), sorted(stories)
    while remaining:
        free = [s for s in remaining if all(d in placed or d not in stories for d in stories[s]["deps"])]
        if not free:
            break
        order.append(free[0])
        placed.add(free[0])
        remaining.remove(free[0])
    for story_id in remaining:
        order.append(story_id)
    for story_id in order:
        story = stories[story_id]
        if story["state"] not in RUNNABLE:
            continue
        unknown = [d for d in story["deps"] if d not in stories]
        if story_id in remaining:
            story.update(state="blocked", start=None, detail="on a dependency cycle: "
                         + ", ".join(sorted(s for s in remaining)))
        elif unknown:
            story.update(state="blocked", start=None, detail="depends on unknown " + ", ".join(unknown))
        else:
            pending = [d for d in story["deps"] if stories[d]["state"] != "delivered"]
            if pending:
                story.update(state="blocked", start=None, detail="depends on " + ", ".join(
                    f"{d} ({stories[d]['state']})" for d in pending))

    # A stage that started and has not ended is running — unless it has shown no sign of life for longer
    # than a stage may take, then it was interrupted and the story may be picked up again.
    now = datetime.now(timezone.utc)
    for story_id, stage, started in running_stages(runs):
        if story_id not in stories or stories[story_id]["state"] in ("delivered", "superseded"):
            continue                              # done is done: a killed runner's open stage changes nothing
        since = parse_time(started)
        if since and (now - since).total_seconds() <= stale_after():
            stories[story_id].update(state="running", start=None, detail=f"stage {stage} since {started}")
        else:
            stories[story_id]["detail"] = (stories[story_id]["detail"] + " · " if stories[story_id]["detail"] else "") \
                + f"stage {stage} started {started} and never ended — possibly interrupted"
    holders = [s for s in order if stories[s].get("holds")]
    nxt, reason, wait = None, "", False
    stray = unclaimed_changes(cwd, runs, stories) if not holders else []
    if stray:
        reason = (f"{len(stray)} changed file(s) in the checkout that no story's run folder claims "
                  f"({', '.join(stray[:3])}{', …' if len(stray) > 3 else ''}) — a run folder removed mid-story, or work "
                  f"in progress; commit or stash it, or restore the run folder, before another story starts")
    elif holders:
        holder = stories[holders[0]]
        if holder["state"] in RUNNABLE:
            nxt = holders[0]
        else:
            reason = (f"{holders[0]} holds unfinished code in the checkout ({holder['state']}) — "
                      f"no other story starts until it is delivered")
            wait = holder["state"] in ("waiting", "running")
    else:
        busy = [s for s in order if stories[s]["state"] == "running"]
        nxt = None if busy else next((s for s in order if stories[s]["state"] in RUNNABLE), None)
        wait = any(stories[s]["state"] in ("waiting", "running") for s in order)
        if busy:
            reason = f"{busy[0]} is running ({stories[busy[0]]['detail']}) — one story at a time per checkout"
        elif nxt is None:
            reason = "nothing can run"
    counts = {}
    for story in stories.values():
        counts[story["state"]] = counts.get(story["state"], 0) + 1
    return dict(stories=stories, order=order, next=nxt, reason=reason, wait=wait, counts=counts, hint=hint)


#: What people write and the pipeline installs: a change there is not code a story left behind.
PEOPLE_OWNED = ("project/", ".agents/", ".claude/", ".codex/", ".opencode/", ".githooks/", "docs/")


def unclaimed_changes(cwd, runs, stories):
    """Code changed in the checkout that no story's run folder claims — a run folder removed while a story was
    past its plan, or a person's work in progress. Neither is something to start the next story on top of.
    Not read as that: a story delivered after HEAD was committed (its code waits for its commit, the normal
    state), and a project without a commit, where nothing can be compared."""
    code, stamp = git(cwd, "log", "-1", "--format=%cI")
    committed = parse_time(stamp.strip()) if code == 0 else None
    if not committed:
        return []
    for story in stories.values():
        delivered = parse_time(delivered_on(story.get("front") or {}))
        if delivered and delivered > committed:
            return []
    snapshot = tree_snapshot(cwd) or {}
    fixed = (PROFILE_FILE, "AGENTS.md", "CLAUDE.md", ".gitignore", ".gitattributes")
    # A file that is gone is no code to build on — and a move (the migration's, a person's) reads as a
    # deletion at its origin and an addition where it now is, which the places above already judge.
    return sorted(path for path, digest in snapshot.items()
                  if digest != DELETED and not run_owned(path, runs) and not path.startswith(PEOPLE_OWNED)
                  and path not in fixed)


def schedule(cwd, epics, runs):
    """Print every story's state and the next one to run; return 0. The runner and the tests read
    these lines (`schedule:`, `wait:`, `next:`): they are a contract, not the person's view."""
    data = schedule_data(cwd, epics, runs)
    stories, order, nxt, reason, wait = data["stories"], data["order"], data["next"], data["reason"], data["wait"]
    if data["hint"]:
        print(f"layout: {data['hint']}")
    for story_id in order:
        story = stories[story_id]
        start = f"from {story['start']}" if story["start"] else ""
        # What the story cost so far, from the runner's journal — kept per story on disk, so a
        # restart, a second session or a new run never resets it. An in-session run writes none.
        journal = os.path.join(runs, story_id, ".verify", "journal.tsv")
        spent = ""
        if os.path.isfile(journal):
            used = journal_usage(runs, story_id)
            count = sum(e["invocations"] for e in used.values())
            tokens = sum(tokens_of(e) for e in used.values())
            spent = (f" · {count} stage invocation(s)" + (f", {tokens:,} tokens" if tokens else "")) if count else ""
        print(f"{story_id}  {story['state']:<11} {start:<13} {story['detail']}{spent}".rstrip())
    counts = data["counts"]
    print("schedule: " + (", ".join(f"{n} {state}" for state, n in sorted(counts.items()))
                          or "no story under " + epics + "/"))
    print(f"wait: {'yes' if wait else 'no'}")
    print(f"next: {nxt} {stories[nxt]['start']}" if nxt else f"next: none — {reason}")
    return 0


def start(cwd, epics, runs, story_id):
    """Where `run --story <id>` begins when no stage is named: the schedule's view of that one story.

    Prints `state:`, `start:` (a stage, or `none`) and `detail:` — a contract the runner reads. A story
    that is delivered, waits, is blocked or stopped gets `start: none`; another story's unfinished
    code in the checkout blocks it the way it blocks the backlog run. Exit 2 for an unknown story."""
    data = schedule_data(cwd, epics, runs)
    story = data["stories"].get(story_id)
    if story is None:
        print(f"factory: no story {story_id} under {epics}/", file=sys.stderr)
        return 2
    state, stage, detail = story["state"], story["start"], story["detail"]
    holder = next((s for s in data["order"] if data["stories"][s].get("holds")), None)
    if stage and holder and holder != story_id:
        state, stage, detail = "blocked", None, (f"{holder} holds unfinished code in the checkout "
                                                 f"({data['stories'][holder]['state']}) — it is delivered first")
    print(f"state: {state}")
    print(f"start: {stage or 'none'}")
    print(f"detail: {detail}")
    return 0


# --- what the runner reads through here ----------------------------------------------------
# One reader for the profile, a stage file and a decision record: the gate's. The runner used to parse
# them with `sed` and could read a line the gate read differently — a determinism gap with no check.

COMMAND_KEYS = ("compile", "test", "e2eTest", "architecture", "format", "formatFix")
CARRIER_KEY = re.compile(r"^(carrier\.[a-z]+|review\.[a-z-]+|knowledge)$")


def first_word(value):
    parts = str(value or "").split()
    return parts[0] if parts else ""


def command_heads(profile):
    """The first word of every command the profile declares, once each, in the profile's order."""
    heads = []
    for key, value in profile.items():
        if key in COMMAND_KEYS or key.startswith("test."):
            head = first_word(value)
            if head and not head.startswith("{{") and head not in heads:
                heads.append(head)
    return heads


def carrier_lines(profile):
    return [(key, first_word(value)) for key, value in profile.items() if CARRIER_KEY.match(key) and first_word(value)]


def carriers(profile):
    """The skill names, without a `plugin:` prefix, sorted and unique."""
    return sorted({value.rsplit(":", 1)[-1] for _, value in carrier_lines(profile)})


def model_for(profile, tool, stage):
    return first_word(profile.get(f"model.{tool}.{stage}") or profile.get(f"model.{tool}") or "")


def verdict_of_story(runs, story_id):
    path = os.path.join(runs, story_id, "judge.md")
    return verdict_in(read_text(path)) if os.path.isfile(path) else ""


def needs_human_lines(path, story_id=None):
    """`<id>\\t<stage>\\t<record path>` for every decision the file's needs-human section names; None when it
    asks nobody. The record lives beside the story, so the story's id says where to look."""
    ids = needs_human_ids(read_text(path)) if os.path.isfile(path) else None
    if ids is None:
        return None
    lines = []
    for decision_id in ids:
        record, stage = "", ""
        try:
            record = record_path(story_id, decision_id) if story_id else ""
        except GateError:
            record = ""
        if record and os.path.isfile(record):
            try:
                stage = str(read_front_matter(record)[0].get("stage", "") or "")
            except GateError:
                stage = ""
        lines.append(f"{decision_id}\t{stage or '-'}\t{shown(record) if record else '-'}")
    return lines


def open_decision_files(cwd, story_id):
    """The records beside the story that carry no `## Answer` yet — the cheap check a run makes
    before a stage; the gate does the fine reading (a draft without a name is still open)."""
    try:
        store = decisions_store(find_story(place("epics"), story_id))
    except GateError:
        return []
    if not os.path.isdir(store):
        return []
    found = []
    for name in sorted(os.listdir(store)):
        if not name.endswith(".md"):
            continue
        text = read_text(os.path.join(store, name))
        if not re.search(r"^## Answer", text, re.M):
            found.append(shown(os.path.join(store, name)))
    return found


def move_path(cwd, src, dst):
    """Move a file or folder, through git where it is tracked so history follows; a folder moves whole, the
    untracked files in it included. Returns how."""
    os.makedirs(os.path.dirname(os.path.join(cwd, dst)) or cwd, exist_ok=True)
    tracked = git(cwd, "ls-files", "--error-unmatch", "--", src)[0] == 0
    if tracked and git(cwd, "mv", "-k", "--", src, dst)[0] == 0 and not os.path.lexists(os.path.join(cwd, src)):
        return "git mv"
    import shutil
    shutil.move(os.path.join(cwd, src), os.path.join(cwd, dst))
    return "mv"


#: The marks that make a `tasks/<story>/` folder the factory's: without one it is the project's own.
FACTORY_MARKS = (".verify", STORY_DIGEST, ".delivered", ".rounds", ".tests-red", TESTS_BASELINE, ".story-planned")


def adopted_on(run_folder, delivered_file):
    """When an adopted story was delivered: the journal's adopt gate, else the mark's own time."""
    journal = os.path.join(run_folder, ".verify", "journal.tsv")
    if os.path.isfile(journal):
        for line in reversed(read_text(journal).splitlines()):
            parts = line.split("\t")
            if len(parts) >= 4 and parts[1] == "gate" and parts[2] == "adopt" and parts[3] == "exit=0":
                return parts[0]
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(os.path.getmtime(delivered_file)))


def migrate_layout(cwd):
    """`factory.sh update`'s one move to the layout with one owner per place: the profile to the root
    (`backlog:` → `epics:`), `project/backlog/` → `project/epics/`, each decision record beside its story,
    each `tasks/<story>/` that carries factory marks to the run folder, and the delivery mark into the story
    as `status: delivered` + `delivered:`. Idempotent — what is where it belongs is left alone — and every
    move is printed. Anything else under `tasks/` is the project's and is not touched."""
    moved = []

    def say(what):
        moved.append(what)
        print(f"migrate: {what}")

    old_profile = os.path.join(".agents", "factory", "factory.profile.yaml")
    profile_path = resolve_profile(None, cwd)
    moved_profile = False
    if not profile_path and os.path.isfile(old_profile):
        say(f"{old_profile.replace(os.sep, '/')} → {PROFILE_FILE} ({move_path(cwd, old_profile, PROFILE_FILE)})")
        profile_path, moved_profile = PROFILE_FILE, True
    profile = read_profile(profile_path)
    renaming = profile_path and "backlog" in profile and "epics" not in profile
    declared = profile.get("contract", "")
    # The profile is rewritten only where the layout is its subject: the key that named the epics, and the
    # contract line — this layout is what contract 10 describes, so a moved profile says so.
    if renaming or (moved_profile and declared.isdigit() and int(declared) < CONTRACT):
        text = read_text(profile_path)
        changed = []
        if renaming:
            value = profile["backlog"]
            renamed = "project/epics" if value.replace("\\", "/").strip("/") == "project/backlog" else value
            text = re.sub(r"^backlog:.*$", f"epics: {renamed}", text, count=1, flags=re.M)
            changed.append(f"`backlog: {value}` is `epics: {renamed}`")
        if declared.isdigit() and int(declared) < CONTRACT:
            text = re.sub(r"^contract:.*$", f"contract: {CONTRACT}", text, count=1, flags=re.M)
            changed.append(f"contract {declared} → {CONTRACT}")
        with open(profile_path, "w", encoding="utf-8") as handle:
            handle.write(text)
        say(f"{profile_path}: " + ", ".join(changed))
        profile = read_profile(profile_path)
    set_places(profile)
    epics, runs = place("epics"), place("runs")
    old_epics = os.path.join("project", "backlog")
    if os.path.isdir(old_epics) and not os.path.isdir(epics) and epics == DEFAULTS["epics"]:
        say(f"project/backlog/ → {epics}/ ({move_path(cwd, old_epics, epics)})")
    store = os.path.join(".agents", "factory", "decisions")
    if os.path.isdir(store):
        for name in sorted(os.listdir(store)):
            if not name.endswith(".md"):
                continue
            src = os.path.join(store, name)
            try:
                front, _body = read_front_matter(src)
                story_id, rid = str(front.get("story", "")).strip(), str(front.get("id", "")).strip()
                story_path = find_story(epics, story_id)
            except GateError as error:
                print(f"migrate: kept {shown(src)} — {error}")
                continue
            if not rid.startswith(story_id + "-"):
                print(f"migrate: kept {shown(src)} — its id {rid!r} does not start with its story {story_id!r}")
                continue
            dst = record_path(story_id, rid, story_path)
            if os.path.exists(dst):
                print(f"migrate: kept {shown(src)} — {shown(dst)} exists already")
                continue
            say(f"{shown(src)} → {shown(dst)} ({move_path(cwd, src, dst)})")
        if not os.listdir(store):
            os.rmdir(store)
    tasks = "tasks"
    if os.path.isdir(tasks):
        for name in sorted(os.listdir(tasks)):
            src = os.path.join(tasks, name)
            if not os.path.isdir(src) or not any(os.path.exists(os.path.join(src, mark)) for mark in FACTORY_MARKS):
                continue
            dst = os.path.join(runs, name)
            if os.path.exists(dst):
                print(f"migrate: kept {shown(src)} — {shown(dst)} exists already")
                continue
            say(f"{shown(src)}/ → {shown(dst)}/ ({move_path(cwd, src, dst)})")
            try:
                story_path = find_story(epics, name)
                front, _body = read_front_matter(story_path)
            except GateError:
                continue
            delivered_file = os.path.join(dst, ".delivered")
            if os.path.isfile(delivered_file):
                value = read_text(delivered_file).strip()
                if not is_delivered(front):
                    if value == "adopted":
                        write_story_fields(story_path, delivered=adopted_on(dst, delivered_file))
                    else:
                        write_story_fields(story_path, status="delivered", delivered=value)
                    front, _body = read_front_matter(story_path)
                    say(f"{shown(story_path)} carries the delivery ({value})")
                os.remove(delivered_file)
            digest = os.path.join(dst, STORY_DIGEST)
            if os.path.isfile(digest) and not is_delivered(front):
                write_mark(runs, name, STORY_DIGEST, story_digest(story_path))
        if not os.listdir(tasks):
            os.rmdir(tasks)
            say("tasks/ removed — it held nothing but the factory's run artefacts")
    attributes = ".gitattributes"
    if os.path.isfile(attributes):
        text = read_text(attributes)
        old_line, new_line = "tasks/**/.verify/journal.tsv merge=union", f"{runs}/**/.verify/journal.tsv merge=union"
        if old_line in text and runs != tasks:
            with open(attributes, "w", encoding="utf-8") as handle:
                handle.write(text.replace(old_line, new_line))
            say(f"{attributes}: the journals' merge rule follows the run folder")
    if not moved:
        print("migrate: nothing to move — the layout is current")
    return 0


CONTRACT_HEAD = ("What the gate checks in this stage's file — the exact shape, from the gate's own code. A stage that "
                 "wants certainty reads this, not the gate.")


def contract_text(stage, runs):
    """The stage's contract, with the hand-over's measure appended: what the file has to say fits in a base plus a
    share per criterion (the gate notes a larger file, never refuses it)."""
    text = contract_body(stage, runs)
    if text is None:
        return None
    files = {"plan": ("plan.md",), "test": ("tests.md",), "build": ("build.md",), "tidy": ("tidy.md",),
             "judge": ("judge.md",), "document": ("document.md",)}.get(stage, ())
    for name in files:
        base, per = HANDOVER_BUDGET[name]
        text += (f"\n- size: what {name} has to say fits in {base / 1000:.1f} kB"
                 + (f" plus {per} bytes per criterion" if per else "")
                 + " — keys and levels, not the story's text; one citation per row; nothing a reader has elsewhere. "
                   "Larger is a `gate:note size`, never a refusal; a reason is one line")
    return text


def contract_body(stage, runs):
    """The shape the gate holds a stage's file to, in a page: the table columns, the selector form, the
    path rule, the section names — taken from the constants the checks read, so the two cannot drift apart
    without this text changing with them."""
    folder = f"{runs}/<story>"
    if stage == "plan":
        return f"""{CONTRACT_HEAD}

plan — {folder}/plan.md (gate before the stage: story, epic, context map, decisions, rounds; the test gate reads the plan)
- `## Acceptance criteria`: one line per criterion, the story's key verbatim and its level — not the story's text:
  `- <key>  →  level: e2e | integration | browser-only (<why>)`
  `factory-cli.py --plan-skeleton <story>` writes the file's headings and these lines with the keys: give each its level.
  The test gate reads `level: browser-only` here (`levels`); a key is `[a-z0-9][a-z0-9-]*`
- `## Changed tests` (only when the story contradicts an existing test): `| <path from the project root> | <backing line or decision id> |`
- `## Files`: `- <path from the project root> — <changes|read>: <why>` (the path in backticks) — the next stages open these first
- `## Glossary proposals`: `- <term>: <definition>` — the document gate checks each term landed in a glossary or is named open
- `## needs-human` only to stop: `decision: <story>-<nn>`, with the record `<story>.decisions/<nn>.md` beside the story
  (`id:`, `story:`, `stage: plan`, `asked:`; `## Question`, `## Options`, `## Recommendation`)
- A citation is a path from the project root, `src/main/java/…/Thing.java:12`; a bare `Thing.java:12` resolves to nothing.
  A catalog node is cited by its path inside the catalog (`recipe/add-an-aggregate.md`), as the knowledge skill cites it —
  never by a path into a skill folder"""
    if stage == "test":
        return f"""{CONTRACT_HEAD}

test — {folder}/tests.md (gate after the stage: tests-mapped, tests-exist, compiles, tests-red, levels, test-titles, files-listed)
- the table, right after the marker `<!-- gate:tests -->`, one row per criterion (a criterion may have several rows):
  `| criterion | test |` then `| <key> | <selector> |`
  row pattern: {MAPPING_ROW.pattern!r}
- selector: `<fully.qualified.Class>#<method>` — pattern {SELECTOR.pattern!r}; the class resolves to a file named after it
  (`WidgetTest.java`), or to a module path (`tests.test_widgets#test_shows` → `tests/test_widgets.py`)
- levels: a test the profile's `e2eTest:` command runs belongs to the story's `(happy path)` scenario or to a key the
  plan gave `level: browser-only`; every other scenario's test lives in a `test.<name>:` source set
- titles: an end-user test's display name is the scenario's `Title:` line verbatim, else its key in words
  (`shows-empty-state` → "Shows empty state"); never the key itself in a name, display name or comment
- one process per test command: every selector a command covers runs in one invocation and is read from the report by name
- red: every selector in the table fails before any production code — the gate writes `{folder}/.tests-red`
  (`<selector>\t<sha256 of the test file>`); the build gate refuses a test changed after it was seen red (`red-proof`)
- a round the judge sent back (`back: test`): a test you strengthen is already green and cannot be seen red — write its
  break, `{folder}/breaks/<fully.qualified.Class>--<method>.patch`, a `git apply` patch against the production code that
  turns it red; the gate applies it on a scratch copy (`break-proof`) and records the test's new version
- `## Files`: every test file this stage wrote or changed, one per line, as a path from the project root —
  `files-listed` compares the list with the pipeline's changed-files record. `factory-cli.py --files-skeleton
  <story> test` writes the list from the tree (the file's skeleton, or the missing paths): run it, add the rest
- `## Notes`: `- unit tests: <Class>#<method> for invariant <rule>`; `- uncovered: <key> — <why>` only when unavoidable —
  not what a test fails on: the red run records that
- stubs: a type with nothing a criterion observes (a record and its fields, an enum, an interface, an exception type) is
  written whole here; a method whose outcome a criterion asserts throws — whatever a criterion observes, throws"""
    if stage in ("build", "tidy"):
        table, name = ("## Changed", "build") if stage == "build" else ("## Moves", "tidy")
        return f"""{CONTRACT_HEAD}

{name} — {folder}/{STAGE_FILES[stage]} (gate after the stage: tests-green, red-proof, files-listed, existing tests, architecture, format)
- `{table}`: `| File | Why |` — the first cell is a path from the project root, in backticks or bare; the other cells
  are prose. `files-listed` refuses a file the pipeline recorded as changed that no row names; a listed file that did
  not change is a note. A stage that changed no file needs no such section (tidy) — say so and why.
  `factory-cli.py --files-skeleton <story> {stage}` writes the rows' first column from the tree (the file's
  skeleton, or the missing rows): run it when the changes are done, fill in the rest
- a test file put back to the version the test stage saw red is a restoration, not a change to list
- tests: every selector of the `gate:tests` table green, and its file's digest as `.tests-red` holds it (`red-proof`)
- {'`## Deviations from the plan`: `- <element>: <what differed and why>`, or nothing when the plan held. No `## Criteria` (the judge re-checks each one) and no `## Checks`: the gate\'s report is the evidence, and a stage edits no hand-over after the gate ran — the gate is the stage\'s test run' if stage == 'build' else '`## Left alone`: what you saw and did not change, and why. No `## Checks`: the gate\'s report is the evidence, and a stage edits no hand-over after the gate ran — the gate is the stage\'s test run'}
- `## needs-human` only to stop, with `decision: <story>-<nn>` and the record beside the story (`stage: {name}`)
- {'a test that cannot pass for a reason in its own code — a helper, a locator, a fixture — while what it asserts stays as it is: write `back: test` on a line of its own and say what is wrong; the round goes to the test stage, which repairs it and proves it with a break. A change to what a test asserts is still a question (`## needs-human`)' if stage == 'build' else 'no test change: a defect in a test goes back through the build stage'}
- no criterion key in code, a comment or a test name; no `TODO` for the criterion delivered"""
    if stage == "judge":
        return f"""{CONTRACT_HEAD}

judge — {folder}/judge.md (the runner reads the verdict; the document gate reads `story-pass`)
- `## Verdict`: `verdict: pass | changes-requested | story-conflict` — one line, exactly one of the three
  (pass: deliverable; changes-requested: back one round; story-conflict: a human, never build)
- `back: test` under the verdict when a confirmed defect is in a test (it asserts less than its criterion): the round
  goes to the test stage, then build; without it the round goes to build, which may not change a test
- `## Perspectives covered`: `- <perspective>: <skill or agent that ran it, or "in-session"> | not covered — <why>`
- `## Confirmed defects`: `| Perspective | File:line | Severity | Defect | Fix |` — file as a path from the project root
  with its line; severity blocker | major | minor; only blocker and major prevent `pass`
- `## Considered and dropped`, `## Criteria re-checked`: `- <key>: met | met only nominally — <what the test does not assert>`
- `## Previous round` in a repeat round: every defect the previous verdict confirmed — fixed (file:line) | withdrawn (why) | still open
- a `story-conflict` names a decision record: `## needs-human` with `decision: <story>-<nn>`, the record's `stage:` is the one
  that applies the answer (plan or test)"""
    if stage == "document":
        return f"""{CONTRACT_HEAD}

document — {folder}/document.md (gate after the stage: story-pass, documented, glossary, architecture)
- `## Glossary`: `| Term | Context | Added or changed | Definition source |` — the last cell names where the definition
  came from; a row without it is an unsourced claim
- `## Documents updated`: `| File | What changed | Verified by |` — the first cell is a path from the project root that
  exists; `Verified by` names the file read or the command run. Nothing updated: one row `| — | none | <what you read> |`
  (`{'`, `'.join(sorted(n for n in NOTHING if n))}` read as no file). `document.md` itself is never listed
- `## Not documented`: `- <thing>: <why, and what it waits for>` — one line each
- every backticked path anywhere in the file resolves from the project root: `src/main/java/com/example/Thing.java:12`,
  `{folder}/build.md:20`; a bare `Thing.java:12` or a package-relative `example/Thing.java` is refused (`documented`)
- `## Paths`, when the pipeline wrote the file's skeleton (`factory-cli.py --document-skeleton <story>`): the story's
  changed files and the run's files in exactly that form — cite from there, do not retype
- every term the plan proposed under `## Glossary proposals` is in a glossary now, or named as still open under
  `## Not documented` (`glossary`). The skeleton pre-fills a `## Glossary` row per proposal — write the entry from it
{GLOSSARY_RULE}
- `## needs-human` only to stop (`decision: <story>-<nn>`, record `stage: document`)"""
    if stage == "glossary":
        return f"""{CONTRACT_HEAD}

glossary — how the document gate matches a proposed term (`glossary`), and the entry the glossary skill writes
{GLOSSARY_RULE}
- an entry: `### <Term>` — the heading carries the term as the plan proposed it, the domain word with the code word in
  parentheses where they differ (`### Titel (TaskTitle)`) — then `**Definition:**` and `**Type:**` (the glossary skill's
  format; `Type` is one of Aggregate Root, Entity, Value Object, Domain Event, Integration Event, Domain Service,
  Specification, Concept); `Identity`, `Synonyms (avoid)`, `Related terms`, `Operations` where they apply"""
    return None


#: How `check_proposals_landed` finds a proposed term, said once for `--contract document` and `--contract glossary`.
GLOSSARY_RULE = ("- a term is found in a glossary by any of its words: the term as written, the word before a parenthesis or "
                 "the word inside it (`Titel (title)` is found by `titel` or by `title`), case aside; the whole glossary "
                 "file counts, a heading is the place to put it. A term not landed is named open under `## Not documented`, "
                 "nowhere else — a pre-filled `## Glossary` row does not account for it")


#: The section each builder hand-over lists its files in, and the row shape the gate's `listed_files` reads.
FILES_SECTIONS = {
    "test": ("## Files", None, "- `{path}`"),
    "build": ("## Changed", "| File | Why |\n|---|---|", "| `{path}` | |"),
    "tidy": ("## Moves", "| File | Move | Why it reads better |\n|---|---|---|", "| `{path}` | | |"),
}
FILES_SKELETONS = {
    "test": "# Tests — {story}\n\n<!-- gate:tests -->\n| criterion | test |\n| --- | --- |\n\n## Files\n{rows}\n\n## Notes\n",
    "build": "# Build — {story}\n\n## Changed\n| File | Why |\n|---|---|\n{rows}\n\n## Deviations from the plan\n",
    "tidy": "# Tidy — {story}\n\n## Moves\n| File | Move | Why it reads better |\n|---|---|---|\n{rows}\n\n"
            "## Left alone\n",
}


def changed_for_skeleton(cwd, runs, story_id, stage):
    """The files the stage has to list, from the same sources `files-listed` reads and no other: the stage's
    changed-files record where the stage has ended; a shared builder's record, or its open window's tree against
    the story's base, minus what the story's other hand-overs list (the gate checks their union).
    `None` when nothing was observed — the list is then the stage's, as the gate's skip says."""
    folder = os.path.join(runs, story_id, ".verify")
    record = os.path.join(folder, f"changed-{stage}.txt")
    if os.path.isfile(record) and not _gate.snapshot_reason(record):
        return [line.split("\t", 1)[1] for line in read_text(record).splitlines() if "\t" in line]
    # the gate checks the union of the three hand-overs against the builder's record: a file another
    # hand-over lists is not this stage's to list (inside the open window only the earlier ones exist)
    listed = set()
    for name in ("test", "build", "tidy"):
        if name != stage:
            listed |= _gate.listed_files(os.path.join(runs, story_id, STAGE_FILES[name])) or set()
    not_listed = lambda path: path not in listed and not any(path.endswith("/" + n) for n in listed)
    builder = os.path.join(folder, "changed-builder.txt")
    if os.path.isfile(builder) and not _gate.snapshot_reason(builder):
        return [path for path in (line.split("\t", 1)[1] for line in read_text(builder).splitlines() if "\t" in line)
                if not_listed(path)]
    base_file = os.path.join(folder, "base-tree")
    if os.path.isfile(base_file):
        base = read_text(base_file).strip()
        now = _gate.git_tree(cwd) if base and base != "none" else None
        rows = _gate.tree_changes(cwd, base, now, runs) if now else None
        if rows is not None:
            return [path for _kind, path in rows if not_listed(path)]
    return None


def files_skeleton(runs, story_id, stage, cwd="."):
    """The stage's hand-over with its file list written by the pipeline: created with the stage's headings
    when the file is missing, or the missing paths added to its list when the stage wrote the file first.
    The stage fills in the why; it never types the list — the one refusal that cost the test stage a
    gate run in the bench. Idempotent: a path already listed is not added twice."""
    if stage not in FILES_SECTIONS:
        print(f"factory: --files-skeleton takes test, build or tidy, not {stage!r}", file=sys.stderr)
        return 2
    changed = changed_for_skeleton(cwd, runs, story_id, stage)
    if changed is None:
        print(f"factory: nothing observed — no changed-files record and no base tree for {story_id}; the {stage} "
              f"stage lists its files itself", file=sys.stderr)
        return 1
    heading, header, row = FILES_SECTIONS[stage]
    folder = os.path.join(runs, story_id)
    target = os.path.join(folder, STAGE_FILES[stage])
    os.makedirs(folder, exist_ok=True)
    if not os.path.isfile(target):
        rows = "\n".join(row.format(path=path) for path in changed)
        with open(target, "w", encoding="utf-8") as handle:
            handle.write(FILES_SKELETONS[stage].format(story=story_id, rows=rows))
        print(f"factory: {runs}/{story_id}/{STAGE_FILES[stage]} — the skeleton with {len(changed)} path(s) under `{heading}`")
        return 0
    already = _gate.listed_files(target) or set()
    missing = [path for path in changed if path not in already and not any(path.endswith("/" + n) for n in already)]
    if not missing:
        print(f"factory: {runs}/{story_id}/{STAGE_FILES[stage]} lists every changed file already — nothing added")
        return 0
    lines = read_text(target).splitlines()
    start = next((i for i, line in enumerate(lines) if line.strip().lower() == heading.lower()), None)
    addition = [row.format(path=path) for path in missing]
    if start is None:
        lines += ["", heading] + ([header] if header else []) + addition
    else:
        end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
        body = lines[start + 1:end]
        while body and not body[-1].strip():
            body.pop()
        if header and not any(line.lstrip().startswith("|") for line in body):
            body += header.split("\n")
        lines = lines[:start + 1] + body + addition + [""] + lines[end:]
    with open(target, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines).rstrip("\n") + "\n")
    print(f"factory: {runs}/{story_id}/{STAGE_FILES[stage]} — {len(missing)} path(s) added under `{heading}`")
    return 0


PLAN_SKELETON = ("# Plan — {story}\n\n## Context\n\n## Changes\n| Element | Kind | Location | New or changed | Evidence |\n"
                 "| --- | --- | --- | --- | --- |\n\n## Acceptance criteria\n{rows}\n\n## Files\n\n## Glossary proposals\n\n"
                 "## Open assumptions\n")


def plan_skeleton(runs, story_id, cwd="."):
    """`plan.md` before the plan stage runs: the file's headings and, under `## Acceptance criteria`, one line per
    criterion of the story with its key — the stage gives each its level and never retypes the story's text.
    Idempotent: an existing file (a refused round's, a stage's own) is left as it is."""
    folder = os.path.join(runs, story_id)
    target = os.path.join(folder, "plan.md")
    if os.path.isfile(target):
        print(f"factory: {runs}/{story_id}/plan.md exists — left as it is")
        return 0
    try:
        story_path = find_story(place("epics"), story_id)
        criteria = criteria_of(story_path, read_front_matter(story_path)[1])
    except GateError as error:
        print(f"factory: {error}", file=sys.stderr)
        return 1
    rows = "\n".join(f"- {key}  →  level: " for key, _text in criteria)
    os.makedirs(folder, exist_ok=True)
    with open(target, "w", encoding="utf-8") as handle:
        handle.write(PLAN_SKELETON.format(story=story_id, rows=rows))
    print(f"factory: {runs}/{story_id}/plan.md — the skeleton with {len(criteria)} criterion key(s) under `## Acceptance criteria`")
    return 0


def document_skeleton(runs, story_id, cwd="."):
    """`document.md` before the document stage runs: the file's headings, and under `## Paths` every file the
    story changed and every run file, as they resolve from the project root. A path the model never types
    cannot be package-relative — the one refusal that cost the document stage its rounds. Idempotent: an
    existing file (a refused round's, a stage's own) is left as it is."""
    folder = os.path.join(runs, story_id)
    target = os.path.join(folder, "document.md")
    if os.path.isfile(target):
        return 0
    paths = []
    record = os.path.join(folder, ".verify", "changed.txt")
    if os.path.isfile(record):
        for line in read_text(record).splitlines():
            parts = line.split("\t", 1)
            if len(parts) == 2 and parts[0] in ("added", "modified") and os.path.isfile(os.path.join(cwd, parts[1])):
                paths.append(parts[1])
    for name in STAGE_ORDER:
        run_file = os.path.join(folder, STAGE_FILES[name])
        if os.path.isfile(run_file):
            paths.append(f"{runs}/{story_id}/{STAGE_FILES[name]}")
    # the plan's proposals as the glossary table's rows: the term as the plan wrote it — the word the gate
    # looks for — the story's context, and the plan line as the definition's source; the stage writes the
    # glossary entry from the row and never retypes the term (the refusal that cost the bench a second run)
    glossary_rows = ""
    plan_file = os.path.join(folder, "plan.md")
    if os.path.isfile(plan_file):
        context = ""
        try:
            story_path = find_story(place("epics"), story_id)
            context = str(read_front_matter(story_path)[0].get("context", "")).strip()
        except GateError:
            pass
        for term in _gate.plan_proposals(read_text(plan_file)):
            glossary_rows += f"| {term} | {context} | added | `{runs}/{story_id}/plan.md` `## Glossary proposals` |\n"
    os.makedirs(folder, exist_ok=True)
    with open(target, "w", encoding="utf-8") as handle:
        handle.write(f"# Document — {story_id}\n\n## Glossary\n| Term | Context | Added or changed | Definition source |\n"
                     f"|---|---|---|---|\n{glossary_rows}\n## Documents updated\n| File | What changed | Verified by |\n|---|---|---|\n\n"
                     "## Not documented\n\n## Paths\n"
                     "The files this story changed and the run's files, as they resolve from the project root — cite them in "
                     "exactly this form (with `:<line>` where a line matters); the pipeline wrote this list, leave it in place.\n")
        for path in paths:
            handle.write(f"- `{path}`\n")
    terms = glossary_rows.count("\n")
    print(f"factory: {runs}/{story_id}/document.md — the skeleton with {len(paths)} path(s) under `## Paths`"
          + (f" and {terms} proposed term(s) under `## Glossary`" if terms else ""))
    return 0


def main(argv):
    parser = argparse.ArgumentParser(add_help=True, description="factory cli")
    parser.add_argument("--version", action="version", version=f"factory-cli {VERSION} (file contract {CONTRACT})")
    parser.add_argument("--story")
    parser.add_argument("--list-decisions", action="store_true",
                        help="print the decision inbox (all stories, or --story's) and exit")
    parser.add_argument("--claim", metavar="OWNER", help="take the checkout for one worker (exit 3: held by another)")
    parser.add_argument("--release", nargs="?", const="", metavar="OWNER",
                        help="give the checkout back (default: this session's claim)")
    parser.add_argument("--listening", action="store_true",
                        help="record that this session looked at the backlog (a listening loop's sign of life)")
    parser.add_argument("--status", action="store_true",
                        help="print what runs, what waits for a human, every story's state and the cost")
    parser.add_argument("--brief", action="store_true", help="with --status: two lines, for a session's start")
    parser.add_argument("--format", choices=("text", "md", "json"), default="text",
                        help="with --status: aligned text for a terminal, Markdown for a session, JSON for tools")
    parser.add_argument("--color", choices=("auto", "always", "never"), default="auto",
                        help="with --status: colour on a terminal (auto), always (a screenshot) or never")
    parser.add_argument("--part", choices=("all", "backlog"), default="all",
                        help="with --status: the whole view, or only the backlog, its tokens and what comes next")
    parser.add_argument("--live", action="store_true",
                        help="with --status: add what depends on the clock — how long ago, the activity, the worker")
    parser.add_argument("--session-start", action="store_true",
                        help="with --status --brief: add what a session should do with them (the SessionStart hook)")
    parser.add_argument("--help-view", action="store_true",
                        help="print the factory explained: the flow and where the project stands, the commands, "
                             "the marks, the files (with --format, --color)")
    parser.add_argument("--usage", action="store_true",
                        help="print the tokens each story and stage used, from the runner's journals")
    parser.add_argument("--total", action="store_true", help="with --usage: print only the token total")
    parser.add_argument("--usage-from", nargs=2, metavar=("FORMAT", "FILE"),
                        help="read one invocation's usage from a tool's raw output (claude-json, codex-jsonl, opencode-json)")
    parser.add_argument("--usage-model", help="with --usage-from: the model, where the output does not name it")
    parser.add_argument("--window-start", metavar="WORK", help="with --story: start measuring work on the story "
                                                              "outside a stage — backlog or decisions")
    parser.add_argument("--window-end", metavar="WORK", help="with --story: end that measuring window")
    parser.add_argument("--stage-start", metavar="STAGE", help="mark a stage's start inside a session (with --story)")
    parser.add_argument("--stage-end", metavar="STAGE",
                        help="mark its end and record what it used, read from the session's own log")
    parser.add_argument("--session-log", help="with --stage-end: the session log to read, where it is not found")
    parser.add_argument("--reopen", metavar="STORY",
                        help="take a delivered story back for a human's correction (an answered acceptance "
                             "record the story cites), and exit")
    parser.add_argument("--kind", action="store_true",
                        help="with --story: print `story`, `journey` or `adopt` — the stages it runs — and exit")
    parser.add_argument("--resolve", metavar="ARGUMENT",
                        help="what /factory-run <argument> means: `story <id>`, `wish`, `backlog`, or `unknown <word>` "
                             "(exit 2), and exit")
    parser.add_argument("--start", action="store_true",
                        help="with --story: the story's state and the stage a run without --from begins at, and exit")
    parser.add_argument("--schedule", action="store_true",
                        help="print every story's state and the next one to run, and exit")
    parser.add_argument("--get", metavar="KEY", help="the profile's value for KEY, or nothing")
    parser.add_argument("--command-heads", action="store_true",
                        help="the first word of every command the profile declares, one per line")
    parser.add_argument("--carriers", action="store_true",
                        help="the skills the profile names as carrier, reviewer or knowledge, one per line")
    parser.add_argument("--carrier-lines", action="store_true", help="those keys with their values, `key value` per line")
    parser.add_argument("--model", nargs=2, metavar=("TOOL", "STAGE"),
                        help="the profile's model for that tool and stage (model.<tool>.<stage>, else model.<tool>)")
    parser.add_argument("--verdict", metavar="STORY", help="the judge's verdict of that story, or nothing")
    parser.add_argument("--back-to", metavar="STORY",
                        help="where a changes-requested verdict sends the story: test (the judge's `back: test`) or build; "
                             "with --stage build: `test` when build.md sends the story back, else nothing")
    parser.add_argument("--stage", choices=("build",), help="with --back-to: read that stage's file instead of judge.md")
    parser.add_argument("--needs-human", metavar="FILE",
                        help="the decision ids a stage file's needs-human section names; exit 1 when it asks nobody")
    parser.add_argument("--open-decisions", metavar="STORY",
                        help="the decision records that name the story and carry no answer, one path per line")
    parser.add_argument("--drift", action="store_true",
                        help="name a difference between the profile's architecture command and the conventions file's "
                             "(exit 1), or nothing (exit 0); with --brief the same one line")
    parser.add_argument("--place", metavar="KEY",
                        help="where the factory reads KEY (product, tech, domain, epics, runs), from the profile or its default")
    parser.add_argument("--delivered", metavar="STORY",
                        help="exit 0 when the story carries the gate's delivered mark, 1 when it does not")
    parser.add_argument("--contract", metavar="STAGE",
                        help="the exact shape the gate holds that stage's file to (plan, test, build, tidy, judge, "
                             "document), from the gate's own constants, and exit")
    parser.add_argument("--files-skeleton", nargs=2, metavar=("STORY", "STAGE"),
                        help="write the test, build or tidy hand-over's file list from what the tree changed "
                             "(the file's skeleton when it is missing, the missing paths when the stage wrote it)")
    parser.add_argument("--plan-skeleton", metavar="STORY",
                        help="write plan.md's headings and, under `## Acceptance criteria`, one line per criterion "
                             "key of the story (a stage gives each its level; an existing file is left as it is)")
    parser.add_argument("--document-skeleton", metavar="STORY",
                        help="write the document stage's file skeleton with every changed path and run file under "
                             "`## Paths`, as they resolve from the project root; an existing file is kept; and exit")
    parser.add_argument("--migrate-layout", action="store_true",
                        help="move an older layout to one owner per place — what `factory.sh update` runs once — and exit")
    parser.add_argument("--epics", help="where the epics and stories are (default: the profile's `epics:`, else project/epics)")
    parser.add_argument("--runs", help="the run artefacts (default: the profile's `runs:`, else .dca-factory/runs)")
    parser.add_argument("--profile", help=f"the stack profile (default: FACTORY_PROFILE, else {PROFILE_FILE} at the root)")
    parser.add_argument("--root", default=".", help="the project's root directory")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    cwd = os.path.abspath(args.root)
    os.chdir(cwd)
    profile_path = resolve_profile(args.profile or os.environ.get("FACTORY_PROFILE") or None, cwd)
    set_places(read_profile(profile_path), epics=args.epics, runs=args.runs)
    args.epics, args.runs = place("epics"), place("runs")
    # the runner's questions first: they read one file and print one answer
    if args.contract:
        text = contract_text(args.contract, args.runs)
        if text is None:
            print(f"factory-cli: --contract takes one of {', '.join(STAGE_ORDER)} or glossary, not {args.contract!r}", file=sys.stderr)
            return 2
        print(text)
        return 0
    if args.files_skeleton:
        return files_skeleton(args.runs, args.files_skeleton[0], args.files_skeleton[1], cwd)
    if args.plan_skeleton:
        return plan_skeleton(args.runs, args.plan_skeleton, cwd)
    if args.document_skeleton:
        return document_skeleton(args.runs, args.document_skeleton, cwd)
    if args.migrate_layout:
        return migrate_layout(cwd)
    if args.drift:
        drift = conventions_drift(cwd, read_profile(profile_path))
        if drift:
            print(f"factory: {drift}")
        return 1 if drift else 0
    if args.place:
        if args.place not in DEFAULTS:
            parser.error(f"--place takes one of {', '.join(DEFAULTS)}")
        print(place(args.place))
        return 0
    if args.delivered:
        try:
            return 0 if is_delivered(read_front_matter(find_story(args.epics, args.delivered))[0]) else 1
        except GateError as error:
            print(f"factory: {error}", file=sys.stderr)
            return 2
    if args.get is not None:
        print(read_profile(profile_path).get(args.get, ""))
        return 0
    if args.command_heads:
        print("\n".join(command_heads(read_profile(profile_path))))
        return 0
    if args.carriers:
        print("\n".join(carriers(read_profile(profile_path))))
        return 0
    if args.carrier_lines:
        print("\n".join(f"{key} {value}" for key, value in carrier_lines(read_profile(profile_path))))
        return 0
    if args.model:
        print(model_for(read_profile(profile_path), *args.model))
        return 0
    if args.verdict:
        print(verdict_of_story(args.runs, args.verdict))
        return 0
    if args.back_to:
        if args.stage == "build":
            # the build stage found a defect in a test's own code, not in what it asserts: only `test` sends it back
            path = os.path.join(args.runs, args.back_to, STAGE_FILES["build"])
            print("test" if os.path.isfile(path) and back_in(read_text(path)) == "test" else "")
            return 0
        path = os.path.join(args.runs, args.back_to, "judge.md")
        print(back_in(read_text(path)) if os.path.isfile(path) else "build")
        return 0
    if args.needs_human:
        lines = needs_human_lines(args.needs_human, args.story)
        if lines is None:
            return 1
        print("\n".join(lines))
        return 0
    if args.open_decisions:
        print("\n".join(open_decision_files(cwd, args.open_decisions)))
        return 0
    if args.list_decisions:
        return list_decisions(cwd, args.story, args.format, args.color)
    if args.kind:
        if not args.story:
            parser.error("--kind needs --story")
        print(story_kind(read_front_matter(find_story(args.epics, args.story))[0]))
        return 0
    if args.resolve is not None:
        return resolve(args.epics, args.resolve)
    if args.schedule:
        return schedule(cwd, args.epics, args.runs)
    if args.start:
        if not args.story:
            parser.error("--start needs --story")
        return start(cwd, args.epics, args.runs, args.story)
    if args.reopen:
        return reopen(cwd, args.runs, args.epics, args.reopen)
    if args.listening or args.claim or args.release is not None:
        freeze_all(args.runs)
    if args.listening:
        return mark_listening(cwd)
    if args.claim:
        return claim(cwd, args.claim)
    if args.release is not None:
        return release(cwd, args.release or session_owner())
    if args.status and args.brief:
        try:
            return status_brief(cwd, args.epics, args.runs, args.session_start)
        except Exception as error:                      # a hook must never break a session's start
            print(f"factory: status unavailable ({error.__class__.__name__})")
            return 0
    if args.help_view:
        return factory_help(cwd, args.epics, args.runs, args.format, args.color)
    if args.status:
        return status(cwd, args.epics, args.runs, args.story, args.format, args.color, args.live, args.part)
    if args.window_start or args.window_end:
        if not args.story:
            parser.error("--window-start/--window-end need --story")
        return mark_window(cwd, args.runs, args.story, args.window_start or args.window_end,
                           "start" if args.window_start else "end", args.session_log)
    if args.stage_start or args.stage_end:
        if not args.story:
            parser.error("--stage-start/--stage-end need --story")
        return mark_stage(cwd, args.runs, args.story, args.stage_start or args.stage_end,
                          "start" if args.stage_start else "end", args.session_log)
    if args.usage_from:
        return usage_from(args.usage_from[0], args.usage_from[1], args.usage_model)
    if args.usage:
        return usage_report(args.runs, args.story, args.total, cwd, args.epics, args.format)
    parser.error("nothing asked — --status, --schedule, --usage, --list-decisions, … (a stage's gate is story-gate.py's)")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
