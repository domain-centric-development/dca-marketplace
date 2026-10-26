"""A window's marks in the story's journal — a stage's or a session's start and end — and the streams frozen into it."""

from __future__ import annotations


import contextlib
import glob
import os
import typing
from datetime import datetime, timezone
from .....sharedkernel.adapter.outgoing.markdown.front_matter import GateError
from .....sharedkernel.adapter.outgoing.profile.profile_files import evidence_dir, place, read_profile, resolve_profile
from .journal_files import append_event, journal_writer, read_events
from .....sharedkernel.adapter.outgoing.markdown.front_matter import read_text
from ..tools.streams import current_session, log_kind, session_usage_allowed, usage_fields, WINDOWS
from ....application.status.texts import parse_time
from ....domain.model.usage import USAGE_FIELDS
from .snapshots import record_base, record_changes, write_snapshot
from .usage_files import resolve_window, window_logs
from ..claims.checkout_claim import claim, session_owner
from .story_record import prune_raw
from .stream_records import freeze_streams
from ....application.profile.profile_rules import model_for


def mark_window(cwd: str, runs: str, story_id: str, name: str, edge: str,
                session_log: typing.Optional[str] = None) -> int:
    """`--window-start`/`--window-end`: the session's tokens and time spent on a story outside a stage."""
    if name not in WINDOWS:
        print(f"window: {name!r} is none of {', '.join(WINDOWS)}")
        return 2
    journal = os.path.join(evidence_dir(runs, story_id), "journal.tsv")
    os.makedirs(os.path.dirname(journal), exist_ok=True)
    now = datetime.now(timezone.utc)
    stamp = now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"
    kind, session_id = current_session()
    if session_log:
        kind = log_kind(session_log)
    freeze_all(runs)
    request = os.environ.get("FACTORY_REQUEST", "")
    with journal_writer(runs, story_id) as handle:
        if edge == "start":
            handle.write(f"{stamp}\twindow-start\t{name}\ttool={kind}" + (f"\trequest={request}" if request else "") + "\n")
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
        if request:
            # the request's process measures it, priced: the runner books its share here once the process ended
            print(f"window: {name} of {story_id} ended — its usage is request {request}'s")
        elif not session_usage_allowed(cwd) or not started or not source:
            handle.write(f"{stamp}\tusage\t{name}\ttool={kind}\tunknown\n")
            print(f"window: {name} of {story_id} ended — its usage is unknown")
        else:
            begun = started.strftime("%Y-%m-%dT%H:%M:%S.") + f"{started.microsecond // 1000:03d}Z"
            handle.write(f"{stamp}\tusage\t{name}\ttool={kind}\twindow={begun}/{stamp}\t{source}\n")
            print(f"window: {name} of {story_id} ended — its usage is read from the session log")
    return 0


def mark_stage(cwd: str, runs: str, story_id: str, stage: str, edge: str,
               session_log: typing.Optional[str] = None) -> int:
    """`--stage-start`/`--stage-end` for a stage run inside a session: the same journal the runner writes."""
    journal = os.path.join(evidence_dir(runs, story_id), "journal.tsv")
    os.makedirs(os.path.dirname(journal), exist_ok=True)
    now = datetime.now(timezone.utc)
    stamp = now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"
    kind, session_id = current_session()
    owner = session_owner()
    if owner and claim(cwd, owner) == 3:
        return 3                               # another worker holds the checkout: this stage does not start
    freeze_all(runs)                          # the earlier stages' logs have caught up by now
    if session_log:
        kind = log_kind(session_log)
    allowed = session_usage_allowed(cwd)
    with journal_writer(runs, story_id) as handle:
        if edge == "start":
            # The model the profile asks this tool to run the stage on. A session cannot switch its own
            # model; a subagent may run on it. Which model the window actually used is read from the
            # session log later, and the status shows a request that did not reach the stage.
            profile = read_profile(resolve_profile(None, cwd))
            tool = kind.split("-")[0]
            requested = model_for(profile, tool, stage)
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


def freeze_windows(journal: str) -> None:
    """Write the numbers of every session window that can be read now into the journal itself.

    The window points at a session log on this machine, which a clone does not have and the tool
    deletes after a while. Once read, the numbers are appended as a usage line of their own with the same window and
    no path — the line that pointed at the log stays, and the reader counts a window once, the read line first. The
    journal is only ever appended to, so nothing another writer appends meanwhile is lost.

    A settled window whose log is here but holds no model answer inside it — a decision written in a second, between
    two answers — is frozen with zero tokens: it was read and nothing was spent. Left pending, every status would read
    the whole log for it again, which for a long session's log costs seconds per window. Only a window whose log is not
    on this machine stays pending, for a machine that has it."""
    if not os.path.isfile(journal):
        return
    settled = datetime.now(timezone.utc).timestamp() - FREEZE_AFTER
    events = read_events(journal)
    frozen = {(e["name"], e["fields"].get("window")) for e in events if e["kind"] == "usage"
              and "window" in e["fields"] and "log" not in e["fields"] and "session" not in e["fields"]}
    for event in events:
        fields = event["fields"]
        if event["kind"] != "usage" or "window" not in fields or ("log" not in fields and "session" not in fields):
            continue
        if (event["name"], fields["window"]) in frozen:
            continue
        end = parse_time(fields.get("window", "").partition("/")[2])
        if end is None or end.timestamp() > settled:
            continue                            # the log may still lag behind this window
        read = resolve_window(fields)
        if read is None:
            if not window_logs(fields):
                continue                        # the log is not here: another machine may read it
            read = {"model": "", **{k: 0 for k in USAGE_FIELDS}}
        append_event(journal, "usage", event["name"], f"tool={fields.get('tool', '')}", *usage_fields(read).split("\t"),
                     f"window={fields['window']}", at=event["at"])
        frozen.add((event["name"], fields["window"]))


def freeze_all(runs: str) -> None:
    """`freeze_windows` over every story's journal. A story's last stages end its run, so no stage
    start of its own ever comes back to freeze them; the next command that writes anyway — a stage
    of another story, a claim, a release, a listening loop's look — does it for them. Never fails
    the command it rides on."""
    for journal in glob.glob(os.path.join(evidence_dir(runs, "*"), "journal.tsv")):
        with contextlib.suppress(OSError, GateError, ValueError):
            freeze_windows(journal)
        with contextlib.suppress(OSError, GateError, ValueError):
            freeze_streams(journal)
    with contextlib.suppress(OSError, GateError, ValueError):
        prune_raw(runs, place("epics"))


