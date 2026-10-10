"""What the runner asks before and between stages — its stage arrays, a story's worktree, the skeletons.

The shell tables the runner reads once at its start, the worktree a story runs in (prepare, link, squash,
integrate, remove), the layout migration an update runs, and the skeleton of every stage file the runner
writes before a stage.
"""

import argparse
import contextlib
import glob
import hashlib
import os
import re
import secrets
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
from .contract import (
    ALL_KINDS, CONTRACT, DECISIONS_DIR, DEFAULTS, evidence_dir, evidence_rel, find_story, FINDINGS_FILE, flat_stories,
    GateError, git, is_delivered, MAPPING_ROW, NOTHING, place, PROFILE_FILE, read_front_matter, read_profile, read_text,
    record_path, resolve_profile, SELECTOR, set_places, SHARED_WINDOWS, shown, STAGE, STAGE_FILES, STAGE_ORDER, STAGES,
    STORY_BRANCH, story_digest, STORY_FILE, story_files, story_folder, story_kind, worktree_places, decisions_store,
    needs_human_ids)
from .reports import (
    tokens_of, usage_lines)
from .state import (
    back_in, git_tree, has_worktree, journal_usage, journal_writer, listed_files, run_owned, run_stories, snapshot_reason, start_of,
    STAGE_WORD, STAGES_MADE, STORY_DIGEST, story_title, tree_changes, verdict_in, worktree_of, worktrees_dir,
    write_mark, write_story_fields)
from .gate import (
    BUILT_IN_PERSPECTIVES, CLAUSES_MARKER, CONFLICT_MARKER, contract_of, criteria_of, HANDOVER_BUDGET,
    integration_target, INVARIANTS_MARKER, perspectives_of, plan_invariants, plan_proposals, read_clause_rows,
    read_invariant_rows, scenario_clauses, TESTS_BASELINE)
from .tools import (
    isolation_args, TOOL, tool_command, TOOLS, tools_shell)


FILE_WORD = re.compile(r"[a-z0-9][a-z0-9_.-]*")


def stage_names(kind=None, window=None, every=False):
    """The table's stage names in its order: the run order (every row with `every`), narrowed to the stages a story
    of `kind` runs and to those `window` carries."""
    return [s.name for s in STAGES if (every or s.in_order) and (kind is None or kind in s.kinds)
            and (window is None or s.window == window)]


def stages_shell(places=()):
    """The table as the runner reads it once at its start, one bash assignment per line: the run order, the steps
    after it, each shared window's stages, which gate runs before and which after its stage, the stages whose gate
    runs the mapped tests without the suite, the stages under the guard, which kind runs which row, the hand-over each stage writes — and the
    places asked for, quoted. Every name is the table's, checked to be a plain word; nothing is read from a file."""
    names = [s.name for s in STAGES] + list(SHARED_WINDOWS) + list(ALL_KINDS)
    bad = [name for name in names if not STAGE_WORD.fullmatch(name)]
    bad += [file for file in STAGE_FILES.values() if not FILE_WORD.fullmatch(file)]
    if bad:
        print(f"factory-cli: the stage table holds a name the runner cannot take as a word: {', '.join(bad)}",
              file=sys.stderr)
        return 2
    array = lambda name, values: f"{name}=({' '.join(values)})"
    lines = [array("STAGES", STAGE_ORDER), array("STEPS", [s.name for s in STAGES if not s.in_order])]
    lines += [array(f"{window.upper().replace('-', '_')}_STAGES", stages) for window, stages in SHARED_WINDOWS.items()]
    lines += [array("PRE_GATED", [s.name for s in STAGES if s.in_order and s.gated and not s.post_gated]),
              array("POST_GATED", [s.name for s in STAGES if s.in_order and s.post_gated]),
              array("RED_STAGES", [s.name for s in STAGES if s.in_order and s.tested and not s.suite]),
              array("GUARDED_STAGES", [s.name for s in STAGES if s.guarded])]
    lines.append("KIND_STAGES=' " + " ".join(f"{kind}:{s.name}" for s in STAGES for kind in s.kinds) + " '")
    lines.append("STAGE_FILES=' " + " ".join(f"{name}:{file}" for name, file in STAGE_FILES.items()) + " '")
    tools = tools_shell()
    if tools is None:
        return 2
    lines += tools + [f"PLACE_{key.upper()}={shlex.quote(place(key))}" for key in places]
    print("\n".join(lines))
    return 0


# --- a story's worktree (WP-92) --------------------------------------------------------------------------
# The runner makes, links, integrates and removes a story's worktree through these; every git call is here,
# never in the runner, so one reader decides what a worktree is on every platform.

def link_folder(source, link):
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
            _winapi.CreateJunction(source, link)
            return "junction"
        except Exception:                        # no junction either: the caller copies and says so
            pass
    return None


def is_linked(path):
    """A symlink, or on Windows a junction — something that points elsewhere and goes without its target."""
    if os.path.islink(path):
        return True
    if os.name == "nt" and os.path.isdir(path):
        with contextlib.suppress(OSError, ValueError):
            return bool(os.readlink(path))
    return False


def unlink_folder(path):
    if os.path.islink(path):
        os.unlink(path)
    elif is_linked(path):
        os.rmdir(path)                           # a junction goes, its target stays


def git_identity(cwd):
    """`-c user.name=… -c user.email=…` where the repository names no committer — a factory commit must not
    fail on a machine that never committed."""
    if git(cwd, "config", "user.email")[1].strip():
        return []
    return ["-c", "user.name=dca-factory", "-c", "user.email=dca-factory@localhost"]


def exclude_worktrees(cwd):
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


def restore_places(path):
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


def link_places(path, home, runs):
    """The worktree sees what is state through the main checkout: the epics with their records, the run folder,
    the discovery reports, the pipeline and the skills as links; the description and the profile as copies."""
    import shutil
    folders, files = worktree_places()
    copied = []
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


def write_base(runs, story_id, tree):
    """The tree the story's diff is taken against, once the worktree moved onto another base."""
    folder = evidence_dir(runs, story_id)
    if os.path.isdir(folder) and tree:
        with open(os.path.join(folder, "base-tree"), "w", encoding="utf-8") as handle:
            handle.write(tree + "\n")


def worktree_prepare(cwd, runs, story_id):
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
    # Resumed after waiting: a branch with no commit of its own moves onto the main line as it is now — what the
    # other stories delivered is there for its next stage. Git refuses where the story's changes are in the way;
    # then it keeps its base, and the integrate step merges.
    own = git(path, "rev-list", "--count", f"{target}..HEAD")[1].strip()
    if own == "0" and git(path, "rev-parse", "HEAD")[1].strip() != git(path, "rev-parse", target)[1].strip():
        if git(path, "merge", "--ff-only", "--quiet", target)[0] == 0:
            write_base(runs, story_id, git(path, "rev-parse", "HEAD^{tree}")[1].strip())
            print(f"worktree: {story_id} moved onto {target} as it is now", file=sys.stderr)
        else:
            print(f"worktree: {story_id} keeps its base — {target} changed what the story changes; the integrate "
                  f"step merges", file=sys.stderr)
    link_places(path, cwd, runs)
    print(os.path.abspath(path).replace("\\", "/"))
    return 0


def worktree_remove(cwd, story_id):
    """After the story is integrated: its worktree and its branch go — the commit is on the main line."""
    import shutil
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


def worktree_prune(cwd, epics):
    """Worktrees no story will come back to: its story superseded, or no story of that id any more. Nothing
    of them reaches the main line — the story's code goes with its branch."""
    statuses = {}
    for path in story_files(epics):
        front, _body = read_front_matter(path)
        statuses[str(front.get("id") or os.path.basename(story_folder(path))).strip()] = \
            str(front.get("status", "")).strip().lower()
    folder = os.path.join(cwd, worktrees_dir())
    for story_id in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
        if statuses.get(story_id, "superseded") == "superseded":
            why = "superseded" if story_id in statuses else "no story of that id"
            print(f"worktree: {story_id} — {why}; its worktree goes, nothing of it is integrated")
            worktree_remove(cwd, story_id)
    return 0


def squash_story(path, runs, story_id, target, front, body):
    """The story as one commit on top of the target: `feat(<context>): <title>`, the story's id in the body."""
    if git(path, "rev-parse", "HEAD")[1].strip() != git(path, "rev-parse", target)[1].strip():
        git(path, "reset", "--soft", target)
    if git(path, "diff", "--cached", "--quiet")[0] != 0:
        scope = re.sub(r"[^a-z0-9]+", "-", str(front.get("context", "")).lower()).strip("-") or "story"
        kind = "feat" if story_kind(front) == "story" else "test"
        message = f"{kind}({scope}): {story_title(front, body) or story_id}\n\nStory: {story_id}\n"
        done = git(path, *git_identity(path), "commit", "--no-verify", "--quiet", "-m", message)
        if done[0] != 0:
            print(f"factory: the story's commit could not be made — {done[1]}", file=sys.stderr)
            return 1
    write_base(runs, story_id, git(path, "rev-parse", f"{target}^{{tree}}")[1].strip())
    head = git(path, "rev-parse", "--short", "HEAD")[1].strip()
    print(f"integrate: {story_id} is {'one commit, ' + head + ',' if head != git(path, 'rev-parse', '--short', target)[1].strip() else 'no commit'} on top of {target}")
    return 0


CONFLICTS_FILE = "conflicts"


def stage_story(path, runs, story_id):
    """Into the index of the story's worktree: every tracked file the story changed or removed, and the untracked
    ones a stage window of the story made (`stages-made.txt`) — the files the gates held to the hand-overs. An
    untracked file no stage made (a gate command's report nobody ignored, a file manager's) stays out of the
    story's commit and is named."""
    git(path, "add", "-u", "--", ".")
    made = os.path.join(evidence_dir(runs, story_id), STAGES_MADE)
    named = {line.strip() for line in read_text(made).splitlines() if line.strip()} if os.path.isfile(made) else set()
    untracked = [p for p in git(path, "ls-files", "--others", "--exclude-standard", "-z")[1].split("\0") if p]
    taken = [p for p in untracked if p in named]
    left = [p for p in untracked if p not in named and not run_owned(p, runs)]
    if taken:
        git(path, "add", "--", *taken)
    if left:
        print(f"integrate: left out of {story_id}'s commit, no stage's record names them: {', '.join(left[:8])}"
              f"{' …' if len(left) > 8 else ''}", file=sys.stderr)


def integrate_prepare(cwd, runs, epics, story_id):
    """The integrate step's git half: the story's code committed on its branch, the main line merged in, the
    whole squashed to one commit. Exit 3 with `conflict: <path>` lines where the merge needs a hand; 0 when the
    story is one commit on top of the target."""
    path = worktree_of(story_id, cwd)
    if not has_worktree(story_id, cwd):
        print(f"factory: {story_id} has no worktree to integrate", file=sys.stderr)
        return 1
    target = integration_target(runs, story_id)
    front, body = read_front_matter(find_story(epics, story_id))
    restore_places(path)
    stage_story(path, runs, story_id)
    if git(path, "diff", "--cached", "--quiet")[0] != 0:
        git(path, *git_identity(path), "commit", "--no-verify", "--quiet", "-m", f"wip({story_id}): before integration")
    if git(path, "merge-base", "--is-ancestor", target, "HEAD")[0] != 0:
        done = git(path, *git_identity(path), "merge", "--no-ff", "--no-edit", "--no-verify", "--quiet", target)
        if done[0] != 0:
            conflicted = [p for p in git(path, "diff", "--name-only", "--diff-filter=U")[1].split("\n") if p.strip()]
            if not conflicted:
                print(f"factory: merging {target} into {story_id} failed — {done[1]}", file=sys.stderr)
                return 1
            with open(os.path.join(evidence_dir(runs, story_id), CONFLICTS_FILE), "w", encoding="utf-8") as handle:
                handle.write("\n".join(conflicted) + "\n")
            for conflict in conflicted:
                print(f"conflict: {conflict}")
            return 3
    return squash_story(path, runs, story_id, target, front, body)


def integrate_finish(cwd, runs, epics, story_id):
    """After the conflicts were resolved in the worktree: no marker left in a conflicted file, the merge committed,
    the story squashed. Exit 1, naming the files, while a marker is left."""
    path = worktree_of(story_id, cwd)
    target = integration_target(runs, story_id)
    listed = os.path.join(evidence_dir(runs, story_id), CONFLICTS_FILE)
    files = [line.strip() for line in read_text(listed).splitlines() if line.strip()] if os.path.isfile(listed) else []
    left = []
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
    stage_story(path, runs, story_id)
    done = git(path, *git_identity(path), "commit", "--no-verify", "--quiet", "--no-edit")
    if done[0] != 0 and git(path, "diff", "--name-only", "--diff-filter=U")[1].strip():
        print(f"factory: the merge could not be committed — {done[1]}", file=sys.stderr)
        return 1
    with contextlib.suppress(OSError):
        os.remove(listed)
    front, body = read_front_matter(find_story(epics, story_id))
    return squash_story(path, runs, story_id, target, front, body)


def move_path(cwd, src, dst):
    """Move a file or folder, through git where it is tracked so history follows; a folder moves whole, the
    untracked files in it included. Returns how."""
    os.makedirs(os.path.dirname(os.path.join(cwd, dst)) or cwd, exist_ok=True)
    tracked = git(cwd, "ls-files", "--error-unmatch", "--", src)[0] == 0
    if tracked and git(cwd, "mv", "-k", "--", src, dst)[0] == 0 and not os.path.lexists(os.path.join(cwd, src)):
        return "git mv"
    import shutil
    shutil.move(os.path.join(cwd, src), os.path.join(cwd, dst))
    return "mv"


#: What the gate and the runner keep in a story's evidence folder that a new pass starts without: the red ledger, the
#: story's digest, the tests baseline, the round count and the base tree. The journal and the snapshots carry on.
PASS_MARKS = (".tests-red", STORY_DIGEST, TESTS_BASELINE, ".rounds", "base-tree", STAGES_MADE)


def migrate_evidence(cwd, runs, say):
    """Each story's evidence out of its run folder (contract 17): `<runs>/<story>/.verify/*` and the marks the gate
    and the runner wrote there move to `<evidence>/<story>/`. Where the evidence folder has one already, the gate
    wrote it since and it is kept; the run folder's older copy goes, and the move says so."""
    import shutil
    if not os.path.isdir(runs):
        return
    for name in sorted(os.listdir(runs)):
        folder = os.path.join(runs, name)
        if not os.path.isdir(folder):
            continue
        evidence = evidence_dir(runs, name)
        verify = os.path.join(folder, ".verify")
        sources = [(os.path.join(verify, entry), os.path.join(evidence, entry))
                   for entry in (sorted(os.listdir(verify)) if os.path.isdir(verify) else [])]
        sources += [(os.path.join(folder, mark), os.path.join(evidence, mark)) for mark in PASS_MARKS
                    if mark != "base-tree" and os.path.lexists(os.path.join(folder, mark))]
        if not sources:
            continue
        kept = []
        for src, dst in sources:
            if os.path.lexists(dst):
                kept.append(os.path.basename(src))
                if os.path.isdir(src) and not os.path.islink(src):
                    shutil.rmtree(src)
                else:
                    os.remove(src)
                continue
            move_path(cwd, src, dst)
        if os.path.isdir(verify) and not os.listdir(verify):
            os.rmdir(verify)
        say(f"{shown(folder)}/ evidence → {shown(evidence)}/"
            + (f" (the evidence folder's own kept, the run folder's dropped: {', '.join(kept)})" if kept else ""))


#: The marks that make a `tasks/<story>/` folder the factory's: without one it is the project's own.
FACTORY_MARKS = (".verify", STORY_DIGEST, ".delivered", ".rounds", ".tests-red", TESTS_BASELINE, ".story-planned")


def adopted_on(run_folder, delivered_file):
    """When an adopted story was delivered: the journal's adopt gate, else the mark's own time."""
    journal = os.path.join(run_folder, ".verify", "journal.tsv")
    if os.path.isfile(journal):
        for line in reversed(read_text(journal).splitlines()):
            parts = line.split("\t")
            if len(parts) >= 4 and parts[1] == "gate" and parts[2] == "adopt" and parts[3] == "exit=0":
                return parts[0]
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(os.path.getmtime(delivered_file)))


def migrate_layout(cwd):
    """`factory.sh update`'s one move to the layout with one owner per place: the profile to the root
    (`backlog:` → `epics:`), `project/backlog/` → `project/epics/`, each story into a folder of its own with its
    decisions and findings inside, each decision record of the old central store into its story's folder,
    each `tasks/<story>/` that carries factory marks to the run folder, and the delivery mark into the story
    as `status: delivered` + `delivered:`. Idempotent — what is where it belongs is left alone — and every
    move is printed. Anything else under `tasks/` is the project's and is not touched."""
    moved = []

    def say(what):
        moved.append(what)
        print(f"migrate: {what}")

    old_profile = os.path.join(".agents", "factory", "factory.profile.yaml")
    profile_path = resolve_profile(None, cwd)
    moved_profile = False
    if not profile_path and os.path.isfile(old_profile):
        say(f"{old_profile.replace(os.sep, '/')} → {PROFILE_FILE} ({move_path(cwd, old_profile, PROFILE_FILE)})")
        profile_path, moved_profile = PROFILE_FILE, True
    profile = read_profile(profile_path)
    renaming = profile_path and "backlog" in profile and "epics" not in profile
    declared = profile.get("contract", "")
    # The profile is rewritten only where the layout is its subject: the key that named the epics, and the
    # contract line — this layout is what contract 10 describes, so a moved profile says so.
    if renaming or (moved_profile and declared.isdigit() and int(declared) < CONTRACT):
        text = read_text(profile_path)
        changed = []
        if renaming:
            value = profile["backlog"]
            renamed = "project/epics" if value.replace("\\", "/").strip("/") == "project/backlog" else value
            text = re.sub(r"^backlog:.*$", f"epics: {renamed}", text, count=1, flags=re.M)
            changed.append(f"`backlog: {value}` is `epics: {renamed}`")
        if declared.isdigit() and int(declared) < CONTRACT:
            text = re.sub(r"^contract:.*$", f"contract: {CONTRACT}", text, count=1, flags=re.M)
            changed.append(f"contract {declared} → {CONTRACT}")
        with open(profile_path, "w", encoding="utf-8") as handle:
            handle.write(text)
        say(f"{profile_path}: " + ", ".join(changed))
        profile = read_profile(profile_path)
    set_places(profile)
    epics, runs = place("epics"), place("runs")
    old_epics = os.path.join("project", "backlog")
    if os.path.isdir(old_epics) and not os.path.isdir(epics) and epics == DEFAULTS["epics"]:
        say(f"project/backlog/ → {epics}/ ({move_path(cwd, old_epics, epics)})")
    # A story is a folder (contract 16): `<epic>/<story>.md` → `<epic>/<story>/story.md`, its `.decisions/`
    # folder → `<story>/decisions/`, its `.findings.md` → `<story>/findings.md`. The folder takes the story's id.
    for src in flat_stories(epics):
        try:
            front, _body = read_front_matter(src)
        except GateError:
            front = {}
        stem = os.path.splitext(os.path.basename(src))[0]
        folder = os.path.join(os.path.dirname(src), str(front.get("id") or "").strip() or stem)
        dst = os.path.join(folder, STORY_FILE)
        if os.path.exists(dst):
            print(f"migrate: kept {shown(src)} — {shown(dst)} exists already")
            continue
        say(f"{shown(src)} → {shown(dst)} ({move_path(cwd, src, dst)})")
        for old_name, new_name in ((stem + ".decisions", DECISIONS_DIR), (stem + ".findings.md", FINDINGS_FILE)):
            old_part = os.path.join(os.path.dirname(src), old_name)
            new_part = os.path.join(folder, new_name)
            if not os.path.exists(old_part):
                continue
            if os.path.exists(new_part):
                print(f"migrate: kept {shown(old_part)} — {shown(new_part)} exists already")
                continue
            say(f"{shown(old_part)} → {shown(new_part)} ({move_path(cwd, old_part, new_part)})")
    store = os.path.join(".agents", "factory", "decisions")
    if os.path.isdir(store):
        for name in sorted(os.listdir(store)):
            if not name.endswith(".md"):
                continue
            src = os.path.join(store, name)
            try:
                front, _body = read_front_matter(src)
                story_id, rid = str(front.get("story", "")).strip(), str(front.get("id", "")).strip()
                story_path = find_story(epics, story_id)
            except GateError as error:
                print(f"migrate: kept {shown(src)} — {error}")
                continue
            if not rid.startswith(story_id + "-"):
                print(f"migrate: kept {shown(src)} — its id {rid!r} does not start with its story {story_id!r}")
                continue
            dst = record_path(story_id, rid, story_path)
            if os.path.exists(dst):
                print(f"migrate: kept {shown(src)} — {shown(dst)} exists already")
                continue
            say(f"{shown(src)} → {shown(dst)} ({move_path(cwd, src, dst)})")
        if not os.listdir(store):
            os.rmdir(store)
    tasks = "tasks"
    if os.path.isdir(tasks):
        for name in sorted(os.listdir(tasks)):
            src = os.path.join(tasks, name)
            if not os.path.isdir(src) or not any(os.path.exists(os.path.join(src, mark)) for mark in FACTORY_MARKS):
                continue
            dst = os.path.join(runs, name)
            if os.path.exists(dst):
                print(f"migrate: kept {shown(src)} — {shown(dst)} exists already")
                continue
            say(f"{shown(src)}/ → {shown(dst)}/ ({move_path(cwd, src, dst)})")
            try:
                story_path = find_story(epics, name)
                front, _body = read_front_matter(story_path)
            except GateError:
                continue
            delivered_file = os.path.join(dst, ".delivered")
            if os.path.isfile(delivered_file):
                value = read_text(delivered_file).strip()
                if not is_delivered(front):
                    if value == "adopted":
                        write_story_fields(story_path, delivered=adopted_on(dst, delivered_file))
                    else:
                        write_story_fields(story_path, status="delivered", delivered=value)
                    front, _body = read_front_matter(story_path)
                    say(f"{shown(story_path)} carries the delivery ({value})")
                os.remove(delivered_file)
            digest = os.path.join(dst, STORY_DIGEST)
            if os.path.isfile(digest):
                if not is_delivered(front):
                    write_mark(runs, name, STORY_DIGEST, story_digest(story_path))
                os.remove(digest)
        if not os.listdir(tasks):
            os.rmdir(tasks)
            say("tasks/ removed — it held nothing but the factory's run artefacts")
    migrate_evidence(cwd, runs, say)
    attributes = ".gitattributes"
    if os.path.isfile(attributes):
        text = read_text(attributes)
        new_line = f"{evidence_rel()}/**/journal.tsv merge=union"
        old_lines = [line for line in (f"tasks/**/.verify/journal.tsv merge=union",
                                       f"{runs}/**/.verify/journal.tsv merge=union") if line in text.splitlines()]
        if old_lines:
            for line in old_lines:
                text = text.replace(line, new_line if new_line not in text else "")
            with open(attributes, "w", encoding="utf-8") as handle:
                handle.write(re.sub(r"\n{2,}", "\n", text))
            say(f"{attributes}: the journals' merge rule follows the evidence folder")
    if not moved:
        print("migrate: nothing to move — the layout is current")
    return 0


CONTRACT_HEAD = ("What the gate checks in this stage's file — the exact shape, from the gate's own code. A stage that "
                 "wants certainty reads this, not the gate.")


def contract_text(stage, runs):
    """The stage's contract, with the hand-over's measure appended: what the file has to say fits in a base plus a
    share per criterion (the gate notes a larger file, never refuses it)."""
    text = contract_body(stage, runs)
    if text is None:
        return None
    for name in (STAGE_FILES[stage],) if stage in STAGE_FILES else ():
        base, per = HANDOVER_BUDGET[name]
        text += (f"\n- size: what {name} has to say fits in {base / 1000:.1f} kB"
                 + (f" plus {per} bytes per criterion" if per else "")
                 + " — keys and levels, not the story's text; one citation per row; nothing a reader has elsewhere. "
                   "Larger is a `gate:note size`, never a refusal, and never a reason to edit the file after the gate "
                   "ran; a reason is one line"
                 + (" (the pipeline's `## Paths` does not count)" if name == "document.md" else ""))
    return text


def contract_body(stage, runs):
    """The shape the gate holds a stage's file to, in a page: the table columns, the selector form, the
    path rule, the section names — taken from the constants the checks read, so the two cannot drift apart
    without this text changing with them."""
    folder = f"{runs}/<story>"
    evidence = f"{evidence_dir(runs)}/<story>".replace(os.sep, "/")
    if stage == "plan":
        return f"""{CONTRACT_HEAD}

plan — {folder}/plan.md (gate before the stage: story, epic, context map, decisions, rounds; the test gate reads the plan)
- `## Acceptance criteria`: one line per criterion, the story's key verbatim and its level — not the story's text:
  `- <key>  →  level: e2e | integration | browser-only (<why>)`
  `factory-cli.py --plan-skeleton <story>` writes the file's headings and these lines with the keys: give each its level.
  The test gate reads `level: browser-only` here (`levels`); a key is `[a-z0-9][a-z0-9-]*`
- `## Invariants`: one line per aggregate, entity, value object or domain service `## Changes` names —
  `- <Element>: <rule>; <rule>` with its guards (required, trimmed, in range), or `- <Element>: none — <why>`.
  The test gate reads it (`invariants`): each named rule needs a unit test in tests.md's `## Notes`
- `## Changed tests` (only when the story contradicts an existing test): `| <path from the project root> | <backing line or decision id> |`
- `## Files`: `- <path from the project root> — <changes|read>: <why>` (the path in backticks) — the next stages open these first
- `## Glossary proposals`: `- <term>: <definition>` — the document gate checks each term landed in a glossary or is named open
- `## needs-human` only to stop: `decision: <story>-<nn>`, with the record `<story>/decisions/<nn>.md` in the story's folder
  (`id:`, `story:`, `stage: plan`, `asked:`; `## Question`, `## Options`, `## Recommendation`)
- A citation is a path from the project root, `src/main/java/…/Thing.java:12`; a bare `Thing.java:12` resolves to nothing.
  A catalog node is cited by its path inside the catalog (`recipe/add-an-aggregate.md`), as the knowledge skill cites it —
  never by a path into a skill folder"""
    if stage == "test":
        return f"""{CONTRACT_HEAD}

test — {folder}/tests.md (gate after the stage: tests-mapped, tests-exist, compiles, tests-red, levels, test-titles, invariants, files-listed)
- the table, right after the marker `<!-- gate:tests -->`, one row per criterion (a criterion may have several rows):
  `| criterion | test |` then `| <key> | <selector> |`
  row pattern: {MAPPING_ROW.pattern!r}
- selector: `<fully.qualified.Class>#<method>` — pattern {SELECTOR.pattern!r}; the class resolves to a file named after it
  (`WidgetTest.java`), or to a module path (`tests.test_widgets#test_shows` → `tests/test_widgets.py`)
- levels: a test the profile's `e2eTest:` command runs belongs to the story's `(happy path)` scenario or to a key the
  plan gave `level: browser-only`; every other scenario's test lives in a `test.<name>:` source set
- titles: an end-user test's display name is the scenario's `Title:` line verbatim, else its key in words
  (`shows-empty-state` → "Shows empty state"); never the key itself in a name, display name or comment
- one process per test command; each selector is read from its report by name
- red: every selector in the table fails before any production code — the gate writes `{evidence}/.tests-red`
  (`<selector>\t<sha256 of the test file>`); the build gate refuses a test changed after it was seen red (`red-proof`)
- a round the judge sent back (`back: test`): a test you strengthen is already green and cannot be seen red — write its
  break, `{folder}/breaks/<fully.qualified.Class>--<method>.patch`, a `git apply` patch against the production code that
  turns it red; the gate applies it on a scratch copy (`break-proof`) and records the test's new version
- `## Files`: every test file this stage wrote or changed, one per line, as a path from the project root —
  `files-listed` compares it with the changed-files record; `factory-cli.py --files-skeleton <story> test`
  writes it from the tree, and the invariant rows below: run it, add the rest
- `## Invariants`: `<!-- gate:invariants -->`, a row per plan rule `| <Element> | <n> | <rule> | <Class>#<method> |`:
  each its own test, not a criterion's (`invariants`)
- `## Clauses` (contract 15): `<!-- gate:clauses -->`, per `Then`/`And` `| <key> | <n> | <clause> | <File>:<line> | <level> |`
  — the line asserting it, level `unit|port|adapter|e2e`; a stored-state clause never `adapter` (`clauses`)
- `## Notes`: `- uncovered: <key> — <why>` only when unavoidable — not what a test fails on: the red run records it
- stubs: a type with nothing a criterion observes (a record and its fields, an enum, an interface, an exception type) is
  written whole here; a method whose outcome a criterion asserts throws — whatever a criterion observes, throws"""
    if stage in FILES_SECTIONS and STAGE[stage].suite:
        table, name = ("## Changed", "build") if stage == "build" else ("## Moves", "tidy")
        return f"""{CONTRACT_HEAD}

{name} — {folder}/{STAGE_FILES[stage]} (gate after the stage: tests-green, red-proof, files-listed, existing tests, architecture, format)
- `{table}`: `| File | Why |` — the first cell is a path from the project root, in backticks or bare; the other cells
  are prose. `files-listed` refuses a file the pipeline recorded as changed that no row names; a listed file that did
  not change is a note. A stage that changed no file needs no such section (tidy) — say so and why.
  `factory-cli.py --files-skeleton <story> {stage}` writes the rows' first column from the tree (the file's
  skeleton, or the missing rows): run it when the changes are done, fill in the rest
- a test file put back to the version the test stage saw red is a restoration, not a change to list
- tests: every selector of the `gate:tests` table green, and its file's digest as `.tests-red` holds it (`red-proof`)
- {'`## Deviations from the plan`: `- <element>: <what differed and why>`, or nothing when the plan held. No `## Criteria` (the judge re-checks each one) and no `## Checks`: the gate\'s report is the evidence, and a stage edits no hand-over after the gate ran — the gate is the stage\'s test run' if stage == 'build' else '`## Left alone`: what you saw and did not change, and why. No `## Checks`: the gate\'s report is the evidence, and a stage edits no hand-over after the gate ran — the gate is the stage\'s test run'}
- `## needs-human` only to stop, with `decision: <story>-<nn>` and the record beside the story (`stage: {name}`)
- {'a test that cannot pass for a reason in its own code — a helper, a locator, a fixture — while what it asserts stays as it is: write `back: test` on a line of its own and say what is wrong; the round goes to the test stage, which repairs it and proves it with a break. A change to what a test asserts is still a question (`## needs-human`)' if stage == 'build' else 'no test change: a defect in a test goes back through the build stage'}
- no criterion key in code, a comment or a test name; no `TODO` for the criterion delivered"""
    if stage == "judge":
        return f"""{CONTRACT_HEAD}

judge — {folder}/judge.md (the runner reads the verdict; the document gate reads `story-pass`)
- `## Verdict`: `verdict: pass | changes-requested | story-conflict` — one line, exactly one of the three
  (pass: deliverable; changes-requested: back one round; story-conflict: a human, never build)
- `back: test` under the verdict when a confirmed defect is in a test (it asserts less than its criterion): the round
  goes to the test stage, then build; without it the round goes to build, which may not change a test
- `## Perspectives covered`: `- <perspective>: reviews/<perspective>.md (<carrier>) | in-session — <why no file> | not covered — <why>`
- `## Confirmed defects`: `| Perspective | File:line | Severity | Defect | Fix |` — file as a path from the project root
  with its line; severity blocker | major | minor; only blocker and major prevent `pass`
- `## Considered and dropped`, `## Criteria re-checked`: `- <key>: met | met only nominally — <what the test does not assert>`
- `## Previous round` in a repeat round: every defect the previous verdict confirmed — fixed (file:line) | withdrawn (why) | still open
- a `story-conflict` names a decision record: `## needs-human` with `decision: <story>-<nn>`, the record's `stage:` is the one
  that applies the answer (plan or test)"""
    if stage == "document":
        return f"""{CONTRACT_HEAD}

document — {folder}/document.md (gate after the stage: story-pass, outcome, documented, glossary, architecture)
- `## Glossary`: `| Term | Context | Added or changed | Definition source |` — the last cell names where the definition
  came from; a row without it is an unsourced claim
- `## Documents updated`: `| File | What changed | Verified by |` — the first cell is a path from the project root that
  exists; `Verified by` names the file read or the command run. Nothing updated: one row `| — | none | <what you read> |`
  (`{'`, `'.join(sorted(n for n in NOTHING if n))}` read as no file). `document.md` itself is never listed
- `## Not documented`: `- <thing>: <why, and what it waits for>` — one line each
- every backticked path anywhere in the file resolves from the project root: `src/main/java/com/example/Thing.java:12`,
  `{folder}/build.md:20`; a bare `Thing.java:12` or a package-relative `example/Thing.java` is refused (`documented`)
- `## Paths`, when the pipeline wrote the file's skeleton (`factory-cli.py --document-skeleton <story>`): the story's
  changed files and the run's files in exactly that form — cite from there, do not retype
- every term the plan proposed under `## Glossary proposals` is in a glossary now, or named as still open under
  `## Not documented` (`glossary`). The skeleton pre-fills a `## Glossary` row per proposal — write the entry from it
{GLOSSARY_RULE}
- `## needs-human` only to stop (`decision: <story>-<nn>`, record `stage: document`)"""
    if stage == "review":
        return f"""{CONTRACT_HEAD}

review — {folder}/reviews/<perspective>.md (one per perspective: {', '.join(BUILT_IN_PERSPECTIVES)} and the profile's
`reviews:`; the document gate reads them as `reviews`)
- written by the perspective's carrier — the review skill `review.<perspective>:` names, or `review-<perspective>` — in that
  skill's report format: `## Findings` with `### must-fix`, `### should-fix`, `### nits`, each finding with the file and
  line it stands on and a one-line fix; "nothing found" said plainly where that is the case
- the reviewer reads the diff (`{evidence}/story.diff`), the story, plan.md, tests.md, build.md and the product and
  technical description; it opens a file only where the diff's context does not carry the question; it changes nothing
- the judge converges from these files: it confirms each must-fix and should-fix in the code, drops what it cannot point at,
  deduplicates across perspectives, and names the file it read per perspective under `## Perspectives covered`
- a missing file is a note at the document gate (the judge ran that pass itself and says so); a file without a findings
  section is refused"""
    if stage == "glossary":
        return f"""{CONTRACT_HEAD}

glossary — how the document gate matches a proposed term (`glossary`), and the entry the glossary skill writes
{GLOSSARY_RULE}
- an entry: `### <Term>` — the heading carries the term as the plan proposed it, the domain word with the code word in
  parentheses where they differ (`### Titel (TaskTitle)`) — then `**Definition:**` and `**Type:**` (the glossary skill's
  format; `Type` is one of Aggregate Root, Entity, Value Object, Domain Event, Integration Event, Domain Service,
  Specification, Concept); `Identity`, `Synonyms (avoid)`, `Related terms`, `Operations` where they apply"""
    return None


#: How `check_proposals_landed` finds a proposed term, said once for `--contract document` and `--contract glossary`.
GLOSSARY_RULE = ("- a term is found in a glossary by any of its words: the term as written, the word before a parenthesis or "
                 "the word inside it (`Titel (title)` is found by `titel` or by `title`), case aside; the whole glossary "
                 "file counts, a heading is the place to put it. A term not landed is named open under `## Not documented`, "
                 "nowhere else — a pre-filled `## Glossary` row does not account for it")


#: The section each builder hand-over lists its files in, and the row shape the gate's `listed_files` reads.
FILES_SECTIONS = {
    "test": ("## Files", None, "- `{path}`"),
    "build": ("## Changed", "| File | Why |\n|---|---|", "| `{path}` | |"),
    "tidy": ("## Moves", "| File | Move | Why it reads better |\n|---|---|---|", "| `{path}` | | |"),
}


FILES_SKELETONS = {
    "test": "# Tests — {story}\n\n<!-- gate:tests -->\n| criterion | test |\n| --- | --- |\n\n## Files\n{rows}\n\n## Notes\n",
    "build": "# Build — {story}\n\n## Changed\n| File | Why |\n|---|---|\n{rows}\n\n## Deviations from the plan\n",
    "tidy": "# Tidy — {story}\n\n## Moves\n| File | Move | Why it reads better |\n|---|---|---|\n{rows}\n\n"
            "## Left alone\n",
}


def changed_for_skeleton(cwd, runs, story_id, stage):
    """The files the stage has to list, from the same sources `files-listed` reads and no other: the stage's
    changed-files record where the stage has ended; a shared builder's record, or its open window's tree against
    the story's base, minus what the story's other hand-overs list (the gate checks their union).
    `None` when nothing was observed — the list is then the stage's, as the gate's skip says."""
    folder = evidence_dir(runs, story_id)
    record = os.path.join(folder, f"changed-{stage}.txt")
    if os.path.isfile(record) and not snapshot_reason(record):
        return [line.split("\t", 1)[1] for line in read_text(record).splitlines() if "\t" in line]
    # the gate checks the union of the three hand-overs against the builder's record: a file another
    # hand-over lists is not this stage's to list (inside the open window only the earlier ones exist)
    listed = set()
    for name in FILES_SECTIONS:
        if name != stage:
            listed |= listed_files(os.path.join(runs, story_id, STAGE_FILES[name])) or set()
    not_listed = lambda path: path not in listed and not any(path.endswith("/" + n) for n in listed)
    builder = os.path.join(folder, "changed-builder.txt")
    if os.path.isfile(builder) and not snapshot_reason(builder):
        return [path for path in (line.split("\t", 1)[1] for line in read_text(builder).splitlines() if "\t" in line)
                if not_listed(path)]
    base_file = os.path.join(folder, "base-tree")
    if os.path.isfile(base_file):
        base = read_text(base_file).strip()
        now = git_tree(cwd) if base and base != "none" else None
        rows = tree_changes(cwd, base, now, runs) if now else None
        if rows is not None:
            return [path for _kind, path in rows if not_listed(path)]
    return None


def _files_skeleton(runs, story_id, stage, cwd="."):
    """The stage's hand-over with its file list written by the pipeline: created with the stage's headings
    when the file is missing, or the missing paths added to its list when the stage wrote the file first.
    The stage fills in the why; it never types the list — the one refusal that cost the test stage a
    gate run in the bench. Idempotent: a path already listed is not added twice."""
    if stage not in FILES_SECTIONS:
        print(f"factory: --files-skeleton takes {', '.join(FILES_SECTIONS)}, not {stage!r}", file=sys.stderr)
        return 2
    changed = changed_for_skeleton(cwd, runs, story_id, stage)
    if changed is None:
        print(f"factory: nothing observed — no changed-files record and no base tree for {story_id}; the {stage} "
              f"stage lists its files itself", file=sys.stderr)
        return 1
    heading, header, row = FILES_SECTIONS[stage]
    folder = os.path.join(runs, story_id)
    target = os.path.join(folder, STAGE_FILES[stage])
    os.makedirs(folder, exist_ok=True)
    if not os.path.isfile(target):
        rows = "\n".join(row.format(path=path) for path in changed)
        with open(target, "w", encoding="utf-8") as handle:
            handle.write(FILES_SKELETONS[stage].format(story=story_id, rows=rows))
        print(f"factory: {runs}/{story_id}/{STAGE_FILES[stage]} — the skeleton with {len(changed)} path(s) under `{heading}`")
        return 0
    already = listed_files(target) or set()
    missing = [path for path in changed if path not in already and not any(path.endswith("/" + n) for n in already)]
    if not missing:
        print(f"factory: {runs}/{story_id}/{STAGE_FILES[stage]} lists every changed file already — nothing added")
        return 0
    lines = read_text(target).splitlines()
    start = next((i for i, line in enumerate(lines) if line.strip().lower() == heading.lower()), None)
    addition = [row.format(path=path) for path in missing]
    if start is None:
        lines += ["", heading] + ([header] if header else []) + addition
    else:
        end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
        body = lines[start + 1:end]
        while body and not body[-1].strip():
            body.pop()
        if header and not any(line.lstrip().startswith("|") for line in body):
            body += header.split("\n")
        lines = lines[:start + 1] + body + addition + [""] + lines[end:]
    with open(target, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines).rstrip("\n") + "\n")
    print(f"factory: {runs}/{story_id}/{STAGE_FILES[stage]} — {len(missing)} path(s) added under `{heading}`")
    return 0


def files_skeleton(runs, story_id, stage, cwd="."):
    """The stage's file list (below), and at the test stage the `gate:invariants` table with one row per rule the
    plan names — element, number, the rule's text — so the stage fills in only each row's test."""
    code = _files_skeleton(runs, story_id, stage, cwd)
    if code == 0 and stage == "test":
        invariants_skeleton(runs, story_id)
        clauses_skeleton(runs, story_id, cwd)
    return code


def clauses_skeleton(runs, story_id, cwd="."):
    """Contract 15: tests.md's `## Clauses` table from the story's scenarios — one row per `Then` and each `And` after
    it, the clause's text written by the pipeline; the stage fills in only `<File>:<line>` and the level. Rows already
    there are kept, missing ones added."""
    if contract_of(read_profile(resolve_profile(None, cwd))) < 15:
        return
    target = os.path.join(runs, story_id, "tests.md")
    try:
        story_path = find_story(place("epics"), story_id)
        wanted = scenario_clauses(read_front_matter(story_path)[1])
    except GateError:
        return
    if not wanted or not os.path.isfile(target):
        return
    text = read_text(target)
    present = {(key, n) for key, n, _loc, _lvl in (read_clause_rows(text) or [])}
    rows = [f"| {key} | {n} | {clause.replace('|', '/')} | | |" for key, clauses in wanted.items()
            for n, clause in clauses if (key, n) not in present]
    if not rows:
        return
    if CLAUSES_MARKER not in text:
        text = text.rstrip("\n") + "\n\n## Clauses\n" + CLAUSES_MARKER + \
            "\n| criterion | n | clause | assertion | level |\n| --- | --- | --- | --- | --- |\n" + "\n".join(rows) + "\n"
    else:
        lines = text.splitlines()
        at = next(i for i, line in enumerate(lines) if CLAUSES_MARKER in line)
        end = next((i for i in range(at + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
        while end > at + 1 and not lines[end - 1].strip():
            end -= 1
        lines = lines[:end] + rows + lines[end:]
        text = "\n".join(lines).rstrip("\n") + "\n"
    with open(target, "w", encoding="utf-8") as handle:
        handle.write(text)
    print(f"factory: {runs}/{story_id}/tests.md — {len(rows)} clause row(s) under `## Clauses`; fill in each "
          "`<File>:<line>` and level (unit, port, adapter, e2e)")


def invariants_skeleton(runs, story_id):
    """tests.md's `## Invariants` table from plan.md's `## Invariants`: one row per rule, the test cell empty for the
    stage to fill; rows already there are kept, missing ones added. Nothing when the plan names no rule."""
    plan_path, target = os.path.join(runs, story_id, "plan.md"), os.path.join(runs, story_id, "tests.md")
    if not os.path.isfile(plan_path) or not os.path.isfile(target):
        return
    named = plan_invariants(read_text(plan_path)) or {}
    wanted = [(element, n, rule) for element, rules in named.items() for n, rule in enumerate(rules, 1)]
    if not wanted:
        return
    text = read_text(target)
    present = {(e, n) for e, numbers, _sel in (read_invariant_rows(text) or []) for n in numbers}
    rows = [f"| {e} | {n} | {rule.replace('|', '/')} | |" for e, n, rule in wanted if (e, n) not in present]
    if not rows:
        return
    if INVARIANTS_MARKER not in text:
        text = text.rstrip("\n") + "\n\n## Invariants\n" + INVARIANTS_MARKER + \
            "\n| element | rule | invariant | test |\n| --- | --- | --- | --- |\n" + "\n".join(rows) + "\n"
    else:
        lines = text.splitlines()
        at = next(i for i, line in enumerate(lines) if INVARIANTS_MARKER in line)
        end = next((i for i in range(at + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
        while end > at + 1 and not lines[end - 1].strip():
            end -= 1
        lines = lines[:end] + rows + lines[end:]
        text = "\n".join(lines).rstrip("\n") + "\n"
    with open(target, "w", encoding="utf-8") as handle:
        handle.write(text)
    print(f"factory: {runs}/{story_id}/tests.md — {len(rows)} invariant row(s) under `## Invariants`; fill in each test")


PLAN_SKELETON = ("# Plan — {story}\n\n## Context\n\n## Changes\n| Element | Kind | Location | New or changed | Evidence |\n"
                 "| --- | --- | --- | --- | --- |\n\n## Acceptance criteria\n{rows}\n\n## Invariants\n\n## Files\n\n## Glossary proposals\n\n"
                 "## Open assumptions\n")


def plan_skeleton(runs, story_id, cwd="."):
    """`plan.md` before the plan stage runs: the file's headings and, under `## Acceptance criteria`, one line per
    criterion of the story with its key — the stage gives each its level and never retypes the story's text.
    Idempotent: an existing file (a refused round's, a stage's own) is left as it is."""
    folder = os.path.join(runs, story_id)
    target = os.path.join(folder, "plan.md")
    if os.path.isfile(target):
        print(f"factory: {runs}/{story_id}/plan.md exists — left as it is")
        return 0
    try:
        story_path = find_story(place("epics"), story_id)
        criteria = criteria_of(story_path, read_front_matter(story_path)[1])
    except GateError as error:
        print(f"factory: {error}", file=sys.stderr)
        return 1
    rows = "\n".join(f"- {key}  →  level: " for key, _text in criteria)
    os.makedirs(folder, exist_ok=True)
    with open(target, "w", encoding="utf-8") as handle:
        handle.write(PLAN_SKELETON.format(story=story_id, rows=rows))
    print(f"factory: {runs}/{story_id}/plan.md — the skeleton with {len(criteria)} criterion key(s) under `## Acceptance criteria`")
    return 0


def document_skeleton(runs, story_id, cwd="."):
    """`document.md` before the document stage runs: the file's headings, and under `## Paths` every file the
    story changed and every run file, as they resolve from the project root. A path the model never types
    cannot be package-relative — the one refusal that cost the document stage its rounds. Idempotent: an
    existing file (a refused round's, a stage's own) is left as it is."""
    folder = os.path.join(runs, story_id)
    target = os.path.join(folder, "document.md")
    if os.path.isfile(target):
        return 0
    paths = []
    record = os.path.join(evidence_dir(runs, story_id), "changed.txt")
    if os.path.isfile(record):
        for line in read_text(record).splitlines():
            parts = line.split("\t", 1)
            if len(parts) == 2 and parts[0] in ("added", "modified") and os.path.isfile(os.path.join(cwd, parts[1])):
                paths.append(parts[1])
    for name in STAGE_ORDER:
        run_file = os.path.join(folder, STAGE_FILES[name])
        if os.path.isfile(run_file):
            paths.append(f"{runs}/{story_id}/{STAGE_FILES[name]}")
    # the plan's proposals as the glossary table's rows: the term as the plan wrote it — the word the gate
    # looks for — the story's context, and the plan line as the definition's source; the stage writes the
    # glossary entry from the row and never retypes the term (the refusal that cost the bench a second run)
    glossary_rows = ""
    plan_file = os.path.join(folder, "plan.md")
    if os.path.isfile(plan_file):
        context = ""
        try:
            story_path = find_story(place("epics"), story_id)
            context = str(read_front_matter(story_path)[0].get("context", "")).strip()
        except GateError:
            pass
        for term in plan_proposals(read_text(plan_file)):
            glossary_rows += f"| {term} | {context} | added | `{runs}/{story_id}/plan.md` `## Glossary proposals` |\n"
    os.makedirs(folder, exist_ok=True)
    with open(target, "w", encoding="utf-8") as handle:
        handle.write(f"# Document — {story_id}\n\n## Glossary\n| Term | Context | Added or changed | Definition source |\n"
                     f"|---|---|---|---|\n{glossary_rows}\n## Documents updated\n| File | What changed | Verified by |\n|---|---|---|\n\n"
                     "## Not documented\n\n## Paths\n"
                     "The files this story changed and the run's files, as they resolve from the project root — cite them in "
                     "exactly this form (with `:<line>` where a line matters); the pipeline wrote this list, leave it in place.\n")
        for path in paths:
            handle.write(f"- `{path}`\n")
    terms = glossary_rows.count("\n")
    print(f"factory: {runs}/{story_id}/document.md — the skeleton with {len(paths)} path(s) under `## Paths`"
          + (f" and {terms} proposed term(s) under `## Glossary`" if terms else ""))
    return 0


# --- the run: what `factory.sh run` starts once its checks before the first stage passed -------------------------
# One process per stage, so every stage starts with a fresh context and reads only its story and its predecessor's
# file. The runner composes and starts; every project file it reads it reads with the cli's readers, in its own
# process, after `Run.profile` set the places from where it stands — the checkout or a story's worktree — exactly
# as a cli started there would. What changes the checkout's state — the claim, a skeleton, a worktree — runs as
# the cli, a process of its own (`Run.cli`); what it may not decide — whether a stage is done — is the gate's, a
# process of its own as well.
#
# Exit codes: 0 the story ran through, 1 a failure, 2 a usage error, 3 it stopped for a decision, 4 at --max-stages
# or --story-budget, 5 another worker holds the checkout, 7 the pipeline or a person's file changed under it,
# 124 a stage ran past its time limit is reported as a failure (1), 129/130/143 a hang-up, an interrupt, a TERM.

#: The shell a stage may use without asking, beside the gate, the cli and the profile's commands: the ordinary
#: reading and text tools, and the git verbs that look without changing anything (`git apply --check` is how a
#: stage tries a break patch). What writes or runs anything stays out — `sed -i`, `xargs`, `find -exec`, a redirect
#: of `echo`/`printf`, `mkdir`: each allowed head is allowed with every argument (WP-94). Measured on the bench:
#: without the reading tools a stage hit the allow-list about three times per story, each a wasted turn.
STAGE_SHELL_HEADS = ("cd", "ls", "cat", "head", "tail", "wc", "sort", "grep", "diff", "pwd",
                     "git status", "git diff", "git log", "git ls-files", "git apply --check")
STAGE_SHELL = ("cd, ls, cat, head, tail, wc, sort, grep, diff, pwd, and git status, git diff, git log, git ls-files, "
               "git apply --check")

#: The first line of a snapshot written without a hash: the observer reads such a snapshot as absent, because a
#: snapshot of empty digests compares equal to every other and would read as "this stage changed nothing".
NO_HASHES = "# no-sha256-command: names only, no content hashes"

#: Where a tool ran past this many seconds, it is stopped (0: no limit) — FACTORY_STAGE_TIMEOUT, else the profile's
#: `stageTimeout:`. A number with `s`, `m` or `h`; a bare number is seconds.
TIMEOUT_UNITS = {"": 1, "s": 1, "m": 60, "h": 3600}
TIMED_OUT = 124
SIGNAL_EXITS = {"SIGTERM": 143, "SIGHUP": 129, "SIGINT": 130}


class Stopped(Exception):
    """The run ends here with this exit code — the pipeline changed under it, a signal arrived."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def utc(fmt="%Y-%m-%dT%H:%M:%SZ"):
    return time.strftime(fmt, time.gmtime())


def seconds_of(text):
    """`90`, `90s`, `30m`, `2h` → seconds; None for anything else."""
    match = re.fullmatch(r"\s*(\d+)\s*([smh]?)\s*", str(text or ""))
    return int(match.group(1)) * TIMEOUT_UNITS[match.group(2)] if match else None


def first_word(value):
    parts = str(value or "").split()
    return parts[0] if parts else ""


def newer(path, than):
    """`[ path -nt than ]`: path exists and is newer, or than does not exist."""
    if not os.path.exists(path):
        return False
    return not os.path.exists(than) or os.path.getmtime(path) > os.path.getmtime(than)


class Run:
    """One runner process: the story or the backlog it runs, and what it keeps between stages."""

    def __init__(self, options, home, runs, worker=None):
        self.py = os.environ.get("FACTORY_RUNNER_PYTHON") or "python3"   # the name the prompts and the list carry
        self.scripts = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.cli_path = os.path.join(self.scripts, "factory-cli.py")
        self.gate_rel = ".agents/factory/story-gate.py"
        self.gate_path = self.gate_rel
        self.home = home
        self.pwd = os.getcwd()
        self.runs_rel = runs
        self.runs = runs
        absolute = os.path.isabs(runs) or re.match(r"^[A-Za-z]:", runs)
        parent = os.path.dirname(runs) if absolute else os.path.join(home, os.path.dirname(runs))
        self.stop_file = os.path.join(parent, "stop").replace("\\", "/") if absolute else f"{home}/{os.path.dirname(runs)}/stop"
        self.lock_dir = f"{os.path.dirname(runs)}/integrate.lock" if absolute else f"{home}/{os.path.dirname(runs)}/integrate.lock"
        self.worker = worker or f"runner:{socket.gethostname() or 'host'}:{os.getpid()}"
        self.suites_key = secrets.token_hex(16)
        self.invocations = 0
        self.nested_code = 0
        self.gate_first = False
        self.max_stages = options.max_stages
        self.story_budget = options.story_budget
        self.shared_builder = options.builder == "shared"
        self.shared_verifier = options.verifier == "shared"
        self.parallel = options.parallel
        self.options = options
        self.add_dirs, self.read_dirs = [], []
        self.tool_in_flight = ""
        self.pipeline_sha = os.environ.get("FACTORY_RUNNER_PIPELINE_SHA", "")
        self.claimed = False
        self.lock_held = False
        self.sleeping = False
        self.pending = None
        self.timeout = self.stage_timeout()

    # --- processes -----------------------------------------------------------------------------------------
    def wait(self, process, timeout=None):
        return process.wait(timeout=timeout)

    def checkpoint(self):
        """A TERM or HUP that arrived ends the run here — between stages, never inside one."""
        if self.pending is not None:
            code, self.pending = self.pending, None
            raise Stopped(code)

    def run(self, argv, *, capture=False, quiet=False, merge=False, cwd=None, env=None, stdin=None, stdout=None):
        """A child process run to its end: (exit code, its stdout when captured)."""
        out = subprocess.PIPE if capture else stdout
        errors = subprocess.STDOUT if merge else (subprocess.DEVNULL if quiet else None)
        flush()
        process = subprocess.Popen(argv, cwd=cwd, env=env, stdin=stdin, stdout=out, stderr=errors)
        data = b""
        if capture:
            data, _ = process.communicate()
            code = process.returncode
        else:
            code = self.wait(process)
        return code, data.decode("utf-8", errors="replace").rstrip("\n") if capture else ""

    def cli(self, *args, quiet=True, merge=False, cwd=None, env=None):
        """The cli beside this runner: (exit code, stdout without its last newlines)."""
        return self.run([sys.executable, self.cli_path, *args], capture=True, quiet=quiet and not merge, merge=merge,
                        cwd=cwd, env=env)

    def profile(self):
        """The stack profile as a cli started here would read it, with the places set from it — in a story's
        worktree the main checkout's (FACTORY_HOME). Read again on every question: a person may edit the profile
        while a run waits, and the places change as the runner moves between the checkout and a worktree."""
        profile = read_profile(resolve_profile(os.environ.get("FACTORY_PROFILE") or None, os.getcwd()))
        set_places(profile)
        return profile

    def home_env(self):
        """The environment of a call made in the main checkout: no FACTORY_HOME, as there."""
        env = dict(os.environ)
        env.pop("FACTORY_HOME", None)
        return env

    def journal_line(self, story, line):
        """Every journal line is numbered under the journal's lock, a folder — the same for the gate, the cli and
        a reviewer appending beside the runner."""
        self.profile()
        with contextlib.suppress(OSError, GateError, ValueError):   # an unwritable journal costs the line, not the run
            journal_writer(place("runs"), story).write(line + "\n")

    def gate_installed(self):
        return os.path.isfile(self.gate_path)

    # --- places --------------------------------------------------------------------------------------------
    def evidence(self, story):
        parent = os.path.dirname(self.runs)
        parent = ".dca-factory" if parent in (".", "") else parent
        return f"{parent}/evidence/{story}"

    def evidence_rel(self):
        parent = os.path.dirname(self.runs_rel)
        parent = ".dca-factory" if parent in (".", "") else parent
        return f"{parent}/evidence"

    def stage_file(self, stage):
        return STAGE_FILES.get(stage, "")

    def artefact(self, story, stage):
        return f"{self.runs}/{story}/{self.stage_file(stage)}"

    @staticmethod
    def kind_runs(kind, stage):
        return stage in STAGE and kind in STAGE[stage].kinds

    def back_for(self, kind, stage):
        """Where a round goes back to: <stage>, or the last builder stage before it the kind runs."""
        if self.kind_runs(kind, stage):
            return stage
        back = stage
        for st in SHARED_WINDOWS["builder"]:
            if self.kind_runs(kind, st):
                back = st
            if st == stage:
                break
        return back

    # --- the pipeline, unchanged ---------------------------------------------------------------------------
    @staticmethod
    def hashing():
        return os.environ.get("FACTORY_SHA256", "") != "none"

    def pipeline_hash(self, folder=None):
        """One SHA-256 over the installed files' digests — the stamp's `sha256:` line."""
        if not self.hashing():
            return None
        folder = folder or os.path.join(self.home, ".agents", "factory")
        listing = ""
        for name in PIPELINE_FILES:
            path = os.path.join(folder, name)
            if name.endswith("/"):
                if not os.path.isdir(path):
                    listing += f"missing  {name}\n"
                    continue
                for module in sorted(n for n in os.listdir(path) if n.endswith(".py")):
                    listing += f"{file_sha(os.path.join(path, module))}  {name}{module}\n"
            elif os.path.isfile(path):
                listing += f"{file_sha(path)}  {name}\n"
            else:
                listing += f"missing  {name}\n"
        return hashlib.sha256(listing.encode("utf-8")).hexdigest()

    def guard_pipeline_start(self):
        stamp = os.path.join(self.home, STAMP)
        if not os.path.isfile(stamp):
            return 0
        self.pipeline_sha = self.pipeline_hash() or ""
        if not self.pipeline_sha:
            return 0
        stamped = next((line.split(":", 1)[1].strip() for line in read_text(stamp).splitlines()
                        if line.startswith("sha256:")), "")
        if not stamped:
            err(f"factory: {STAMP} carries no hash (installed before 0.68.0) — the gates compare against the pipeline as it")
            err("factory:   is now; 'factory.sh update' records one.")
        elif stamped != self.pipeline_sha:
            err(f"factory: the installed pipeline is not the one {STAMP} records — a file under .agents/factory/ changed")
            err("factory:   since the install. Nothing was started; 'factory.sh update' installs it again.")
            return 7
        return 0

    def guard_pipeline(self, stage, story):
        """Before every gate the runner runs: the pipeline is still the one the run started with."""
        if not self.pipeline_sha:
            return 0
        now = self.pipeline_hash()
        if not now or now == self.pipeline_sha:
            return 0
        err(f"factory: the installed pipeline changed during {story}'s run, before its {stage} gate — a stage never writes")
        err("factory:   .agents/factory/. Nothing more runs; 'factory.sh update' installs it again, and the story runs")
        err("factory:   from the stage that changed it.")
        self.journal_line(story, f"{utc()}\tpipeline-changed\t{stage}")
        with contextlib.suppress(OSError):
            open(self.stop_file, "w").close()
        return 7

    # --- the checkout ----------------------------------------------------------------------------------------
    def take_checkout(self):
        if not self.gate_installed():
            err(f"factory: no gate at {self.gate_rel} — the checkout is not claimed; install the pipeline")
            return 0
        code, _ = self.run([sys.executable, self.cli_path, "--claim", self.worker])
        if code != 0:
            err("factory: another worker holds this checkout — see 'factory.sh status'. Nothing was started.")
            return 5
        self.claimed = True
        return 0

    def release(self):
        if self.claimed:
            self.claimed = False
            with contextlib.suppress(Exception):
                subprocess.run([sys.executable, self.cli_path, "--release", self.worker], cwd=self.home,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=self.home_env())

    def renew(self):
        """The claim, renewed before a stage: False when another worker took the checkout over."""
        if not self.gate_installed():
            return True
        code, _ = self.run([sys.executable, self.cli_path, "--claim", self.worker], stdout=subprocess.DEVNULL)
        return code == 0

    def take_lock(self):
        """One integration at a time: the git work in the main checkout runs under a lock beside the run folder."""
        with contextlib.suppress(OSError):
            os.makedirs(os.path.dirname(self.lock_dir), exist_ok=True)
        stale = int(os.environ.get("FACTORY_STALE_AFTER") or 7200)
        while True:
            try:
                os.mkdir(self.lock_dir)
                self.lock_held = True
                return 0
            except FileExistsError:
                pass
            except OSError:
                if not os.path.isdir(os.path.dirname(self.lock_dir)):
                    err(f"factory: no place for the lock at {self.lock_dir}")
                    return 1
            try:
                age = int(time.time() - os.path.getmtime(self.lock_dir))
            except OSError:
                age = 0
            if age > stale:
                err(f"factory: {self.lock_dir} is {age}s old — its holder ended without giving it back; taken over.")
                with contextlib.suppress(OSError):
                    os.rmdir(self.lock_dir)
                continue
            self.sleep(2)

    def drop_lock(self):
        if self.lock_held:
            self.lock_held = False
            with contextlib.suppress(OSError):
                os.rmdir(self.lock_dir)
        return 0

    def sleep(self, seconds):
        """A pause a TERM or HUP ends at once — nothing runs beside it."""
        self.checkpoint()
        self.sleeping = True
        try:
            time.sleep(seconds)
        finally:
            self.sleeping = False
        self.checkpoint()

    # --- the tool ----------------------------------------------------------------------------------------------
    def stage_timeout(self):
        given = os.environ.get("FACTORY_STAGE_TIMEOUT")
        if given is None:
            given = first_word(self.profile().get("stageTimeout", "")) if self.gate_installed() else ""
        value = seconds_of(given) if given else 0
        if given and value is None:
            err(f"factory: the stage time limit '{given}' is no number of seconds (90, 90s, 30m, 2h) — no limit applies")
        return value or 0

    @staticmethod
    def isolated():
        return os.environ.get("FACTORY_ISOLATION", "on") != "off"

    def isolation_flags(self, tool):
        if not self.isolated():
            return ""
        return (" ".join(shlex.quote(w) for w in isolation_args(TOOL[tool])) if tool in TOOL else "") + " "

    def allowed_commands(self):
        heads = [f"Bash({self.py} {self.gate_rel}:*)", f"Bash({self.py} .agents/factory/factory-cli.py:*)"]
        for head in command_heads(self.profile()) + list(STAGE_SHELL_HEADS):
            if f"Bash({head}:*)" not in heads:
                heads.append(f"Bash({head}:*)")
        return ",".join(heads)

    def model_key(self, tool, stage):
        return model_for(self.profile(), tool, (stage or "").split(":")[0])

    @staticmethod
    def tool_args(tool):
        record = TOOL.get(tool)
        return os.environ.get(record.args_env, "") if record and record.args_env else ""

    def env_model(self, tool):
        match = re.search(r".*(?:^| )(?:-m|--model)[ =]([^ ]*)", self.tool_args(tool))
        return match.group(1) if match else ""

    def model_choice(self, tool, stage):
        """The model flag for one stage, and why a request does not become one: (flag words, note). The model is
        the project's choice, stated in the profile per tool and stage (`model.<tool>.<stage>`, falling back to
        `model.<tool>`); the pipeline names none. A `--model`/`-m` in FACTORY_<TOOL>_ARGS wins — the person's local
        override — and the run says so. Exactly one model flag is ever passed."""
        requested = self.model_key(tool, stage)
        if not requested:
            return "", ""
        if os.environ.get("FACTORY_TOOL_CMD"):
            return "", "passed as FACTORY_MODEL to the custom command"
        if self.env_model(tool):
            return "", f"overridden by FACTORY_{tool.upper()}_ARGS ({self.env_model(tool)})"
        flag = TOOL[tool].model_flag if tool in TOOL else ""
        return (f"{flag} {requested}", "") if flag else ("", f"no model flag for tool {tool}")

    def model_flag(self, tool, stage=""):
        """The model a tool ran with, where its output does not say."""
        if stage and self.model_key(tool, stage) and not self.env_model(tool):
            return self.model_key(tool, stage)
        match = re.search(r".*(?:-m|--model)[ =]([^ ]*)", self.tool_args(tool))
        return match.group(1) if match else ""

    def protected_dirs(self):
        dirs = [".agents/factory", self.evidence_rel(), *TOOL_SKILL_DIRS, ".agents/skills"]
        return [d if os.path.isabs(d) or re.match(r"^[A-Za-z]:", d) else f"{self.home}/{d}" for d in dirs]

    def usage_format(self, tool):
        if os.environ.get("FACTORY_TOOL_CMD"):
            return os.environ.get("FACTORY_USAGE_FORMAT") or "none"
        return (TOOL[tool].usage if tool in TOOL else "") or "none"

    def dry_lines(self, tool, prompt, model_stage):
        print(f"   would run: {prompt}")
        isolation = os.environ.get("FACTORY_ISOLATION")
        print(f"   tool flags: {self.isolation_flags(tool)}" + (f"(FACTORY_ISOLATION={isolation})" if isolation else ""))
        print(f"   shell allowed: {self.allowed_commands()}")
        flags, note = self.model_choice(tool, model_stage)
        print(f"   model: {flags}{note}")

    def invoke(self, tool, prompt, raw, stage, story, count=True):
        """One stage's tool process; its output kept in <raw>, where the tool also says what the stage cost."""
        if count:
            self.invocations += 1
        flags, _note = self.model_choice(tool, stage)
        command = os.environ.get("FACTORY_TOOL_CMD")
        env = dict(os.environ, FACTORY_WORKER=self.worker, FACTORY_STAGE=stage or "", FACTORY_STORY=story or "")
        if command:
            env.update(FACTORY_PROMPT=prompt, FACTORY_RUNS=self.runs, FACTORY_MODEL=self.model_key(tool, stage))
            code = self.tool_process(["sh", "-c", command], env, raw, stdin=None, stage=stage)
            if raw != os.devnull and not os.environ.get("FACTORY_USAGE_FORMAT"):
                with contextlib.suppress(OSError):
                    sys.stdout.write(read_text(raw))
                    flush()
            return code
        if tool not in TOOL:
            err(f"factory: unknown tool '{tool}'")
            return 2
        variables, argv = tool_command(TOOL[tool], model=flags.split(" ", 1)[1] if flags else "",
                                       writable=self.add_dirs, readable=self.read_dirs,
                                       protected=self.protected_dirs(), allowed=self.allowed_commands())
        env.update(variables)
        return self.tool_process(spawnable(argv + [prompt]), env, raw, stdin=subprocess.DEVNULL, stage=stage)

    def tool_process(self, argv, env, raw, stdin, stage):
        """A tool started in a session of its own, so a time limit or an interrupt stops it with what it started."""
        flush()
        with open(raw, "wb") as out:
            try:
                process = subprocess.Popen(argv, env=env, stdin=stdin, stdout=out, start_new_session=os.name != "nt")
            except OSError as error:
                err(f"factory: the tool could not be started — {error}")
                return 127
            try:
                return self.wait(process, timeout=self.timeout or None)
            except subprocess.TimeoutExpired:
                stop_group(process)
                err(f"factory: stage '{stage}' ran past its time limit of {self.timeout}s (FACTORY_STAGE_TIMEOUT, the "
                    f"profile's stageTimeout:) — the tool was stopped.")
                return TIMED_OUT
            except KeyboardInterrupt:
                stop_group(process, signal.SIGINT)
                raise Stopped(SIGNAL_EXITS["SIGINT"])

    def exit_field(self, code):
        return "0" if code == 0 else "timeout" if code == TIMED_OUT else "nonzero"

    def record_usage(self, story, stage, tool, raw, seconds=None):
        """One `usage` line in the story's journal per invocation, and the stage's final message on screen."""
        fmt = self.usage_format(tool)
        model = self.model_flag(tool, stage)
        try:
            lines = "\n".join(usage_lines(fmt, raw, model)).split("\n")
        except Exception:                   # a raw output no reader understands costs the line, never the run
            lines = ["unknown"]
        fields = lines[0]
        if seconds is not None:
            fields += f"\tseconds={seconds}"
        if fmt != "none" and len(lines) > 1:
            print("\n".join(lines[1:]))
        self.journal_line(story, f"{utc()}\tusage\t{stage}\ttool={tool}\t{fields}")

    # --- what the files say --------------------------------------------------------------------------------
    def verdict_of(self, story):
        self.profile()
        return verdict_of_story(place("runs"), story)

    def asks_human(self, path):
        self.profile()
        return needs_human_lines(path) is not None

    def back_to(self, story, stage=None):
        """The stage a refusal sends the story back to: from the judge's file (`build` without one); with a stage,
        `test` where that stage found the defect in a test's own code, else nothing."""
        self.profile()
        path = os.path.join(place("runs"), story, STAGE_FILES[stage] if stage else "judge.md")
        if stage:
            return "test" if os.path.isfile(path) and back_in(read_text(path)) == "test" else ""
        return back_in(read_text(path)) if os.path.isfile(path) else "build"

    def start_stage(self, story):
        self.profile()
        found = start_of(os.getcwd(), place("epics"), place("runs"), story, 1)
        return "" if found is None else found[1] or "none"

    def open_decisions(self, story):
        self.profile()
        return "\n".join(open_decision_files(os.getcwd(), story))

    def delivered(self, story):
        self.profile()
        try:
            return is_delivered(read_front_matter(find_story(place("epics"), story))[0])
        except GateError:
            return False

    def kind_of(self, story):
        """`story`, `journey` or `adopt` — `story` for one that cannot be read."""
        self.profile()
        try:
            return story_kind(read_front_matter(find_story(place("epics"), story))[0])
        except GateError:
            return "story"

    def stopped_for_human(self, artefact, stage, story):
        """A stage that ends with a needs-human section has stopped: name the record and the command that resumes.
        3 when the question is a record — what a backlog run can wait on —, 1 when the section names none."""
        err(f"factory: stage '{stage}' ends with a needs-human section — the run stops here.")
        self.profile()
        rows = [line.split("\t") for line in needs_human_lines(artefact, story) or [] if line.strip()]
        ids = [row[0] for row in rows]
        if not ids:
            err("factory:   the section names no 'decision: <id>' — the stage has to write the question as")
            err("factory:   <story>/decisions/<nn>.md in the story's folder; the next gate refuses a question nobody was asked.")
        for rid in ids:
            record = next((row[2] for row in rows if row[0] == rid and len(row) > 2), "")
            if record and record != "-" and os.path.isfile(record):
                applies = next((row[1] for row in rows if row[0] == rid and len(row) > 1 and row[1] != "-"), "")
                err(f"factory:   decision {rid} → {record} — answer it there under '## Answer'")
                err(f"factory:   with answer:, by: and at:, then: factory.sh run --story {story} — it resumes at "
                    f"{applies or stage}, or earlier where the answer's applies: names an earlier stage")
            else:
                err(f"factory:   decision {rid} is named but its record {record or 'beside the story'} does not exist.")
        err(f"factory:   read {artefact} and decide; the stages after it were not run.")
        return 3 if ids else 1

    def refused_from(self, story, refused):
        """The stage a refused gate's round starts at: the refused stage, or an earlier one whose file the story's
        state reads as an earlier pass's."""
        start = self.start_stage(story)
        for st in STAGE_ORDER:
            if st == refused:
                break
            if st == start:
                return start
        return refused

    def bump_rounds(self, story):
        path = f"{self.evidence(story)}/.rounds"
        count = int("".join(c for c in read_text(path) if c.isdigit()) or 0) if os.path.isfile(path) else 0
        count += 1
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(f"{count}\n")
        return count

    def environment_refused(self, stage, story):
        """A refusal whose cause is the machine: no stage can put a tool on the PATH, so no round is counted."""
        report = f"{self.runs}/{story}/.gate-{stage}.txt"
        lines = read_text(report).splitlines() if os.path.isfile(report) else []
        if not any(line.startswith("gate:fail environment") for line in lines):
            return False
        reason = next((line[len("gate:fail environment — "):] for line in lines
                       if line.startswith("gate:fail environment — ")), "")
        err(f"factory: gate '{stage}' refused on the environment, not on the story — {reason}")
        err(f"factory:   no round is counted. Fix it, then: factory.sh run --story {story}")
        return True

    def reset_rounds(self, story, given_from):
        """A person's --from restarts the story's count; the old one is kept beside it, never deleted."""
        path = f"{self.evidence(story)}/.rounds"
        if not os.path.isfile(path):
            return
        os.replace(path, f"{self.evidence(story)}/rounds.{utc('%Y%m%dT%H%M%SZ')}")
        self.journal_line(story, f"{utc()}\trounds-reset\t-\tby=--from")
        print(f"factory: --from {given_from} starts a new count of rounds for {story} (the old one is under "
              f"{self.evidence(story)}/).")

    # --- what a stage is told ----------------------------------------------------------------------------------
    def skill_dirs(self, tool):
        first = TOOL[tool].skills if tool in TOOL else ""
        return [d for d in (first, *TOOL_SKILL_DIRS, ".agents/skills") if d]

    def where_things_are(self, tool, story):
        """What a stage otherwise searches for — the profile, the run folder, the gate's expectations, the
        catalog — named in its prompt."""
        common = next((f"{d}/factory-run/reference/stage-common.md" for d in self.skill_dirs(tool)
                       if os.path.isfile(f"{d}/factory-run/reference/stage-common.md")), "")
        own = os.path.abspath(os.path.join(self.scripts, "..", "reference", "stage-common.md"))
        if not common and os.path.isfile(own):
            common = own[len(self.pwd) + 1:] if own.startswith(self.pwd + "/") else own
        common = f" The rules every stage holds to: {common}." if common else ""
        catalog = ""
        profile = self.profile()
        knowledge = first_word(profile.get("knowledge", ""))
        if knowledge:
            at = next((f"{d}/{knowledge}/catalog/" for d in self.skill_dirs(tool)
                       if os.path.isdir(f"{d}/{knowledge}/catalog")), "")
            if at:
                catalog = f" The {knowledge} skill's catalog: {at}."
                read = [f"{at}{path}" for path in profile.get("knowledge.read", "").replace(",", " ").split()
                        if os.path.isfile(f"{at}{path}")]
                if read:
                    catalog += f" Before you write code, read once: {', '.join(read)}."
        cli_path = self.cli_path[len(self.pwd) + 1:] if self.cli_path.startswith(self.pwd + "/") else self.cli_path
        if os.path.isfile(".agents/factory/factory-cli.py"):
            cli_path = ".agents/factory/factory-cli.py"
        return (f"Where things are: the stack profile is {PROFILE_FILE}; the story's run folder {self.runs}/{story}/; "
                f"its evidence folder {self.evidence_rel()}/{story}/; what the gate checks in a stage's file: "
                f"`{self.py} {cli_path} --contract <stage>`.{common}{catalog} The shell you have without asking: "
                f"the gate, the cli, the profile's commands, and {STAGE_SHELL}.")

    def later_refusals(self, story, stage, where):
        """The reports of the gates after <stage> that refused the story and sent it back."""
        found, seen = "", False
        for later in STAGE_ORDER:
            if later == stage:
                seen = True
                continue
            if seen and os.path.isfile(f"{self.runs}/{story}/.gate-{later}.txt"):
                found += (f" The {later} gate refused the story and sent it back to {where}: "
                          f"{self.runs}/{story}/.gate-{later}.txt.")
        return found

    def worktree_sentence(self):
        home = os.environ.get("FACTORY_HOME")
        return f" This story's own worktree: {self.pwd}; the main checkout: {home}." if home else ""

    def guard_sentence(self):
        guard = first_word(self.profile().get("carrier.guard", ""))
        return f" The guard (the profile's carrier.guard): the {guard} skill." if guard else ""

    def prompt_for(self, stage, story):
        repeat = ""
        if os.path.isfile(f"{self.runs}/{story}/.gate-{stage}.txt"):
            repeat = f" The gate refused this stage before: {self.runs}/{story}/.gate-{stage}.txt."
        later = self.later_refusals(story, stage, "this stage")
        if later and stage == self.start_stage(story):
            repeat += later
        if stage == "test" and self.back_to(story, "build") == "test":
            repeat += f" The build stage sent the story back: {self.runs}/{story}/build.md."
        if stage == "judge" and os.path.isfile(f"{self.runs}/{story}/.judge-previous.md"):
            repeat = f" This is a repeat round; the previous verdict: {self.runs}/{story}/.judge-previous.md."
        guard = self.guard_sentence() if stage in STAGE and STAGE[stage].guarded else ""
        return (f"Apply the stage-{stage} skill for backlog story {story}.{self.worktree_sentence()} "
                f"{self.where_things_are(self.tool_in_flight, story)}{guard}{repeat}")

    def integrate_prompt(self, story, conflicts):
        return (f"Apply the stage-integrate skill for backlog story {story}. Merging the main line into this story's "
                f"branch stopped on conflicts in: {conflicts}. Their list: {self.evidence(story)}/conflicts."
                f"{self.worktree_sentence()} {self.where_things_are(self.tool_in_flight, story)}")

    # --- the gate --------------------------------------------------------------------------------------------
    def owned(self, edge, window, story, code=None):
        """What is the person's is unchanged across a stage window — recorded at its start, compared at its end."""
        if not self.gate_installed():
            return 0
        return self.run([sys.executable, self.gate_path, "--owned", edge, window,
                         *([str(code)] if code is not None else []), "--story", story])[0]

    def record(self, flag, story, *more):
        """`--record-base` / `--record-changes <stage>`: what the story's diff is taken against, and what it changed."""
        if self.gate_installed():
            self.run([sys.executable, self.gate_path, flag, *more, "--story", story], quiet=True,
                     stdout=subprocess.DEVNULL)

    def gate(self, stage, story, gate_path=None):
        gate_path = gate_path or self.gate_path
        if not os.path.isfile(gate_path):
            err(f"factory: no gate at {gate_path} — run 'factory.sh setup'")
            return 2
        report = f"{self.runs}/{story}/.gate-{stage}.txt"
        journal = self.evidence(story)
        os.makedirs(f"{self.runs}/{story}", exist_ok=True)
        os.makedirs(journal, exist_ok=True)
        if self.guard_pipeline(stage, story):
            raise Stopped(7)
        flush()
        env = dict(os.environ, FACTORY_SUITES_KEY=self.suites_key)
        process = subprocess.Popen([sys.executable, gate_path, "--story", story, "--stage", stage, "--record-suites"],
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)
        with open(report, "wb") as kept:
            for chunk in iter(lambda: process.stdout.readline(), b""):
                kept.write(chunk)
                sys.stdout.buffer.write(chunk)
                sys.stdout.flush()
        code = process.wait()
        # Every gate run is kept for the observer, with its verdict; only a refusal is kept where the next stage
        # reads it. 3 is not a refusal: every check passed and a human is asked (acceptance).
        shutil.copy(report, f"{journal}/gate-{stage}.{utc('%H%M%S')}.txt")
        if code in (0, 3):
            os.remove(report)
        return code

    def snapshot(self, story, label):
        """What the working tree looks like right now, so a later stage's claim about what it changed can be
        checked rather than believed."""
        journal = self.evidence(story)
        os.makedirs(journal, exist_ok=True)
        hashing = self.hashing()
        if not hashing:
            err("factory: no sha256 command found (shasum, sha256sum, openssl) — the tree snapshots")
            err("factory:   record file names without content, and factory-verify reports every check")
            err("factory:   that needs a digest as not observed. Install one of the three for full evidence.")
        lines = [NO_HASHES] if not hashing else []
        prefix = subprocess.run(["git", "rev-parse", "--show-prefix"], capture_output=True, text=True).stdout.strip()
        status = subprocess.run(["git", "-c", "core.fileMode=false", "status", "--porcelain", "-z", "-uall", "--", "."],
                                capture_output=True).stdout.decode("utf-8", errors="replace")
        strip = lambda name: name[len(prefix):] if prefix and name.startswith(prefix) else name
        origin = ""
        for entry in status.split("\0"):
            if not entry:
                continue
            if origin:                          # -z writes a rename's source as the next entry
                if origin == "R":
                    lines.append(f"deleted  {strip(entry)}")
                origin = ""
                continue
            code, name = entry[:2], strip(entry[3:])
            if code[:1] in ("R", "C"):
                origin = code[:1]
            if "D" in code:
                lines.append(f"deleted  {name}")
                continue
            if not os.path.isfile(name):
                continue
            lines.append(f"{file_sha(name) if hashing else '-'}  {name}")
        with contextlib.suppress(OSError):
            with open(f"{journal}/tree-{label}.txt", "w", encoding="utf-8", newline="\n") as handle:
                handle.write("".join(line + "\n" for line in lines))

    def adopt_gate(self, story, tool, dry):
        """Every scenario on a green test, the judge's pass, a break for every test the adoption wrote: passed, it
        delivers the story; refused, the test stage runs again, one round counted."""
        print("── gate adopt")
        if dry:
            return 0
        if self.gate("adopt", story) == 0:
            if os.environ.get("FACTORY_HOME"):
                return self.integrate_story(story, tool, dry)
            print(f"factory: story {story} is adopted.")
            return 0
        if self.environment_refused("adopt", story):
            return 1
        rounds = self.bump_rounds(story)
        if rounds >= 3:
            err(f"factory: gate 'adopt' refused in round {rounds} — three rounds did not converge. needs-human.")
            return 1
        err(f"factory: gate 'adopt' refused — round {rounds} runs the test stage again with the gate's report.")
        return self.run_stages(story, tool, "test", dry)

    # --- the budget before a dispatch ------------------------------------------------------------------------
    def used_tokens(self, story):
        try:
            self.profile()
            runs = place("runs")
            return sum(tokens_of(entry) for s in run_stories(runs) if s == story for entry in journal_usage(runs, s).values())
        except (OSError, ValueError, GateError):
            return 0

    def may_dispatch(self, story, what, count=1):
        """The claim renewed, the story's budget and the cap on stages checked before an invocation, never after.
        None when it may run, else the exit code (5 the checkout is gone, 4 a limit)."""
        self.checkpoint()
        if not self.renew():
            err(f"factory: the checkout was taken over by another worker before {what} — stopping.")
            return 5
        if self.story_budget and self.used_tokens(story) >= self.story_budget:
            return "budget"
        if self.max_stages and self.invocations + count - 1 >= self.max_stages:
            return "stages"
        return None

    def window(self, story, tool, window, stages, prompt):
        """One shared process — the builder or the verifier — from its snapshot to its usage line; the tool's exit
        code, or 7 when a person's file changed in it."""
        raw = f"{self.evidence(story)}/{window}.{utc('%H%M%S')}.out"
        self.record("--record-base", story)
        self.snapshot(story, f"before-{window}")
        self.owned("start", window, story)
        self.journal_line(story, f"{utc()}\tstage-start\t{window}\ttool={tool}\tstages={','.join(stages)}")
        began = time.time()
        invoked = self.invoke(tool, prompt, raw, window, story)
        self.record_usage(story, window, tool, raw, int(time.time() - began))
        self.journal_line(story, f"{utc()}\tstage-end\t{window}\texit={self.exit_field(invoked)}")
        self.checkpoint()
        if self.owned("end", window, story, invoked) != 0:
            return 7
        if invoked != 0:
            err("factory: the tool exited non-zero during the shared stages.")
            return 1
        self.snapshot(story, f"after-{window}")
        self.record("--record-changes", story, window)
        return 0

    # --- the shared processes ----------------------------------------------------------------------------------
    def budget_note(self, story, what):
        err(f"factory: story {story} has reached its --story-budget {self.story_budget} — {what} are not dispatched.")
        return 4

    def run_shared_builder(self, story, tool, start, dry, kind="story"):
        """Plan to tidy in one tool process, so each stage builds on what the one before read. The process runs
        each stage's gate itself; the runner checks, not believes: the red proof must exist and the gates after
        it run again here."""
        stages, on = [], False
        for st in SHARED_WINDOWS["builder"]:
            on = on or st == start
            if self.kind_runs(kind, st) and on:
                stages.append(st)
        if not stages:
            return 0
        prompt = (f"Carry out these stages of the delivery pipeline for backlog story {story}, one after another, in "
                  f"this one session: {', '.join(f'stage-{s}' for s in stages)}. The gate: "
                  f"`{self.py} {self.gate_rel} --story {story} --stage <stage> --brief`; the skeletons: "
                  f"`{self.py} {self.cli_path} --files-skeleton {story} <stage>`, "
                  f"`{self.py} {self.cli_path} --plan-skeleton {story}`. {self.where_things_are(tool, story)}")
        prompt += self.guard_sentence()
        if self.back_to(story, "build") == "test":
            prompt += f" The build stage sent the story back: {self.runs}/{story}/build.md."
        for refused in stages:
            if os.path.isfile(f"{self.runs}/{story}/.gate-{refused}.txt"):
                prompt += f" The gate refused stage {refused} before: {self.runs}/{story}/.gate-{refused}.txt."
        prompt += self.later_refusals(story, stages[-1], f"stage {start}")
        if os.path.isfile(f"{self.runs}/{story}/judge.md") and self.verdict_of(story) == "changes-requested":
            prompt += f" The judge asked for changes: {self.runs}/{story}/judge.md."
        print(f"── stage {'+'.join(stages)}  (tool: {tool}, one shared context)")
        if dry:
            self.dry_lines(tool, prompt, "builder")
            return 0
        refused = self.may_dispatch(story, "the shared stages")
        if refused == "budget":
            return self.budget_note(story, "the shared stages")
        if refused == "stages":
            err(f"factory: --max-stages {self.max_stages} reached before the shared stages of {story}.")
            return 4
        if refused:
            return refused
        code = self.window(story, tool, "builder", stages, prompt)
        if code:
            return code
        # A `back: test` the session already acted on is no round: tidy.md newer than build.md says it repaired the
        # test, built again and tidied — the re-checked gates below decide.
        repaired = "tidy" in stages and newer(f"{self.runs}/{story}/tidy.md", f"{self.runs}/{story}/build.md")
        sent_back = "build" in stages and self.back_to(story, "build") == "test"
        if sent_back and repaired:
            print("factory: build.md names a defect in a test's own code that the shared session repaired before tidy "
                  "— the gates re-check it.")
        if sent_back and not repaired:
            rounds = self.bump_rounds(story)
            if rounds >= 3:
                err(f"factory: the build stage sent the story back in round {rounds} — three rounds did not converge. "
                    "needs-human.")
                return 1
            err(f"factory: the build stage found a defect in a test's own code — round {rounds} goes back to the test stage.")
            self.nested_code = self.run_stages(story, tool, "test", dry)
            return 99
        for st in stages:
            artefact = self.artefact(story, st)
            if not os.path.isfile(artefact):
                err(f"factory: the shared stages produced no {artefact} — stage '{st}' is not finished.")
                return 1
            if self.asks_human(artefact):
                return self.stopped_for_human(artefact, st, story)
        # Checked, not believed: a story's tests were seen red; a journey's and an adoption's are green at their
        # test gate, so that gate runs again here.
        for st in stages:
            if not (STAGE[st].in_order and STAGE[st].tested and not STAGE[st].suite):
                continue
            if kind != "story":
                print(f"── gate {st}  (re-checked by the runner)")
                if self.gate(st, story) != 0:
                    err(f"factory: the runner's re-check of gate '{st}' refused the shared stages' work.")
                    return 1
            elif not os.path.isfile(f"{self.evidence(story)}/.tests-red") \
                    or not os.path.getsize(f"{self.evidence(story)}/.tests-red"):
                err(f"factory: the shared stages left no red proof ({self.evidence(story)}/.tests-red) — the {st} "
                    f"gate never saw the tests fail.")
                return 1
        for st in stages:
            if not STAGE[st].post_gated or (STAGE[st].tested and not STAGE[st].suite):
                continue
            print(f"── gate {st}  (re-checked by the runner)")
            if self.gate(st, story) != 0:
                if self.environment_refused(st, story):
                    return 1
                rounds = self.bump_rounds(story)
                if rounds >= 3:
                    err(f"factory: the runner's re-check of gate '{st}' refused in round {rounds} — three rounds did "
                        "not converge. needs-human.")
                    return 1
                err(f"factory: the runner's re-check of gate '{st}' refused — round {rounds} runs the shared stages "
                    f"again from '{st}' with the gate's report.")
                self.nested_code = self.run_stages(story, tool, st, dry)
                return 99
        return 0

    def run_reviews(self, story, tool, dry, kind="story"):
        """One tool process per perspective, started at once, each writing reviews/<perspective>.md; the judge then
        converges from the files. An adoption reviews no change and gets none."""
        if kind == "adopt":
            return 0
        self.profile()
        rows = [(name, carrier) for name, carrier in perspectives_of(read_profile(resolve_profile(None, os.getcwd())))
                if name]
        if not rows:
            return 0
        names = [row[0] for row in rows]
        carriers = [row[1] for row in rows]
        folder = f"{self.runs}/{story}/reviews"
        print(f"   reviews: {', '.join(names)} — one process each, at once; the judge converges from "
              "reviews/<perspective>.md")
        prompts = [(f"Review the change of backlog story {story} from the {name} perspective: apply the `{carrier}` "
                    f"skill to the diff {self.evidence(story)}/story.diff, as *A review the runner started* in the "
                    f"rules every stage holds to says. Its input beside the diff: the story and its epic (epic.md "
                    f"beside it), {self.runs}/{story}/plan.md, tests.md and build.md, and the product and technical "
                    f"description. Your report: {folder}/{name}.md. {self.where_things_are(tool, story)}")
                   for name, carrier in zip(names, carriers)]
        if dry:
            for name, prompt in zip(names, prompts):
                print(f"   would run (review:{name}): {prompt}")
            return 0
        refused = self.may_dispatch(story, "the reviews", count=len(names))
        if refused == "budget":
            return self.budget_note(story, "the reviews")
        if refused == "stages":
            err(f"factory: --max-stages {self.max_stages} reached before the reviews of {story} ({len(names)} process(es)).")
            return 4
        if refused:
            return refused
        os.makedirs(folder, exist_ok=True)
        os.makedirs(self.evidence(story), exist_ok=True)
        for old in glob.glob(f"{folder}/*.md"):           # a repeat round reviews today's change, never last round's
            os.remove(old)
        began = time.time()
        raws = {}
        for name in names:
            self.journal_line(story, f"{utc()}\tstage-start\treview:{name}\ttool={tool}")
            raws[name] = f"{self.evidence(story)}/review-{name}.{utc('%H%M%S')}.out"
        codes = {}
        threads = [threading.Thread(target=lambda n=name, p=prompt: codes.__setitem__(
                       n, self.invoke(tool, p, raws[n], f"review:{n}", story, count=False)))
                   for name, prompt in zip(names, prompts)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.invocations += len(names)
        seconds = int(time.time() - began)
        for name in names:
            self.record_usage(story, f"review:{name}", tool, raws[name], seconds)
            self.journal_line(story, f"{utc()}\tstage-end\treview:{name}\texit={self.exit_field(codes.get(name, 1))}")
            if not os.path.isfile(f"{folder}/{name}.md"):
                err(f"factory: the {name} reviewer left no {folder}/{name}.md — the judge runs that pass itself and says so.")
        self.checkpoint()
        return 0

    def judged(self, story, tool, dry, kind):
        """The judge's verdict decides what comes next — read from its file, never assumed. None to go on."""
        verdict = self.verdict_of(story)
        if verdict == "pass":
            print("factory: judge verdict 'pass'.")
            return None
        if verdict == "changes-requested":
            rounds = self.bump_rounds(story)
            if rounds >= 3:
                err(f"factory: judge verdict 'changes-requested' in round {rounds} — three rounds did not converge. "
                    "needs-human.")
                return 1
            back = self.back_for(kind, self.back_to(story) or "build")
            err(f"factory: judge verdict 'changes-requested' — round {rounds} goes back to the {back} stage.")
            return self.run_stages(story, tool, back, dry)
        if verdict == "story-conflict":
            err("factory: judge verdict 'story-conflict' — the story or the plan is wrong. This never goes back to the "
                f"build stage. needs-human: read {self.runs}/{story}/judge.md.")
            return 1
        if not verdict:
            err(f"factory: {self.runs}/{story}/judge.md carries no 'verdict:' line — the judge stage is not finished.")
            return 1
        err(f"factory: judge verdict '{verdict}' is not one of pass|changes-requested|story-conflict.")
        return 1

    def accepting(self, story):
        err(f"factory: story {story} waits for a human's acceptance — answer it with /factory-decisions;")
        err("factory:   the story holds the checkout until then.")
        return 3

    def run_shared_verifier(self, story, tool, dry, kind="story"):
        """Judge and document in one tool process — never one process with the builder: the judge's independence
        from the builder is the point of the split."""
        stages = [st for st in SHARED_WINDOWS["verifier"] if self.kind_runs(kind, st)]
        cli_path = self.cli_path[len(self.pwd) + 1:] if self.cli_path.startswith(self.pwd + "/") else self.cli_path
        document = (f" The skeleton: `{self.py} {cli_path} --document-skeleton {story}`; the document gate: "
                    f"`{self.py} {self.gate_rel} --story {story} --stage document --brief`.") if kind != "adopt" else ""
        prompt = (f"Carry out these stages of the delivery pipeline for backlog story {story}, one after another, in "
                  f"this one session: {', '.join(f'stage-{s}' for s in stages)}.{document} "
                  f"{self.where_things_are(tool, story)}")
        print(f"── stage {'+'.join(stages)}  (tool: {tool}, one shared context)")
        if dry:
            self.dry_lines(tool, prompt, "verifier")
            return 0
        refused = self.may_dispatch(story, "the shared stages")
        if refused == "budget":
            return self.budget_note(story, "the shared stages")
        if refused == "stages":
            err(f"factory: --max-stages {self.max_stages} reached before the shared stages of {story}.")
            return 4
        if refused:
            return refused
        judge = f"{self.runs}/{story}/judge.md"
        if os.path.isfile(judge):
            os.replace(judge, f"{self.runs}/{story}/.judge-previous.md")
        code = self.window(story, tool, "verifier", stages, prompt)
        if code:
            return code
        if not os.path.isfile(judge):
            err(f"factory: the shared stages produced no {judge} — stage 'judge' is not finished.")
            return 1
        if self.asks_human(judge):
            return self.stopped_for_human(judge, "judge", story)
        code = self.judged(story, tool, dry, kind)
        if code is not None:
            return code
        if self.kind_runs(kind, "adopt"):
            return self.adopt_gate(story, tool, dry)
        artefact = f"{self.runs}/{story}/document.md"
        if not os.path.isfile(artefact):
            err(f"factory: the shared stages produced no {artefact} — stage 'document' is not finished.")
            return 1
        if self.asks_human(artefact):
            return self.stopped_for_human(artefact, "document", story)
        print("── gate document  (re-checked by the runner)")
        gate_code = self.gate("document", story)
        if gate_code == 3:
            return self.accepting(story)
        if gate_code != 0:
            if self.environment_refused("document", story):
                return 1
            rounds = self.bump_rounds(story)
            if rounds >= 3:
                err(f"factory: gate 'document' refused in round {rounds} — three rounds did not converge. needs-human.")
                return 1
            again = self.refused_from(story, "document")
            err(f"factory: gate 'document' refused — round {rounds} runs stage '{again}' again with the gate's report.")
            return self.run_stages(story, tool, again, dry)
        return 0

    # --- a story's stages ----------------------------------------------------------------------------------------
    def run_stages(self, story, tool, start=None, dry=False):
        """The story's stages from <start> on, in the checkout it is called in."""
        start = start or STAGE_ORDER[0]
        waiting = self.open_decisions(story)
        if waiting:
            err(f"factory: story {story} waits for a decision — no stage runs until it is answered:")
            for record in waiting.split():
                err(f"factory:   {record}")
            err("factory:   answer under '## Answer' with answer:, by: and at:, then run the stage that asked (--from <stage>).")
            return 3
        kind = self.kind_of(story)
        # Every gate passed in the story's worktree: only the integration is left, and it delivers the story; an
        # adopted story whose judge passed: only the adopt gate.
        if start == "integrate":
            return self.integrate_story(story, tool, dry)
        if start == "adopt":
            return self.adopt_gate(story, tool, dry)
        started, ran, built = False, [], False
        for stage in STAGE_ORDER:
            started = started or stage == start
            if not started:
                continue
            row = STAGE[stage]
            if not self.kind_runs(kind, stage):
                why = {"journey": "a journey builds nothing", "adopt": "an adopted story is not built"}.get(
                    kind, f"a {kind} story does not run it")
                print(f"── stage {stage}  (skipped: {why})")
                continue
            if row.gated and not row.post_gated:
                print(f"── gate {stage}")
                if self.gate(stage, story) != 0:
                    err(f"factory: gate '{stage}' refused the story. Fix it before the stage runs.")
                    return 1
            if self.shared_builder and row.window == "builder":
                if not built:
                    code = self.run_shared_builder(story, tool, stage, dry, kind)
                    if code == 99:                  # a refused re-check ran the story again from there
                        return self.nested_code
                    if code != 0:
                        return code
                    built = True
                ran.append(stage)
                continue
            # The reviews come before the judge: one process per perspective, at once.
            if stage == "judge":
                code = self.run_reviews(story, tool, dry, kind)
                if code != 0:
                    return code
            # The verifier runs where the judge would; resumed at the document stage alone it runs in its own context.
            if self.shared_verifier and stage == SHARED_WINDOWS["verifier"][0]:
                code = self.run_shared_verifier(story, tool, dry, kind)
                if code != 0:
                    return code
                ran += [st for st in SHARED_WINDOWS["verifier"] if self.kind_runs(kind, st)]
                break
            artefact = self.artefact(story, stage)
            # Resumed at a gated stage whose file exists: the gate decides first, on today's tree.
            if self.gate_first and stage == start and not dry and stage != "document" and row.post_gated \
                    and os.path.isfile(artefact):
                self.gate_first = False
                print(f"── gate {stage}  (the file exists — checked before the stage is invoked)")
                if self.quiet_gate(stage, story) == 0:
                    print(f"factory: {artefact} already holds — stage '{stage}' is not invoked again.")
                    ran.append(stage)
                    continue
                if self.environment_refused(stage, story):
                    return 1
            self.gate_first = False
            # A resumed story whose document file exists and was never refused: its gate decides first.
            if stage == "document" and not dry and os.path.isfile(artefact) \
                    and not os.path.isfile(f"{self.runs}/{story}/.gate-document.txt") and not self.delivered(story):
                print("── gate document  (the file exists — checked before the stage is invoked)")
                if self.quiet_gate("document", story) == 0:
                    print(f"factory: {artefact} already holds — the document stage is not invoked again.")
                    ran.append("document")
                    break
            print(f"── stage {stage}  (tool: {tool}, fresh context)")
            self.tool_in_flight = tool
            if dry:
                self.dry_lines(tool, self.prompt_for(stage, story), stage)
            else:
                code = self.run_one(story, tool, stage, dry)
                if code is not None:
                    return code
            if row.post_gated:
                print(f"── gate {stage}")
                gate_code = 0 if dry else self.gate(stage, story)
                if gate_code == 3:
                    return self.accepting(story)
                if gate_code != 0:
                    if self.environment_refused(stage, story):
                        return 1
                    rounds = self.bump_rounds(story)
                    if rounds >= 3:
                        err(f"factory: gate '{stage}' refused in round {rounds} — three rounds did not converge. needs-human.")
                        return 1
                    again = self.refused_from(story, stage)
                    err(f"factory: gate '{stage}' refused — round {rounds} runs stage '{again}' again with the gate's report.")
                    return self.run_stages(story, tool, again, dry)
            ran.append(stage)
            if stage == "judge" and not dry:
                code = self.judged(story, tool, dry, kind)
                if code is not None:
                    return code
                if self.kind_runs(kind, "adopt"):
                    return self.adopt_gate(story, tool, dry)
        # What ran, not what the script knows how to run.
        print(f"factory: story {story} ran through {','.join(ran) or 'nothing'}.")
        if os.environ.get("FACTORY_HOME") and not dry and self.start_stage(story) == "integrate":
            return self.integrate_story(story, tool, dry)
        return 0

    def quiet_gate(self, stage, story):
        """A gate whose lines nobody reads — the runner asks it only whether a file already holds."""
        with open(os.devnull, "w") as null:
            saved = sys.stdout, sys.stderr
            sys.stdout = sys.stderr = null
            try:
                return self.gate(stage, story)
            finally:
                sys.stdout, sys.stderr = saved

    def run_one(self, story, tool, stage, dry):
        """One stage in a process of its own; None when it ran and its file stands, else the run's exit code."""
        self.checkpoint()
        if not self.renew():
            err(f"factory: the checkout was taken over by another worker before stage '{stage}' — stopping.")
            return 5
        if self.story_budget and self.used_tokens(story) >= self.story_budget:
            err(f"factory: story {story} has used {self.used_tokens(story)} tokens of its")
            err(f"factory:   --story-budget {self.story_budget} — stage '{stage}' is not dispatched; the work so far stays.")
            return 4
        if self.max_stages and self.invocations >= self.max_stages:
            err(f"factory: --max-stages {self.max_stages} reached before stage '{stage}' of {story} — nothing more is")
            err("factory:   dispatched; the work so far stays as it is and the next run continues from it.")
            return 4
        stage_started = utc()
        # The previous verdict is an input to the next one, not something to overwrite.
        if stage == "judge" and os.path.isfile(f"{self.runs}/{story}/judge.md"):
            os.replace(f"{self.runs}/{story}/judge.md", f"{self.runs}/{story}/.judge-previous.md")
        self.record("--record-base", story)
        artefact = self.artefact(story, stage)
        evidence = self.evidence(story)
        had_file = os.path.isfile(artefact)
        # The plan's and the document's file start as the pipeline's skeleton; a skeleton the pipeline wrote is kept
        # aside, so a stage that left it untouched produced nothing. A file an earlier pass left is no skeleton.
        skeleton = {"document": "--document-skeleton", "plan": "--plan-skeleton"}.get(stage)
        if skeleton and self.gate_installed():
            self.cli(skeleton, story)
        with contextlib.suppress(OSError):
            os.remove(f"{evidence}/{stage}.skeleton")
        if not had_file and skeleton and os.path.isfile(artefact):
            os.makedirs(evidence, exist_ok=True)
            shutil.copy(artefact, f"{evidence}/{stage}.skeleton")
        self.snapshot(story, f"before-{stage}")
        flags, note = self.model_choice(tool, stage)
        requested = self.model_key(tool, stage)
        model_fields = (f"\tmodel_requested={requested}" if requested else "") + \
            (f"\tmodel_applied=no ({note})" if note else "")
        if note:
            print(f"factory: model.{tool}.{stage}: {requested} — {note}")
        self.owned("start", stage, story)
        self.journal_line(story, f"{stage_started}\tstage-start\t{stage}\ttool={tool}{model_fields}")
        raw = f"{evidence}/{stage}.{utc('%H%M%S')}.out"
        began = time.time()
        invoked = self.invoke(tool, self.prompt_for(stage, story), raw, stage, story)
        self.record_usage(story, stage, tool, raw, int(time.time() - began))
        if self.owned("end", stage, story, invoked) != 0:
            self.journal_line(story, f"{utc()}\tstage-end\t{stage}\texit=owned")
            return 7
        if invoked != 0:
            self.journal_line(story, f"{utc()}\tstage-end\t{stage}\texit={self.exit_field(invoked)}")
            self.checkpoint()
            err(f"factory: the tool exited non-zero during stage '{stage}'.")
            return 1
        self.journal_line(story, f"{utc()}\tstage-end\t{stage}\texit=0")
        self.checkpoint()
        self.snapshot(story, f"after-{stage}")
        self.record("--record-changes", story, stage)
        if not os.path.isfile(artefact):
            err(f"factory: stage '{stage}' produced no {artefact} — a stage is finished when its file exists.")
            return 1
        kept = f"{evidence}/{stage}.skeleton"
        if os.path.isfile(kept) and read_bytes(kept) == read_bytes(artefact):
            err(f"factory: stage '{stage}' produced no {artefact} beyond the pipeline's skeleton — a stage is finished "
                "when it wrote its file.")
            return 1
        # The build stage found a defect in a test's own code: the round goes to the test stage, no human is asked.
        sent_back = self.back_to(story, stage) if stage == "build" else ""
        if sent_back:
            rounds = self.bump_rounds(story)
            if rounds >= 3:
                err(f"factory: the build stage sent the story back in round {rounds} — three rounds did not converge. "
                    "needs-human.")
                return 1
            err(f"factory: the build stage found a defect in a test's own code — round {rounds} goes back to the "
                f"{sent_back} stage.")
            return self.run_stages(story, tool, sent_back, dry)
        # A stage that ends with a needs-human section has stopped, whatever its file otherwise says.
        if self.asks_human(artefact):
            return self.stopped_for_human(artefact, stage, story)
        return None

    # --- a story in its worktree (WP-92) -------------------------------------------------------------------------
    def in_home(self, *args, merge=True):
        """A cli call made in the main checkout, as a person's would be there: (exit code, its lines)."""
        return self.cli(*args, merge=merge, quiet=False, cwd=os.environ.get("FACTORY_HOME") or self.home,
                        env=self.home_env())

    def link_worktree(self, story):
        self.run([sys.executable, self.cli_path, "--worktree-link", story], cwd=os.environ.get("FACTORY_HOME") or self.home,
                 env=self.home_env())

    def integrate_story(self, story, tool, dry):
        """Delivered is the integration: the main line merged into the story (a stage-integrate agent where git stops
        on a conflict), squashed, the gate once more on that tree, the main checkout fast-forwarded — under the lock."""
        print("── integrate")
        if dry:
            print(f"   would merge {story}'s branch with the main line and fast-forward the main checkout")
            return 0
        home = os.environ.get("FACTORY_HOME") or self.home
        for attempt in (1, 2, 3):
            self.take_lock()
            try:
                code, out = self.in_home("--integrate-prepare", story)
                print(out)
                if code == 3:
                    conflicts = "".join(line[len("conflict: "):] + " " for line in out.split("\n")
                                        if line.startswith("conflict: "))
                    print(f"── stage integrate  (tool: {tool}, fresh context — the merge stopped on: {conflicts})")
                    self.link_worktree(story)
                    self.tool_in_flight = tool
                    raw = f"{self.evidence(story)}/integrate.{utc('%H%M%S')}.out"
                    began = time.time()
                    self.owned("start", "integrate", story)
                    self.journal_line(story, f"{utc()}\tstage-start\tintegrate\ttool={tool}")
                    code = self.invoke(tool, self.integrate_prompt(story, conflicts), raw, "integrate", story)
                    self.record_usage(story, "integrate", tool, raw, int(time.time() - began))
                    self.journal_line(story, f"{utc()}\tstage-end\tintegrate\texit={self.exit_field(code)}")
                    self.checkpoint()
                    if self.owned("end", "integrate", story, code) != 0:
                        return 7
                    record = f"{self.runs}/{story}/integrate.md"
                    if os.path.isfile(record) and self.asks_human(record):
                        self.drop_lock()
                        return self.stopped_for_human(record, "integrate", story)
                    code, out = self.in_home("--integrate-finish", story)
                    print(out)
                    if code != 0:
                        err(f"factory: the conflicts of {story} are not resolved — needs-human: the worktree {self.pwd} "
                            "holds the merge.")
                        return 1
                elif code != 0:
                    err(f"factory: {story} could not be merged with the main line — the worktree {self.pwd} keeps it as it was.")
                    return 1
                print("── gate integrate")
                code = self.gate("integrate", story, gate_path=f"{home}/{self.gate_rel}")
            finally:
                self.drop_lock()
            if code == 0:
                print(f"factory: story {story} is integrated and delivered.")
                return 0
            report = f"{self.runs}/{story}/.gate-integrate.txt"
            fails = [line for line in (read_text(report).splitlines() if os.path.isfile(report) else [])
                     if line.startswith("gate:fail ")]
            if fails and all(line.startswith("gate:fail moved") for line in fails):
                print(f"factory: the main line moved on while {story} was merged — merged again (attempt {attempt + 1}).")
                continue
            if any(line.startswith("gate:fail checkout") for line in fails):
                err(f"factory: the main checkout could not take {story} — see {report}; then: factory.sh run --story "
                    f"{story} --from integrate")
                return 1
            if self.environment_refused("integrate", story):
                return 1
            rounds = self.bump_rounds(story)
            if rounds >= 3:
                err(f"factory: gate 'integrate' refused in round {rounds} — three rounds did not converge. needs-human.")
                return 1
            err(f"factory: gate 'integrate' refused the story on the main line — round {rounds} runs the build stage "
                "again with the gate's report.")
            # the integration took the links down; the build stage works with them again — and document.md is an
            # earlier pass's: the document stage writes it for the story as it now is, or its gate passes it as it is
            self.take_lock()
            try:
                self.link_worktree(story)
            finally:
                self.drop_lock()
            self.journal_line(story, f"{utc()}\toutdated\tdocument.md\tby=integrate")
            return self.run_stages(story, tool, "build", dry)
        err(f"factory: the main line moved on three times while {story} was integrated — run it again.")
        return 1

    def run_story(self, story, tool, start, dry):
        """Every story in its worktree: made or brought up to date and linked, under the lock; the stages run in it
        with the run folder named absolutely and FACTORY_HOME naming this checkout; delivered, its worktree goes."""
        if dry:
            return self.run_stages(story, tool, start, dry)
        self.take_lock()
        try:
            _, out = self.cli("--worktree-prepare", story, quiet=False)
        finally:
            self.drop_lock()
        wt = out.split("\n")[-1] if out else ""
        if wt.startswith("none"):
            print(f"factory: {story} runs in the checkout — {wt[len('none — '):] if wt.startswith('none — ') else wt}")
            return self.run_stages(story, tool, start, dry)
        if not wt:
            err(f"factory: no worktree could be made for {story} — nothing ran.")
            return 1
        print(f"factory: {story} works in its worktree, {wt[len(self.home) + 1:] if wt.startswith(self.home + '/') else wt}")
        self.profile()
        self.add_dirs = [f"{self.home}/{linked}" for linked in (self.runs_rel, place("epics"), place("discovery"))
                         if linked and os.path.isdir(f"{self.home}/{linked}")]
        self.read_dirs = [f"{self.home}/{linked}" for linked in
                          (".agents/factory", self.evidence_rel(), *TOOL_SKILL_DIRS, ".agents/skills")
                          if os.path.isdir(f"{self.home}/{linked}")]
        os.chdir(wt)
        self.pwd = wt
        os.environ["FACTORY_HOME"] = self.home
        self.runs = f"{self.home}/{self.runs_rel}"
        try:
            code = self.run_stages(story, tool, start, dry)
        finally:
            os.chdir(self.home)
            self.pwd = self.home
            os.environ.pop("FACTORY_HOME", None)
            self.runs = self.runs_rel
            self.add_dirs, self.read_dirs = [], []
            self.profile()
        if code == 0 and self.delivered(story):
            self.take_lock()
            try:
                self.run([sys.executable, self.cli_path, "--worktree-remove", story])
            finally:
                self.drop_lock()
        return code

    # --- the backlog -------------------------------------------------------------------------------------------
    def parallel_slots(self):
        """How many stories run at once: --parallel, else FACTORY_PARALLEL, else the profile's `parallel:`, else 1."""
        given = self.parallel or os.environ.get("FACTORY_PARALLEL") or first_word(self.profile().get("parallel", "")) or "1"
        if not given.isdigit() or int(given) == 0:
            err(f"factory: parallel takes a whole number of stories, 1 or more — not '{given}'")
            return None
        return int(given)

    def nothing_more(self, out, watch):
        print(out)
        print("factory: nothing more can run" + (", and nothing waits on an answer that would change that" if watch else "")
              + ".")

    def waiting_note(self, out, previous, interval):
        """Waiting is reading files, never asking an agent: an unchanged schedule is said once."""
        if out != previous:
            print(out)
            print(f"factory: waiting for an answer — the schedule is read again every {interval}s; {self.stop_file} "
                  "ends the watch.")
        return out

    def run_backlog(self, tool, watch, interval, dry):
        """Story after story, in the order the schedule names, read off the files every time. A failure ends it."""
        if not self.gate_installed():
            err(f"factory: no gate at {self.gate_rel} — run 'factory.sh setup'")
            return 2
        slots = self.parallel_slots()
        if slots is None:
            return 2
        # a superseded story's worktree has nothing to integrate; it goes before the first story starts
        if not dry:
            self.take_lock()
            try:
                self.run([sys.executable, self.cli_path, "--worktree-prune"])
            finally:
                self.drop_lock()
        if slots > 1 and not dry:
            return self.run_parallel(tool, watch, interval, slots)
        previous, last = "", ""
        while True:
            # waiting is working too: the claim is renewed on every look
            if not dry and not self.renew():
                err("factory: another worker took over this checkout — the backlog run ends here.")
                return 5
            if os.path.isfile(self.stop_file):
                print(f"factory: {self.stop_file} exists — the backlog run stops here. Remove it to run again.")
                return 0
            code, out = self.cli("--schedule", "--slots", "1", merge=True)
            if code != 0:
                err(out)
                err("factory: the schedule could not be read.")
                return 1
            following = next((line[len("next: "):] for line in out.split("\n") if line.startswith("next: ")), "")
            if following and not following.startswith("none"):
                story, start = following.split(" ", 1)[0], following.split(" ", 1)[-1]
                if following == last:
                    print(out)
                    err(f"factory: {story} ran from {start} and the schedule names it there again — no progress, stopping.")
                    return 1
                print(f"══ story {story} from {start}")
                if dry:
                    print(out)
                    print(f"   would run: factory.sh run --story {story} --from {start}")
                    return 0
                code = self.run_story(story, tool, start, False)
                if code == 0:
                    last = following
                    continue
                if code == 3:                       # waits for a decision; the schedule skips it now
                    last = ""
                    continue
                err(f"factory: story {story} stopped (exit {code}) — the backlog run ends here.")
                return code
            if not watch or not any(line == "wait: yes" or line.startswith("wait: yes") for line in out.split("\n")):
                self.nothing_more(out, watch)
                return 0
            previous = self.waiting_note(out, previous, interval)
            last = ""
            self.sleep(interval)

    def run_parallel(self, tool, watch, interval, slots):
        """Several stories at once, each in its worktree, each a runner process of its own whose lines carry its id.
        A failure starts nothing more and lets the running ones finish; so does the stop file and a TERM."""
        children, seen, failed, stopping, previous, out = {}, set(), 0, None, "", ""
        while True:
            if stopping is None and self.pending is not None:
                stopping, failed = self.pending, failed or self.pending
                self.pending = None
                err("factory: stopped by a signal — no further story starts; the running ones finish.")
            if stopping is None and not self.renew():
                err("factory: another worker took over this checkout — no further story starts.")
                stopping, failed = 5, 5
            if stopping is None and os.path.isfile(self.stop_file):
                print(f"factory: {self.stop_file} exists — no further story starts; the running ones finish.")
                stopping = "stop"
            for story, (process, start, pump) in list(children.items()):
                if process.poll() is None:
                    continue
                pump.join()
                del children[story]
                code = process.returncode
                if code == 0:
                    seen.add(f"{story}@{start}")
                elif code != 3:
                    err(f"factory: story {story} stopped (exit {code}) — no further story starts; the running ones finish.")
                    stopping = stopping if stopping is not None else code
                    failed = failed or code
            launched = False
            if stopping is None:
                code, out = self.cli("--schedule", "--slots", str(slots), "--busy", ",".join(children), merge=True)
                if code != 0:
                    err(out)
                    err("factory: the schedule could not be read.")
                    stopping, failed = 1, 1
                else:
                    for following in [line[len("next: "):] for line in out.split("\n") if line.startswith("next: ")]:
                        if following.startswith("none"):
                            continue
                        story, start = following.split(" ", 1)[0], following.split(" ", 1)[-1]
                        if f"{story}@{start}" in seen:
                            err(f"factory: {story} ran from {start} and the schedule names it there again — no "
                                "progress, not started again.")
                            failed = failed or 1
                            stopping = stopping if stopping is not None else 1
                            continue
                        print(f"══ story {story} from {start}  (slots: {slots})")
                        os.makedirs(f"{self.home}/{self.evidence_rel()}/{story}", exist_ok=True)
                        children[story] = self.start_child(story, tool, start)
                        launched = True
            if not children and not launched:
                if stopping is not None:
                    return failed if isinstance(stopping, int) or failed else 0
                if not watch or not any(line.startswith("wait: yes") for line in out.split("\n")):
                    self.nothing_more(out, watch)
                    return failed
                previous = self.waiting_note(out, previous, interval)
                time.sleep(interval)
                continue
            time.sleep(2)

    def start_child(self, story, tool, start):
        """One story's run as a runner process of its own — the same worker on the claim, the run's pipeline hash —
        its lines named with the story's id."""
        options = self.options
        argv = [sys.executable, self.cli_path, "--run", "--child", "--story", story, "--from", start, "--tool", tool,
                "--builder", options.builder, "--verifier", options.verifier]
        argv += ["--max-stages", str(options.max_stages)] if options.max_stages else []
        argv += ["--story-budget", str(options.story_budget)] if options.story_budget else []
        env = dict(os.environ, FACTORY_RUNNER_WORKER=self.worker, FACTORY_RUNNER_PIPELINE_SHA=self.pipeline_sha)
        flush()
        process = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)

        def pump():
            for line in iter(process.stdout.readline, b""):
                sys.stdout.write(f"[{story}] {line.decode('utf-8', errors='replace').rstrip(chr(10))}\n")
                sys.stdout.flush()
        thread = threading.Thread(target=pump, daemon=True)
        thread.start()
        return process, start, thread


TOOL_SKILL_DIRS = tuple(tool.skills for tool in TOOLS)


# --- what the runner reads from the project's files ----------------------------------------
# One reader for the profile, a stage file and a decision record: the gate's. The runner calls these in its
# own process; the cli prints the same answers for a person or a stage.

COMMAND_KEYS = ("compile", "test", "e2eTest", "architecture", "format", "formatFix")


def command_heads(profile):
    """The first word of every command the profile declares, once each, in the profile's order."""
    heads = []
    for key, value in profile.items():
        if key in COMMAND_KEYS or key.startswith("test."):
            head = first_word(value)
            if head and not head.startswith("{{") and head not in heads:
                heads.append(head)
    return heads


def model_for(profile, tool, stage):
    return first_word(profile.get(f"model.{tool}.{stage}") or profile.get(f"model.{tool}") or "")


def verdict_of_story(runs, story_id):
    path = os.path.join(runs, story_id, "judge.md")
    return verdict_in(read_text(path)) if os.path.isfile(path) else ""


def needs_human_lines(path, story_id=None):
    """`<id>\\t<stage>\\t<record path>` for every decision the file's needs-human section names; None when it
    asks nobody. The record lives beside the story, so the story's id says where to look."""
    ids = needs_human_ids(read_text(path)) if os.path.isfile(path) else None
    if ids is None:
        return None
    lines = []
    for decision_id in ids:
        record, stage = "", ""
        try:
            record = record_path(story_id, decision_id) if story_id else ""
        except GateError:
            record = ""
        if record and os.path.isfile(record):
            try:
                stage = str(read_front_matter(record)[0].get("stage", "") or "")
            except GateError:
                stage = ""
        lines.append(f"{decision_id}\t{stage or '-'}\t{shown(record) if record else '-'}")
    return lines


def open_decision_files(cwd, story_id):
    """The records beside the story that carry no `## Answer` yet — the cheap check a run makes
    before a stage; the gate does the fine reading (a draft without a name is still open)."""
    try:
        store = decisions_store(find_story(place("epics"), story_id))
    except GateError:
        return []
    if not os.path.isdir(store):
        return []
    found = []
    for name in sorted(os.listdir(store)):
        if not name.endswith(".md"):
            continue
        text = read_text(os.path.join(store, name))
        if not re.search(r"^## Answer", text, re.M):
            found.append(shown(os.path.join(store, name)))
    return found




# --- the run's start ---------------------------------------------------------------------------------------------
STAMP = ".agents/factory/gate.installed"
#: The files the install puts into .agents/factory/, in the stamp's order; a name ending in `/` is the package.
PIPELINE_FILES = ("story-gate.py", "factory-cli.py", "observe.py", "factory.sh", "dca_factory/")


def file_sha(path):
    try:
        with open(path, "rb") as handle:
            return hashlib.sha256(handle.read()).hexdigest()
    except OSError:
        return ""


def read_bytes(path):
    with open(path, "rb") as handle:
        return handle.read()


def field_of(text, key):
    return next((line[len(key) + 2:] for line in text.split("\n") if line.startswith(f"{key}: ")), "")


def flush():
    sys.stdout.flush()
    sys.stderr.flush()


def err(text):
    sys.stdout.flush()
    print(text, file=sys.stderr, flush=True)


def stop_group(process, first=None):
    """A tool and what it started, stopped: <first> (TERM by default), then KILL after five seconds."""
    if os.name == "nt":
        process.kill()
        process.wait()
        return
    for sig, grace in ((first or signal.SIGTERM, 5), (signal.SIGKILL, 5)):
        with contextlib.suppress(OSError):
            os.killpg(process.pid, sig)
        try:
            process.wait(timeout=grace)
            return
        except subprocess.TimeoutExpired:
            continue


def spawnable(argv):
    """On Windows a tool found on the PATH may be a script or a `.cmd`, which no process starts by itself."""
    if os.name != "nt":
        return argv
    found = shutil.which(argv[0]) or argv[0]
    if found.lower().endswith((".cmd", ".bat")):
        return ["cmd", "/c", found, *argv[1:]]
    if not found.lower().endswith((".exe", ".com")):
        return ["sh", found, *argv[1:]]
    return [found, *argv[1:]]


def run_options(argv):
    parser = argparse.ArgumentParser(prog="factory.sh run", description="the runner, started by `factory.sh run`")
    parser.add_argument("--story")
    parser.add_argument("--tool", default="")
    parser.add_argument("--from", dest="start", default="")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--interval", type=int, default=30)
    parser.add_argument("--max-stages", type=int, default=0)
    parser.add_argument("--story-budget", type=int, default=0)
    parser.add_argument("--builder", choices=("shared", "separate"), default="shared")
    parser.add_argument("--verifier", choices=("shared", "separate"), default="shared")
    parser.add_argument("--parallel", default="")
    parser.add_argument("--child", action="store_true", help="one story of a parallel run, under its parent's claim")
    return parser.parse_args(argv)


def run_main(argv):
    """`factory.sh run` once its checks passed: the claim, the pipeline's hash, the story or the backlog, and the
    claim and the lock given back however the run ends."""
    for stream in (sys.stdout, sys.stderr):
        with contextlib.suppress(AttributeError, ValueError):
            stream.reconfigure(line_buffering=True)
    options = run_options(argv)
    cwd = os.getcwd()
    home = os.environ.get("FACTORY_HOME") or os.path.realpath(cwd)
    set_places(read_profile(resolve_profile(os.environ.get("FACTORY_PROFILE") or None, cwd)))
    run = Run(options, home, place("runs"), worker=os.environ.get("FACTORY_RUNNER_WORKER") if options.child else None)

    def stop(signum, _frame):
        name = signal.Signals(signum).name
        err("factory: stopped by a hang-up — after the running stage, nothing more starts" if name == "SIGHUP" else
            "factory: stopped by a signal — after the running stage, nothing more starts")
        run.pending = SIGNAL_EXITS[name]
        if run.sleeping:
            run.pending = None
            raise Stopped(SIGNAL_EXITS[name])
    for name in ("SIGTERM", "SIGHUP"):
        if hasattr(signal, name):
            signal.signal(getattr(signal, name), stop)
    try:
        code = run_start(run, options)
        run.checkpoint()
        return code
    except Stopped as stopped:
        return stopped.code
    except KeyboardInterrupt:
        err("factory: interrupted — the claim and the lock are given back; the stage's files stay as they are.")
        return SIGNAL_EXITS["SIGINT"]
    finally:
        run.drop_lock()
        if not options.child:
            run.release()


def run_start(run, options):
    tool = options.tool
    if options.child:
        run.gate_first = False
        return run.run_story(options.story, tool or "stand-in", options.start, False)
    if options.story:
        story, start = options.story, options.start
        if not start:
            # No stage named: the story starts where its files say, as the backlog run would start it.
            code, answer = run.cli("--story", story, "--start", "--slots", "1", quiet=False)
            if code != 0:
                return code
            state, start, detail = field_of(answer, "state"), field_of(answer, "start"), field_of(answer, "detail")
            if start in ("none", ""):
                if state == "delivered":
                    print(f"factory: story {story} is delivered" + (f" ({detail})" if detail else "") + " — nothing runs.")
                    return 0
                if state == "waiting":
                    err(f"factory: story {story} waits for {detail} — answer it with /factory-decisions.")
                    return 3
                if state == "running":
                    err(f"factory: story {story} is running ({detail}) — one run at a time.")
                    return 5
                err(f"factory: story {story} is {state}" + (f" — {detail}" if detail else "") + ".")
                err(f"factory:   nothing runs; name the stage to run it anyway: factory.sh run --story {story} --from <stage>")
                return 1
            print(f"factory: story {story} starts at {start}" + (f" — {detail}" if detail else ""))
        else:
            names = [s.name for s in STAGES if s.in_order] + [s.name for s in STAGES if not s.in_order]
            if start not in names:
                err(f"factory: --from {start} names no stage ({' '.join(names)}) — nothing ran, the rounds are as they were")
                return 2
            if not options.dry_run:
                run.reset_rounds(story, start)
        run.gate_first = True
        if not options.dry_run:
            code = run.take_checkout() or run.guard_pipeline_start()
            if code:
                return code
        return run.run_story(story, tool or "stand-in", start, options.dry_run)
    if not options.dry_run:
        code = run.take_checkout() or run.guard_pipeline_start()
        if code:
            return code
    return run.run_backlog(tool or "stand-in", options.watch, max(1, min(3600, options.interval)), options.dry_run)
