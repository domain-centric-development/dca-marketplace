"""What the stack profile must hold for a gate to trust a run: a contract this gate knows, model keys bound to a tool,
instructions a tool loads whole."""

from __future__ import annotations


from ....building_blocks import DomainService
from ..gateway.stage_evidence import StageEvidence
from ..model.stage import StoryKind
from ..model.workflow import Workflow
from ..model.verdict import CheckName, Findings, Said

MODELS = CheckName("models")

#: The tools a `model.<tool>` key may name: model names are the tool's.
MODEL_TOOLS = ("claude", "codex", "opencode")
#: The processes a `model.<tool>.<process>` key may name beside the stages: the shared builder and verifier, the
#: reviewers, and a person's request worked headless.
MODEL_PROCESSES = ("builder", "verifier", "review", "request")


class ProfileChecks(DomainService):
    """The profile's checks against the workflow."""

    @staticmethod
    def models(evidence: StageEvidence, workflow: Workflow) -> Findings:
        """`model.<tool>.<stage>` and `model.<tool>`: the model a tool runs a stage on. The key names the tool because
        model names are the tool's: a profile is shared, and an unqualified `model.tidy: <a model name>` would break a
        colleague's run with another tool. So the unqualified forms are refused, and so is a key whose tool or stage
        is misspelled (a stage of a story's run order in <workflow>) — an ignored key is a cost saving nobody gets while
        everyone believes in it."""
        keys = evidence.model_keys()
        if not keys:
            return ()
        stages = tuple(s.value for s in workflow.order(StoryKind.STORY))
        bad = []
        for model in keys:
            key = model.key.value
            parts = key.split(".")
            if len(parts) == 1 or (len(parts) == 2 and parts[1] in stages):
                bad.append(f"`{key}` names no tool — write `model.<tool>.<stage>` or `model.<tool>` "
                           f"({', '.join(MODEL_TOOLS)})")
            elif parts[1] not in MODEL_TOOLS:
                bad.append(f"`{key}`: no tool `{parts[1]}` ({', '.join(MODEL_TOOLS)})")
            elif len(parts) == 3 and parts[2] not in stages + MODEL_PROCESSES:
                bad.append(f"`{key}`: no stage `{parts[2]}` ({', '.join(stages + MODEL_PROCESSES)})")
            elif len(parts) > 3:
                bad.append(f"`{key}` is not `model.<tool>.<stage>`")
            elif not model.value_written.value.strip():
                bad.append(f"`{key}` has no value")
        if bad:
            return (MODELS.fail(Said("; ".join(bad))),)
        return (MODELS.ok(Said(f"{len(keys)} model key(s), each bound to a tool")),)
