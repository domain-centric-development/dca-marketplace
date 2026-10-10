"""Where a story stands — read from its journal, its files and the checkout claim, never from a clock.

The journal's events in order (`seq=`), the owned files' digests, which pass wrote which stage file, the story
state the runner and the status read, the schedule over every story and the claim one worker holds on a
checkout.
"""

import contextlib
import glob
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from .contract import (
    ADOPT_ORDER, CRITERION, DECISIONS_DIR, decisions_store, DEFAULTS, delivered_on, depends_on, duplicate_ids,
    EPIC_FILE, epic_folder, epic_graph, epic_order, evidence_dir, evidence_rel, factory_home, file_digest, find_story,
    GateError, git, in_worktree, is_delivered, JOURNAL, JOURNEY_ORDER, layout_hint, MAX_ROUNDS, needs_human_ids,
    OWNED_DIGEST, place, PLACES_REL, POST_GATED, PROFILE_FILE, read_front_matter, read_profile, read_text, records_of,
    resolve_profile, resume_stage, section_of, SHARED_WINDOWS, shown, STAGE_FILES, STAGE_ORDER, story_digest,
    STORY_FILE, story_files, story_folder, story_id_of, story_kind, WINDOW_DIGEST, worktree_owned)
from .reports import (
    claude_session_logs, codex_session_log, current_session, parse_time, PROCESS_RANKS, session_usage,
    session_usage_allowed, tokens_of, USAGE_FIELDS, usage_fields, WINDOWS)


def journal_path(runs, story_id):
    return os.path.join(evidence_dir(runs, story_id), JOURNAL)


def journal_events(runs, story_id):
    """[{seq, at, kind, name, fields}] in order. A line from before sequence numbers takes its position."""
    return read_events(journal_path(runs, story_id))


def read_events(path):
    events = []
    if not os.path.isfile(path):
        return events
    for position, line in enumerate(read_text(path).splitlines(), 1):
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        fields = dict(p.split("=", 1) for p in parts[3:] if "=" in p)
        seq = fields.pop("seq", "")
        events.append({"seq": int(seq) if seq.isdigit() else position, "at": parts[0], "kind": parts[1],
                       "name": parts[2], "fields": fields, "line": line})
    # A union merge of two branches that ran the same story can repeat a number: the time decides between them.
    events.sort(key=lambda e: (e["seq"], e["at"]))
    return events


@contextlib.contextmanager
def journal_lock(path):
    """One writer at a time on a journal: parallel reviewers and a stage's own gate append beside the runner. A
    folder is made atomically on every platform; one left by a killed process is taken over after half a minute."""
    lock = path + ".lock"
    deadline = time.time() + 10
    while True:
        try:
            os.mkdir(lock)
            break
        except FileExistsError:
            with contextlib.suppress(OSError):
                if time.time() - os.path.getmtime(lock) > 30:
                    os.rmdir(lock)
                    continue
            if time.time() > deadline:
                break                               # never block a run on a stale lock: append unlocked
            time.sleep(0.02)
    try:
        yield
    finally:
        with contextlib.suppress(OSError):
            os.rmdir(lock)


def journal_append(runs, story_id, kind, name, *fields, at=None):
    """Append one event with the next sequence number; returns it."""
    return append_event(journal_path(runs, story_id), kind, name, *fields, at=at)


def append_event(path, kind, name, *fields, at=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with journal_lock(path):
        seq = 1 + max((e["seq"] for e in read_events(path)), default=0)
        stamp = at or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        cells = [stamp, kind, name] + [str(f) for f in fields if str(f)] + [f"seq={seq}"]
        with open(path, "a", encoding="utf-8") as handle:
            handle.write("\t".join(c.replace("\t", " ").replace("\n", " ") for c in cells) + "\n")
    return seq


class journal_writer:
    """`with journal_writer(runs, story) as handle: handle.write("<time>\t<kind>\t<name>\t…\n")` — the old
    append idiom, every line through `journal_append`, so a writer that composes its lines keeps doing so."""

    def __init__(self, runs, story_id):
        self.runs, self.story_id = runs, story_id

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def write(self, text):
        for line in text.splitlines():
            parts = line.split("\t")
            if len(parts) >= 3:
                journal_append(self.runs, self.story_id, parts[1], parts[2], *parts[3:], at=parts[0])


def worktrees_dir():
    """Where the stories' worktrees live, relative to the main checkout: beside the run folder."""
    runs = (PLACES_REL.get("runs") or DEFAULTS["runs"]).rstrip("/")
    return os.path.join(os.path.dirname(runs) or ".dca-factory", "worktrees").replace("\\", "/")


def worktree_of(story_id, home=None):
    """The story's worktree in the main checkout (here, unless FACTORY_HOME names another)."""
    return os.path.join(home or factory_home() or os.getcwd(), worktrees_dir(), story_id)


def has_worktree(story_id, home=None):
    """Whether the story has its worktree: a checkout with git's `.git` file in it."""
    return os.path.isfile(os.path.join(worktree_of(story_id, home), ".git"))


#: The product description's headings — what is built, for whom, through which surfaces.
PRODUCT_HEADINGS = (
    "What and for whom",
    "Surfaces",
    "How it works",
    "Look and feel",
    "Qualities",
    "Not part of the product",
)


def write_story_fields(path, **fields):
    """Set — or with None remove — flat keys in a story's front matter; everything else stays byte for byte.
    The gate's one write into a story: `status: delivered` and `delivered:` at the gate that delivers it, and
    their removal when a reopen takes the story back."""
    if not os.path.isfile(path):
        raise GateError(f"{path}: file not found")
    with open(path, encoding="utf-8", newline="") as handle:      # the line endings as they are
        text = handle.read()
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise GateError(f"{path}: no front matter to write into")
    newline = "\r\n" if "\r\n" in parts[1] else "\n"
    lines = parts[1].split(newline)
    is_key = lambda line, key: not line.startswith((" ", "\t", "-")) and line.split(":", 1)[0].strip().lower() == key
    for key, value in fields.items():
        index = next((i for i, line in enumerate(lines) if is_key(line, key)), None)
        if value is None:
            if index is not None:
                del lines[index]
        elif index is not None:
            lines[index] = f"{key}: {value}"
        else:
            after = next((i for i, line in enumerate(lines) if is_key(line, "status")), None)
            lines.insert(after + 1 if after is not None else max(len(lines) - 1, 1), f"{key}: {value}")
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write("---" + newline.join(lines) + "---" + parts[2])
    rebaseline_owned(path)


OWNED_CHANGED = ".owned-changed"


def answer_section(text):
    """A record's `## Answer` section as written, up to the next `## ` heading — the person's part of it."""
    lines, inside = [], False
    for line in text.splitlines():
        if line.strip().lower() == "## answer":
            inside = True
        elif inside and line.startswith("## "):
            break
        if inside:
            lines.append(line)
    return "\n".join(lines).rstrip() if lines else None      # a section appended after it leaves it as it was


def owned_parts(story_path):
    """{part: sha256} of what is the person's: the story file, and the `## Answer` of every record that has one."""
    parts = {STORY_FILE: file_digest(story_path)} if story_path and os.path.isfile(story_path) else {}
    store = decisions_store(story_path) if story_path else None
    for name in sorted(os.listdir(store)) if store and os.path.isdir(store) else []:
        if name.endswith(".md"):
            answer = answer_section(read_text(os.path.join(store, name)))
            if answer is not None:
                parts[f"{DECISIONS_DIR}/{name} ## Answer"] = hashlib.sha256(answer.encode("utf-8")).hexdigest()
    return parts


def owned_story_path(story_id):
    try:
        return find_story(place("epics"), story_id)
    except GateError:
        return None


def record_owned(runs, story_id, story_path=None):
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


def owned_changes(runs, story_id, story_path=None):
    """The parts that changed since the window's start — None where no window recorded them."""
    path = os.path.join(evidence_dir(runs, story_id), OWNED_DIGEST)
    if not os.path.isfile(path):
        return None
    before = {}
    for line in read_text(path).splitlines():
        digest, _, part = line.partition("  ")
        if part:
            before[part] = digest
    now = owned_parts(story_path or owned_story_path(story_id))
    return sorted(part for part in set(before) | set(now) if before.get(part) != now.get(part))


def rebaseline_owned(story_path):
    """The gate wrote the story itself (delivered, reopened): an open window's digest takes the new state."""
    story_id = story_id_of(story_path)
    runs = place("runs")
    if os.path.isfile(os.path.join(evidence_dir(runs, story_id), OWNED_DIGEST)):
        record_owned(runs, story_id, story_path)


def mark_window_files(runs, story_id, window):
    """A window that ran its stages to the end wrote their files — also one it wrote again as it was: the journal
    then says so (`wrote <file> same=1`), after what the window wrote anew, in the stages' order."""
    folder, run_folder = evidence_dir(runs, story_id), os.path.join(runs, story_id)
    path = os.path.join(folder, WINDOW_DIGEST)
    at_start = {}
    if os.path.isfile(path):
        for line in read_text(path).splitlines():
            digest, _, name = line.partition("  ")
            at_start[name] = digest
        os.remove(path)
    for stage in SHARED_WINDOWS.get(window, (window,)):
        name = STAGE_FILES.get(stage)
        full = os.path.join(run_folder, name) if name else None
        if full and os.path.isfile(full) and at_start.get(name) == file_digest(full):
            journal_append(runs, story_id, "wrote", name, f"sha={at_start[name]}", "same=1")


def owned_end(runs, story_id, window, ran="0"):
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


def run_owned(path, runs):
    """A path the pipeline writes itself and no stage answers for: the run folder, the evidence folder, a story's
    decision records (a stage's question, written into the story's folder)."""
    epics = place("epics").rstrip("/") + "/"
    return path.startswith((runs.rstrip("/") + "/", evidence_rel() + "/")) \
        or (path.startswith(epics) and f"/{DECISIONS_DIR}/" in path[len(epics):]) \
        or (in_worktree() and worktree_owned(path))


DELETED = "deleted"


#: The paths every stage window of a pass changed, one per line: what the story's commit takes of the untracked files.
STAGES_MADE = "stages-made.txt"


#: The first line of a snapshot or a changed-files record that carries no observation, and says why.
NOT_OBSERVED = "# not observed: "


def tree_snapshot(cwd):
    """{path: sha256 or `deleted`} of every file under `cwd` that git reports as differing from HEAD —
    or None outside a repository: an empty snapshot would read as "nothing changed", the strongest
    claim a record can make, from no evidence at all."""
    listing = subprocess.run(["git", "-c", "core.fileMode=false", "status", "--porcelain", "-z", "-uall", "--", "."],
                             cwd=cwd, capture_output=True)
    files = {}
    if listing.returncode != 0:
        return None
    prefix = subprocess.run(["git", "rev-parse", "--show-prefix"], cwd=cwd, capture_output=True,
                            text=True).stdout.strip()
    local = lambda path: path[len(prefix):] if prefix and path.startswith(prefix) else path
    entries = iter(listing.stdout.decode("utf-8", "replace").split("\0"))
    for entry in entries:
        code, path = entry[:2], local(entry[3:])
        if not path:
            continue
        if code[0] in "RC":
            origin = local(next(entries, ""))       # -z writes a rename's source as the next entry
            if code[0] == "R" and origin:
                files[origin] = DELETED
        full = os.path.join(cwd, path)
        if "D" in code:
            files[path] = DELETED
        elif os.path.isfile(full):
            with open(full, "rb") as handle:
                files[path] = hashlib.sha256(handle.read()).hexdigest()
    return files


def write_snapshot(cwd, runs, story_id, label):
    folder = evidence_dir(runs, story_id)
    os.makedirs(folder, exist_ok=True)
    snapshot = tree_snapshot(cwd)
    with open(os.path.join(folder, f"tree-{label}.txt"), "w", encoding="utf-8") as handle:
        if snapshot is None:
            handle.write(NOT_OBSERVED + "not a git repository, so the tree cannot be compared\n")
            return
        for path, digest in sorted(snapshot.items()):
            handle.write(f"{digest}  {path}\n")


def load_snapshot(path):
    """{path: digest} from a snapshot file, or None when there is none (or it carries no digests)."""
    if not os.path.isfile(path):
        return None
    files = {}
    for line in read_text(path).splitlines():
        if line.startswith("#"):
            return None
        digest, _, name = line.partition("  ")
        if name:
            files[name] = digest
    return files


def snapshot_reason(path):
    """Why a snapshot (or a changed-files record) carries no observation, from its first line; None
    when it is a real one or there is none."""
    if not os.path.isfile(path):
        return None
    first = (read_text(path).splitlines() or [""])[0]
    if first.startswith(NOT_OBSERVED):
        return first[len(NOT_OBSERVED):].strip()
    if first.startswith("#"):
        return first.lstrip("# ").strip()
    return None


def tracked_files(cwd):
    listing = subprocess.run(["git", "ls-files", "-z"], cwd=cwd, capture_output=True)
    return set(listing.stdout.decode("utf-8", "replace").split("\0")) if listing.returncode == 0 else set()


def changes_between(before, after, runs, tracked=frozenset()):
    """A path missing from a snapshot is as HEAD has it: there when git tracks it, absent otherwise."""
    state = lambda snapshot, path: snapshot.get(path, "head" if path in tracked else None)
    exists = lambda value: value not in (None, DELETED)
    rows = []
    for path in sorted(set(before) | set(after)):
        if run_owned(path, runs):
            continue
        was, now = state(before, path), state(after, path)
        if was == now or not (exists(was) or exists(now)):
            continue
        rows.append(("removed" if not exists(now) else "added" if not exists(was) else "modified", path))
    return rows


def git_tree(cwd):
    """A tree object of the project as it is — `git add -A` into a throwaway index, never a commit."""
    import tempfile
    with tempfile.TemporaryDirectory() as scratch:
        env = dict(os.environ, GIT_INDEX_FILE=os.path.join(scratch, "index"))
        if subprocess.run(["git", "add", "-A", "--", "."], cwd=cwd, env=env, capture_output=True).returncode != 0:
            return None
        tree = subprocess.run(["git", "write-tree"], cwd=cwd, env=env, capture_output=True, text=True)
        return tree.stdout.strip() if tree.returncode == 0 and tree.stdout.strip() else None


def tree_changes(cwd, base, now, runs):
    """[(kind, path)] between two trees, relative to the project, the run's own files left out."""
    listing = subprocess.run(["git", "diff", "--name-status", "-z", "--no-renames", "--relative", base, now, "--", "."],
                             cwd=cwd, capture_output=True)
    if listing.returncode != 0:
        return None
    fields = listing.stdout.decode("utf-8", "replace").split("\0")
    kinds = {"A": "added", "D": "removed"}
    return [(kinds.get(code[:1], "modified"), path) for code, path in zip(fields[0::2], fields[1::2])
            if path and not run_owned(path, runs)]


def record_base(cwd, runs, story_id):
    """At a story's first stage: the tree the story's diff is taken against. Written once."""
    folder = evidence_dir(runs, story_id)
    os.makedirs(folder, exist_ok=True)
    base = os.path.join(folder, "base-tree")
    if not os.path.isfile(base):
        tree = git_tree(cwd)
        with open(base, "w", encoding="utf-8") as handle:
            handle.write((tree or "none") + "\n")


def record_changes(cwd, runs, story_id, stage):
    """`changed-<stage>.txt`, the story's `changed.txt` and `story.diff`, after a stage has ended."""
    folder = evidence_dir(runs, story_id)
    after = load_snapshot(os.path.join(folder, f"tree-after-{stage}.txt"))
    before = load_snapshot(os.path.join(folder, f"tree-before-{stage}.txt"))
    if after is None or before is None:
        # A snapshot that carries no observation (outside git, or without a digest command) says why
        # in its first line; the record repeats it, so the gate skips the files check and names the reason
        # instead of passing an empty record as "nothing changed".
        reason = snapshot_reason(os.path.join(folder, f"tree-after-{stage}.txt")) \
            or snapshot_reason(os.path.join(folder, f"tree-before-{stage}.txt"))
        if reason:
            for name in (f"changed-{stage}.txt", "changed.txt"):
                with open(os.path.join(folder, name), "w", encoding="utf-8") as handle:
                    handle.write(NOT_OBSERVED + reason + "\n")
            with open(os.path.join(folder, "story.diff"), "w", encoding="utf-8") as handle:
                handle.write(f"# no diff: {reason}\n")
        return
    tracked = tracked_files(cwd)
    rows = changes_between(before, after, runs, tracked)
    with open(os.path.join(folder, f"changed-{stage}.txt"), "w", encoding="utf-8") as handle:
        handle.writelines(f"{kind}\t{path}\n" for kind, path in rows)
    # Every path a stage window of this pass changed, kept across rounds: a later round's record of the same stage
    # replaces the earlier one, and a file the first round made would drop out of the story's commit with it.
    made = os.path.join(folder, STAGES_MADE)
    known = set(read_text(made).splitlines()) if os.path.isfile(made) else set()
    with open(made, "w", encoding="utf-8") as handle:
        handle.writelines(f"{path}\n" for path in sorted(known | {path for _kind, path in rows}))
    base_file = os.path.join(folder, "base-tree")
    base = read_text(base_file).strip() if os.path.isfile(base_file) else "none"
    now = git_tree(cwd) if base != "none" else None
    story_rows = tree_changes(cwd, base, now, runs) if now else None
    if story_rows is None:
        first = next((snap for snap in (load_snapshot(os.path.join(folder, f"tree-before-{name}.txt"))
                                        for name in STAGE_ORDER) if snap is not None), before)
        story_rows = changes_between(first, after, runs, tracked)
    with open(os.path.join(folder, "changed.txt"), "w", encoding="utf-8") as handle:
        handle.writelines(f"{kind}\t{path}\n" for kind, path in story_rows)
    diff_path = os.path.join(folder, "story.diff")
    if base == "none" or not now:
        with open(diff_path, "w", encoding="utf-8") as handle:
            handle.write("# no diff: the project is not a git repository, or no base tree was recorded — "
                         "changed.txt lists the files\n")
        return
    paths = [path for _, path in story_rows]
    diff = subprocess.run(["git", "diff", "--no-color", "--relative", base, now, "--"] + paths, cwd=cwd,
                          capture_output=True, text=True, encoding="utf-8", errors="replace") if paths else None
    with open(diff_path, "w", encoding="utf-8") as handle:
        handle.write(diff.stdout if diff and diff.returncode == 0 else "")


def listed_files(handover):
    """The paths a hand-over names under `## Files`, or in the build's `## Changed` / tidy's `## Moves`
    table: in backticks, as a list item's first word, or in a table's first cell. A table's other cells
    say why, and a backticked route or a lone `/` there is prose, not a path."""
    if not os.path.isfile(handover):
        return None
    names, inside, found = set(), False, False
    for line in read_text(handover).splitlines():
        if line.startswith("## "):
            inside = line[3:].strip().lower() in ("files", "changed", "moves")
            found = found or inside
            continue
        if not inside:
            continue
        if line.lstrip().startswith("|"):
            cell = line.lstrip()[1:].split("|", 1)[0].strip()
            if cell.startswith("`") and cell.endswith("`") and len(cell) > 2:
                cell = cell[1:-1].strip()
            if cell and " " not in cell and not set(cell) <= set("-:"):
                names.add(cell)
            continue
        names.update(re.findall(r"`([^`\s]+)`", line))
        item = re.match(r"^\s*[-*]\s+([^\s`|]+)", line)
        if item:
            names.add(item.group(1))
    return {name for name in names if re.search(r"[A-Za-z0-9]", name)} if found else None


def last_ended(runs, story_id, names):
    """Which of the named windows ended last in the story's journal, or None."""
    journal = os.path.join(evidence_dir(runs, story_id), "journal.tsv")
    last = None
    if os.path.isfile(journal):
        for line in read_text(journal).splitlines():
            parts = line.split("\t")
            if len(parts) >= 3 and parts[1] == "stage-end" and parts[2] in names:
                last = parts[2]
    return last


def window_open(runs, story_id, window):
    """True while the journal's last mark for that exact window name is its start."""
    journal = os.path.join(evidence_dir(runs, story_id), "journal.tsv")
    if not os.path.isfile(journal):
        return False
    last = None
    for line in read_text(journal).splitlines():
        parts = line.split("\t")
        if len(parts) >= 3 and parts[1] in ("stage-start", "stage-end") and parts[2] == window:
            last = parts[1]
    return last == "stage-start"


def stage_open(runs, story_id, stage):
    """True while the journal's last mark for the stage is its start: the stage is running (plan to tidy
    also while a shared builder, which marks itself `builder`, runs them; judge and document also while a
    shared verifier, `verifier`, runs them)."""
    journal = os.path.join(evidence_dir(runs, story_id), "journal.tsv")
    if not os.path.isfile(journal):
        return False
    last = None
    for line in read_text(journal).splitlines():
        parts = line.split("\t")
        if len(parts) >= 3 and parts[1] in ("stage-start", "stage-end") and (
                parts[2] == stage or parts[2] in SHARED_WINDOWS and stage in SHARED_WINDOWS[parts[2]]):
            last = parts[1]
    return last == "stage-start"


#: Processes a model key may name beside the stages: the shared builder and verifier, and the reviewers.
MODEL_PROCESSES = ("builder", "verifier", "review")


RUNNABLE = ("ready", "in-progress", "resumable")


def verdict_in(text):
    for line in text.splitlines():
        if line.strip().lower().startswith("verdict:"):
            return line.split(":", 1)[1].strip().strip("`\"' ").lower()
    return ""


def back_in(text):
    """Where a `changes-requested` verdict sends the story: `test` when the judge wrote `back: test` — a
    confirmed defect is in a test (it asserts less than its criterion), which only the test stage may
    change — else `build`."""
    for line in text.splitlines():
        if line.strip().lower().startswith("back:"):
            return "test" if line.split(":", 1)[1].strip().strip("`\"' ").lower() == "test" else "build"
    return "build"


#: What the plan gate leaves for the schedule: the digest of the story it let through, so a story edited
#: afterwards is planned again rather than built on a plan that describes something else. Protocol, not
#: state — a run folder without it is a story to plan. Delivered is written into the story itself
#: (`status: delivered`, `delivered:`), by the document or adopt gate alone.
STORY_DIGEST = ".story-digest"


def write_mark(runs, story_id, name, content):
    folder = evidence_dir(runs, story_id)
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, name), "w", encoding="utf-8") as handle:
        handle.write(content + "\n")


#: A story delivered only once a human looked at it: the record kind, the modes of `acceptance:`.
ACCEPTANCE_KIND = "acceptance"


ACCEPTANCE_MODES = ("none", "pages", "all")


def acceptance_mode(profile):
    mode = str(profile.get("acceptance", "none")).strip().lower() or "none"
    if mode not in ACCEPTANCE_MODES:
        raise GateError(f"`acceptance: {mode}` is none of {', '.join(ACCEPTANCE_MODES)}")
    return mode


def is_acceptance(front):
    return str(front.get("kind", "")).strip().lower() == ACCEPTANCE_KIND


def acceptance_records(cwd, story_id, story_path=None):
    """This story's acceptance records, oldest first: [(id, front, state, answer, body)]."""
    records = records_of(story_id, story_path)
    found = [(str(f["id"]).strip(), f, state, answer, body) for _p, f, body, state, answer in records if is_acceptance(f)]
    number = lambda rid: int(re.search(r"(\d+)$", rid).group(1)) if re.search(r"(\d+)$", rid) else 0
    return sorted(found, key=lambda r: number(r[0]))


def accepted(answer):
    return str(answer.get("answer", "")).strip().lower().startswith("accept")


def acceptance_state(cwd, story_id, story_path):
    """('ask' | 'open' | 'accepted' | 'correction', id or None) for the story as it is now.

    An answer holds for the story it was given for: the record carries the story's digest, and a
    story changed since — a correction written in — is asked again once it has run."""
    records = acceptance_records(cwd, story_id, story_path)
    if not records:
        return "ask", None
    rid, front, state, answer, _body = records[-1]
    if state in ("open", "draft"):
        return "open", rid
    if str(front.get("digest", "")).strip() != story_digest(story_path):
        return "ask", rid
    return ("accepted" if accepted(answer) else "correction"), rid


ACCEPTED_TESTS = re.compile(r"\s+—\s+`[^`]*`$")


def accepted_criteria(body):
    """The criteria an acceptance record listed, as (key, text) — the story as it was accepted."""
    found = []
    for line in section_of(body, "question") or []:
        match = CRITERION.match(line.strip())
        if match:
            found.append((match.group(1), ACCEPTED_TESTS.sub("", match.group(2)).strip()))
    return found


def observe_writes(runs, story_id):
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


def pass_marks(runs, story_id):
    """{name: seq} of what the journal says about the hand-overs: `wrote:<file>` (the last write), `pass:<gate>` (the
    last pass of that gate), `fail:<gate>` (the last refusal), `outdated:<file>` (marked an earlier pass's)."""
    marks = {}
    for event in journal_events(runs, story_id):
        kind, name, fields = event["kind"], event["name"], event["fields"]
        if kind == "wrote" and fields.get("sha") != "gone":
            marks[f"wrote:{name}"] = event["seq"]
        elif kind == "wrote":
            marks.pop(f"wrote:{name}", None)
        elif kind == "gate":
            # 3: every check passed and a person is asked — the file holds, though the gate has not passed yet
            marks[f"{'pass' if fields.get('exit') == '0' else 'held' if fields.get('exit') == '3' else 'fail'}:{name}"] \
                = event["seq"]
        elif kind == "outdated":
            marks[f"outdated:{name}"] = event["seq"]
    return marks


def written_at(marks, stage):
    """When the stage's file last held for the pass: its last write, or a later pass of its own gate."""
    name = STAGE_FILES[stage]
    at = marks.get(f"wrote:{name}", 0)
    if stage in POST_GATED:
        at = max(at, marks.get(f"pass:{stage}", 0), marks.get(f"held:{stage}", 0))
    return None if marks.get(f"outdated:{name}", -1) > at else at


def gate_passed_since(runs, story_id, gate, stage):
    """Whether the gate passed after the stage's file was last written — the runner's or a stage's own run."""
    marks = pass_marks(runs, story_id)
    return os.path.isfile(os.path.join(runs, story_id, STAGE_FILES[stage])) \
        and marks.get(f"pass:{gate}", 0) >= marks.get(f"wrote:{STAGE_FILES[stage]}", 0) > 0


def current_stage_files(runs, story_id, order):
    """{stage: text} for the stage files of the story's current pass, from the journal's order alone. A stage that
    ran again — a re-plan, a build after `changes-requested`, a test stage applying an answer — makes every later file
    an earlier pass's: it stays on disk as history, but it no longer says where the story stands. A stage whose gate
    passed after the file before it was written holds for this pass, though its own file is older: a shared session
    that went back to its test stage after the build and had the build gate pass again."""
    folder = os.path.join(runs, story_id)
    marks = pass_marks(runs, story_id)
    texts, newest = {}, None
    for stage in order:
        path = os.path.join(folder, STAGE_FILES[stage])
        if not os.path.isfile(path):
            continue
        written = written_at(marks, stage)
        if written is None or (newest is not None and written < newest):
            break
        texts[stage] = read_text(path)
        newest = max(written, newest or 0)
    return texts


def backlog_digest(story_path):
    """The story and its epic as the plan gate read them: a refusal holds until one of the two changes."""
    digest = hashlib.sha256()
    for path in (story_path, story_path and os.path.join(epic_folder(story_path), EPIC_FILE)):
        if path and os.path.isfile(path):
            with open(path, "rb") as handle:
                digest.update(handle.read())
    return digest.hexdigest()


def story_state(cwd, runs, story_id, front, story_path=None):
    """(state, stage to run from or None, detail) for one story, from its files alone."""
    # Before anything the story says about itself: a stage may have written it (WP-94).
    if os.path.isfile(os.path.join(evidence_dir(runs, story_id), OWNED_CHANGED)):
        return "stopped", None, (f"the story or an answer changed under a stage — a person looks at it, then "
                                 f"`factory-cli.py --owned-confirm {story_id}`")
    status = str(front.get("status", "")).strip().lower()
    if status == "superseded":
        return "superseded", None, "replaced by another story"
    # Delivered is delivered: the gate wrote it into the story, and nothing under the run folder — a refusal
    # left from an earlier round, a deleted folder — changes that.
    if is_delivered(front):
        return "delivered", None, "adopted" if status == "adopted" else ""
    if status and status not in ("approved", "adopted"):
        return "unreleased", None, f"status {status} — a human releases it first"
    folder, evidence = os.path.join(runs, story_id), evidence_dir(runs, story_id)
    kind = story_kind(front)

    texts = current_stage_files(runs, story_id, ADOPT_ORDER if kind == "adopt" else JOURNEY_ORDER if kind == "journey"
                                else STAGE_ORDER)
    marks = pass_marks(runs, story_id)
    try:
        records = records_of(story_id, story_path)
    except GateError as error:
        return "stopped", None, str(error)
    waiting = [str(front_["id"]).strip() for _p, front_, _b, state, _a in records
               if state in ("open", "draft")]
    if waiting:
        return "waiting", None, "decision " + ", ".join(waiting)
    answered, resolved = {}, {}
    for _path, front_, _body, state, answer_ in records:
        rid, asked_by = str(front_["id"]).strip(), resume_stage(front_, answer_)
        if is_acceptance(front_):
            resolved[rid] = asked_by
            continue                             # answered through the document gate, not a stage
        text = texts.get(asked_by)
        if state in ("answered", "applied"):
            resolved[rid] = asked_by
        # The record's `stage:` applies the answer — usually the stage that asked, for a judge's
        # story conflict the stage the answer lands in. Until that stage's file cites the id, it is next.
        if state == "answered" and (text is None or rid in (needs_human_ids(text) or []) or rid not in text):
            answered.setdefault(asked_by, rid)
    if answered:
        stage = min(answered, key=lambda s: STAGE_ORDER.index(s) if s in STAGE_ORDER else 0)
        return "resumable", stage, f"decision {answered[stage]} answered — its stage applies it"
    rounds_file = os.path.join(evidence, ".rounds")
    if os.path.isfile(rounds_file) and (read_text(rounds_file).strip() or "0").isdigit() \
            and int(read_text(rounds_file).strip() or "0") >= MAX_ROUNDS:
        return "stopped", None, f"{MAX_ROUNDS} rounds did not converge"
    refusal = os.path.join(folder, ".gate-plan.txt")
    if os.path.isfile(refusal):
        # Repaired since: the story or its epic is not what the plan gate refused, so the plan gate asks again.
        refused = next((e["fields"].get("backlog") for e in reversed(journal_events(runs, story_id))
                        if e["kind"] == "gate" and e["name"] == "plan" and e["fields"].get("exit") != "0"), None)
        if not refused or refused == backlog_digest(story_path):
            return "stopped", None, "the plan gate refused the story — the backlog needs a fix"
        return "in-progress", "plan", "the story changed after the plan gate refused it — planned again"
    conflict = needs_human_ids(texts.get("judge", "")) or []
    if verdict_in(texts.get("judge", "")) == "story-conflict" and conflict and all(i in resolved for i in conflict):
        applied_at = max((resolved[i] for i in conflict),
                         key=lambda s: STAGE_ORDER.index(s) if s in STAGE_ORDER else 0)
        after = STAGE_ORDER[min(STAGE_ORDER.index(applied_at) + 1, len(STAGE_ORDER) - 1)] \
            if applied_at in STAGE_ORDER else "build"
        return "in-progress", after, (f"the story conflict was answered and applied at {applied_at} — "
                                      f"the stages after it run again")
    for stage, text in texts.items():
        ids = needs_human_ids(text)
        if ids and all(i in resolved for i in ids):
            continue
        if ids is not None:
            return "stopped", None, f"{STAGE_FILES[stage]} ends in `## needs-human` without an open record"
    if verdict_in(texts.get("judge", "")) == "story-conflict":
        return "stopped", None, "the judge found a story conflict"
    planned = os.path.join(evidence, STORY_DIGEST)
    if story_path and texts and os.path.isfile(planned) and os.path.isfile(os.path.join(folder, "plan.md")) \
            and read_text(planned).strip() != story_digest(story_path):
        return "in-progress", "plan", "the story changed after it was planned — every stage runs again"
    integrate_refusal = os.path.join(folder, ".gate-integrate.txt")
    if os.path.isfile(integrate_refusal) and not marks.get(f"wrote:{STAGE_FILES['build']}", 0) > marks.get("fail:integrate", 0):
        report = read_text(integrate_refusal)
        if "gate:fail checkout" in report:
            return "stopped", None, ("the main checkout could not take the story's commit — see .gate-integrate.txt; "
                                     "then `factory.sh run --story " + story_id + " --from integrate`")
        if "gate:fail moved" in report:
            return "in-progress", "integrate", "the main line moved on — the story is merged with it again"
        return "in-progress", "build", "the integrate gate refused the story on the main line — the build stage runs again"
    refused = [stage for stage in STAGE_ORDER
               if os.path.isfile(os.path.join(folder, f".gate-{stage}.txt"))]
    if refused:
        # A refusal over an earlier pass's file — the document gate's `story-pass` — runs on from that stage:
        # running the refused stage again changes nothing it could fix.
        order = STAGE_ORDER[:STAGE_ORDER.index(refused[0])] if refused[0] in STAGE_ORDER else []
        stale = [stage for stage in order
                 if stage not in texts and os.path.isfile(os.path.join(folder, STAGE_FILES[stage]))]
        if stale:
            return "in-progress", stale[0], (f"the {refused[0]} gate refused over an earlier pass's "
                                             f"{STAGE_FILES[stale[0]]} — the story runs on from {stale[0]}")
        # The outcome event is code: the document stage cannot write it, the build can.
        if refused[0] == "document" and "gate:fail outcome" in read_text(os.path.join(folder, ".gate-document.txt")):
            return "in-progress", "build", "the document gate found no outcome event in the code — the build adds it"
        return "in-progress", refused[0], f"the {refused[0]} gate refused — the stage runs again"
    adopt = story_kind(front) == "adopt"
    integrating = has_worktree(story_id, factory_home() or cwd)
    if adopt and verdict_in(texts.get("judge", "")) == "pass":
        if integrating and gate_passed_since(runs, story_id, "adopt", "judge"):
            return "in-progress", "integrate", "the adopt gate passed — its worktree is integrated next"
        return "in-progress", "adopt", "the judge confirmed the tests — the adopt gate delivers it"
    if "document" in texts:
        if integrating and gate_passed_since(runs, story_id, "document", "document"):
            return "in-progress", "integrate", "every gate passed — its worktree is integrated next"
        if story_path:
            with contextlib.suppress(GateError, OSError):
                verdict, rid = acceptance_state(cwd, story_id, story_path)
                if verdict == "accepted":
                    return "resumable", "document", f"{rid} accepted — the document gate delivers it"
        return "in-progress", "document", "document.md is written, its gate has not passed yet"
    if not texts:
        return "ready", "plan", ""
    journey = story_kind(front) == "journey"
    if verdict_in(texts.get("judge", "")) == "changes-requested":
        return "in-progress", "test" if journey or adopt else "build", "the judge requested changes"
    order = ADOPT_ORDER if adopt else JOURNEY_ORDER if journey else STAGE_ORDER
    missing = next(stage for stage in order if stage not in texts)
    return "in-progress", missing, f"{STAGE_FILES[missing]} not written yet"


def story_title(front, body):
    """The story's own name: `title:` in its front matter, else its first heading."""
    if str(front.get("title", "")).strip():
        return str(front["title"]).strip()
    for line in body.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return ""


def mark_window(cwd, runs, story_id, name, edge, session_log=None):
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
        kind = "claude-session" if "/.claude/" in session_log.replace(os.sep, "/") else "codex-session"
    freeze_all(runs)
    with journal_writer(runs, story_id) as handle:
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
        kind = "claude-session" if "/.claude/" in session_log.replace(os.sep, "/") else "codex-session"
    allowed = session_usage_allowed(cwd)
    with journal_writer(runs, story_id) as handle:
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
    deletes after a while. Once read, the numbers are appended as a usage line of their own with the same window and
    no path — the line that pointed at the log stays, and the reader counts a window once, the read line first. The
    journal is only ever appended to, so nothing another writer appends meanwhile is lost."""
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
            continue
        append_event(journal, "usage", event["name"], f"tool={fields.get('tool', '')}", *usage_fields(read).split("\t"),
                     f"window={fields['window']}", at=event["at"])
        frozen.add((event["name"], fields["window"]))


def freeze_all(runs):
    """`freeze_windows` over every story's journal. A story's last stages end its run, so no stage
    start of its own ever comes back to freeze them; the next command that writes anyway — a stage
    of another story, a claim, a release, a listening loop's look — does it for them. Never fails
    the command it rides on."""
    for journal in glob.glob(os.path.join(evidence_dir(runs, "*"), "journal.tsv")):
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


def journal_usage(runs, story_id, resolve=True):
    """{stage: {invocations, measured, input, cache_read, cache_write, output, cost}} from the journal.

    `resolve=False` counts only what the journal carries itself, without opening a session log."""
    journal = os.path.join(evidence_dir(runs, story_id), "journal.tsv")
    stages = {}
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


OUTSIDE_RANKS = {"backlog": -1, "decisions": 98}


def stage_rank(stage):
    """Stage order for reports: the table's run order, the processes beside the stages they carry."""
    if stage in STAGE_ORDER:
        return STAGE_ORDER.index(stage)
    process = "review:" if stage.startswith("review:") else stage
    if process in PROCESS_RANKS:
        anchor, offset = PROCESS_RANKS[process]
        return STAGE_ORDER.index(anchor) + offset
    return OUTSIDE_RANKS.get(stage, 99)


#: What a stage name may look like for the runner: the cli prints the table as shell lines the runner evaluates,
#: so a name is checked to be a plain word before it is printed.
STAGE_WORD = re.compile(r"[a-z][a-z0-9_-]*")


def run_stories(runs):
    """Every story with a run folder or an evidence folder — a story's journal outlives its deleted run folder."""
    folders = (runs, evidence_dir(runs))
    return sorted({d for root in folders if os.path.isdir(root) for d in os.listdir(root)
                   if os.path.isdir(os.path.join(root, d))})


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
    # One claim per main checkout: a stage in a story's worktree renews the runner's claim there, not one of its own.
    if in_worktree(cwd):
        cwd = factory_home()
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
    for story in run_stories(runs):
        journal = os.path.join(evidence_dir(runs, story), "journal.tsv")
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


def schedule_data(cwd, epics, runs, slots=None, busy=()):
    """Every story's state, the order and the next one to run — read off the files, printed by
    `schedule` for the runner and by `status` for a person.

    One story with unfinished code in the checkout at a time: a story past its plan stage that is not
    delivered and has no worktree holds the checkout, because its tests and code are in the working tree
    and a second story would build on them. Such a story is next if it can run, and nothing else starts
    while it cannot. A story that stopped at its plan stage wrote no code, so independent work runs past it.

    With `slots` — the runner, which gives every story a worktree of its own — a story's code is in its
    worktree, so a story that waits holds nothing: up to `slots` stories run at once, `busy` names the ones
    this runner runs already. A story with a worktree goes first (it has code), then the order; between stories
    of one epic the one whose context no running story changes."""
    stories, order = {}, []
    hint = layout_hint(cwd, read_profile(resolve_profile(None, cwd)))
    twice = duplicate_ids(epics)
    for path in story_files(epics):
        name = os.path.basename(story_folder(path))
        epic = os.path.basename(epic_folder(path))
        try:
            front, story_body = read_front_matter(path)
        except GateError as error:
            stories[name] = dict(state="stopped", start=None, detail=str(error), deps=[], path=path,
                                      epic=epic, title="", front={}, body="")
            continue
        story_id = str(front.get("id") or name).strip()
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
                                     os.path.join(runs, story_id, STAGE_FILES["test"]))
                                 and not has_worktree(story_id, factory_home() or cwd),
                                 path=path, epic=str(front.get("epic") or epic).strip(), front=front,
                                 body=story_body, title=story_title(front, story_body))

    # dependency order, ties by the epic's place (an epic's `depends_on:` first, then its id) and then the
    # story's id; whatever is left after that sits on a cycle
    graph = epic_graph(epics)
    ranked, epic_cycle = epic_order(graph)
    rank = {epic: index for index, epic in enumerate(ranked)}
    placed, remaining = set(), sorted(stories, key=lambda s: (rank.get(stories[s]["epic"], len(rank)), s))
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
            else:
                waits = epic_waits(story["epic"], graph, epic_cycle, stories)
                if waits:
                    story.update(state="blocked", start=None, detail=waits)

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
    if slots:
        return slotted(stories, order, holders, slots, busy, factory_home() or cwd, hint)
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
        # A story the runner began in its worktree has its code there: a session in this checkout does not take it up.
        elsewhere = [s for s in order if stories[s]["state"] in RUNNABLE and has_worktree(s, factory_home() or cwd)]
        nxt = None if busy else next((s for s in order if stories[s]["state"] in RUNNABLE and s not in elsewhere), None)
        wait = any(stories[s]["state"] in ("waiting", "running") for s in order)
        if busy:
            reason = f"{busy[0]} is running ({stories[busy[0]]['detail']}) — one story at a time per checkout"
        elif nxt is None and elsewhere:
            reason = (f"{elsewhere[0]} has its code in its worktree — the runner takes it up: "
                      f"factory.sh run --story {elsewhere[0]}")
        elif nxt is None:
            reason = "nothing can run"
    counts = {}
    for story in stories.values():
        counts[story["state"]] = counts.get(story["state"], 0) + 1
    return dict(stories=stories, order=order, next=nxt, reason=reason, wait=wait, counts=counts, hint=hint)


def epic_waits(epic, graph, cycle, stories):
    """Why a story of this epic may not start yet because of its epic's `depends_on:`, or "". An epic it depends on
    is done when it has stories and every one of them is delivered or superseded — an epic without a story has
    not been built, so what depends on it waits."""
    if epic in cycle:
        return f"its epic {epic} is on a dependency cycle between epics: {', '.join(sorted(cycle))}"
    for needed in graph.get(epic, []):
        if needed not in graph:
            return f"its epic {epic} depends on unknown epic {needed}"
        own = [s for s in stories.values() if s.get("epic") == needed and s.get("state") != "superseded"]
        done = sum(1 for s in own if s.get("state") == "delivered")
        if not own or done < len(own):
            return (f"its epic {epic} depends on epic {needed} ({done} of {len(own)} delivered)" if own
                    else f"its epic {epic} depends on epic {needed}, which has no story yet")
    return ""


def slotted(stories, order, holders, slots, busy, cwd, hint):
    """The schedule for a runner with `slots` (WP-92): every story in its worktree, up to `slots` at once."""
    for story_id in busy:
        if story_id in stories and stories[story_id]["state"] not in ("delivered", "superseded"):
            stories[story_id].update(state="running", start=None, detail="in this runner")
    running = [s for s in order if stories[s]["state"] == "running"]
    picked, reason = [], ""
    if holders:
        # A story that began in the checkout before it had a worktree finishes there, alone — as before.
        holder = holders[0]
        if stories[holder]["state"] in RUNNABLE and holder not in busy and not running:
            picked = [holder]
        else:
            reason = (f"{holder} holds unfinished code in the checkout ({stories[holder]['state']}) — "
                      f"no other story starts until it is delivered")
    else:
        context = lambda s: str(stories[s]["front"].get("context", "")).strip()
        coded = lambda s: 0 if has_worktree(s, cwd) else 1
        candidates = sorted((s for s in order if stories[s]["state"] in RUNNABLE and s not in busy),
                            key=lambda s: (coded(s), order.index(s)))
        changing = {context(s) for s in running}
        while candidates and len(picked) + len(running) < slots:
            first = candidates[0]
            peers = [c for c in candidates if (coded(c), stories[c]["epic"]) == (coded(first), stories[first]["epic"])]
            choice = next((c for c in peers if context(c) not in changing), first)
            picked.append(choice)
            candidates.remove(choice)
            changing.add(context(choice))
        if not picked:
            reason = (f"{len(running)} of {slots} slot(s) busy: {', '.join(running)}" if running and len(running) >= slots
                      else "nothing can run")
    counts = {}
    for story in stories.values():
        counts[story["state"]] = counts.get(story["state"], 0) + 1
    wait = any(stories[s]["state"] in ("waiting", "running") for s in order)
    return dict(stories=stories, order=order, next=picked[0] if picked else None, also=picked[1:], reason=reason,
                wait=wait, counts=counts, hint=hint)


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


def schedule(cwd, epics, runs, slots=None, busy=()):
    """Print every story's state and the next one to run; return 0. The runner and the tests read
    these lines (`schedule:`, `wait:`, `next:`): they are a contract, not the person's view. With `slots`,
    one `next:` line per story that may start now."""
    data = schedule_data(cwd, epics, runs, slots, busy)
    stories, order, nxt, reason, wait = data["stories"], data["order"], data["next"], data["reason"], data["wait"]
    if data["hint"]:
        print(f"layout: {data['hint']}")
    for story_id in order:
        story = stories[story_id]
        start = f"from {story['start']}" if story["start"] else ""
        # What the story cost so far, from the runner's journal — kept per story on disk, so a
        # restart, a second session or a new run never resets it. An in-session run writes none.
        journal = os.path.join(evidence_dir(runs, story_id), "journal.tsv")
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
    for also in data.get("also", []):
        print(f"next: {also} {stories[also]['start']}")
    return 0


def start(cwd, epics, runs, story_id, slots=None):
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
    if stage and not slots and has_worktree(story_id, factory_home() or cwd):
        state, stage, detail = "blocked", None, (f"its code is in its worktree — the runner takes it up: "
                                                 f"factory.sh run --story {story_id}")
    holder = next((s for s in data["order"] if data["stories"][s].get("holds")), None)
    if stage and holder and holder != story_id:
        state, stage, detail = "blocked", None, (f"{holder} holds unfinished code in the checkout "
                                                 f"({data['stories'][holder]['state']}) — it is delivered first")
    print(f"state: {state}")
    print(f"start: {stage or 'none'}")
    print(f"detail: {detail}")
    return 0
