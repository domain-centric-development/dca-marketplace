"""Where a pipeline is found on this machine, which release a folder holds, and the method plugins beside it.

A release states two things about itself, read out of its files by name — `VERSION` (where a copy came from) and
`CONTRACT` (the version of the files it reads and writes) —, because the copy in a project is the only thing that
knows which release governs that project (`gate_field`). Versions are ordered as `sort -V` orders them.
"""

from __future__ import annotations

import fnmatch
import glob
import os
import re
import typing

#: The skills the method plugins renamed: <old> <new> <the plugin that shipped the old one>. A profile that still
#: names an old one would run yesterday's copy without a word, so a run stops on it, and `update` removes a copy
#: under the old name that nobody edited.
RENAMED_SKILLS = (
    ("dca-review", "dca-audit", "dca-core"),
    ("review-domain", "review-ddd", "dca-core"),
    ("review-boundaries", "review-hexagonal", "dca-core"),
    ("review-craft", "review-clean-code", "software-craftsmanship"),
    ("ddd-modelling", "dca-modelling", "dca-core"),
    ("dca-bootstrap", "dca-init", "dca-core"),
    ("dca-scaffold", "dca-new", "dca-core"),
)
RENAMED_KEYS = (("review.domain", "review.ddd"), ("review.boundaries", "review.hexagonal"),
                ("review.craft", "review.clean-code"))
#: Left in a plugin cache after a rename; never a source.
RETIRED_PLUGINS = ("software-craftsmanship",)
#: The pipeline's own skill names, for the one guess that remains: an install from before the list.
PIPELINE_SKILLS = ("factory-backlog", "factory-decisions", "factory-help", "factory-run", "factory-setup",
                   "factory-status", "factory-update", "factory-verify")
GATE_IN_SKILLS = os.path.join("factory-run", "scripts", "story-gate.py")


def gate_field(path: str, field: str) -> typing.Optional[str]:
    """<field> (VERSION, CONTRACT) of the release whose gate is <path>: from the gate where it names it, else from the
    version stamp beside it; None without the file, "" without the line."""
    if not os.path.isfile(path):
        return None
    source = path
    if not re.search(rf"^{field} = ", read(path), re.M):
        source = os.path.join(os.path.dirname(path), "dca_factory", "contract.py")
    if not os.path.isfile(source):
        return None
    found = re.search(rf"^{field} = *(.*)$", read(source), re.M)
    return found.group(1).replace('"', "").replace("'", "") if found else ""


def read(path: str) -> str:
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            return handle.read()
    except OSError:
        return ""


def version_key(version: str) -> typing.Tuple[typing.Tuple[int, int, str], ...]:
    """A version as `sort -V` compares it: digit runs by their number, everything else by its characters."""
    return tuple((0, int(part), "") if part.isdigit() else (1, 0, part) for part in re.findall(r"\d+|\D+", version))


def later(first: str, second: str) -> str:
    """The later of two versions (`sort -V | tail -1`); the second on a tie."""
    return max((first, second), key=lambda v: (version_key(v), v)) if first != second else second


def newer(candidate: str, than: str) -> bool:
    """<candidate> sorts after <than> — a tie is no newer."""
    return candidate != than and later(than, candidate) == candidate


def slashed(path: str) -> str:
    return path.replace(os.sep, "/")


def is_cache(path: str) -> bool:
    """A plugin cache's skill folder: `<cache>/<marketplace>/<plugin>/<version>/skills`."""
    return fnmatch.fnmatchcase(slashed(path), "*/plugins/cache/*/*/*/skills")


def home() -> str:
    return os.environ.get("HOME") or os.path.expanduser("~")


def plugin_skills(own: str, tool_dirs: typing.Sequence[str]) -> typing.Optional[str]:
    """The pipeline's skill folder this project can update from, the newest one found: an explicit
    FACTORY_PLUGIN_DIR, the folder this runner belongs to (<own>), the pipeline the skill folders the install linked
    lead to, and Claude Code's plugin cache. "Newest" decides, not the order. The project's own copies are never a
    candidate: an update replaces them, so they are no source."""
    root = os.path.realpath(os.getcwd())
    best: typing.Optional[str] = None
    best_version = ""
    candidates = [os.environ.get("FACTORY_PLUGIN_DIR", ""), own, *tool_dirs,
                  *sorted(glob.glob(os.path.join(home(), ".claude", "plugins", "cache", "*", "dca-factory", "*",
                                                 "skills")))]
    for candidate in candidates:
        if not candidate or not os.path.isfile(os.path.join(candidate, GATE_IN_SKILLS)):
            continue
        # through the skill, not the folder: a project's skill folder holds one link per skill, so the folder resolves
        # to the project itself while its `factory-run` resolves to where the pipeline is
        found = os.path.dirname(os.path.realpath(os.path.join(candidate, "factory-run")))
        if fnmatch.fnmatchcase(slashed(candidate), ".*/skills") and inside(found, root):
            continue
        version = gate_field(os.path.join(found, GATE_IN_SKILLS), "VERSION") or ""
        if best is None or later(best_version, version) != best_version:
            best, best_version = found, version
    return best


def inside(path: str, root: str) -> bool:
    """<path> lies in <root> (`case "$path/" in "$root"/*`)."""
    return slashed(path + "/").startswith(slashed(root) + "/")


def source_kind(source: str) -> str:
    """Where a source lies: `cache` (versioned, and a version is removed some time after an update, so a link into it
    goes stale) or `checkout` (a clone of the marketplace, or FACTORY_PLUGIN_DIR — live, a developer's)."""
    named = os.environ.get("FACTORY_PLUGIN_DIR", "")
    if named and os.path.isdir(named) and os.path.realpath(named) == source:
        return "checkout"
    return "cache" if is_cache(source) else "checkout"


def subfolders(pattern: str) -> typing.List[str]:
    return sorted(p for p in glob.glob(pattern) if os.path.isdir(p))


def method_skill_dirs(source: str) -> typing.List[str]:
    """The skill folders of the plugins beside the pipeline at <source>. In a checkout they are
    `plugins/<plugin>/skills`; in a plugin cache every plugin has a folder per version — `<plugin>/<version>/skills` —
    and there `../../*/skills` would be the other versions of this pipeline, so each neighbour's newest is taken."""
    plugin = os.path.abspath(os.path.join(source, ".."))
    if not os.path.isdir(plugin):
        return []
    if os.path.isfile(os.path.join(plugin, ".claude-plugin", "plugin.json")) \
            and os.path.basename(plugin) != "dca-factory" and os.path.basename(os.path.dirname(plugin)) == "dca-factory":
        plugins = os.path.abspath(os.path.join(plugin, "..", ".."))       # the cache: <plugin>/<version>/
        found = []
        for folder in subfolders(os.path.join(plugins, "*")):
            name = os.path.basename(folder)
            if name == "dca-factory" or name in RETIRED_PLUGINS:
                continue
            versions = [os.path.basename(os.path.dirname(v)) for v in subfolders(os.path.join(folder, "*", "skills"))]
            if versions:
                newest = ""
                for version in versions:
                    newest = later(newest, version)
                found.append(os.path.abspath(os.path.join(folder, newest, "skills")))
        return found
    plugins = os.path.abspath(os.path.join(source, "..", ".."))
    found = []
    for folder in subfolders(os.path.join(plugins, "*", "skills")):
        folder = os.path.abspath(folder)
        if folder == source or os.path.basename(os.path.dirname(folder)) in RETIRED_PLUGINS:
            continue
        found.append(folder)
    return found


def presets_dir(skills: typing.Optional[str], own: str, tool_dirs: typing.Sequence[str]) -> typing.Optional[str]:
    """Where the presets are: FACTORY_STACKS_DIR; the pipeline at <skills>; the one this runner belongs to (<own>)
    when it runs from the plugin; the newest one found otherwise."""
    named = os.environ.get("FACTORY_STACKS_DIR")
    if named:
        return named
    if not skills and os.path.isdir(os.path.join(own, "factory-run", "templates", "presets")):
        skills = own
    if not skills:
        skills = plugin_skills(own, tool_dirs)
        if not skills:
            return None
    folder = os.path.join(skills, "factory-run", "templates", "presets")
    return folder if os.path.isdir(folder) else None


def method_skill_names(presets: str, own: str, tool_dirs: typing.Sequence[str]) -> typing.List[str]:
    """The skill names of the method plugins beside the pipeline whose presets are in <presets>."""
    if presets and os.path.isfile(os.path.join(presets, "..", "..", "scripts", "story-gate.py")):
        skills = os.path.abspath(os.path.join(presets, "..", "..", ".."))
    elif os.path.isfile(os.path.join(own, GATE_IN_SKILLS)):
        skills = own
    else:
        skills = plugin_skills(own, tool_dirs) or ""
        if not skills:
            return []
    names = {os.path.basename(os.path.dirname(entry)) for folder in method_skill_dirs(skills)
             for entry in glob.glob(os.path.join(folder, "*", "SKILL.md")) if os.path.isfile(entry)}
    return sorted(names)
