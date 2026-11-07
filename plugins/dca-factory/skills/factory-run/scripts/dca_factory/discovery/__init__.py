"""The bounded context *discovery*: which problem is worth solving and how anyone will know it got better — a report
per topic and the epics it proposes, before anything is planned. It never edits the backlog or the description;
a person releases a proposal and delivery takes it from there (`api` is what delivery asks). Its glossary:
`docs/glossary/discovery.md` in the plugin."""

from ..building_blocks import BoundedContext, Consumes, Translation, Upstream

__dca__ = BoundedContext(
    name="discovery",
    upstreams=(
        Upstream(
            context="delivery",
            translation=Translation.ANTI_CORRUPTION_LAYER,
            via=(Consumes.API,),
            rationale="which proposals became epics, discovery asks delivery, not its files",
        ),
    ),
)
