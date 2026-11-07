"""The bounded context *spec*: what holds — per context and feature, each criterion proven by one test — changed only
by a delivery. It knows no story, no epic and no way of delivery: two implementations of the same backlog end in the
same spec. Delivery hands it a story's criteria and the plan's delta through `api`; spec merges them. Its glossary:
`docs/glossary/spec.md` in the plugin."""

from ..building_blocks import BoundedContext, Consumes, Translation, Upstream

__dca__ = BoundedContext(
    name="spec",
    upstreams=(
        Upstream(
            context="delivery",
            translation=Translation.ANTI_CORRUPTION_LAYER,
            via=(Consumes.API,),
            rationale="the open stories and their proofs, asked through delivery's open host service",
        ),
    ),
)
