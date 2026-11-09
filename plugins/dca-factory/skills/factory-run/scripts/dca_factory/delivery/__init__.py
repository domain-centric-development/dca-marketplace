"""The bounded context *delivery*: what is built next, who decides, how it is delivered and what it cost — the
features backlog, decisions, delivery, description and cost on one model (story, epic, decision record, journal).
Its glossary: `docs/glossary/delivery.md` in the plugin."""

from ..building_blocks import BoundedContext, Consumes, ExternalUpstream, Interaction, Translation, Upstream

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
    external_upstreams=(
        ExternalUpstream(
            name="git",
            translation=Translation.ANTI_CORRUPTION_LAYER,
            interaction=Interaction.OUTBOUND,
            protocol="the git command line",
            exchanges="commits, branches, worktrees, diffs and the checkout's state",
            rationale="the stories, their runs and their deliveries live in the project's repository",
        ),
        ExternalUpstream(
            name="git remote",
            translation=Translation.ANTI_CORRUPTION_LAYER,
            interaction=Interaction.OUTBOUND,
            protocol="git over the remote's transport",
            exchanges="a story's claim as a branch, the published branches",
            rationale="a claim holds across factories where the profile asks for it",
        ),
        ExternalUpstream(
            name="claude",
            translation=Translation.ANTI_CORRUPTION_LAYER,
            interaction=Interaction.OUTBOUND,
            protocol="the agent tool's command line and its event stream",
            exchanges="a stage's brief in, the stage's work and its usage out",
            rationale="a stage runs in an agent tool",
        ),
        ExternalUpstream(
            name="codex",
            translation=Translation.ANTI_CORRUPTION_LAYER,
            interaction=Interaction.OUTBOUND,
            protocol="the agent tool's command line and its event stream",
            exchanges="a stage's brief in, the stage's work and its usage out",
            rationale="a stage runs in an agent tool",
        ),
        ExternalUpstream(
            name="opencode",
            translation=Translation.ANTI_CORRUPTION_LAYER,
            interaction=Interaction.OUTBOUND,
            protocol="the agent tool's command line and its event stream",
            exchanges="a stage's brief in, the stage's work and its usage out",
            rationale="a stage runs in an agent tool",
        ),
    ),
)
