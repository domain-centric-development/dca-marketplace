"""What a story's journal says it used: the usage per window, its session logs, the tool's denials."""

from __future__ import annotations

import os
import typing
from .....sharedkernel.adapter.outgoing.profile.profile_files import evidence_dir
from .....sharedkernel.adapter.outgoing.markdown.front_matter import read_text
from ..tools.streams import session_reader, session_usage, session_usage_allowed
from ....application.status.texts import parse_time
from ....domain.model.usage import USAGE_FIELDS
from .journal_files import Event
from .stream_records import stream_lines


def journal_denials(events: typing.List[Event], process: str) -> typing.List[typing.Dict[str, str]]:
    """[{stage, tool, command}] — the calls the tool denied one process, from the `denied` lines in their order."""
    return [dict(stage="" if e["name"] == "-" else e["name"], tool=e["fields"].get("tool", ""),
                 command=e["fields"].get("call", ""))
            for e in stream_lines(events, "denied") if e["fields"].get("process") == process]


def window_logs(fields: typing.Dict[str, str]) -> typing.List[str]:
    """The session logs a recorded window points at that are on this machine — [] where session usage is switched off."""
    if not session_usage_allowed(os.getcwd()):
        return []
    paths = [p for p in fields.get("log", "").split(",") if p]
    tool, _, session_id = fields.get("session", "").partition(":")
    reader = session_reader(f"{tool}-session") if session_id else None
    if reader:
        paths = reader.session_logs(session_id)
    return [p for p in paths if os.path.isfile(p)]


def resolve_window(fields: typing.Dict[str, str]) -> typing.Optional[typing.Dict[str, typing.Any]]:
    """A recorded session window, read now: {usage fields} or None."""
    paths = window_logs(fields)
    start, _, end = fields.get("window", "").partition("/")
    return session_usage(fields.get("tool", ""), paths, parse_time(start), parse_time(end)) if paths else None


def journal_usage(runs: str, story_id: str, resolve: bool = True) -> typing.Dict[str, typing.Dict[str, typing.Any]]:
    """{stage: {invocations, measured, input, cache_read, cache_write, output, cost}} from the journal.

    `resolve=False` counts only what the journal carries itself, without opening a session log."""
    journal = os.path.join(evidence_dir(runs, story_id), "journal.tsv")
    stages: typing.Dict[str, typing.Dict[str, typing.Any]] = {}
    if not os.path.isfile(journal):
        return stages
    # A journal merged with `merge=union` can hold one session window twice — read on one branch,
    # still pending on the other. A window is one stage run, so it is counted once, the read one first.
    counted_windows = set()
    lines = sorted(read_text(journal).splitlines(), key=lambda l: ("log=" in l or "session=" in l, l))
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
