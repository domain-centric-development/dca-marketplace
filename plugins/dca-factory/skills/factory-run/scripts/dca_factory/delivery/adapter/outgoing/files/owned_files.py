"""What is the person's (WP-94): the story file and the `## Answer` of every record, digested at a window's start so a
stage that changed them is stopped; the gate's one write into a story — its state fields — rebaselines the digest;
and every hand-over a stage wrote, journaled with its digest."""

from __future__ import annotations

import hashlib
import os
import typing

from .....contract import OWNED_DIGEST, STAGE_FILES, STAGE_ORDER, WINDOW_DIGEST
from .....sharedkernel.adapter.outgoing.markdown.front_matter import MarkdownError as GateError, read_text, split_front
from .....sharedkernel.adapter.outgoing.profile.profile_files import evidence_dir, place
from .decision_record_files import answer_section, decisions_store
from .journal_files import journal_append, journal_events
from .story_layout import DECISIONS_DIR, file_digest, find_story, STATE_KEYS, STORY_FILE, story_id_of


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
