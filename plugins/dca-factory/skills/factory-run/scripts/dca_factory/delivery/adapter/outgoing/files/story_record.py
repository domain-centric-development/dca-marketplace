"""A story's record: its journal and streams kept once the story is delivered, the raw material pruned after it."""

from __future__ import annotations


import glob
import os
import time
import typing
from .story_layout import delivered_on, is_delivered, story_files, story_folder, story_id_of
from .....sharedkernel.adapter.outgoing.profile.profile_files import evidence_dir, JOURNAL, read_profile, resolve_profile
from .journal_files import append_event, Event, journal_path, read_events
from .....sharedkernel.adapter.outgoing.markdown.front_matter import read_front_matter, read_text
from ....application.status.texts import parse_time
from .run_marks import verdict_in
from .signals import journal_signal, latest_signal, plan_left_open, record_judge_signal
from .stream_records import freeze_streams, frozen_streams, STREAM_VERSION


#: Every named rule's unit test at the test gate (WP-148 A): `<element>\t<rules>\t<selector>\t<verdict>` — `red`
#: seen red before the build (the rule is new), `killed` red under its break, `survived` green under it, `no-break`
#: green with no break that applies, `unchecked` no run gave a verdict. The bench computes the rate; the gate keeps
#: the facts.
INVARIANT_BREAKS = "invariant-breaks.tsv"


# --- the record complete (WP-150 D) -----------------------------------------------------------------------------
#: The version of what a journal holds as the story's record: a `record <version>` line says the facts that stood
#: in streams and hand-overs are journal lines now — written live from this version on, read once from the files for
#: a story from before. `unknown=` names the facts whose material was gone; the views say "not recorded" for them.
RECORD_VERSION = "1"


def streams_current(events: typing.List[Event], folder: str) -> bool:
    """Whether every stream beside the journal is frozen with today's reading — what must hold before one is deleted."""
    frozen = frozen_streams(events)
    return all(frozen.get(os.path.basename(p), 0) >= STREAM_VERSION for p in glob.glob(os.path.join(folder, "*.out")))


def recorded(events: typing.List[Event]) -> typing.Optional[typing.Dict[str, typing.Any]]:
    """The `record` line's fields, or None for a journal that is not the record yet."""
    return next((e["fields"] for e in events if e["kind"] == "record"), None)


def record_story(runs: str, story_id: str) -> typing.Optional[typing.Dict[str, str]]:
    """Make a story's journal its record, once: freeze every ended stream, write the signals no gate wrote from the
    hand-overs that are still there, then the `record` line. None while a stream's process still runs (the story
    is recorded on a later call), or when the journal is the record already; the `record` line's fields otherwise."""
    journal = journal_path(runs, story_id)
    if not (os.path.isfile(journal) or os.path.isdir(os.path.join(runs, story_id))):
        return None
    if recorded(read_events(journal)) is not None:
        freeze_streams(journal)                 # an improved reading freezes the streams that are still here again
        return None
    os.makedirs(os.path.dirname(journal), exist_ok=True)        # hand-overs from before the journal: it begins here
    freeze_streams(journal)
    events = read_events(journal)
    folder = evidence_dir(runs, story_id)
    if not streams_current(events, folder):
        return None
    frozen = frozen_streams(events)
    unknown: typing.List[str] = []
    if latest_signal(events, "plan") is None:
        plan = os.path.join(runs, story_id, "plan.md")
        if os.path.isfile(plan):
            journal_signal(runs, story_id, "plan", open=len(plan_left_open(read_text(plan))))
        elif any(e["kind"] == "gate" and e["name"] == "plan" and e["fields"].get("exit") == "0" for e in events):
            unknown.append("plan")
    if latest_signal(events, "rules") is None:
        tsv = os.path.join(folder, INVARIANT_BREAKS)
        rows = [l.split("\t") for l in read_text(tsv).splitlines()] if os.path.isfile(tsv) else []
        rows = [r for r in rows if len(r) == 4]
        if rows:
            journal_signal(runs, story_id, "rules", [("rule", r[2], dict(element=r[0], rules=r[1], verdict=r[3]))
                                                     for r in rows],
                           named=sum(len([n for n in r[1].split(",") if n]) for r in rows))
    if latest_signal(events, "judge") is None:
        judge = os.path.join(runs, story_id, "judge.md")
        if os.path.isfile(judge) and verdict_in(read_text(judge)) == "pass":
            record_judge_signal(runs, story_id, read_text(judge))
        elif any(e["kind"] == "stage-start" and e["name"] in ("judge", "verifier") for e in events):
            unknown.append("judge")
    if not frozen and any(e["kind"] == "usage" and "seconds" in e["fields"] for e in events):
        unknown.append("streams")             # the runner ran it, and no stream of it is left
    fields = [f"unknown={','.join(unknown)}"] if unknown else []
    append_event(journal, "record", RECORD_VERSION, *fields)
    return dict(unknown=",".join(unknown)) if unknown else {}


# --- what only a run needs goes (WP-150 C) -----------------------------------------------------------------------
KEEP_DAYS = 7


PRUNED = "pruned"


def keep_days(profile: typing.Mapping[str, typing.Any]) -> int:
    """`evidence.keepDays` from the profile — a whole number of days, 7 where it is missing or no number."""
    value = str(profile.get("evidence.keepDays") or "").strip()
    return int(value) if value.isdigit() else KEEP_DAYS


def raw_material(folder: str) -> typing.List[str]:
    """A story's raw streams, tree snapshots and the runner's suite record (`suites.tsv`, the signed runs a later gate
    on the same tree reuses) — read only while it runs and right after."""
    return sorted(glob.glob(os.path.join(folder, "*.out")) + glob.glob(os.path.join(folder, "tree-*.txt"))
                  + glob.glob(os.path.join(folder, "suites.tsv")))


def prune_raw(runs: str, epics: str, days: typing.Optional[int] = None,
              now: typing.Optional[float] = None) -> typing.List[typing.Tuple[str, int]]:
    """Delete the streams, snapshots and suite record of every story delivered more than `days` ago (the profile's
    `evidence.keepDays`) once its journal is its record — `record_story` first, so nothing goes unread — and say
    so in a `pruned` line. The journal, the gate reports, story.diff and the hand-overs stay. A story that is not
    delivered — running, waiting, reopened — is never touched. [(story, files removed)]."""
    if days is None:
        days = keep_days(read_profile(resolve_profile(None, os.getcwd())))
    limit = (now or time.time()) - days * 86400
    pruned: typing.List[typing.Tuple[str, int]] = []
    candidates = [j for j in sorted(glob.glob(os.path.join(evidence_dir(runs, "*"), JOURNAL)))
                  if raw_material(os.path.dirname(j))]
    if not candidates:
        return pruned
    stories: typing.Dict[str, str] = {}
    for path in story_files(epics):
        stories.setdefault(story_id_of(path), path)
        stories.setdefault(os.path.basename(story_folder(path)), path)
    for journal in candidates:
        folder = os.path.dirname(journal)
        raw = raw_material(folder)
        story_id = os.path.basename(folder)
        story_path = stories.get(story_id)
        if not story_path:
            continue
        front, _body = read_front_matter(story_path)
        when = parse_time(delivered_on(front)) if is_delivered(front) else None
        if when is None or when.timestamp() > limit:
            continue
        record_story(runs, story_id)
        events = read_events(journal)
        if recorded(events) is None or not streams_current(events, folder):
            continue                            # nothing is deleted that is not read with today's reading
        for name in raw:
            os.remove(name)
        append_event(journal, PRUNED, "-", f"files={len(raw)}", f"days={days}")
        pruned.append((story_id, len(raw)))
    return pruned


# --- the journal is committed (WP-150, the user's decision 2) ------------------------------------------------------
def journal_ignore_lines(evidence: str) -> typing.List[str]:
    """The .gitignore lines that keep the pipeline's protocol out of git and every story's journal in: git does not
    look into a folder it ignores, so the folders on the way are let in and their contents ignored again."""
    top = evidence.strip("/").split("/")[0]
    lines, path = [f"/{top}/*"], top
    for part in evidence.strip("/").split("/")[1:]:
        path += "/" + part
        lines += [f"!/{path}/", f"/{path}/*"]
    return lines + [f"!/{path}/*/", f"/{path}/*/*", f"!/{path}/*/journal.tsv"]


def ignore_journals_in(cwd: str, evidence: str) -> bool:
    """Rewrite the project's ignore of the pipeline's folder so the story journals are committed: the line that
    ignores the whole folder becomes the lines of `journal_ignore_lines`. A .gitignore that holds them already, or
    names the folder in no line of its own, is left as it is. True when the file changed."""
    path = os.path.join(cwd, ".gitignore")
    if not os.path.isfile(path):
        return False
    text = read_text(path)
    lines = text.splitlines()
    wanted = journal_ignore_lines(evidence)
    if wanted[-1] in lines:
        return False
    top = evidence.strip("/").split("/")[0]
    whole = [i for i, l in enumerate(lines) if l.strip().rstrip("/") in (f"/{top}", top)]
    if not whole:
        return False
    lines[whole[0]:whole[0] + 1] = wanted
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write("\n".join(lines) + "\n")
    return True
