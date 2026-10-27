"""A change outside a story, as git holds it: the places a person writes (the backlog, the description) and the
pipeline's own, the staged paths, the index against the working tree — and the reports a parity config names."""

from __future__ import annotations

import glob
import hashlib
import os
import time
import typing

from .....sharedkernel.adapter.outgoing.markdown.front_matter import GateError
from .....sharedkernel.adapter.outgoing.profile.profile_files import (
    DEFAULTS, evidence_rel, findings_rel, PLACES_REL, read_profile)
from ....domain.model.stage_story import (
    Count, ImplementationReports, ParityFacts, ParityScenario, Place, Presence, Snapshot)
from ....domain.model.story_state import Detail
from ..stack.commands import tail, TOOL_FOLDERS
from ..stack.test_reports import read_scenarios, reported_names
from ..files.decision_record_files import project_decisions_rel
from .repository import git

#: (folders, files) — or (folders, files, never)
Places = typing.Tuple[typing.Any, ...]


def pipeline_owned() -> typing.Callable[[str], bool]:
    """Whether a path is one the pipeline writes itself, outside any story's commit: under `.dca-factory/`, the
    run folder or the evidence beside it, as the profile places them."""
    runs = (PLACES_REL.get("runs") or DEFAULTS["runs"]).strip("/")
    prefixes = tuple(dict.fromkeys(folder + "/" for folder in (".dca-factory", runs, evidence_rel()) if folder))
    return lambda path: path.replace("\\", "/").startswith(prefixes)


def rel(key: str) -> str:
    return (PLACES_REL.get(key) or DEFAULTS[key]).strip("/")


def backlog_places() -> typing.Tuple[typing.Tuple[str, ...], typing.Set[str]]:
    """The backlog and the description — what a person writes and nothing the project's checks read: the epics with
    their stories, decisions and findings, the project's findings and decision records, the discovery and the
    description's files. Never the spec, never `docs/` (a project's tests may read what it holds). (folders, files)"""
    folders = {rel("epics"), findings_rel(), project_decisions_rel(), rel("discovery")}
    return (tuple(sorted(f.strip("/") + "/" for f in folders if f and f.strip("/") not in ("", "."))),
            {rel("product"), rel("tech"), rel("domain")})


def people_places() -> typing.Tuple[typing.Tuple[str, ...], typing.Set[str], typing.Tuple[str, ...]]:
    """What a request may write and the factory commits: the backlog and the description (`backlog_places`), and
    beside them the folder the epics lie in with everything in it, `docs/` and the agents' instructions a
    description writes a line into. Never the spec: what holds is merged by the gate that delivers.
    (folders, files, never)"""
    folders, files = backlog_places()
    more = {os.path.dirname(rel("epics")) or rel("epics"), "docs"}
    return (tuple(sorted(set(folders) | {f.strip("/") + "/" for f in more if f.strip("/") not in ("", ".")})),
            files | {"AGENTS.md", "CLAUDE.md"}, (rel("spec") + "/",))


def in_places(path: str, places: Places) -> bool:
    """Whether a path lies in (folders, files[, never])."""
    path = path.replace("\\", "/")
    folders, files, never = (tuple(places) + ((),))[:3]
    return bool((path in files or path.startswith(folders)) and not (never and path.startswith(never)))


def backlog_paths(cwd: str, env: typing.Mapping[str, str]) -> typing.Optional[typing.List[str]]:
    """The staged paths when every one of them is the backlog or the description (`backlog_places`) or the pipeline's
    own protocol, else None. A commit that stages nothing is None: it is checked as any other."""
    code, names = git(cwd, "diff", "--cached", "--name-only", "--no-renames", env=env)
    paths = [p for p in names.splitlines() if p] if code == 0 else []
    if not paths:
        return None
    owned, places = pipeline_owned(), backlog_places()
    return paths if all(in_places(p, places) or owned(p) for p in paths) else None


def snapshot(cwd: str, env: typing.Mapping[str, str]) -> Snapshot:
    """The index tree against the working tree. The agent tools' own folders — skill links, a settings file the
    install wrote — are no input to any check, and refusing every commit over them would stop the first commit after
    an install. Nor is what the pipeline writes itself while a runner works: a person's commit is not refused by a
    running factory's protocol."""
    code, _top = git(cwd, "rev-parse", "--show-toplevel", env=env)
    if code:
        return Snapshot(Detail("--staged needs a git repository"), Detail(""), (), Count(0))
    code, tree = git(cwd, "write-tree", env=env)
    if code:
        return Snapshot(Detail(f"the index cannot be written as a tree: {tail(tree, 300)}"), Detail(""), (), Count(0))
    _, unstaged = git(cwd, "diff", "--name-only", env=env)
    _, untracked = git(cwd, "ls-files", "--others", "--exclude-standard", env=env)

    def tooling(path: str) -> bool:
        return any(folder in "/" + path for folder in TOOL_FOLDERS)
    owned = pipeline_owned()
    left = [p for p in unstaged.splitlines() + untracked.splitlines() if p and owned(p)]
    drift = [f"modified, not staged: {p}" for p in unstaged.splitlines() if p and not tooling(p) and not owned(p)] \
        + [f"untracked: {p}" for p in untracked.splitlines() if p and not tooling(p) and not owned(p)]
    return Snapshot(None, Detail(tree), tuple(Detail(d) for d in drift), Count(len(left)))


def parity_facts(config_path: str) -> ParityFacts:
    """A parity config read: its scenario contract and each implementation's reports. The gate's error where the
    config or its contract cannot be read."""
    config = read_profile(config_path)
    if not config:
        raise GateError(f"{config_path}: no parity config (`scenarios:` and `implementation.<name>:` lines)")
    base = os.path.dirname(os.path.abspath(config_path))
    contract = os.path.join(base, config.get("scenarios", ""))
    if not config.get("scenarios") or not os.path.isfile(contract):
        raise GateError(f"{config_path}: `scenarios:` names no readable contract ({contract})")
    with open(contract, "rb") as handle:
        digest = hashlib.sha256(handle.read()).hexdigest()[:12]
    scenarios = tuple(ParityScenario(Detail(s["id"]), Detail(s["title"]),
                                     Presence.PRESENT if s["runs"].strip().lower() == "always" else Presence.ABSENT)
                      for s in read_scenarios(contract))
    implementations = []
    for key in sorted(k for k in config if k.startswith("implementation.")):
        paths = sorted(p for p in glob.glob(os.path.join(base, config[key]), recursive=True) if os.path.isfile(p))
        names = reported_names(paths) if paths else {}
        newest = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(max(os.path.getmtime(p) for p in paths))) \
            if paths else ""
        implementations.append(ImplementationReports(
            Detail(key.split(".", 1)[1]), Detail(config[key]), Count(len(paths)), Detail(newest),
            tuple((Detail(title), Detail(outcome)) for title, outcome in names.items())))
    return ParityFacts(Place(config_path), Detail(config["scenarios"]), Detail(digest), scenarios,
                       tuple(implementations))


class ChangeIndexFiles:
    """The index and the working tree of the project <cwd>, as git holds them."""

    def __init__(self, cwd: str) -> None:
        self._cwd = cwd
        self._env = dict(os.environ)

    def backlog_paths(self) -> typing.Optional[typing.List[str]]:
        return backlog_paths(self._cwd, self._env)

    def snapshot(self) -> Snapshot:
        return snapshot(self._cwd, self._env)

    def head(self) -> typing.Optional[str]:
        code, head = git(self._cwd, "rev-parse", "--short", "HEAD", env=self._env)
        return head if code == 0 else None

    def tree(self) -> str:
        return git(self._cwd, "write-tree", env=self._env)[1]

    def detach(self) -> None:
        os.environ.pop("GIT_INDEX_FILE", None)


class ParityReportFiles:
    """The parity configs, each read with the reports it names."""

    def facts(self, config: str) -> ParityFacts:
        return parity_facts(config)
