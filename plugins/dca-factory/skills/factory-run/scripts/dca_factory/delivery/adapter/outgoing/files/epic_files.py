"""The epics as folders: `<epics>/<epic>/epic.md` beside its story folders."""

from __future__ import annotations

import contextlib
import os
import typing

from .....sharedkernel.adapter.outgoing.profile.profile_files import place, shown
from .....sharedkernel.adapter.outgoing.markdown.front_matter import MarkdownError, read_front_matter
from ....application.shared.front import created_of, front_text
from .story_layout import depends_on, EPIC_FILE
from ....domain.model.epic import EpicId

Facts = typing.Dict[str, typing.Any]
GateError = MarkdownError


def epic_dir(epics: str, epic_id: str) -> typing.Optional[str]:
    """The folder of the epic with this id — its folder's name or its `id:` — or None."""
    if not os.path.isdir(epics):
        return None
    for name in sorted(os.listdir(epics)):
        path = os.path.join(epics, name, "epic.md")
        if not os.path.isfile(path):
            continue
        if name.lower() == epic_id.lower():
            return os.path.dirname(path)
        with contextlib.suppress(MarkdownError):
            if str(read_front_matter(path)[0].get("id", "")).strip().lower() == epic_id.lower():
                return os.path.dirname(path)
    return None



def epic_files(epics: str) -> typing.List[Facts]:
    """Every epic folder with an epic.md, the one with no story yet included — the status lists the epics
    from their own files, not from the stories that name them."""
    found: typing.List[Facts] = []
    if not os.path.isdir(epics):
        return found
    for name in sorted(os.listdir(epics)):
        path = os.path.join(epics, name, "epic.md")
        if not os.path.isfile(path):
            continue
        try:
            front = read_front_matter(path)[0]
        except GateError:
            front = {}
        found.append(dict(epic=str(front.get("id") or name), folder=name, created=created_of(front), path=shown(path),
                          **{k: front_text(front.get(k))
                             for k in ("title", "goal", "metric", "discovery", "intent", "domain_contact")}))
    return found


def epic_holding(epics: str, proposal: str) -> str:
    """The epic that holds a proposal of discovery — its id or its folder is the proposal's — '' where none does."""
    return next((e["epic"] for e in epic_files(epics) if proposal in (e["epic"], e["folder"])), "")


def epic_graph(epics: str) -> typing.Dict[str, typing.List[str]]:
    """{epic id: [epic ids it depends on]} for every epic under the epics — `depends_on:` in its `epic.md`, the
    same two shapes a story's takes. An epic's id is its `id:`, else its folder's name."""
    graph: typing.Dict[str, typing.List[str]] = {}
    if not os.path.isdir(epics):
        return graph
    for name in sorted(os.listdir(epics)):
        path = os.path.join(epics, name, EPIC_FILE)
        if not os.path.isfile(path):
            continue
        try:
            front, _body = read_front_matter(path)
        except GateError:
            front = {}
        graph[str(front.get("id") or name).strip()] = depends_on(front)
    return graph


def epic_order(graph: typing.Mapping[str, typing.List[str]]) -> typing.Tuple[typing.List[str], typing.Set[str]]:
    """The epics in dependency order, ties by id; the ones on a cycle last, in id order. An epic named as a
    dependency that does not exist is no node and does not hold anything up here — the check names it."""
    order, placed, remaining = [], set(), sorted(graph)
    while remaining:
        free = [e for e in remaining if all(d in placed or d not in graph for d in graph[e])]
        if not free:
            break
        order.append(free[0])
        placed.add(free[0])
        remaining.remove(free[0])
    return order + remaining, set(remaining)


def epic_dependency_problem(epics: str, epic: str) -> typing.Optional[str]:
    """Why an epic's `depends_on:` cannot hold — an unknown epic, itself, a cycle — or None."""
    graph = epic_graph(epics)
    deps = graph.get(epic, [])
    unknown = [d for d in deps if d not in graph]
    if unknown:
        return f"epic {epic!r} depends on {', '.join(repr(d) for d in unknown)}, which is no epic under {epics}/"
    if epic in deps:
        return f"epic {epic!r} depends on itself"
    _order, cycle = epic_order(graph)
    if epic in cycle:
        return f"epic {epic!r} is on a dependency cycle between epics: {', '.join(sorted(cycle))}"
    return None


class EpicFiles:
    """The epic catalog as folders, under the project the process works in."""

    def __init__(self, cwd: str) -> None:
        self._epics = os.path.join(cwd, place("epics"))

    def exists(self, epic: EpicId) -> bool:
        return epic_dir(self._epics, epic.value) is not None

    def where(self) -> str:
        return str(place("epics"))
