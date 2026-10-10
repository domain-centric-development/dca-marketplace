"""What the runner asks before and between stages — its stage arrays, a story's worktree, the skeletons.

The shell tables the runner reads once at its start, the worktree a story runs in (prepare, link, squash,
integrate, remove), the layout migration an update runs, and the skeleton of every stage file the runner
writes before a stage.
"""

import contextlib
import os
import re
import shlex
import shutil
import sys
import time
from .contract import (
    ALL_KINDS, CONTRACT, DECISIONS_DIR, DEFAULTS, evidence_dir, evidence_rel, find_story, FINDINGS_FILE, flat_stories,
    GateError, git, is_delivered, MAPPING_ROW, NOTHING, place, PROFILE_FILE, read_front_matter, read_profile, read_text,
    record_path, resolve_profile, SELECTOR, set_places, SHARED_WINDOWS, shown, STAGE, STAGE_FILES, STAGE_ORDER, STAGES,
    STORY_BRANCH, story_digest, STORY_FILE, story_files, story_folder, story_kind, worktree_places)
from .state import (
    git_tree, has_worktree, listed_files, run_owned, snapshot_reason, STAGE_WORD, STAGES_MADE, STORY_DIGEST,
    story_title, tree_changes, worktree_of, worktrees_dir, write_mark, write_story_fields)
from .gate import (
    BUILT_IN_PERSPECTIVES, CLAUSES_MARKER, CONFLICT_MARKER, contract_of, criteria_of, HANDOVER_BUDGET,
    integration_target, INVARIANTS_MARKER, plan_invariants, plan_proposals, read_clause_rows, read_invariant_rows,
    scenario_clauses, TESTS_BASELINE)
from .tools import (
    tools_shell)


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
