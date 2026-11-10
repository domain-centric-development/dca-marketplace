"""A tool's skill folder in the project: what the install placed there, linked or copied, beside what is the project's.

The list an install keeps beside the skills it placed (`<folder>/.dca-factory-skills`): two header lines — the mode
(`link` or `copy`) and where the source was (`cache` or `checkout`) — then one skill name per line. Committed with the
project in both modes, so a clone and an update read the mode and the install's own entries from it instead of
guessing from what the folder holds. An entry the list does not name is the project's, whatever its name. A list from
before the header (names only) is read as a copy install.
"""

from __future__ import annotations

import fnmatch
import filecmp
import glob
import os
import re
import shutil
import subprocess
import sys
import tempfile
import typing

from .sources import PIPELINE_SKILLS, RENAMED_SKILLS, home, is_cache, later, method_skill_dirs, slashed

MANIFEST_NAME = ".dca-factory-skills"


class InstallFailed(Exception):
    """An install step that had to work and did not: the project is unchanged from here on, exit 1."""

    def __init__(self, what: str) -> None:
        super().__init__(what)
        self.what = what


def say(text: str) -> None:
    print(text)


def warn(text: str) -> None:
    sys.stdout.flush()
    print(text, file=sys.stderr, flush=True)


def must(what: str, done: bool) -> None:
    if not done:
        raise InstallFailed(what)


def present(path: str) -> bool:
    """`[ -e ] || [ -L ]`: there, a link that points nowhere included."""
    return os.path.lexists(path)


def remove(path: str) -> None:
    """`rm -rf`: a link goes as a link, a folder with what it holds."""
    if os.path.islink(path) or os.path.isfile(path):
        os.unlink(path)
    elif os.path.isdir(path):
        shutil.rmtree(path, ignore_errors=True)


def link(source: str, path: str) -> bool:
    try:
        os.symlink(source, path, target_is_directory=os.path.isdir(source))
        return True
    except OSError:
        return False


def copy_tree(source: str, target: str) -> bool:
    """A skill's folder, without the bytecode a run left in it (`cp -R`, links kept as links)."""
    try:
        # bytecode left out while copying, not only after: a process importing the source beside the copy may write
        # or replace a .pyc under it at that moment, and the copy would fail on a file that changed under it
        shutil.copytree(source, target, symlinks=True, copy_function=shutil.copy,
                        ignore=shutil.ignore_patterns("__pycache__"))
    except (OSError, shutil.Error):
        return False
    for top, dirs, _files in os.walk(target):
        for name in [d for d in dirs if d == "__pycache__"]:
            shutil.rmtree(os.path.join(top, name), ignore_errors=True)
            dirs.remove(name)
    return True


def same_tree(first: str, second: str, left_out: typing.Sequence[str] = ()) -> bool:
    """`diff -rq`: the same names and the same bytes below both, <left_out> names aside."""
    if not (os.path.isdir(first) and os.path.isdir(second)):
        return False
    try:
        names = sorted(n for n in os.listdir(first) if n not in left_out)
        if names != sorted(n for n in os.listdir(second) if n not in left_out):
            return False
    except OSError:
        return False
    for name in names:
        one, other = os.path.join(first, name), os.path.join(second, name)
        if os.path.isdir(one) and os.path.isdir(other):
            if not same_tree(one, other, left_out):
                return False
        elif os.path.isfile(one) and os.path.isfile(other):
            if not filecmp.cmp(one, other, shallow=False):
                return False
        else:
            return False
    return True


def can_symlink() -> bool:
    """Whether a link made here is a link. On Windows it needs developer mode or an administrator; without them the
    install copies openly and says so. Probed, not inferred from the platform."""
    probe = tempfile.mkdtemp()
    try:
        open(os.path.join(probe, "a"), "w").close()
        try:
            os.symlink(os.path.join(probe, "a"), os.path.join(probe, "b"))
        except OSError:
            return False
        return os.path.islink(os.path.join(probe, "b"))
    finally:
        shutil.rmtree(probe, ignore_errors=True)


def entries(folder: str) -> typing.List[str]:
    """`"$folder"/*`: the entries a shell's glob names, hidden ones left out, in its order — joined with `/`, as a shell
    names them."""
    try:
        return sorted(f"{folder}/{n}" for n in os.listdir(folder) if not n.startswith("."))
    except OSError:
        return []


# --- the list beside the skills -------------------------------------------------------------------------------------


def manifest_lines(target: str) -> typing.List[str]:
    try:
        with open(os.path.join(target, MANIFEST_NAME), encoding="utf-8") as handle:
            return handle.read().splitlines()
    except OSError:
        return []


def manifest_field(target: str, field: str) -> str:
    for line in manifest_lines(target):
        found = re.match(rf"^{field}:\s*(.*)$", line)
        if found:
            return found.group(1)
    return ""


def manifest_names(target: str) -> typing.List[str]:
    return [line for line in manifest_lines(target) if ":" not in line and line]


def manifest_has(target: str, name: str) -> bool:
    return name in manifest_names(target)


def write_manifest(target: str, mode: str, kind: str, names: typing.Sequence[str]) -> None:
    """The list written whole: `<list>.new`, then put in place."""
    path = os.path.join(target, MANIFEST_NAME)
    with open(path + ".new", "w", encoding="utf-8", newline="\n") as handle:
        handle.write(f"mode: {mode}\nsource: {kind}\n" + "".join(f"{name}\n" for name in names))
    os.replace(path + ".new", path)


def manifest_add(target: str, name: str) -> None:
    """<name> into the list, once."""
    path = os.path.join(target, MANIFEST_NAME)
    if name in manifest_lines(target):
        return
    exists = os.path.isfile(path)
    with open(path, "a", encoding="utf-8", newline="\n") as handle:
        if not exists:
            handle.write("mode: link\nsource: checkout\n")
        handle.write(f"{name}\n")


def manifest_drop(target: str, name: str) -> None:
    path = os.path.join(target, MANIFEST_NAME)
    if os.path.isfile(path):
        kept = [line for line in manifest_lines(target) if line != name]
        with open(path + ".new", "w", encoding="utf-8", newline="\n") as handle:
            handle.write("".join(f"{line}\n" for line in kept))
        os.replace(path + ".new", path)


def skills_mode(target: str) -> str:
    """How the project holds the skills for one tool: `link` (into a checkout or cache — live), `copy` (its own
    folders — pinned, committed with the project), or "" for a tool it does not use. The list says it; without one
    the pipeline's own names decide by majority — never one entry, which a project may own itself."""
    if os.path.islink(target):
        return "link"
    mode = manifest_field(target, "mode")
    if mode:
        return mode
    if os.path.isfile(os.path.join(target, MANIFEST_NAME)):
        return "copy"                                  # names only: the list before the header
    links = dirs = 0
    for name in PIPELINE_SKILLS:
        # a link whose target is gone is still a link: the update is what repairs it
        if os.path.islink(os.path.join(target, name)):
            links += 1
        elif os.path.isdir(os.path.join(target, name)):
            dirs += 1
    if links == 0 and dirs == 0:
        # Links are machine-local and kept out of git, so a fresh clone has none — the ignore rule is what says the
        # project used them, and `update` is how a clone gets them back.
        ignored = subprocess.run(["git", "check-ignore", "-q", f"{target}/factory-run"], stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL).returncode == 0
        return "link" if ignored else ""
    return "link" if links >= dirs else "copy"


# --- whose an entry is ------------------------------------------------------------------------------------------------


def ours(target: str, sources: typing.Sequence[str]) -> bool:
    """Whether a link's target points into one of the folders the install takes from — the only links it may replace
    or prune. Another version of the same plugin, in a plugin cache or a checkout elsewhere, is the install's too."""
    target = slashed(target)
    for folder in sources:
        if target.startswith(slashed(folder) + "/"):
            return True
        plugin = os.path.basename(os.path.dirname(folder))
        if is_cache(folder):
            plugin = os.path.basename(os.path.dirname(os.path.dirname(folder)))
        if fnmatch.fnmatchcase(target, f"*/plugins/cache/*/{plugin}/*/skills/*"):
            return True
        if fnmatch.fnmatchcase(target, f"*/{plugin}/skills/*"):
            return True
    return False


def ours_entry(target: str, name: str, sources: typing.Sequence[str]) -> bool:
    """Whether an entry of a skill folder is the install's to replace: named in the install's list (a link — or a
    copy, when the list says the project held copies and is switching), or, from before the list, a link into a source
    the install uses."""
    entry = os.path.join(target, name)
    if manifest_has(target, name):
        if os.path.islink(entry):
            return True
        mode = manifest_field(target, "mode")
        return mode in ("copy", "") and os.path.isdir(entry)
    return os.path.islink(entry) and ours(os.readlink(entry), sources)


def only_links_into(folder: str, sources: typing.Sequence[str]) -> bool:
    """Whether a folder holds nothing but links into the given sources — then it is the install's to fill, and no
    project-owned skill is lost."""
    if not os.path.isdir(folder):
        return False
    for name in sorted(os.listdir(folder)):
        if name == MANIFEST_NAME:
            continue
        entry = os.path.join(folder, name)
        if not os.path.islink(entry) or not ours(os.readlink(entry), sources):
            return False
    return True


# --- one tool's folder filled ----------------------------------------------------------------------------------------


class SkillFolder:
    """One tool's skill folder, filled from the pipeline at <source> — the method plugins' skill folders beside it,
    the carriers the profile names (<carriers>, asked each time: the profile can change during the install), the
    skills the person adopts."""

    def __init__(self, target: str, source: str, kind: str, plugins: bool,
                 carriers: typing.Callable[[], typing.List[str]], adopt: typing.Sequence[str]) -> None:
        self.target, self.source, self.kind, self.plugins = target, source, kind, plugins
        self.carriers, self.adopt = carriers, adopt
        self.method_dirs = method_skill_dirs(source)

    def adopts(self, name: str) -> bool:
        """The person named it with --adopt (or all)."""
        return "all" in self.adopt or name in self.adopt

    def copy(self, reason: str) -> None:
        """Copies: a copy looks like a skill of the project's own, so the install keeps a list of what it copied —
        only those are its to replace, and one the pipeline no longer has is removed. A folder of the project's own
        with a pipeline skill's name is left alone and named."""
        target = self.target
        must(f"create {target}", makedirs(target))
        # The same set a link install gives this tool: for a tool without a plugin mechanism the craft of the method
        # plugins beside the pipeline, not only the carriers the profile already names.
        copy_dirs = [self.source] + ([] if self.plugins else self.method_dirs)
        if os.path.isfile(os.path.join(target, MANIFEST_NAME)):
            previous = manifest_names(target)                  # links too, when the project switches to copies
        else:
            # A copy from before the list: a folder is taken as the pipeline's only when it is byte for byte the
            # source's skill — an edited one, or one that merely shares a name, is the project's.
            previous = [os.path.basename(skill) for folder in copy_dirs for skill in entries(folder)
                        if os.path.isdir(skill) and os.path.isdir(os.path.join(target, os.path.basename(skill)))
                        and not os.path.islink(os.path.join(target, os.path.basename(skill)))
                        and same_tree(skill, os.path.join(target, os.path.basename(skill)))]
        names: typing.List[str] = []
        copied = kept = removed = 0
        for skill in [skill for folder in copy_dirs for skill in entries(folder)]:
            if not os.path.isdir(skill):
                continue
            name = os.path.basename(skill)
            if name in names:                                  # the pipeline's own wins a name clash
                continue
            if present(os.path.join(target, name)) and name not in previous and not self.adopts(name):
                warn(f"factory: kept the project's own {target}/{name} — the pipeline's {name} was not copied "
                     f"('factory.sh update --adopt {name}' takes it over)")
                kept += 1
                continue
            remove(os.path.join(target, name))
            must(f"copy {name} into {target}", copy_tree(skill, os.path.join(target, name)))
            names.append(name)
            copied += 1
        # Claude's folder gets the method plugins' skills only as carriers — but a project may hold copies of them
        # made by hand. Not the install's, so never replaced unasked: a copy that is byte for byte the plugin's, or
        # one the person names with --adopt, becomes the install's and follows the plugin from then on; a different
        # one is named. Only what the project already holds — nothing is added.
        if self.plugins:
            for folder in self.method_dirs:
                for skill in entries(folder):
                    if not os.path.isdir(skill):
                        continue
                    name = os.path.basename(skill)
                    if name in names or not present(os.path.join(target, name)):
                        continue
                    if name in previous or self.adopts(name) \
                            or same_tree(skill, os.path.join(target, name), ("__pycache__",)):
                        remove(os.path.join(target, name))
                        must(f"copy {name} into {target}", copy_tree(skill, os.path.join(target, name)))
                        names.append(name)
                        copied += 1
                    else:
                        warn(f"factory: kept the project's own {target}/{name} — the method plugin beside the pipeline "
                             f"has another version; 'factory.sh update --adopt {name}' takes it over and keeps it current")
                        kept += 1
        for name in previous:
            if name in names:                                  # copied again just now
                continue
            # A carrier the profile names is not the pipeline's skill but one it copied beside it: it stays, on the
            # list, for the carriers' refresh — never removed as outdated.
            if name in self.carriers() and os.path.isdir(os.path.join(target, name)):
                names.append(name)
                continue
            remove(os.path.join(target, name))
            removed += 1
            warn(f"factory: removed {target}/{name} — the pipeline no longer has it")
        write_manifest(target, "copy", self.kind, names)
        say(f"factory: skills → {target} ({copied} copied{reason}; {kept} of the project's own kept, {removed} removed)")

    def link(self) -> None:
        """Links, one per skill: an edit at the source is live in the project."""
        target, sources = self.target, [self.source, *self.method_dirs]
        if self.method_dirs and not self.plugins:
            # A tool without a plugin mechanism finds only what is in this folder, so the craft the profile names as
            # a carrier has to be here too. Several sources cannot be one folder link, so these are per skill: an
            # edited skill is still live, but a newly added one needs another install, and that is said out loud.
            makedirs(target)
            names: typing.List[str] = []
            linked = kept = pruned = 0
            # Never wipe the folder: a project may keep skills of its own in it. Only links that point into a source
            # the install takes from are its to replace, and a stale one — its skill gone from the source — is pruned.
            for entry in entries(target):
                if ours_entry(target, os.path.basename(entry), sources):
                    if not os.path.exists(entry):          # its skill is gone
                        remove(entry)
                        pruned += 1
                    continue
                # A link that points nowhere is nobody's skill — typically one into a plugin folder that was renamed.
                if os.path.islink(entry) and not os.path.exists(entry):
                    warn(f"factory: pruned {entry} — it pointed to {os.readlink(entry)}, which no longer exists")
                    remove(entry)
                    pruned += 1
                    continue
                kept += 1
            for folder in sources:
                for skill in entries(folder):
                    if not os.path.isdir(skill):
                        continue
                    name = os.path.basename(skill)
                    # Ours to replace only if it is a link into a source the install takes from. A folder the project
                    # keeps here is obvious; a link the project made is just as much its own.
                    if present(os.path.join(target, name)):
                        if not ours_entry(target, name, sources):
                            warn(f"factory: kept the project's own {target}/{name} — the pipeline's {name} was not "
                                 "installed")
                            kept += 1
                            continue
                        remove(os.path.join(target, name))   # a copy of ours, when the project switches to links
                    link(skill, os.path.join(target, name))
                    names.append(name)
                    linked += 1
            write_manifest(target, "link", self.kind, names)
            if kept > 0:
                warn(f"factory: left {kept} entry/entries in {target} that are the project's own")
            if pruned > 0:
                warn(f"factory: pruned {pruned} link(s) whose skill is gone from the source")
            say(f"factory: skills → {target} ({linked} linked: the pipeline plus the craft it names as carriers)")
            warn("factory:   per skill, because they come from several sources — 'factory.sh update' after a skill is "
                 "added")
        elif not present(target) or only_links_into(target, sources):
            # One link per skill, never the whole folder: through a folder link every skill a tool writes into the
            # project's folder would land in the plugin's own, and a carrier the profile names could not sit beside
            # the pipeline's skills. Per skill freezes the set: a skill added to the pipeline later needs another
            # install (or update), and the report says so.
            must(f"create {target}", makedirs(target))
            names = []
            for skill in entries(self.source):
                if not os.path.isdir(skill):
                    continue
                entry = os.path.join(target, os.path.basename(skill))
                if os.path.islink(entry) or os.path.isfile(entry):
                    os.unlink(entry)
                link(skill, entry)
                names.append(os.path.basename(skill))
            write_manifest(target, "link", self.kind, names)
            say(f"factory: skills → {target} ({len(names)} linked one by one, beside the carriers the profile names)")
            warn("factory:   'factory.sh update' after a skill is added to the pipeline")
        else:
            makedirs(target)
            names = []
            own_kept = 0
            for skill in entries(self.source):
                if not os.path.isdir(skill):
                    continue
                name = os.path.basename(skill)
                # a link of ours is replaced; a folder or a link of the project's own with that name is its skill
                if present(os.path.join(target, name)) and not ours_entry(target, name, sources):
                    warn(f"factory: kept the project's own {target}/{name} — the pipeline's {name} was not linked")
                    own_kept += 1
                    continue
                remove(os.path.join(target, name))
                link(skill, os.path.join(target, name))
                names.append(name)
            write_manifest(target, "link", self.kind, names)
            warn(f"factory: skills → {target} (per skill: the directory holds skills of its own"
                 f"{f'; {own_kept} kept' if own_kept > 0 else ''})")
            warn("factory:   'factory.sh update' after a skill is added to the source")

    def refresh_carriers(self, copies: bool) -> None:
        """The carriers the profile names, into a skill folder that does not already get every craft skill: Claude
        Code's (whose stage processes see only the project) and any folder a copy install wrote. Only what the profile
        names, so an isolated stage's prefix does not grow by skills it never uses; linked where the install links,
        copied where it copies (and then listed as the pipeline's)."""
        target, sources = self.target, [self.source, *self.method_dirs]
        for name in self.carriers():
            # A copy this install made (in its list) is refreshed; any other skill of that name is the project's.
            ours_copy = copies and manifest_has(target, name)
            entry = os.path.join(target, name)
            dangling = os.path.islink(entry) and not os.path.exists(entry)
            if os.path.isfile(os.path.join(entry, "SKILL.md")) and not dangling and not ours_copy \
                    and not ours_entry(target, name, sources):
                continue
            found = next((os.path.join(folder, name) for folder in self.method_dirs
                          if os.path.isdir(os.path.join(folder, name))), "")
            if not found:
                if ours_copy and os.path.isfile(os.path.join(entry, "SKILL.md")):
                    warn(f"factory: kept the copied carrier {target}/{name} — no plugin beside the pipeline has a newer "
                         "one")
                else:
                    warn(f"factory: the profile names carrier '{name}', which no plugin beside the pipeline provides — "
                         f"add it to {target}")
                continue
            remove(entry)
            if copies:
                copy_tree(found, entry)
            else:
                link(found, entry)
            manifest_add(target, name)
            say(f"factory: carrier {name} → {target}")


def makedirs(path: str) -> bool:
    try:
        os.makedirs(path, exist_ok=True)
        return True
    except OSError:
        return False


# --- the ignore lines -------------------------------------------------------------------------------------------------


def write_skill_ignores(target: str, mode: str) -> None:
    """The links are machine-local and stay out of git — one line per link, never the folder, so the list beside them
    and the tool's settings are committed. Copies are the project's: the lines go."""
    names = manifest_names(target)
    want: typing.List[str] = []
    if mode == "link":
        if os.path.islink(target):
            want = [target]
        else:
            want = [f"{target}/{name}" for name in names] or [f"{target}/"]
    out: typing.List[str] = []
    folder_line = changed = False
    if os.path.isfile(".gitignore"):
        with open(".gitignore", encoding="utf-8", errors="surrogateescape", newline="") as handle:
            lines = handle.read().split("\n")
        if lines and lines[-1] == "":
            lines.pop()
        for line in lines:
            if line in (target, target + "/"):
                # a folder-wide line hides the list too; it is replaced by one line per link, and named
                if not (os.path.islink(target) and mode == "link"):
                    folder_line = changed = True
                    continue
            elif line.startswith(target + "/"):
                # a line still wanted stays where it stands — rewritten at the end, it would move the lines around it
                # and leave a diff on every update
                if line in want and line in out:
                    changed = True
                    continue
                if line not in want and (os.path.islink(target) or line[len(target) + 1:] in names):
                    changed = True
                    continue
            out.append(line)
    for line in want:
        if line not in out:
            out.append(line)
            changed = True
    if not changed:
        return
    with open(".gitignore.new", "w", encoding="utf-8", errors="surrogateescape", newline="") as handle:
        handle.write("".join(f"{line}\n" for line in out))
    os.replace(".gitignore.new", ".gitignore")
    if mode == "link":
        say("factory: .gitignore keeps the skill links out of git, one line per link"
            + (" (the folder-wide line is replaced, so the list beside the links is committed)" if folder_line else ""))
    else:
        say(f"factory: .gitignore no longer ignores the skills under {target} — they are copies, committed with the "
            "project")


# --- renamed skills ----------------------------------------------------------------------------------------------------


def prune_renamed_copies(source: str, tool_dirs: typing.Sequence[str]) -> None:
    """A copied skill under a name the method plugins renamed: removed when it is byte for byte the newest version of
    its old plugin still on this machine (the plugin cache, or a checkout beside the pipeline) — nobody edited it —
    and kept and named otherwise, because then the project made it its own."""
    for target in tool_dirs:
        if not os.path.isdir(target) or os.path.islink(target):
            continue
        for old, new, plugin in RENAMED_SKILLS:
            copy = f"{target}/{old}"      # joined with `/`, as every other line of the install names a path
            # A link under the old name whose folder is gone points at nothing: the rename moved the folder, and the
            # new name is linked by the install. A link that still resolves is the project's own choice.
            if os.path.islink(copy) and not os.path.exists(copy):
                os.unlink(copy)
                manifest_drop(target, old)
                say(f"factory: removed the link {copy} — renamed to {new}, and its folder is gone")
                continue
            if not os.path.isdir(copy) or os.path.islink(copy):
                continue
            reference, best = "", ""
            candidates = sorted(glob.glob(os.path.join(home(), ".claude", "plugins", "cache", "*", plugin, "*",
                                                       "skills", old)))
            candidates.append(os.path.join(source, "..", "..", plugin, "skills", old))
            for candidate in candidates:
                if not os.path.isdir(candidate):
                    continue
                version = os.path.basename(os.path.dirname(os.path.dirname(candidate)))
                if not reference or later(best, version) == version:
                    reference, best = candidate, version
            if not reference:
                warn(f"factory: kept {copy} — renamed to {new}, and no {plugin} copy of it is left to compare with")
            elif same_tree(copy, reference, (MANIFEST_NAME,)):
                remove(copy)
                manifest_drop(target, old)
                say(f"factory: removed {copy} — renamed to {new}, and the copy was {plugin}'s own, unedited")
            else:
                warn(f"factory: kept {copy} — renamed to {new}, but the copy differs from {plugin}'s: the project "
                     "edited it")
