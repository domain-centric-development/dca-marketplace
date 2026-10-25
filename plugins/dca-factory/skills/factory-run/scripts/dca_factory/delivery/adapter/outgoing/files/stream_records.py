"""A tool's stream frozen into the story's journal: the parts of a process, kept as lines once it ended."""

from __future__ import annotations

import glob
import os
import typing
from .journal_files import append_event, read_events, Event
from ..tools.streams import stream_denials, stream_parts
from ....domain.model.usage import USAGE_FIELDS


# --- what a process's stream says, written once (WP-150 A) ----------------------------------------------------
# A tool process's raw stream (`<process>.<HHMMSS>.out` beside the journal) holds two facts no other file has: the
# parts of a shared window — each stage it carried, its time and tokens — and the calls the tool denied. Once the
# process has ended both are journal lines, so the views read the journal and the stream may be pruned:
#   part <stage>     process=<window> stream=<file> seconds= input= cache_read= cache_write= output= [cost=]
#   denied <stage>   process=<process> stream=<file> tool=<tool> call=<the call cut to a line>   (`-` outside a part)
#   stream <file>    process=<process> parts=<n> denied=<n> version=<n>  — the stream is frozen
# A stream is frozen again when the reading of it improved (`STREAM_VERSION`): the journal stays append-only, and a
# reader takes for each stream the part and denied lines its last `stream` line closes. Version 2 (0.90.1): a part
# also begins at a stage's skeleton or gate, not only where its skill is loaded — a builder resumed after a question
# loads none, and before 0.90.1 its build and tidy were not seen.
STREAM_FROZEN = "stream"


STREAM_VERSION = 2


def frozen_streams(events: typing.List[Event]) -> typing.Dict[str, int]:
    """{stream file: the version it was frozen with} — 1 for a `stream` line written before versions."""
    versions: typing.Dict[str, int] = {}
    for e in events:
        if e["kind"] == STREAM_FROZEN:
            version = int(e["fields"].get("version") or 1) if str(e["fields"].get("version") or "1").isdigit() else 1
            versions[e["name"]] = max(versions.get(e["name"], 0), version)
    return versions


def stream_lines(events: typing.List[Event], kind: str) -> typing.List[Event]:
    """The `part` or `denied` lines the last freeze of each stream wrote — the lines between a stream's previous
    `stream` line and its last one."""
    pending: typing.Dict[str, typing.List[Event]] = {}
    kept: typing.Dict[str, typing.List[Event]] = {}
    for e in events:
        if e["kind"] == kind:
            pending.setdefault(e["fields"].get("stream", ""), []).append(e)
        elif e["kind"] == STREAM_FROZEN:
            kept[e["name"]] = pending.pop(e["name"], [])
    return [e for lines in kept.values() for e in lines]


def stream_process(name: str) -> str:
    """The process a stream belongs to: `builder.101500.out` and `builder.101500-limit1.out` are `builder`'s."""
    return os.path.basename(name).split(".", 1)[0]


def freeze_stream(journal: str, path: str) -> bool:
    """Append the parts and the denied calls of one ended process's stream to the journal, once: a stream whose
    `stream` line is there is left alone. The cost a part gets is the process's split by the parts' weight — an
    estimate, as the view shows it; a process whose stream reports no cost gives its parts none."""
    name = os.path.basename(path)
    if frozen_streams(read_events(journal)).get(name, 0) >= STREAM_VERSION:
        return False
    process = stream_process(name)
    parts, cost = stream_parts(path)
    weight = sum(p["weight"] for p in parts)
    for part in parts:
        seconds = max((part["end"] - part["start"]).total_seconds(), 0) if part["start"] and part["end"] else 0
        share = [] if cost is None or not weight else [f"cost={cost * part['weight'] / weight:.6f}"]
        append_event(journal, "part", part["stage"], f"process={process}", f"stream={name}", f"seconds={seconds:g}",
                     *(f"{field}={part[field]}" for field in USAGE_FIELDS), *share)
    denials = stream_denials(path)
    for denial in denials:
        append_event(journal, "denied", denial["stage"] or "-", f"process={process}", f"stream={name}",
                     f"tool={denial['tool']}", f"call={denial['command']}")
    append_event(journal, STREAM_FROZEN, name, f"process={process}", f"parts={len(parts)}", f"denied={len(denials)}",
                 f"version={STREAM_VERSION}")
    return True


def process_running(events: typing.List[Event], process: str) -> bool:
    """Whether the journal says a process runs now: its last `stage-start` has no `stage-end` or `usage` after it. A
    reviewer's stream is `review-<name>`, its journal name `review:<name>`. File times are not read — a move or a copy
    sets them anew."""
    names = {process, process.replace("review-", "review:", 1)}
    started = max((e["seq"] for e in events if e["kind"] == "stage-start" and e["name"] in names), default=None)
    ended = max((e["seq"] for e in events if e["kind"] in ("stage-end", "usage") and e["name"] in names), default=None)
    return started is not None and (ended is None or ended < started)


def freeze_streams(journal: str) -> None:
    """`freeze_stream` for every stream beside the journal whose process is not running by the journal and that is not
    frozen with today's reading (`STREAM_VERSION`). The runner freezes its stream right after the usage line; this
    catches one a stopped runner left behind, every stream of a story from before the record, and every stream an
    older reading froze."""
    folder = os.path.dirname(journal)
    events = read_events(journal)
    frozen = frozen_streams(events)
    for path in sorted(glob.glob(os.path.join(folder, "*.out"))):
        name = os.path.basename(path)
        if frozen.get(name, 0) < STREAM_VERSION and not process_running(events, stream_process(name)):
            freeze_stream(journal, path)


def parts_incomplete(events: typing.List[Event], process: str) -> bool:
    """Whether a run of a process is missing from its parts for good: an older reading froze its stream with no part
    at all — a builder resumed after a question, which loads no stage's skill — and the stream is gone, so it cannot
    be read again. The view says so instead of showing the parts as whole. A run the older reading found parts in
    loaded its stages' skills, which that reading saw."""
    versions = frozen_streams(events)
    return any(e["kind"] == STREAM_FROZEN and e["fields"].get("process") == process and e["fields"].get("parts") == "0"
               and versions.get(e["name"], 1) < STREAM_VERSION for e in events)


def journal_parts(events: typing.List[Event], process: str) -> typing.List[typing.Dict[str, typing.Any]]:
    """The `part` lines of one shared process, summed per stage in the order the stages first ran:
    [{stage, runs, seconds, input, cache_read, cache_write, output, tokens, cost (None where a run had none), denied}]."""
    total: typing.Dict[str, typing.Dict[str, typing.Any]] = {}
    for event in stream_lines(events, "part"):
        if event["fields"].get("process") != process:
            continue
        f = event["fields"]
        entry = total.setdefault(event["name"], dict(stage=event["name"], runs=0, seconds=0.0, input=0, cache_read=0,
                                                     cache_write=0, output=0, cost=0.0, denied=0))
        entry["runs"] += 1
        entry["seconds"] += float(f.get("seconds") or 0)
        for field in USAGE_FIELDS:
            entry[field] += int(f.get(field) or 0)
        if entry["cost"] is not None and "cost" in f:
            entry["cost"] += float(f["cost"])
        else:
            entry["cost"] = None
    for event in stream_lines(events, "denied"):
        if event["fields"].get("process") == process and event["name"] in total:
            total[event["name"]]["denied"] += 1
    for entry in total.values():
        entry["tokens"] = sum(entry[f] for f in USAGE_FIELDS)
    return list(total.values())
