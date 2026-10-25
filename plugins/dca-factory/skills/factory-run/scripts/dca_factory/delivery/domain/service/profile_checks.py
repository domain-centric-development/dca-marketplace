"""What the stack profile must hold for a gate to trust a run: a contract this gate knows, model keys bound to a tool,
instructions a tool loads whole."""

from __future__ import annotations

from ....building_blocks import DomainService
from ..gateway.stage_evidence import StageEvidence
from ..model.stage import Pipeline, StoryKind
from ..model.stage_story import ContractNumber, ProfileText
from ..model.verdict import CheckName, Findings, Said

CONTRACT = CheckName("contract")
PROFILE = CheckName("profile")
MODELS = CheckName("models")
INSTRUCTION_SIZE = CheckName("instruction-size")

#: The tools a `model.<tool>` key may name: model names are the tool's.
MODEL_TOOLS = ("claude", "codex", "opencode")
#: The processes a `model.<tool>.<process>` key may name beside the stages: the shared builder and verifier, the
#: reviewers, and a person's request worked headless.
MODEL_PROCESSES = ("builder", "verifier", "review", "request")
#: Codex stops loading project documents at 32 KiB by default and truncates silently; other tools have comparable
#: budgets.
DOC_BUDGET_BYTES = 32 * 1024


def contract_of(declared: ProfileText, implemented: ContractNumber) -> ContractNumber:
    """The contract a profile is read as: the one it declares, else the gate's own."""
    text = declared.value.strip()
    return ContractNumber(int(text)) if text.isdigit() else implemented


class ProfileChecks(DomainService):
    """The profile's own checks."""

    @staticmethod
    def contract_number(evidence: StageEvidence) -> ContractNumber:
        """The contract the profile is read as."""
        return contract_of(evidence.declared_contract(), evidence.gate().contract)

    @staticmethod
    def contract(evidence: StageEvidence) -> Findings:
        """Undeclared is the normal case and only a note: a profile with today's keys is what the template writes. A
        *higher* number than this gate knows is a refusal — the project has keys this gate would ignore, and ignoring a
        key silently is how a check disappears without anyone noticing. A key outside the profile's schema is a note,
        named with the nearest known key: nobody reads it, which is worth knowing and no reason to stop a story."""
        found = [PROFILE.note(Said(f"`{u.key.value}:` is no key the pipeline reads — ignored"
                                   + (f"; did you mean `{u.near.value}:`?" if u.near else "")))
                 for u in evidence.unknown_keys()]
        gate = evidence.gate()
        ours, version = gate.contract.value, gate.version.value
        declared = evidence.declared_contract().value.strip()
        if not declared:
            found.append(CONTRACT.note(Said(f"profile declares no `contract:` — read as {ours} (gate {version})")))
        elif not declared.isdigit():
            found.append(CONTRACT.fail(Said(f"profile's `contract: {declared}` is not a number")))
        elif int(declared) > ours:
            found.append(CONTRACT.fail(Said(
                f"the profile is written for gate contract {declared} and this gate implements {ours} (gate {version}) "
                f"— run `factory.sh update` before trusting a run, because this script would ignore whatever the newer "
                f"contract added")))
        elif int(declared) < ours:
            found.append(CONTRACT.note(Said(
                f"the profile declares contract {declared} and this gate implements {ours} (gate {version}) — still "
                f"read, and worth bringing up to date")))
        else:
            found.append(CONTRACT.ok(Said(f"profile and gate agree on contract {ours} (gate {version})")))
        return tuple(found)

    @staticmethod
    def models(evidence: StageEvidence) -> Findings:
        """`model.<tool>.<stage>` and `model.<tool>`: the model a tool runs a stage on. The key names the tool because
        model names are the tool's: a profile is shared, and an unqualified `model.tidy: <a model name>` would break a
        colleague's run with another tool. So the unqualified forms are refused, and so is a key whose tool or stage
        is misspelled — an ignored key is a cost saving nobody gets while everyone believes in it."""
        keys = evidence.model_keys()
        if not keys:
            return ()
        stages = tuple(s.value for s in Pipeline.order(StoryKind.STORY))
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

    @staticmethod
    def instruction_size(evidence: StageEvidence) -> Findings:
        """A note, not a check: instructions past a tool's document budget are truncated silently, so a run can be
        missing half its rules without anything saying so."""
        found = evidence.instruction_file()
        if found is None:
            return ()
        name, size = found.place.value, found.size.value
        if size > DOC_BUDGET_BYTES:
            return (INSTRUCTION_SIZE.skip(Said(
                f"{name} is {size} bytes, past the {DOC_BUDGET_BYTES}-byte budget some tools load — the rest is "
                f"truncated silently; move detail into referenced files")),)
        return (INSTRUCTION_SIZE.ok(Said(f"{name} is {size} bytes, within a tool's budget")),)
