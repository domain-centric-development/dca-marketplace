"""The stack profile as delivery reads it: which model a tool runs a stage on, which commands a stage may run, which
skills carry the stages and the reviews, and the judge's perspectives. The profile's file is the project's; what its
keys mean for a run is decided here, once."""

from __future__ import annotations

import re
import typing

from ....building_blocks import Value
from .stage import StageName
from .usage import ModelName

#: The profile's command keys whose first word a stage may run; every `test.<name>:` is one as well.
COMMAND_KEYS = ("compile", "test", "e2eTest", "architecture", "format", "formatFix")

#: The judge's built-in perspectives — part of the method, never switched off; `reviews:` in the profile adds more.
BUILT_IN_PERSPECTIVES = ("ddd", "hexagonal", "clean-code")

#: The keys that name a skill: a stage's carrier, a review's, the knowledge skill.
CARRIER_KEY = re.compile(r"^(carrier\.[a-z]+|review\.[a-z-]+|knowledge)$")


class ProfileKey(Value):
    """A key of the profile as the project wrote it — `model.claude.build`, `test.integration`, `reviews`."""

    value: str


class ProfileValue(Value):
    """What the profile says under a key, as written; empty where it says nothing."""

    value: str

    def head(self) -> ProfileValue:
        """The first word: a command's program, a model's name, a skill without what follows it."""
        parts = self.value.split()
        return ProfileValue(parts[0] if parts else "")


class ToolName(Value):
    """An agent tool by its record's name — `claude`, `codex`, `opencode`."""

    value: str


class SkillName(Value):
    """A skill by its folder's name, without the plugin prefix — `dca-modelling`, `review-ddd`."""

    value: str


class Perspective(Value):
    """One way the judge looks at a story, and the skill it looks with."""

    name: SkillName
    carrier: SkillName


class StackProfile(Value):
    """The profile's pairs, in the profile's order."""

    entries: typing.Tuple[typing.Tuple[ProfileKey, ProfileValue], ...]

    def get(self, key: ProfileKey) -> ProfileValue:
        """The value under a key; empty where the profile names none."""
        return next((value for k, value in self.entries if k == key), ProfileValue(""))

    def model_for(self, tool: ToolName, stage: StageName) -> ModelName:
        """`model.<tool>.<stage>`, else `model.<tool>`, else none: the key names the tool, so a colleague's run with
        another tool is never handed a model it does not know."""
        for key in (f"model.{tool.value}.{stage.value}", f"model.{tool.value}"):
            found = self.get(ProfileKey(key)).head()
            if found.value:
                return ModelName(found.value)
        return ModelName("")

    def command_heads(self) -> typing.Tuple[ProfileValue, ...]:
        """The first word of every command the profile declares, once each, in its order — a template's `{{…}}`
        placeholder is none."""
        heads: typing.List[ProfileValue] = []
        for key, value in self.entries:
            if key.value in COMMAND_KEYS or key.value.startswith("test."):
                head = value.head()
                if head.value and not head.value.startswith("{{") and head not in heads:
                    heads.append(head)
        return tuple(heads)

    def carrier_entries(self) -> typing.Tuple[typing.Tuple[ProfileKey, ProfileValue], ...]:
        """Every key that names a skill, with the skill as written (a `plugin:` prefix kept)."""
        return tuple((key, value.head()) for key, value in self.entries
                     if CARRIER_KEY.match(key.value) and value.head().value)

    def carriers(self) -> typing.Tuple[SkillName, ...]:
        """The skills the profile names, without a `plugin:` prefix, sorted and once each."""
        return tuple(SkillName(name) for name in sorted({value.value.rsplit(":", 1)[-1]
                                                         for _key, value in self.carrier_entries()}))

    def perspectives(self) -> typing.Tuple[Perspective, ...]:
        """The three built-ins and the profile's `reviews:`, each with the skill `review.<name>:` names — its
        plugin prefix dropped — or `review-<name>` where the profile names none."""
        names = list(BUILT_IN_PERSPECTIVES)
        for extra in re.split(r"[,\s]+", self.get(ProfileKey("reviews")).value):
            if extra and extra not in names:
                names.append(extra)
        found = []
        for name in names:
            carrier = self.get(ProfileKey(f"review.{name}")).head().value
            found.append(Perspective(SkillName(name), SkillName(carrier.rsplit(":", 1)[-1] if carrier
                                                                else f"review-{name}")))
        return tuple(found)
