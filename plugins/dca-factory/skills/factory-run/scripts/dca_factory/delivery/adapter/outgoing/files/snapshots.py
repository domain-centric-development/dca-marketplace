"""The checkout's tree at a window's edges: one observation per edge (WP-202), the files a stage and the story changed
read from them, and the ones a hand-over lists."""

from __future__ import annotations

import enum
import hashlib
import os
import re
import shutil
import subprocess
import tempfile
import typing
from ..pipeline.stage_rows import stage_order
from .....sharedkernel.adapter.outgoing.profile.profile_files import evidence_dir, evidence_rel
from .....sharedkernel.adapter.outgoing.markdown.front_matter import read_text
from .owned_files import run_owned
from ..git.checkout import Checkout, Checkouts
from ....domain.model.project_path import ProjectPath
from ....domain.model.tree_observation import (
    DELETED as DELETED_DIGEST, Digest, Hashing, ObjectName, ObservedFile, TreeChange, TreeObservation, UNHASHED)


DELETED = DELETED_DIGEST.value


#: The paths every stage window of a pass changed, one per line: what the story's commit takes of the untracked files.
STAGES_MADE = "stages-made.txt"


#: The first line of an observation or a changed-files record that carries no observation, and says why.
NOT_OBSERVED = "# not observed: "
#: The first line of an observation taken without content digests (`FACTORY_SHA256=none`): names only. The observer
#: reads such a file as absent — placeholder digests compare equal and would read as "nothing changed".
NO_HASHES = "# no-sha256-command: names only, no content hashes"
#: The header lines of an observation, and the line after which its untracked paths follow.
HEAD_LINE, TREE_LINE, UNTRACKED_LINE = "# head ", "# tree ", "# untracked"
#: The tree the story's diff is taken against: the tree at its first window's start.
BASE_TREE = "base-tree"


class Edge(enum.Enum):
    """Which edge of a window an observation is taken at — the word in its file name."""

    START = "before"
    END = "after"


def take_tree(cwd: str, checkouts: typing.Optional[Checkouts] = None) -> typing.Optional[str]:
    """A tree object of the project as it is — `git add -A` into a throwaway index, never a commit. The index starts
    as a copy of the checkout's, so a file git tracks although the ignore rules name it (an editor's settings committed
    on purpose) stays in the tree as it is in a commit's, and git hashes only what changed since the checkout's index
    saw it: the base a worktree takes from the main line is a commit's tree, and an empty index would drop the file and
    count it removed by the story."""
    place = (checkouts or Checkouts()).at(cwd)
    if place is None:
        return None
    with tempfile.TemporaryDirectory() as scratch:
        index = os.path.join(scratch, "index")
        env = dict(os.environ, GIT_INDEX_FILE=index)
        try:
            shutil.copyfile(place.index_file, index)
        except OSError:
            subprocess.run(["git", "read-tree", "HEAD"], cwd=cwd, env=env, capture_output=True)   # no HEAD: stays empty
        if subprocess.run(["git", "add", "-A", "--", "."], cwd=cwd, env=env, capture_output=True).returncode != 0:
            return None
        tree = subprocess.run(["git", "write-tree"], cwd=cwd, env=env, capture_output=True, text=True)
        return tree.stdout.strip() if tree.returncode == 0 and tree.stdout.strip() else None


def git_tree(cwd: str, checkouts: typing.Optional[Checkouts] = None) -> typing.Optional[str]:
    """The tree of the project now, between two edges — a gate inside an open window, the red tree at the test gate."""
    return take_tree(cwd, checkouts)


class Take(enum.Enum):
    """Whether an observation takes the tree object too — at a window's end, and at a start with no base yet."""

    FILES = "files"
    WITH_TREE = "files and tree"


def observe(cwd: str, tree: Take, hashing: Hashing = Hashing.HASHED,
            checkouts: typing.Optional[Checkouts] = None) -> typing.Optional[TreeObservation]:
    """The working tree now: every file under `cwd` git reports as differing from HEAD, with its sha256 or `deleted`,
    whether git tracks it, HEAD — and the tree object where `tree` asks for it. None outside a repository: an empty
    observation would read as "nothing changed", the strongest claim a record can make, from no evidence at all.
    `checkouts` are the run's, so a run asks git where the folder sits once per checkout (WP-202)."""
    listing = subprocess.run(["git", "-c", "core.fileMode=false", "status", "--porcelain=v2", "--branch", "-z",
                              "-uall", "--", "."], cwd=cwd, capture_output=True)
    if listing.returncode != 0:
        return None
    checkouts = checkouts if checkouts is not None else Checkouts()
    place: typing.Optional[Checkout] = checkouts.at(cwd)       # asked only once `status` found a repository
    prefix = place.prefix if place else ""
    local = lambda path: path[len(prefix):] if prefix and path.startswith(prefix) else path
    # the story journals are committed (WP-150), and the pipeline appends to them all the time: no one's change
    protocol = evidence_rel().rstrip("/") + "/"
    files: typing.Dict[str, ObservedFile] = {}
    head: typing.Optional[ObjectName] = None

    def seen(path: str, tracked: bool, code: str) -> None:
        """One listed path; `code` is git's two-letter state, a `D` in it a file gone from the working tree."""
        if not path or path.startswith(protocol):
            return
        full = os.path.join(cwd, path)
        if "D" in code:
            files[path] = ObservedFile(ProjectPath(path), DELETED_DIGEST, tracked)
        elif os.path.isfile(full):
            files[path] = ObservedFile(ProjectPath(path), digest_of(full) if hashing is Hashing.HASHED else UNHASHED,
                                       tracked)
    entries = iter(listing.stdout.decode("utf-8", "replace").split("\0"))
    for entry in entries:
        if entry.startswith("# branch.oid "):
            oid = entry[len("# branch.oid "):].strip()
            head = ObjectName(oid) if oid and oid != "(initial)" else None
        elif entry.startswith("? "):
            seen(local(entry[2:]), False, "??")
        elif entry[:2] in ("1 ", "u "):
            fields = entry.split(" ", 8 if entry[0] == "1" else 10)
            seen(local(fields[-1]), True, fields[1])
        elif entry.startswith("2 "):
            fields = entry.split(" ", 9)
            origin = local(next(entries, ""))       # -z writes a rename's source as the next entry
            if fields[1][0] == "R" and origin and not origin.startswith(protocol):
                files[origin] = ObservedFile(ProjectPath(origin), DELETED_DIGEST, True)
            seen(local(fields[-1]), True, fields[1])
    taken = take_tree(cwd, checkouts) if tree is Take.WITH_TREE and place else None
    return TreeObservation(tuple(files[path] for path in sorted(files)), head,
                           ObjectName(taken) if taken else None, hashing)


def digest_of(path: str) -> Digest:
    with open(path, "rb") as handle:
        return Digest(hashlib.sha256(handle.read()).hexdigest())


def tree_snapshot(cwd: str) -> typing.Optional[typing.Dict[str, str]]:
    """{path: sha256 or `deleted`} of every file under `cwd` that git reports as differing from HEAD, now — or None
    outside a repository."""
    seen = observe(cwd, Take.FILES)
    return digest_map(seen) if seen is not None else None


def digest_map(seen: TreeObservation) -> typing.Dict[str, str]:
    """{path: digest} as the snapshot's readers take it."""
    return {f.place.value: f.digest.value for f in seen.files}


def write_observation(path: str, seen: typing.Optional[TreeObservation]) -> None:
    """One file per edge: the header (HEAD, the tree), the tracked paths, then the untracked ones — `<digest>  <path>`
    per line, the snapshot's shape, so a reader of digests reads it as it always did."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        if seen is None:
            handle.write(NOT_OBSERVED + "not a git repository, so the tree cannot be compared\n")
            return
        lines = [NO_HASHES] if seen.hashing is Hashing.NAMES_ONLY else []
        lines += [HEAD_LINE + (seen.head.value if seen.head else "none"),
                  TREE_LINE + (seen.tree.value if seen.tree else "none")]
        lines += [f"{f.digest.value}  {f.place.value}" for f in seen.files if f.tracked]
        untracked = [f"{f.digest.value}  {f.place.value}" for f in seen.files if not f.tracked]
        lines += [UNTRACKED_LINE] + untracked if untracked else []
        handle.write("".join(line + "\n" for line in lines))


def read_observation(path: str) -> typing.Optional[TreeObservation]:
    """The observation an edge's file holds, or None when there is none or it carries none (outside git). A file an
    older release wrote (no HEAD line) reads with every path tracked; `legacy` tells the record so."""
    if not os.path.isfile(path):
        return None
    head: typing.Optional[ObjectName] = None
    tree: typing.Optional[ObjectName] = None
    hashing, tracked = Hashing.HASHED, True
    files = []
    for line in read_text(path).splitlines():
        if line.startswith(NOT_OBSERVED):
            return None
        if line.startswith(NO_HASHES.split(":")[0]):
            hashing = Hashing.NAMES_ONLY
        elif line.startswith(HEAD_LINE) or line.startswith(TREE_LINE):
            value = line.split(" ", 2)[2].strip()
            name = ObjectName(value) if value and value != "none" else None
            head, tree = (name, tree) if line.startswith(HEAD_LINE) else (head, name)
        elif line == UNTRACKED_LINE:
            tracked = False
        else:
            digest, _, name_ = line.partition("  ")
            if name_:
                files.append(ObservedFile(ProjectPath(name_), Digest(digest), tracked))
    return TreeObservation(tuple(files), head, tree, hashing)


def legacy(path: str) -> bool:
    """An observation an older release wrote: a snapshot without its HEAD line, whose tracked paths are not marked."""
    return os.path.isfile(path) and not any(line.startswith(HEAD_LINE) for line in read_text(path).splitlines())


def load_snapshot(path: str) -> typing.Optional[typing.Dict[str, str]]:
    """{path: digest} from an observation's file, or None when there is none (or it carries no digests)."""
    seen = read_observation(path)
    return digest_map(seen) if seen is not None and seen.hashing is Hashing.HASHED else None


def snapshot_reason(path: str) -> typing.Optional[str]:
    """Why an observation (or a changed-files record) carries none, from its first line; None when it is a real one or
    there is none."""
    if not os.path.isfile(path):
        return None
    first = (read_text(path).splitlines() or [""])[0]
    if first.startswith(NOT_OBSERVED):
        return first[len(NOT_OBSERVED):].strip()
    if first.startswith(NO_HASHES.split(":")[0]):
        return first.lstrip("# ").strip()
    return None


def observation_path(folder: str, edge: Edge, window: str) -> str:
    return os.path.join(folder, f"tree-{edge.value}-{window}.txt")


def observe_edge(cwd: str, folder: str, edge: Edge, window: str, hashing: Hashing = Hashing.HASHED,
                 checkouts: typing.Optional[Checkouts] = None) -> None:
    """The one observation of a window's edge, kept in the story's evidence folder. The end takes the tree the record
    reads; a start takes one only where the story has no base yet, and the base is written from it."""
    os.makedirs(folder, exist_ok=True)
    base = os.path.join(folder, BASE_TREE)
    needs_base = edge is Edge.START and not os.path.isfile(base)
    seen = observe(cwd, Take.WITH_TREE if edge is Edge.END or needs_base else Take.FILES, hashing, checkouts)
    write_observation(observation_path(folder, edge, window), seen)
    if needs_base:
        with open(base, "w", encoding="utf-8") as handle:
            handle.write((seen.tree.value if seen is not None and seen.tree else "none") + "\n")


def tracked_files(cwd: str) -> typing.Set[str]:
    listing = subprocess.run(["git", "ls-files", "-z"], cwd=cwd, capture_output=True)
    return set(listing.stdout.decode("utf-8", "replace").split("\0")) if listing.returncode == 0 else set()


def tree_changes(cwd: str, base: str, now: str, runs: str) -> typing.Optional[typing.List[typing.Tuple[str, str]]]:
    """[(kind, path)] between two trees, relative to the project, the run's own files left out."""
    listing = subprocess.run(["git", "diff", "--name-status", "-z", "--no-renames", "--relative", base, now, "--", "."],
                             cwd=cwd, capture_output=True)
    if listing.returncode != 0:
        return None
    fields = listing.stdout.decode("utf-8", "replace").split("\0")
    kinds = {"A": "added", "D": "removed"}
    return [(kinds.get(code[:1], "modified"), path) for code, path in zip(fields[0::2], fields[1::2])
            if path and not run_owned(path, runs)]


def story_change(cwd: str, base: str, now: str, runs: str
                 ) -> typing.Optional[typing.Tuple[typing.List[typing.Tuple[str, str]], str]]:
    """The story's rows and its diff between two trees, in one `git diff --raw -p`: a raw line per path, then one
    section per path in the same order — the run's own files left out of both. None where git answers otherwise
    (a quoted path, a section count that does not match): the caller asks the two questions apart."""
    done = subprocess.run(["git", "-c", "core.quotePath=false", "diff", "--no-color", "--relative", "--raw", "-p",
                           base, now, "--", "."], cwd=cwd, capture_output=True)
    if done.returncode != 0:
        return None
    text = done.stdout.decode("utf-8", "replace")
    lines = text.split("\n")
    raw = []
    at = 0
    while at < len(lines) and lines[at].startswith(":"):
        meta, _, paths = lines[at].partition("\t")
        names = paths.split("\t")
        if any(name.startswith('"') for name in names):
            return None
        raw.append((meta.split()[-1], names))
        at += 1
    sections: typing.List[typing.List[str]] = []
    for line in lines[at:]:
        if line.startswith("diff --git "):
            sections.append([])
        if sections:
            sections[-1].append(line)
    if len(sections) != len(raw):
        return None
    kinds = {"A": "added", "D": "removed"}
    rows: typing.List[typing.Tuple[str, str]] = []
    kept: typing.List[str] = []
    for (code, names), section in zip(raw, sections):
        if code[:1] in "RC":
            parts = ([("removed", names[0])] if code[:1] == "R" else []) + [("added", names[-1])]
        else:
            parts = [(kinds.get(code[:1], "modified"), names[0])]
        own = [(kind, path) for kind, path in parts if not run_owned(path, runs)]
        rows += own
        if own:
            kept.append("\n".join(section))
    rows.sort(key=lambda row: row[1])
    diff = "\n".join(kept)
    return rows, (diff if not diff or diff.endswith("\n") else diff + "\n")


def record_base(cwd: str, runs: str, story_id: str, checkouts: typing.Optional[Checkouts] = None) -> None:
    """`--record-base`: the tree the story's diff is taken against, where no window's start wrote it yet. Written
    once."""
    folder = evidence_dir(runs, story_id)
    os.makedirs(folder, exist_ok=True)
    base = os.path.join(folder, BASE_TREE)
    if not os.path.isfile(base):
        tree = git_tree(cwd, checkouts)
        with open(base, "w", encoding="utf-8") as handle:
            handle.write((tree or "none") + "\n")


def head_changes(cwd: str, before: TreeObservation, after: TreeObservation) -> typing.Dict[ProjectPath, TreeChange]:
    """The paths HEAD itself changed inside the window — a window that committed: empty while HEAD stood."""
    if not before.head or not after.head or not after.head_moved_from(before):
        return {}
    listing = subprocess.run(["git", "diff", "--name-status", "-z", "--no-renames", "--relative", before.head.value,
                              after.head.value, "--", "."], cwd=cwd, capture_output=True)
    if listing.returncode != 0:
        return {}
    fields = listing.stdout.decode("utf-8", "replace").split("\0")
    kinds = {"A": TreeChange.ADDED, "D": TreeChange.REMOVED}
    return {ProjectPath(path): kinds.get(code[:1], TreeChange.MODIFIED) for code, path in zip(fields[0::2], fields[1::2])
            if path}


def with_tracking(seen: TreeObservation, tracked: typing.AbstractSet[str]) -> TreeObservation:
    """An older release's observation, its paths marked tracked or not by the checkout's index."""
    return TreeObservation(tuple(ObservedFile(f.place, f.digest, f.place.value in tracked) for f in seen.files),
                           seen.head, seen.tree, seen.hashing)


def record_changes(cwd: str, runs: str, story_id: str, stage: str) -> None:
    """`changed-<stage>.txt`, the story's `changed.txt` and `story.diff`, after a stage has ended — read from the
    window's two observations and the base, with no observation of its own."""
    folder = evidence_dir(runs, story_id)
    after_path, before_path = observation_path(folder, Edge.END, stage), observation_path(folder, Edge.START, stage)
    after, before = read_observation(after_path), read_observation(before_path)
    if after is None or before is None or Hashing.NAMES_ONLY in (after.hashing, before.hashing):
        # An observation that carries none (outside git, or without a digest) says why in its first line; the record
        # repeats it, so the gate skips the files check and names the reason instead of passing an empty record as
        # "nothing changed".
        reason = snapshot_reason(after_path) or snapshot_reason(before_path)
        if reason:
            for name in (f"changed-{stage}.txt", "changed.txt"):
                with open(os.path.join(folder, name), "w", encoding="utf-8") as handle:
                    handle.write(NOT_OBSERVED + reason + "\n")
            with open(os.path.join(folder, "story.diff"), "w", encoding="utf-8") as handle:
                handle.write(f"# no diff: {reason}\n")
        return
    if legacy(after_path) or legacy(before_path):
        tracked = tracked_files(cwd)
        after, before = with_tracking(after, tracked), with_tracking(before, tracked)
    rows = [(row.change.value, row.place.value) for row in after.changes_since(before, head_changes(cwd, before, after))
            if not run_owned(row.place.value, runs)]
    with open(os.path.join(folder, f"changed-{stage}.txt"), "w", encoding="utf-8") as handle:
        handle.writelines(f"{kind}\t{path}\n" for kind, path in rows)
    # Every path a stage window of this pass changed, kept across rounds: a later round's record of the same stage
    # replaces the earlier one, and a file the first round made would drop out of the story's commit with it.
    made = os.path.join(folder, STAGES_MADE)
    known = set(read_text(made).splitlines()) if os.path.isfile(made) else set()
    with open(made, "w", encoding="utf-8") as handle:
        handle.writelines(f"{path}\n" for path in sorted(known | {path for _kind, path in rows}))
    base_file = os.path.join(folder, BASE_TREE)
    base = read_text(base_file).strip() if os.path.isfile(base_file) else "none"
    now = after.tree.value if after.tree and base != "none" else None
    change = story_change(cwd, base, now, runs) if now else None
    story_rows: typing.Optional[typing.List[typing.Tuple[str, str]]] = change[0] if change else None
    diff: typing.Optional[str] = change[1] if change else None
    if change is None and now:
        story_rows = tree_changes(cwd, base, now, runs)
        paths = [path for _, path in story_rows or []]
        done = subprocess.run(["git", "diff", "--no-color", "--relative", base, now, "--"] + paths, cwd=cwd,
                              capture_output=True, text=True, encoding="utf-8", errors="replace") if paths else None
        diff = done.stdout if done and done.returncode == 0 else ""
    if story_rows is None:
        first = next((seen for seen in (read_observation(observation_path(folder, Edge.START, name))
                                        for name in stage_order()) if seen is not None
                      and seen.hashing is Hashing.HASHED), before)
        story_rows = [(row.change.value, row.place.value) for row in after.changes_since(first)
                      if not run_owned(row.place.value, runs)]
    with open(os.path.join(folder, "changed.txt"), "w", encoding="utf-8") as handle:
        handle.writelines(f"{kind}\t{path}\n" for kind, path in story_rows)
    diff_path = os.path.join(folder, "story.diff")
    if base == "none" or not now:
        with open(diff_path, "w", encoding="utf-8") as handle:
            handle.write("# no diff: the project is not a git repository, or no base tree was recorded — "
                         "changed.txt lists the files\n")
        return
    with open(diff_path, "w", encoding="utf-8") as handle:
        handle.write(diff or "")


def listed_files(handover: str) -> typing.Optional[typing.Set[str]]:
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
