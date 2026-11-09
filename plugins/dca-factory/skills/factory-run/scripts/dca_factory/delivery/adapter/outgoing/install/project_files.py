"""The pipeline's own files in the project and the lines it keeps in the project's files: the package, the workflow,
the gate, the cli, the observer, the runner and the commit hook under `.agents/factory/` and `.githooks/`; the stamp;
the hooks path; the ignore and merge lines; the instruction block in `AGENTS.md`; Claude Code's allow list."""

from __future__ import annotations

import json
import os
import re
import shutil
import stat
import subprocess
import traceback
import typing

from ..files.pipeline_digest import PIPELINE_FILES, STAMP, pipeline_digest
from .skill_folders import copy_tree, must, remove, say, warn
from .sources import gate_field

GATE = ".agents/factory/story-gate.py"
FOLDER = ".agents/factory"


def read(path: str) -> str:
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            return handle.read()
    except OSError:
        return ""


def copied(source: str, target: str) -> bool:
    try:
        shutil.copy(source, target)
        return True
    except OSError:
        return False


def executable(*paths: str) -> bool:
    try:
        for path in paths:
            os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        return True
    except OSError:
        return False


def swapped(source: str, name: str, what: str) -> None:
    """A folder of the pipeline swapped in whole: nothing the new release no longer has stays behind, and no
    __pycache__ travels with it."""
    fresh = os.path.join(FOLDER, f".{name}.new")
    remove(fresh)
    must(f"copy the {what} to {FOLDER}/{name}", copy_tree(source, fresh))
    remove(os.path.join(FOLDER, name))
    try:
        os.rename(fresh, os.path.join(FOLDER, name))
        moved = True
    except OSError:
        moved = False
    must(f"put the {what} in place", moved)


def copy_pipeline(source: str) -> None:
    """The package, the workflow, the gate, the cli, the observer, the runner and the commit hook from the skill
    folder <source>, and the stamp of what was installed."""
    scripts = os.path.join(source, "factory-run", "scripts")
    swapped(os.path.join(scripts, "dca_factory"), "dca_factory", "package")
    # The workflow's elements beside it — the stages and the rules the gate and the runner load at start.
    swapped(os.path.join(scripts, "workflow"), "workflow", "workflow")
    must(f"copy the gate to {GATE}", copied(os.path.join(scripts, "story-gate.py"), GATE))
    # What shows and coordinates, beside the gate that decides — the same release, checked before a run.
    must("copy the cli to .agents/factory/factory-cli.py",
         copied(os.path.join(scripts, "factory-cli.py"), f"{FOLDER}/factory-cli.py"))
    # The observer beside it, for `factory.sh verify --story`: a delivered story is checked in the project.
    must("copy the observer to .agents/factory/observe.py",
         copied(os.path.join(source, "factory-verify", "scripts", "observe.py"), f"{FOLDER}/observe.py"))
    # The runner goes beside the gate, so the project has one entry point for everything it does with the pipeline.
    # Replaced, never written over: a runner reading the old file as it goes keeps the bytes it started with.
    fresh = f"{FOLDER}/.factory.sh.new"
    must("copy the runner to .agents/factory/factory.sh", copied(os.path.join(scripts, "factory.sh"), fresh))
    must("make the runner executable", executable(fresh))
    try:
        os.replace(fresh, f"{FOLDER}/factory.sh")
        moved = True
    except OSError:
        moved = False
    must("put the runner in place", moved)
    must("copy the commit hook to .githooks/pre-commit",
         copied(os.path.join(source, "factory-run", "templates", "githooks", "pre-commit"), ".githooks/pre-commit"))
    must("make the gate, the cli and the commit hook executable",
         executable(".githooks/pre-commit", GATE, f"{FOLDER}/factory-cli.py"))
    # Which pipeline this project is governed by — committed with the project, so it is the same answer for everyone
    # who checks it out. Deliberately no path and no timestamp: both describe the machine that ran the install.
    version, contract = gate_field(GATE, "VERSION") or "", gate_field(GATE, "CONTRACT") or ""
    with open(STAMP, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(f"plugin: dca-factory\nversion: {version}\ncontract: {contract}\n"
                     f"files: {' '.join(PIPELINE_FILES)}\nsha256: {pipeline_digest(FOLDER) or ''}\n")
    say(f"factory: gate → {GATE} (version {version}, file contract {contract})")


def git(*args: str) -> typing.Tuple[int, str]:
    try:
        done = subprocess.run(["git", *args], capture_output=True, text=True, encoding="utf-8", errors="replace")
    except OSError:
        return 127, ""
    return done.returncode, done.stdout


def hooks_path() -> None:
    """Not a must: the project need not be a git repository for the gate to work. The hook is then absent, and said
    to be. Another hook manager owning the hooks is left as it is — it calls ours instead."""
    _code, configured = git("config", "--get", "core.hooksPath")
    configured = configured.strip()
    if configured and configured != ".githooks":
        warn(f"factory: core.hooksPath is {configured}, not .githooks — left as it is. Call .githooks/pre-commit")
        warn(f"factory:   from {configured}/pre-commit, or nothing checks a commit.")
    elif git("config", "core.hooksPath", ".githooks")[0] == 0:
        say("factory: git hooks → .githooks")
    else:
        warn("factory: no git repository here — .githooks/pre-commit is installed but nothing runs it.")


def ends_open(path: str) -> bool:
    """The file is there, not empty, and its last line has no newline."""
    try:
        with open(path, "rb") as handle:
            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                return False
            handle.seek(-1, os.SEEK_END)
            return handle.read(1) != b"\n"
    except OSError:
        return False


def append_line(path: str, line: str) -> None:
    with open(path, "a", encoding="utf-8", newline="") as handle:
        handle.write(("\n" if ends_open(path) else "") + line + "\n")


def file_lines(path: str) -> typing.List[str]:
    return read(path).split("\n")


def project_ignores(runs: str, evidence: str) -> None:
    """The journals merged by keeping both sides; what a file manager drops and the pipeline's own protocol out of
    git."""
    # The journal is append-only, one line per event: two branches that ran the same story both add lines at its end,
    # which git reports as a conflict although keeping both is always right.
    if "journal.tsv merge=union" not in read(".gitattributes"):
        append_line(".gitattributes", f"{evidence}/**/journal.tsv merge=union")
        say("factory: .gitattributes merges the story journals by keeping both sides (merge=union)")
    # What a file manager drops into any folder it shows: no one's work, but a changed file to the gate's
    # files-listed check and the schedule's unclaimed-changes check — one would stop a run.
    added = []
    for name in (".DS_Store", "Thumbs.db"):
        if os.path.isfile(".gitignore") and name in file_lines(".gitignore"):
            continue
        append_line(".gitignore", name)
        added.append(name)
    if added:
        say("factory: .gitignore keeps the files a file manager drops out of git: " + " ".join(added))
    # What the pipeline writes itself — the run folder, the evidence beside it, the worktrees — is protocol: nothing
    # reads it from git, and untracked it would leave every commit beside a run. One line per folder, unless the
    # project's .gitignore already names it.
    own_added = []
    for own in (".dca-factory", runs, evidence):
        own = own[:-1] if own.endswith("/") else own
        if own.startswith(".dca-factory/") and len(own) > len(".dca-factory/"):
            continue                                           # inside the folder the first line already ignores
        if os.path.isfile(".gitignore") and any(named(line, own) for line in file_lines(".gitignore")):
            continue
        append_line(".gitignore", f"/{own}")
        own_added.append(f"/{own}")
    if own_added:
        say("factory: .gitignore keeps the pipeline's own protocol out of git: " + " ".join(own_added))


def named(line: str, own: str) -> bool:
    """An ignore line that names <own> or a path below it — read with its `\\r`, a leading `!` and `/` taken off."""
    line = line[:-1] if line.endswith("\r") else line
    line = line[1:] if line.startswith("!") else line
    line = line[1:] if line.startswith("/") else line
    return line == own or line.startswith(own + "/")


AGENTS_START, AGENTS_END = "<!-- dca-factory: start -->", "<!-- dca-factory: end -->"
AGENTS_BLOCK = AGENTS_START + """
## Delivery pipeline

This project delivers stories through the dca-factory pipeline. At the start of a session, unless the
person names a task right away, run `python3 .agents/factory/factory-cli.py --status --brief`, show
its lines, and ask what they want to do: write or release a story (`/factory-backlog`), answer a
waiting question (`/factory-decisions`), work the backlog (`/factory-run`; to keep listening, a tool
that repeats a prompt runs it again — in Claude Code `/loop /factory-run`), look closer (`/factory-status`), or
learn how the factory works (`/factory-help`).

An instruction that changes what an actor can see or do is a user story. Before any code, ask once, in
these words: "As a story through the factory — to an existing epic, a new epic — or directly by hand?"
For the factory, run `/factory-run` with the person's words: it writes the story through
`/factory-backlog` and runs it once it is released. A fix, a refactoring, documentation, tooling or a
question is done directly.

A session never runs `factory.sh run` — it starts a tool process per stage. One worker per checkout: a
managing session writes backlog and decision files only; a stage the runner started is that worker's own
session and writes its stage file. Every change — by a stage or by hand in a
session — passes `bash .agents/factory/factory.sh check` before it is committed; the commit hook runs it
on what is staged.
""" + AGENTS_END


def agents_block() -> None:
    """The instruction every tool reads: a block in AGENTS.md between two markers. Only the block is the pipeline's —
    replaced on every install and update; the rest of the file is the project's."""
    path = "AGENTS.md"
    text = read(path) if os.path.isfile(path) else ""
    if AGENTS_START in text and AGENTS_END in text:
        head, rest = text.split(AGENTS_START, 1)
        text = head + AGENTS_BLOCK + rest.split(AGENTS_END, 1)[1]
    else:
        text = (text.rstrip() + "\n\n" if text.strip() else "") + AGENTS_BLOCK + "\n"
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)
    say("factory: AGENTS.md carries the pipeline's section (between its dca-factory markers)")
    if os.path.isfile("CLAUDE.md") and not re.search("AGENTS.md", read("CLAUDE.md")):
        warn("factory: CLAUDE.md does not import AGENTS.md — a Claude Code before 2.1.277 (it reads AGENTS.md")
        warn("factory:   natively since) gets the section through the SessionStart hook only; add '@AGENTS.md'")
        warn("factory:   to CLAUDE.md if such a version should read the rest too.")


def claude_permissions(python: str, heads: typing.Sequence[str]) -> None:
    """Claude Code asks before running a command. In a non-interactive run there is nobody to ask, so the gate cannot
    run and no stage can be verified. These entries are the smallest allowlist that lets the pipeline verify itself;
    every other command still asks."""
    try:
        write_claude_permissions(python, heads)
    except Exception:                       # noqa: BLE001 — a broken settings file stops this step, not the install
        traceback.print_exc()


def write_claude_permissions(python: str, heads: typing.Sequence[str]) -> None:
    path = ".claude/settings.json"
    os.makedirs(".claude", exist_ok=True)
    settings: typing.Dict[str, typing.Any] = {}
    if os.path.isfile(path):
        with open(path) as handle:
            settings = json.load(handle)
    allow = settings.setdefault("permissions", {}).setdefault("allow", [])
    wanted = [f"Bash({python} .agents/factory/story-gate.py:*)", f"Bash({python} .agents/factory/factory-cli.py:*)"]
    # the commands the profile declares, read through the cli — the runner parses no profile
    for head in heads:
        wanted.append(f"Bash({head}:*)")
    # the reading commands, so a session looks without being asked; `run` is not in it — it starts a tool process per
    # stage, and the runner refuses it inside a session anyway
    for verb in ("status", "decisions", "backlog", "setup --check", "verify"):
        wanted.append(f"Bash(bash .agents/factory/factory.sh {verb}:*)")
    # what an earlier install allowed under verbs that are gone
    retired = {f"Bash(bash .agents/factory/factory.sh {verb}:*)" for verb in ("usage", "schedule")}
    removed = [entry for entry in allow if entry in retired]
    allow[:] = [entry for entry in allow if entry not in retired]
    added = [entry for entry in dict.fromkeys(wanted) if entry not in allow]
    allow.extend(added)
    # The session starts knowing where the pipeline stands: the hook's output lands in its context. It calls the cli,
    # which only reads — `factory.sh` is the person's, and no hook or skill runs it.
    hook_command = f"{python} .agents/factory/factory-cli.py --status --brief --session-start"
    starts = settings.setdefault("hooks", {}).setdefault("SessionStart", [])
    for entry in starts:                         # an earlier install's hook through factory.sh or the gate is replaced
        entry["hooks"] = [h for h in entry.get("hooks", []) if "factory.sh status --brief" not in h.get("command", "")
                          and "story-gate.py --status --brief" not in h.get("command", "")]
    starts[:] = [entry for entry in starts if entry.get("hooks")]
    if not any(h.get("command") == hook_command for entry in starts for h in entry.get("hooks", [])):
        starts.append({"hooks": [{"type": "command", "command": hook_command}]})
        added.append("a SessionStart hook with the pipeline's status")
    with open(path, "w") as handle:
        json.dump(settings, handle, indent=2)
        handle.write("\n")
    say("factory: .claude/settings.json allows " + ", ".join(added) if added else
        "factory: .claude/settings.json already allowed the gate")
    if removed:
        say("factory: .claude/settings.json no longer allows " + ", ".join(removed) + " — verbs the runner does not have")
