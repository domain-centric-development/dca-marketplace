"""The workflow this process runs stories through, loaded once from the workflow's repository (`WorkflowRepository`,
Markdown files beside the pipeline today) by its composition root (`load`). Everything that asks about a stage asks
`workflow()` when it runs — never at import, so what a module registers against the stages is placed once the workflow
is loaded (`on_load`)."""

from __future__ import annotations

import typing

from ...domain.model.stage import Role, StageName
from ...domain.model.workflow import DELIVERY, Workflow
from ..shared.workflow_repository import WorkflowRepository

#: The loaded workflow — filled by `load`.
LOADED: typing.List[Workflow] = []
#: What places itself against the stages once the workflow is loaded — the gate's checks, its pass actions.
PLACING: typing.List[typing.Callable[[Workflow], None]] = []


def load(repository: WorkflowRepository) -> Workflow:
    """The delivery workflow from <repository> — once per process, by its composition root."""
    found = repository.find_by_id(DELIVERY)
    if found is None:
        raise ValueError(f"the workflow's repository holds no workflow {DELIVERY.value} — its stages are missing "
                         "(workflow/stages/)")
    LOADED[:] = [found]
    for place in PLACING:
        place(found)
    return found


def loaded() -> bool:
    return bool(LOADED)


def role_of(role: Role) -> StageName:
    """The stage that plays <role> in the loaded workflow."""
    return workflow().role(role)


def workflow() -> Workflow:
    """The loaded workflow."""
    if not LOADED:
        raise RuntimeError("the workflow is not loaded — the composition root loads it (`load(StageFiles())`)")
    return LOADED[0]


def on_load(place: typing.Callable[[Workflow], None]) -> None:
    """Call <place> with the workflow once it is loaded — at once where it already is."""
    PLACING.append(place)
    if LOADED:
        place(LOADED[0])
