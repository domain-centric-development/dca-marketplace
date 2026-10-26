"""What is the person's (WP-94): the story file and the `## Answer` of every record, digested at a window's start so a
stage that changed them is stopped; the gate's one write into a story — its state fields — rebaselines the digest;
and every hand-over a stage wrote, journaled with its digest."""

from __future__ import annotations

import contextlib
import hashlib
import os
import sys
import typing

from ..pipeline.stage_rows import SHARED_WINDOWS, STAGE_FILES, STAGE_ORDER
from .....sharedkernel.adapter.outgoing.markdown.front_matter import MarkdownError as GateError, read_text, split_front
from .....sharedkernel.adapter.outgoing.profile.profile_files import (
    evidence_dir, evidence_rel, in_worktree, place, worktree_owned)
from .decision_record_files import answer_section, decisions_store
from .journal_files import journal_append, journal_events
from .run_marks import OWNED_CHANGED, pass_marks, STORY_DIGEST, write_mark, written_at
from ....domain.model.story import StoryId
from .story_layout import (
    DECISIONS_DIR, file_digest, find_story, STATE_KEYS, story_digest, STORY_FILE, story_id_of)


# --- what is the person's: the story and the answers (WP-94) --------------------------------------------------
# A story's file and every decision's `## Answer` are written by a person — through `/factory-decisions`, by hand —
# and by the gate where it delivers or reopens a story; never by a stage. At a stage window's start the runner (or a
# session's `--stage-start`) records a digest of them; a gate inside the window and the window's end compare. A
# change under a stage is marked (`.owned-changed`) and the story stays stopped until a person looked at it and
# confirms (`factory-cli.py --owned-confirm <story>`). `by:` is free text: the digest is the proof, not the name.
OWNED_DIGEST = ".owned-digest"


#: The hand-overs' digests at a window's start: what the window left as it was.
WINDOW_DIGEST = ".window-digest"

def write_story_fields(path: str, **fields: typing.Optional[str]) -> None:
    """Set — or with None remove — flat keys in a story's front matter; everything else stays byte for byte.
    The gate's one write into a story: `status: delivered`, `delivered:` and `delivered_by:` at the gate that
    delivers it, and their removal when a reopen or `--prove` takes the story back. The front matter is read by
    lines (`split_front`): a `---` inside a line is text."""
    if not os.path.isfile(path):
        raise GateError(f"{path}: file not found")
    with open(path, encoding="utf-8", newline="") as handle:      # the line endings as they are
        text = handle.read()
    if split_front(text) is None:
        raise GateError(f"{path}: no front matter to write into")
    newline = "\r\n" if "\r\n" in text.split("\n", 1)[0] + "\n" else "\n"
    raw = text.splitlines(keepends=True)
    close = next(i for i in range(1, len(raw)) if raw[i].rstrip("\r\n") == "---")
    lines = [line.rstrip("\r\n") for line in raw[1:close]]
    is_key = lambda line, key: not line.startswith((" ", "\t", "-")) and line.split(":", 1)[0].strip().lower() == key
    for key, value in fields.items():
        index = next((i for i, line in enumerate(lines) if is_key(line, key)), None)
        if value is None:
            if index is not None:
                del lines[index]
        elif index is not None:
            lines[index] = f"{key}: {value}"
        else:
            # A state line goes after the last state line there is (`status`, `delivered`, …), else at the end.
            after = max((i for i, line in enumerate(lines) if any(is_key(line, k) for k in STATE_KEYS)), default=None)
            lines.insert(after + 1 if after is not None else len(lines), f"{key}: {value}")
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(raw[0] + "".join(line + newline for line in lines) + raw[close] + "".join(raw[close + 1:]))
    rebaseline_owned(path)


def owned_parts(story_path: typing.Optional[str]) -> typing.Dict[str, str]:
    """{part: sha256} of what is the person's: the story file, and the `## Answer` of every record that has one."""
    parts = {STORY_FILE: file_digest(story_path)} if story_path and os.path.isfile(story_path) else {}
    store = decisions_store(story_path) if story_path else ""
    for name in sorted(os.listdir(store)) if store and os.path.isdir(store) else []:
        if name.endswith(".md"):
            answer = answer_section(read_text(os.path.join(store, name)))
            if answer is not None:
                parts[f"{DECISIONS_DIR}/{name} ## Answer"] = hashlib.sha256(answer.encode("utf-8")).hexdigest()
    return parts


def owned_story_path(story_id: str) -> typing.Optional[str]:
    try:
        return find_story(place("epics"), story_id)
    except GateError:
        return None


def record_owned(runs: str, story_id: str, story_path: typing.Optional[str] = None) -> None:
    """At a window's start: the digest of the person's parts, one line per part."""
    story_path = story_path or owned_story_path(story_id)
    folder = evidence_dir(runs, story_id)
    os.makedirs(folder, exist_ok=True)
    observe_writes(runs, story_id)               # what a person or an earlier window left, before this one writes
    run_folder = os.path.join(runs, story_id)
    with open(os.path.join(folder, WINDOW_DIGEST), "w", encoding="utf-8") as handle:
        handle.writelines(f"{file_digest(os.path.join(run_folder, name))}  {name}\n" for name in STAGE_FILES.values()
                          if os.path.isfile(os.path.join(run_folder, name)))
    with open(os.path.join(folder, OWNED_DIGEST), "w", encoding="utf-8") as handle:
        handle.writelines(f"{digest}  {part}\n" for part, digest in sorted(owned_parts(story_path).items()))


def rebaseline_owned(story_path: str) -> None:
    """The gate wrote the story itself (delivered, reopened): an open window's digest takes the new state."""
    story_id = story_id_of(story_path)
    runs = place("runs")
    if os.path.isfile(os.path.join(evidence_dir(runs, story_id), OWNED_DIGEST)):
        record_owned(runs, story_id, story_path)


def observe_writes(runs: str, story_id: str) -> None:
    """Journal a `wrote <file> sha=<digest>` for every hand-over whose content changed since the journal last saw it,
    in the stages' order — at a window's start and end and at every gate run, so the journal alone tells which file
    was written after which. A file gone since is journaled `sha=gone`."""
    folder = os.path.join(runs, story_id)
    seen = {}
    for event in journal_events(runs, story_id):
        if event["kind"] == "wrote":
            seen[event["name"]] = event["fields"].get("sha")
    for stage in STAGE_ORDER:
        name = STAGE_FILES[stage]
        path = os.path.join(folder, name)
        digest = file_digest(path) if os.path.isfile(path) else "gone"
        if seen.get(name, "gone") != digest:
            journal_append(runs, story_id, "wrote", name, f"sha={digest}")


def owned_changes(runs: str, story_id: str,
                  story_path: typing.Optional[str] = None) -> typing.Optional[typing.List[str]]:
    """The parts that changed since the window's start — None where no window recorded them."""
    path = os.path.join(evidence_dir(runs, story_id), OWNED_DIGEST)
    if not os.path.isfile(path):
        return None
    before: typing.Dict[str, str] = {}
    for line in read_text(path).splitlines():
        digest, _, part = line.partition("  ")
        if part:
            before[part] = digest
    now = owned_parts(story_path or owned_story_path(story_id))
    return sorted(part for part in set(before) | set(now) if before.get(part) != now.get(part))


def write_answered(story_path: str, runs: str, rid: str, sentence: str) -> bool:
    """One `- answered: <sentence> (<id>)` line under the story's `## Assumptions` — the gate's write when it stamps
    an answer applied; the section is made where the story has none. The line corrects the story so far that it
    can be carried out; it is not a requirement of its own and is never merged into a spec. In the same write the
    planned digest (`.story-digest`) and an open window's owned digest take the new text, so the gate's own line
    does not read as "the story changed after it was planned"; any other change still does."""
    with open(story_path, encoding="utf-8", newline="") as handle:
        text = handle.read()
    if f"({rid})" in text:
        return False
    newline = "\r\n" if "\r\n" in text else "\n"
    line = f"- answered: {sentence} ({rid})"
    lines = text.split(newline)
    start = next((i for i, l in enumerate(lines) if l.strip().lower().startswith("## assumptions")), None)
    if start is None:
        while lines and not lines[-1].strip():
            lines.pop()
        lines += ["", "## Assumptions", "", line, ""]
    else:
        end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
        last = max((i for i in range(start + 1, end) if lines[i].strip()), default=start)
        lines.insert(last + 1, line)
        if last == start:
            lines.insert(last + 1, "")
    with open(story_path, "w", encoding="utf-8", newline="") as handle:
        handle.write(newline.join(lines))
    story_id = story_id_of(story_path)
    if os.path.isfile(os.path.join(evidence_dir(runs, story_id), STORY_DIGEST)):
        write_mark(runs, story_id, STORY_DIGEST, story_digest(story_path))
    rebaseline_owned(story_path)
    return True


def mark_window_files(runs: str, story_id: str, window: str) -> None:
    """A window that ran its stages to the end wrote their files — also one it wrote again as it was: the journal
    then says so (`wrote <file> same=1`). Only for the stages the window carried (its `stage-start` names them), and
    not for one a later stage of the window built on by writing anew — unless the file would otherwise read as an
    earlier pass's (an earlier stage's file is newer). A file a stage left as it was then holds for this pass; a
    stage the window did not run is never written after the ones it did."""
    folder, run_folder = evidence_dir(runs, story_id), os.path.join(runs, story_id)
    path = os.path.join(folder, WINDOW_DIGEST)
    at_start: typing.Dict[str, str] = {}
    if os.path.isfile(path):
        for line in read_text(path).splitlines():
            digest, _, name = line.partition("  ")
            at_start[name] = digest
        os.remove(path)
    carried = SHARED_WINDOWS.get(window, (window,))
    for event in journal_events(runs, story_id):
        if event["kind"] == "stage-start" and event["name"] == window:
            carried = tuple(event["fields"].get("stages", "").split(",")) if event["fields"].get("stages") else carried
    marks = pass_marks(runs, story_id)
    present = [s for s in STAGE_ORDER if STAGE_FILES.get(s) and os.path.isfile(os.path.join(run_folder, STAGE_FILES[s]))]
    same = {s for s in present if s in carried
            and at_start.get(STAGE_FILES[s]) == file_digest(os.path.join(run_folder, STAGE_FILES[s]))}
    anew = [s for s in present if s in carried and s not in same]
    newest, marked = 0, False
    for stage in present:
        name = STAGE_FILES[stage]
        at = written_at(marks, stage)
        later_anew = any(STAGE_ORDER.index(s) > STAGE_ORDER.index(stage) for s in anew)
        if stage in same and (marked or at is None or at < newest or not later_anew):
            journal_append(runs, story_id, "wrote", name, f"sha={at_start[name]}", "same=1")
            marked = True
            continue
        newest = max(newest, at or 0)


def owned_end(runs: str, story_id: str, window: str, ran: str = "0") -> int:
    """At a window's end: unchanged, the digest goes; changed, the change is marked and named. Exit 7 then."""
    folder = evidence_dir(runs, story_id)
    observe_writes(runs, story_id)               # what the window wrote, in the stages' order
    if ran == "0":
        mark_window_files(runs, story_id, window)
    else:
        with contextlib.suppress(OSError):
            os.remove(os.path.join(folder, WINDOW_DIGEST))
    changed = owned_changes(runs, story_id)
    with contextlib.suppress(OSError):
        os.remove(os.path.join(folder, OWNED_DIGEST))
    if not changed:
        return 0
    with open(os.path.join(folder, OWNED_CHANGED), "w", encoding="utf-8") as handle:
        handle.write(f"window: {window}\n" + "".join(f"changed: {part}\n" for part in changed))
    print(f"factory: {', '.join(changed)} of {story_id} changed while the {window} stage ran — the story and the "
          f"answers are the person's, a stage writes neither. The story stays stopped until a person looked at it: "
          f"`factory-cli.py --owned-confirm {story_id}`.", file=sys.stderr)
    return 7


def run_owned(path: str, runs: str) -> bool:
    """A path the pipeline writes itself and no stage answers for: the run folder, the evidence folder, a story's
    decision records (a stage's question, written into the story's folder)."""
    epics = place("epics").rstrip("/") + "/"
    return path.startswith((runs.rstrip("/") + "/", evidence_rel() + "/")) \
        or (path.startswith(epics) and f"/{DECISIONS_DIR}/" in path[len(epics):]) \
        or (in_worktree() and worktree_owned(path))


class OwnedChangeFiles:
    """The mark `.owned-changed` in a story's evidence, under the run folder <runs>."""

    def __init__(self, runs: str) -> None:
        self._runs = runs

    def _mark(self, story: StoryId) -> str:
        return os.path.join(evidence_dir(self._runs, story.value), OWNED_CHANGED)

    def changed(self, story: StoryId) -> typing.Sequence[str]:
        marked = self._mark(story)
        if not os.path.isfile(marked):
            return ()
        return [line.split(":", 1)[1].strip() for line in read_text(marked).splitlines() if line.startswith("changed:")]

    def clear(self, story: StoryId) -> None:
        os.remove(self._mark(story))
