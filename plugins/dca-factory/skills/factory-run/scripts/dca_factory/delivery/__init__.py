"""The bounded context *delivery*: what is built next, who decides, how it is delivered and what it cost — the
features backlog, decisions, delivery, description and cost on one model (story, epic, decision record, journal).
Its glossary: `docs/glossary/delivery.md` in the plugin."""

from ..building_blocks import BoundedContext, Consumes, Translation, Upstream

__dca__ = BoundedContext(
    name="delivery",
    upstreams=(
        Upstream(
            context="discovery",
            translation=Translation.ANTI_CORRUPTION_LAYER,
            via=(Consumes.API,),
            rationale="a released proposal becomes an epic; the gate checks a discovery report",
        ),
        Upstream(
            context="spec",
            translation=Translation.ANTI_CORRUPTION_LAYER,
            via=(Consumes.API,),
            rationale="delivery hands spec a story's criteria and the plan's delta, and asks it in its terms",
        ),
    ),
)
