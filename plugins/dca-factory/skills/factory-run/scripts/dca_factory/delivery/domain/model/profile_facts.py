"""The stack profile as a gate checks it: the contract it is read as, its keys, its models, the instruction file."""

from __future__ import annotations

import typing

from ....building_blocks import Value
from .story_state import Detail
from .story_words import Place
from .verdict import CheckName, Findings, Said


class ContractNumber(Value):
    """A gate contract: what the gate reads and writes, raised when that changes incompatibly."""

    value: int


#: The checks over the profile: the contract the gate reads it as, the keys nobody reads, the instruction file's size.
CONTRACT_CHECK = CheckName("contract")


PROFILE = CheckName("profile")


INSTRUCTION_SIZE = CheckName("instruction-size")


#: Codex stops loading project documents at 32 KiB by default and truncates silently; other tools have comparable
#: budgets.
DOC_BUDGET_BYTES = 32 * 1024


class GateRelease(Value):
    """The gate that checks: the contract it implements and its version."""

    contract: ContractNumber
    version: Detail

    def reads(self, declared: ProfileText) -> ContractNumber:
        """The contract a profile is read as: the one it declares, else the gate's own."""
        text = declared.value.strip()
        return ContractNumber(int(text)) if text.isdigit() else self.contract

    def profile_findings(self, declared_text: ProfileText, unknown: typing.Sequence[UnknownKey]) -> Findings:
        """Undeclared is the normal case and only a note: a profile with today's keys is what the template writes. A
        *higher* number than this gate knows is a refusal — the project has keys this gate would ignore, and ignoring a
        key silently is how a check disappears without anyone noticing. A key outside the profile's schema is a note,
        named with the nearest known key: nobody reads it, which is worth knowing and no reason to stop a story."""
        found = [PROFILE.note(Said(f"`{u.key.value}:` is no key the pipeline reads — ignored"
                                   + (f"; did you mean `{u.near.value}:`?" if u.near else "")))
                 for u in unknown]
        ours, version = self.contract.value, self.version.value
        declared = declared_text.value.strip()
        if not declared:
            found.append(CONTRACT_CHECK.note(Said(f"profile declares no `contract:` — read as {ours} (gate {version})")))
        elif not declared.isdigit():
            found.append(CONTRACT_CHECK.fail(Said(f"profile's `contract: {declared}` is not a number")))
        elif int(declared) > ours:
            found.append(CONTRACT_CHECK.fail(Said(
                f"the profile is written for gate contract {declared} and this gate implements {ours} (gate {version}) "
                f"— run `factory.sh update` before trusting a run, because this script would ignore whatever the newer "
                f"contract added")))
        elif int(declared) < ours:
            found.append(CONTRACT_CHECK.note(Said(
                f"the profile declares contract {declared} and this gate implements {ours} (gate {version}) — still "
                f"read, and worth bringing up to date")))
        else:
            found.append(CONTRACT_CHECK.ok(Said(f"profile and gate agree on contract {ours} (gate {version})")))
        return tuple(found)


class ProfileKey(Value):
    value: str


class ProfileText(Value):
    """A profile value, as written."""

    value: str


class UnknownKey(Value):
    """A profile key nobody reads, and the nearest key that is read."""

    key: ProfileKey
    near: typing.Optional[ProfileKey]


class ModelKey(Value):
    """A `model…` key of the profile and its value."""

    key: ProfileKey
    value_written: ProfileText


class ByteSize(Value):
    value: int


class InstructionFile(Value):
    """The project's instruction file a tool loads first, and its size."""

    place: Place
    size: ByteSize

    def size_findings(self) -> Findings:
        """A note, not a check: instructions past a tool's document budget are truncated silently, so a run can be
        missing half its rules without anything saying so."""
        name, size = self.place.value, self.size.value
        if size > DOC_BUDGET_BYTES:
            return (INSTRUCTION_SIZE.skip(Said(
                f"{name} is {size} bytes, past the {DOC_BUDGET_BYTES}-byte budget some tools load — the rest is "
                f"truncated silently; move detail into referenced files")),)
        return (INSTRUCTION_SIZE.ok(Said(f"{name} is {size} bytes, within a tool's budget")),)
