"""The checkout's tree as a stage left it: snapshots, the files a stage changed, and the ones its hand-over lists."""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
import typing
from ..pipeline.stage_rows import STAGE_ORDER
from .....sharedkernel.adapter.outgoing.profile.profile_files import evidence_dir, evidence_rel
from .....sharedkernel.adapter.outgoing.markdown.front_matter import read_text
from .owned_files import run_owned


DELETED = "deleted"


#: The paths every stage window of a pass changed, one per line: what the story's commit takes of the untracked files.
STAGES_MADE = "stages-made.txt"


#: The first line of a snapshot or a changed-files record that carries no observation, and says why.
NOT_OBSERVED = "# not observed: "


def tree_snapshot(cwd: str) -> typing.Optional[typing.Dict[str, str]]:
    """{path: sha256 or `deleted`} of every file under `cwd` that git reports as differing from HEAD —
    or None outside a repository: an empty snapshot would read as "nothing changed", the strongest
    claim a record can make, from no evidence at all."""
    listing = subprocess.run(["git", "-c", "core.fileMode=false", "status", "--porcelain", "-z", "-uall", "--", "."],
                             cwd=cwd, capture_output=True)
    files: typing.Dict[str, str] = {}
    if listing.returncode != 0:
        return None
    prefix = subprocess.run(["git", "rev-parse", "--show-prefix"], cwd=cwd, capture_output=True,
                            text=True).stdout.strip()
    local = lambda path: path[len(prefix):] if prefix and path.startswith(prefix) else path
    # the story journals are committed (WP-150), and the pipeline appends to them all the time: no one's change
    protocol = evidence_rel().rstrip("/") + "/"
    entries = iter(listing.stdout.decode("utf-8", "replace").split("\0"))
    for entry in entries:
        code, path = entry[:2], local(entry[3:])
        if not path or path.startswith(protocol):
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


def write_snapshot(cwd: str, runs: str, story_id: str, label: str) -> None:
    folder = evidence_dir(runs, story_id)
    os.makedirs(folder, exist_ok=True)
    snapshot = tree_snapshot(cwd)
    with open(os.path.join(folder, f"tree-{label}.txt"), "w", encoding="utf-8") as handle:
        if snapshot is None:
            handle.write(NOT_OBSERVED + "not a git repository, so the tree cannot be compared\n")
            return
        for path, digest in sorted(snapshot.items()):
            handle.write(f"{digest}  {path}\n")


def load_snapshot(path: str) -> typing.Optional[typing.Dict[str, str]]:
    """{path: digest} from a snapshot file, or None when there is none (or it carries no digests)."""
    if not os.path.isfile(path):
        return None
    files: typing.Dict[str, str] = {}
    for line in read_text(path).splitlines():
        if line.startswith("#"):
            return None
        digest, _, name = line.partition("  ")
        if name:
            files[name] = digest
    return files


def snapshot_reason(path: str) -> typing.Optional[str]:
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


def tracked_files(cwd: str) -> typing.Set[str]:
    listing = subprocess.run(["git", "ls-files", "-z"], cwd=cwd, capture_output=True)
    return set(listing.stdout.decode("utf-8", "replace").split("\0")) if listing.returncode == 0 else set()


def changes_between(before: typing.Mapping[str, str], after: typing.Mapping[str, str], runs: str,
                    tracked: typing.AbstractSet[str] = frozenset()) -> typing.List[typing.Tuple[str, str]]:
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


def git_tree(cwd: str) -> typing.Optional[str]:
    """A tree object of the project as it is — `git add -A` into a throwaway index, never a commit. The index starts
    as HEAD's, so a file git tracks although the ignore rules name it (an editor's settings committed on purpose)
    stays in the tree as it is in a commit's: the base a worktree takes from the main line is a commit's tree, and an
    empty index would drop the file and count it removed by the story."""
    import tempfile
    with tempfile.TemporaryDirectory() as scratch:
        env = dict(os.environ, GIT_INDEX_FILE=os.path.join(scratch, "index"))
        if subprocess.run(["git", "rev-parse", "--verify", "--quiet", "HEAD"], cwd=cwd, capture_output=True).returncode == 0:
            subprocess.run(["git", "read-tree", "HEAD"], cwd=cwd, env=env, capture_output=True)
        if subprocess.run(["git", "add", "-A", "--", "."], cwd=cwd, env=env, capture_output=True).returncode != 0:
            return None
        tree = subprocess.run(["git", "write-tree"], cwd=cwd, env=env, capture_output=True, text=True)
        return tree.stdout.strip() if tree.returncode == 0 and tree.stdout.strip() else None


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


def record_base(cwd: str, runs: str, story_id: str) -> None:
    """At a story's first stage: the tree the story's diff is taken against. Written once."""
    folder = evidence_dir(runs, story_id)
    os.makedirs(folder, exist_ok=True)
    base = os.path.join(folder, "base-tree")
    if not os.path.isfile(base):
        tree = git_tree(cwd)
        with open(base, "w", encoding="utf-8") as handle:
            handle.write((tree or "none") + "\n")


def record_changes(cwd: str, runs: str, story_id: str, stage: str) -> None:
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
