"""What decides whether a gate is green, kept out of the judged stage's reach: the guarded set — the stack profile
and the globs of its `guarded:` key —, the guarded changes a plan announces with their reason, and what the story
changed of them."""

from __future__ import annotations

import re
import typing

from ....building_blocks import Value
from .story_state import Detail
from .story_words import Place


class GuardedPattern(Value):
    """One glob of the guarded set, relative to the project root: `**` any depth, `*` and `?` within one segment; a
    path without a wildcard is the file itself or everything below the folder it names."""

    value: str

    def covers(self, path: Place) -> bool:
        """Whether <path> falls under this glob."""
        glob, plain = self.plain().value, GuardedPattern(path.value).plain().value
        if not any(c in glob for c in "*?"):
            return bool(re.match(re.escape(glob.rstrip("/")) + r"(?:/.*)?\Z", plain))
        out, at = "", 0
        while at < len(glob):
            if glob.startswith("**/", at):
                out, at = out + "(?:.*/)?", at + 3
            elif glob.startswith("**", at):
                out, at = out + ".*", at + 2
            elif glob[at] == "*":
                out, at = out + "[^/]*", at + 1
            elif glob[at] == "?":
                out, at = out + "[^/]", at + 1
            else:
                out, at = out + re.escape(glob[at]), at + 1
        return bool(re.match(out + r"\Z", plain))

    def plain(self) -> GuardedPattern:
        """The glob or path as the records write it: `/` between segments, no leading `./`, no backticks."""
        written = self.value.strip().strip("`").replace("\\", "/")
        return GuardedPattern(written[2:] if written.startswith("./") else written)


class GuardedSet(Value):
    """What judges a stage: the stack profile (always) and the globs the profile's `guarded:` names."""

    patterns: typing.Tuple[GuardedPattern, ...]

    @classmethod
    def of(cls, profile: Place, guarded: Detail) -> GuardedSet:
        """The profile file and every glob of `guarded:`, split on blanks and commas."""
        globs = [g for g in re.split(r"[\s,]+", guarded.value.strip()) if g]
        return cls(tuple(dict.fromkeys(GuardedPattern(g) for g in [profile.value, *globs])))

    def covers(self, path: Place) -> bool:
        """Whether <path> is guarded."""
        return any(p.covers(path) for p in self.patterns)

    def named(self) -> Detail:
        """The globs as a person reads them."""
        return Detail(" ".join(p.value for p in self.patterns))

    def opened(self, announced: typing.Tuple[GuardedChange, ...]) -> typing.Tuple[GuardedPattern, ...]:
        """The globs that cover a path the plan announced."""
        return tuple(p for p in self.patterns if any(p.covers(c.path) for c in announced))

    def walled(self, announced: typing.Tuple[GuardedChange, ...],
               present: typing.Tuple[Place, ...]) -> typing.Tuple[GuardedPattern, ...]:
        """What a stage may not edit: every glob — but one that covers a path the plan announced becomes the files of
        <present> under it (the project's files under the opened globs), the announced ones left out, so the stage
        may change exactly those."""
        said = {GuardedPattern(c.path.value).plain().value for c in announced}
        walls: typing.List[GuardedPattern] = []
        for pattern in self.patterns:
            if pattern not in self.opened(announced):
                walls.append(pattern)
                continue
            walls += [GuardedPattern(p.value).plain() for p in present
                      if pattern.covers(p) and GuardedPattern(p.value).plain().value not in said]
        return tuple(dict.fromkeys(walls))


class GuardedChange(Value):
    """A guarded path a plan announces it will change, and the reason it gives — empty where it gives none."""

    path: Place
    reason: Detail

    def reasoned(self) -> bool:
        """Whether the plan gives a reason for it."""
        return bool(self.reason.value.strip())


class GuardedFacts(Value):
    """The guarded set, the plan's `## Guarded changes` (None where the plan has no such section), and the paths
    the story's stages changed and that still differ from the story's base (None where no record was taken)."""

    guarded: GuardedSet
    announced: typing.Optional[typing.Tuple[GuardedChange, ...]]
    changed: typing.Optional[typing.Tuple[Place, ...]]

    def touched(self) -> typing.Tuple[Place, ...]:
        """The guarded paths the story changed."""
        return tuple(p for p in self.changed or () if self.guarded.covers(p))

    def unannounced(self) -> typing.Tuple[Place, ...]:
        """The guarded paths the story changed that its plan did not announce."""
        said = {GuardedPattern(c.path.value).plain().value for c in self.announced or ()}
        return tuple(p for p in self.touched() if GuardedPattern(p.value).plain().value not in said)
