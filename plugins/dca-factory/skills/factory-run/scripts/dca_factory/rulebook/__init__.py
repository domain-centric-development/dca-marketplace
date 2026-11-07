"""The bounded context *rulebook*: every rule the factory holds a story to — decided by the gate, decided by the
runner, or told to a stage in its brief —, by one id scheme, placed in the flow of a story. It decides nothing itself:
it reads the rules through delivery's `api`, the skills' text for the ids they cite, and shows them. Its glossary: `docs/glossary/rulebook.md` in the plugin."""

from ..building_blocks import BoundedContext, Consumes, Translation, Upstream

__dca__ = BoundedContext(
    name="rulebook",
    upstreams=(
        Upstream(
            context="delivery",
            translation=Translation.CONFORMIST,
            via=(Consumes.API,),
            rationale="the rules delivery registers and the workflow's stages, taken as delivery says them",
        ),
    ),
)
