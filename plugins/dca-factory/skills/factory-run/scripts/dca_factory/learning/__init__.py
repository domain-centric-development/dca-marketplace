"""The bounded context *learning*: what repeats across the stories, counted and never guessed, and what a person
decided about it, so nothing decided is asked again — unless the place did not hold it. It reads delivery's facts
through delivery's `api` and files a lesson in delivery's decision inbox through the same api. Its glossary:
`docs/glossary/learning.md` in the plugin."""

from ..building_blocks import BoundedContext, Consumes, Translation, Upstream

__dca__ = BoundedContext(
    name="learning",
    upstreams=(
        Upstream(
            context="delivery",
            translation=Translation.CONFORMIST,
            via=(Consumes.API,),
            rationale="the findings with their class, the decision records, the journals' refusals and the answered "
                      "assumptions, taken as delivery says them; a lesson filed in delivery's inbox",
        ),
    ),
)
