"""A story's worktree, step by step: made, linked to the main checkout, brought onto the main line, integrated and removed.

The runner makes, links, integrates and removes a story's worktree through these; every git call is here,
never in the runner, so one reader decides what a worktree is on every platform.
"""

from __future__ import annotations

import contextlib
import os
import re
import shutil
import sys
import typing
from ..pipeline.stage_rows import STAGE_FILES, STAGES
from .....sharedkernel.adapter.outgoing.markdown.front_matter import Front, read_front_matter, read_text
from .....sharedkernel.adapter.outgoing.profile.profile_files import (
    evidence_dir, place, shown, STORY_BRANCH, worktree_places)
from ..claims.remote_claims import claim_config_here, CLAIM_TRAILERS, fetch_remote
from ..files.owned_files import run_owned
from ..files.run_marks import story_title
from ..files.snapshots import listed_files, STAGES_MADE
from ..files.story_layout import find_story, is_delivered, story_files, story_folder, story_kind
from .integration import (
    CONFLICT_MARKER, integration_target, merge_target, rebase_tests_baseline, record_main_tests)
from .repository import git, git_identity
from .worktrees import has_worktree, uncommitted_story, worktree_of, worktrees_dir
from ....domain.model.story import StoryStatus


def link_folder(source: str, link: str) -> typing.Optional[str]:
    """Link the worktree's `link` to the main checkout's folder `source`: a symlink, on Windows without the
    right a junction. Returns how, or None where neither can be made."""
    try:
        os.symlink(source, link, target_is_directory=True)
        return "link"
    except (OSError, NotImplementedError, AttributeError):
        pass
    if os.name == "nt":
        try:
            import _winapi
            getattr(_winapi, "CreateJunction")(source, link)
            return "junction"
        except Exception:                        # no junction either: the caller copies and says so
            pass
    return None


def is_linked(path: str) -> bool:
    """A symlink, or on Windows a junction — something that points elsewhere and goes without its target."""
    if os.path.islink(path):
        return True
    if os.name == "nt" and os.path.isdir(path):
        with contextlib.suppress(OSError, ValueError):
            return bool(os.readlink(path))
    return False


def unlink_folder(path: str) -> None:
    if os.path.islink(path):
        os.unlink(path)
    elif is_linked(path):
        os.rmdir(path)                           # a junction goes, its target stays


def exclude_worktrees(cwd: str) -> None:
    """The worktrees folder is git's business only: kept out of the main checkout's status in `.git/info/exclude`
    (local, never committed — the project's `.gitignore` stays the person's)."""
    code, common = git(cwd, "rev-parse", "--git-common-dir")
    if code != 0 or not common.strip():
        return
    path = os.path.join(cwd, common.strip(), "info", "exclude")
    line = "/" + worktrees_dir().strip("/") + "/"
    text = read_text(path) if os.path.isfile(path) else ""
    if line not in text.splitlines():
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(("" if not text or text.endswith("\n") else "\n") + line + "\n")


def restore_places(path: str) -> None:
    """Before git moves anything in the worktree: the links go, and a place git tracks is as the index has it —
    the branch's, or in a merge the merged one, so a change the main line made there is not taken back."""
    folders, files = worktree_places()
    for rel in folders:
        full = os.path.join(path, rel)
        if is_linked(full):
            unlink_folder(full)
    tracked = [rel for rel in folders + files if git(path, "ls-files", "--", rel)[1].strip()]
    if tracked:
        git(path, "checkout", "--", *tracked)
    for rel in files:
        full = os.path.join(path, rel)
        if rel not in tracked and os.path.isfile(full):
            os.remove(full)                      # a copy of the main checkout's, made by link_places


def link_places(path: str, home: str, runs: str) -> None:
    """The worktree sees what is state through the main checkout: the epics with their records, the run folder,
    the discovery reports, the pipeline and the skills as links; the description and the profile as copies."""
    folders, files = worktree_places()
    copied: typing.List[str] = []
    for rel in folders:
        source, link = os.path.join(home, rel), os.path.join(path, rel)
        if os.path.abspath(source) in (os.path.abspath(runs), os.path.abspath(evidence_dir(runs))):
            os.makedirs(source, exist_ok=True)
        if not os.path.isdir(source):
            continue
        if is_linked(link) and os.path.realpath(link) == os.path.realpath(source):
            continue
        if is_linked(link):
            unlink_folder(link)
        elif os.path.isdir(link):
            shutil.rmtree(link)                  # the branch's copy of a place the main checkout owns
        os.makedirs(os.path.dirname(link) or path, exist_ok=True)
        if not link_folder(source, link):
            shutil.copytree(source, link)
            copied.append(rel)
    for rel in files:
        source, copy = os.path.join(home, rel), os.path.join(path, rel)
        if os.path.isfile(source) and (not os.path.isfile(copy) or read_text(copy) != read_text(source)):
            os.makedirs(os.path.dirname(copy) or path, exist_ok=True)
            shutil.copyfile(source, copy)
    if copied:
        print(f"worktree: no link could be made here — {', '.join(copied)} copied; a decision record a stage "
              f"writes there is not seen by the main checkout", file=sys.stderr)


def write_base(path: str, runs: str, story_id: str, tree: str) -> None:
    """The tree the story's diff is taken against, once the worktree moved onto another base — the main line's tree,
    so what the main line brought in counts as base and only the story's own diff as its change. The tests baseline
    moves with it: a test the main line changed existed before this story as the main line has it."""
    folder = evidence_dir(runs, story_id)
    if os.path.isdir(folder) and tree:
        base_file = os.path.join(folder, "base-tree")
        old = read_text(base_file).strip() if os.path.isfile(base_file) else None
        with open(base_file, "w", encoding="utf-8") as handle:
            handle.write(tree + "\n")
        rebase_tests_baseline(path, runs, story_id, tree, old)


def worktree_prepare(cwd: str, runs: str, story_id: str) -> int:
    """Before a story's stages: its worktree, made where it is not, brought onto the main line where it has no
    commit of its own and nothing of it is in the way, and linked to the main checkout. Prints the worktree's path
    as the last line — or `none — <why>` where the project cannot have one, and the story runs in the checkout."""
    if git(cwd, "rev-parse", "--verify", "--quiet", "HEAD")[0] != 0:
        print("none — the repository has no commit yet, so a story has no branch to start from")
        return 0
    path, branch = worktree_of(story_id, cwd), STORY_BRANCH + story_id
    target_file = os.path.join(evidence_dir(runs, story_id), "target")
    on = git(cwd, "symbolic-ref", "--quiet", "--short", "HEAD")[1].strip()
    exclude_worktrees(cwd)
    if not has_worktree(story_id, cwd):
        known = git(cwd, "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}")[0] == 0
        if not known and os.path.isfile(os.path.join(runs, story_id, STAGE_FILES["test"])) and not is_delivered(
                read_front_matter(find_story(place("epics"), story_id))[0]):
            print(f"none — {story_id} began in the checkout, its tests are there; it finishes there")
            return 0
        if not on:
            print("none — the checkout is on a detached HEAD, so the story has no branch to integrate into")
            return 0
        git(cwd, "worktree", "prune")
        made = git(cwd, "worktree", "add", "--quiet", path, branch) if known \
            else git(cwd, "worktree", "add", "--quiet", "-b", branch, path, "HEAD")
        if made[0] != 0:
            print(f"factory: the worktree for {story_id} could not be made — {made[1]}", file=sys.stderr)
            return 1
        print(f"worktree: {shown(path)} on {branch}, from {on}", file=sys.stderr)
    if not os.path.isfile(target_file):
        os.makedirs(os.path.dirname(target_file), exist_ok=True)
        with open(target_file, "w", encoding="utf-8") as handle:
            handle.write((on or git(path, "rev-parse", "HEAD")[1].strip()) + "\n")
    target = integration_target(runs, story_id)
    restore_places(path)
    # Resumed — after an answer, a restart: the story moves onto the main line as it is now, so what the other
    # stories delivered (a dependency added while it waited among them) is there for its next stage. A branch with no
    # commit of its own fast-forwards; where the story's own change is in the way, or it has a commit, it is merged
    # the way the integrate step merges — one commit on top of the main line. A conflict is named (`conflict:` lines,
    # the list in the evidence folder) and left to the integrate stage, which the runner starts before the stage.
    if git(path, "merge-base", "--is-ancestor", target, "HEAD")[0] != 0:
        own = git(path, "rev-list", "--count", f"{target}..HEAD")[1].strip()
        if own == "0" and git(path, "merge", "--ff-only", "--quiet", target)[0] == 0:
            write_base(path, runs, story_id, git(path, "rev-parse", "HEAD^{tree}")[1].strip())
            print(f"worktree: {story_id} moved onto {target} as it is now", file=sys.stderr)
        else:
            index_story(path, runs, story_id)
            if git(path, "diff", "--cached", "--quiet")[0] != 0:
                git(path, *git_identity(path), "commit", "--no-verify", "--quiet", "-m", f"wip({story_id}): before resuming")
            done = git(path, *git_identity(path), "merge", "--no-ff", "--no-edit", "--no-verify", "--quiet", target)
            conflicted = [p for p in git(path, "diff", "--name-only", "--diff-filter=U")[1].split("\n") if p.strip()]
            if done[0] == 0:
                front, body = read_front_matter(find_story(place("epics"), story_id))
                if squash_story(path, runs, story_id, target, front, body) != 0:
                    return 1
                print(f"worktree: {story_id} merged with {target} as it is now", file=sys.stderr)
            elif conflicted:
                with open(os.path.join(evidence_dir(runs, story_id), CONFLICTS_FILE), "w", encoding="utf-8",
                          newline="\n") as handle:          # read line by line by a shell, on Windows too
                    handle.write("\n".join(conflicted) + "\n")
                record_main_tests(path, runs, story_id, target)
                for conflict in conflicted:
                    print(f"conflict: {conflict}")
                print(f"worktree: {story_id} meets {target} in {', '.join(conflicted)} — the integrate stage resolves "
                      f"it before the next stage", file=sys.stderr)
            else:
                git(path, "merge", "--abort")
                print(f"worktree: {story_id} keeps its base — merging {target} failed ({done[1].strip()[:200]}); the "
                      f"integrate step merges", file=sys.stderr)
    else:
        # Already on the main line — merged by a pipeline before the tests baseline moved with the base: held to the
        # main line's tests now, where the base is the main line's tree.
        base_file = os.path.join(evidence_dir(runs, story_id), "base-tree")
        base = read_text(base_file).strip() if os.path.isfile(base_file) else ""
        if base and base == git(path, "rev-parse", f"{target}^{{tree}}")[1].strip():
            rebase_tests_baseline(path, runs, story_id, base)
    link_places(path, cwd, runs)
    print(os.path.abspath(path).replace("\\", "/"))
    return 0


def worktree_remove(cwd: str, story_id: str) -> int:
    """After the story is integrated: its worktree and its branch go — the commit is on the main line."""
    path, branch = worktree_of(story_id, cwd), STORY_BRANCH + story_id
    if os.path.isdir(path):
        folders, _files = worktree_places()
        for rel in folders:
            if is_linked(os.path.join(path, rel)):
                unlink_folder(os.path.join(path, rel))
        git(cwd, "worktree", "remove", "--force", path)
        if os.path.isdir(path):
            shutil.rmtree(path, ignore_errors=True)
    git(cwd, "worktree", "prune")
    if git(cwd, "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}")[0] == 0:
        git(cwd, "branch", "-D", branch)
    print(f"worktree: {story_id}'s worktree and {branch} removed")
    return 0


def worktree_prune(cwd: str, epics: str) -> int:
    """Worktrees no story will come back to: its story superseded, or no story of that id any more. Nothing
    of them reaches the main line — the story's code goes with its branch."""
    statuses: typing.Dict[str, str] = {}
    for path in story_files(epics):
        front, _body = read_front_matter(path)
        statuses[str(front.get("id") or os.path.basename(story_folder(path))).strip()] = \
            str(front.get("status", "")).strip().lower()
    folder = os.path.join(cwd, worktrees_dir())
    for story_id in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
        if statuses.get(story_id, StoryStatus.SUPERSEDED.value) == StoryStatus.SUPERSEDED.value:
            why = "superseded" if story_id in statuses else "no story of that id"
            print(f"worktree: {story_id} — {why}; its worktree goes, nothing of it is integrated")
            worktree_remove(cwd, story_id)
    return 0


def squash_story(path: str, runs: str, story_id: str, target: str, front: Front, body: str) -> int:
    """The story as one commit on top of the target: `feat(<context>): <title>`, the story's id in the body."""
    if git(path, "rev-parse", "HEAD")[1].strip() != git(path, "rev-parse", target)[1].strip():
        git(path, "reset", "--soft", target)
    if git(path, "diff", "--cached", "--quiet")[0] != 0:
        scope = re.sub(r"[^a-z0-9]+", "-", str(front.get("context", "")).lower()).strip("-") or "story"
        kind = {"story": "feat", "task": "refactor"}.get(story_kind(front), "test")
        message = f"{kind}({scope}): {story_title(front, body) or story_id}\n\nStory: {story_id}\n"
        claimed = os.path.join(evidence_dir(runs, story_id), CLAIM_TRAILERS)
        if os.path.isfile(claimed):
            # The claim's trailers survive the squash: the published branch still says who has the story (WP-93).
            message += read_text(claimed).strip() + "\n"
        done = git(path, *git_identity(path), "commit", "--no-verify", "--quiet", "-m", message)
        if done[0] != 0:
            print(f"factory: the story's commit could not be made — {done[1]}", file=sys.stderr)
            return 1
    write_base(path, runs, story_id, git(path, "rev-parse", f"{target}^{{tree}}")[1].strip())
    head = git(path, "rev-parse", "--short", "HEAD")[1].strip()
    print(f"integrate: {story_id} is {'one commit, ' + head + ',' if head != git(path, 'rev-parse', '--short', target)[1].strip() else 'no commit'} on top of {target}")
    return 0


CONFLICTS_FILE = "conflicts"


def index_story(path: str, runs: str, story_id: str) -> None:
    """Into the index of the story's worktree: every tracked file the story changed or removed, and the untracked
    ones a stage window of the story made (`stages-made.txt`) or a hand-over lists (tests.md's, build.md's, tidy.md's
    files) — the files the gates held to the hand-overs. An untracked file neither names (a gate command's report
    nobody ignored, a file manager's) stays out of the story's commit and is named."""
    git(path, "add", "-u", "--", ".")
    made = os.path.join(evidence_dir(runs, story_id), STAGES_MADE)
    named = {line.strip() for line in read_text(made).splitlines() if line.strip()} if os.path.isfile(made) else set()
    for stage in (s for s in STAGES if s.lists):
        named |= listed_files(os.path.join(runs, story_id, stage.file)) or set()
    untracked = [p for p in git(path, "ls-files", "--others", "--exclude-standard", "-z")[1].split("\0") if p]
    taken = [p for p in untracked if p in named]
    left = [p for p in untracked if p not in named and not run_owned(p, runs)]
    if taken:
        git(path, "add", "--", *taken)
    if left:
        print(f"integrate: left out of {story_id}'s commit, no stage's record names them: {', '.join(left[:8])}"
              f"{' …' if len(left) > 8 else ''}", file=sys.stderr)


def integrate_prepare(cwd: str, runs: str, epics: str, story_id: str) -> int:
    """The integrate step's git half: the story's code committed on its branch, the main line merged in, the
    whole squashed to one commit. Exit 3 with `conflict: <path>` lines where the merge needs a hand; 0 when the
    story is one commit on top of the target."""
    path = worktree_of(story_id, cwd)
    if not has_worktree(story_id, cwd):
        print(f"factory: {story_id} has no worktree to integrate", file=sys.stderr)
        return 1
    config = claim_config_here(cwd)
    if config:
        fetch_remote(cwd, config["remote"])
    target = merge_target(runs, story_id, cwd)
    story_path = find_story(epics, story_id)
    missing = uncommitted_story(cwd, story_path, target, changed=False)
    if missing:
        # The integrated tree takes the backlog from the main line: without the story there, a test that reads the
        # backlog fails on it, and no stage of the story can repair that (#162).
        print(f"factory: {missing} on {target} — the integrated tree would not have it; commit the story on {target}, "
              f"then `factory.sh run --story {story_id} --from integrate`", file=sys.stderr)
        return 1
    front, body = read_front_matter(story_path)
    restore_places(path)
    index_story(path, runs, story_id)
    if git(path, "diff", "--cached", "--quiet")[0] != 0:
        git(path, *git_identity(path), "commit", "--no-verify", "--quiet", "-m", f"wip({story_id}): before integration")
    if git(path, "merge-base", "--is-ancestor", target, "HEAD")[0] != 0:
        done = git(path, *git_identity(path), "merge", "--no-ff", "--no-edit", "--no-verify", "--quiet", target)
        if done[0] != 0:
            conflicted = [p for p in git(path, "diff", "--name-only", "--diff-filter=U")[1].split("\n") if p.strip()]
            if not conflicted:
                print(f"factory: merging {target} into {story_id} failed — {done[1]}", file=sys.stderr)
                return 1
            with open(os.path.join(evidence_dir(runs, story_id), CONFLICTS_FILE), "w", encoding="utf-8",
                      newline="\n") as handle:          # read line by line by a shell, on Windows too
                handle.write("\n".join(conflicted) + "\n")
            record_main_tests(path, runs, story_id, target)
            for conflict in conflicted:
                print(f"conflict: {conflict}")
            return 3
    return squash_story(path, runs, story_id, target, front, body)


def integrate_finish(cwd: str, runs: str, epics: str, story_id: str) -> int:
    """After the conflicts were resolved in the worktree: no marker left in a conflicted file, the merge committed,
    the story squashed. Exit 1, naming the files, while a marker is left."""
    path = worktree_of(story_id, cwd)
    target = merge_target(runs, story_id, cwd)
    listed = os.path.join(evidence_dir(runs, story_id), CONFLICTS_FILE)
    files = [line.strip() for line in read_text(listed).splitlines() if line.strip()] if os.path.isfile(listed) else []
    left: typing.List[str] = []
    for rel in files:
        full = os.path.join(path, rel)
        with contextlib.suppress(OSError, UnicodeDecodeError):
            with open(full, encoding="utf-8") as handle:
                if CONFLICT_MARKER.search(handle.read()):
                    left.append(rel)
    if left:
        print(f"factory: a conflict marker is left in {', '.join(left)} — the merge is not resolved", file=sys.stderr)
        return 1
    restore_places(path)
    index_story(path, runs, story_id)
    done = git(path, *git_identity(path), "commit", "--no-verify", "--quiet", "--no-edit")
    if done[0] != 0 and git(path, "diff", "--name-only", "--diff-filter=U")[1].strip():
        print(f"factory: the merge could not be committed — {done[1]}", file=sys.stderr)
        return 1
    with contextlib.suppress(OSError):
        os.remove(listed)
    front, body = read_front_matter(find_story(epics, story_id))
    return squash_story(path, runs, story_id, target, front, body)
