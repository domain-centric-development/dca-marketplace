"""A criterion of what holds, and the words it is made of."""

from __future__ import annotations

import dataclasses
import enum
import re
import typing

from ....building_blocks import Value


class CriterionKey(Value):
    """A criterion's key — unique across its context, so a criterion moves between features keeping it."""

    value: str


class RuleText(Value):
    """The text of a `### Rule:` that groups criteria within a feature."""

    value: str


class Line(Value):
    """One line of a criterion as written: its heading or its text, a step of a scenario."""

    value: str


class Selector(Value):
    """A test, as the `Test:` line names it."""

    value: str


class FeatureName(Value):
    """A feature as its folder is named. Empty for what belongs to no feature: the context's own file."""

    value: str

    @classmethod
    def spelled(cls, words: Line) -> FeatureName:
        """A feature as a story or a delta names it, spelled as its folder and the code's package spell it: lowercase
        letters and digits — `Product Details` and `productdetails` are one feature."""
        return cls(re.sub(r"[^a-z0-9]+", "", words.value.strip().lower()))

    def place(self) -> Place:
        """Where the delta says it stands: the feature's name, or `context` for none."""
        return Place(self.value or CONTEXT_WIDE)


#: What the delta names as the place of what belongs to no feature: the context's own `scenarios.md`.
CONTEXT_WIDE = "context"


class Place(Value):
    """A feature as the delta names it — its name, or `context` for none."""

    value: str


class Form(enum.Enum):
    """How a criterion is written: a scenario (`#### <key>` and its steps) or a line (`- <key>: <criterion>`)."""

    SCENARIO = "scenario"
    LINE = "line"


class Wording(Value):
    """A criterion as it is compared word for word: its rule beside its lines, white space collapsed."""

    rule: RuleText
    lines: Line


class Criterion(Value):
    """One statement of what holds, under its key and its rule, in its form, with the tests that prove it — and the
    feature it stands under in the spec."""

    key: CriterionKey
    rule: typing.Optional[RuleText]
    form: Form
    lines: typing.Tuple[Line, ...]
    tests: typing.Tuple[Selector, ...] = ()
    feature: FeatureName = FeatureName("")

    def wording(self) -> Wording:
        return Wording(self.rule or RuleText(""), Line(" ".join(" ".join(line.value for line in self.lines).split())))

    def proven_by(self, tests: typing.Tuple[Selector, ...]) -> Criterion:
        return dataclasses.replace(self, tests=tests)

    def under(self, rule: typing.Optional[RuleText]) -> Criterion:
        return dataclasses.replace(self, rule=rule)

    def standing_in(self, feature: FeatureName) -> Criterion:
        return dataclasses.replace(self, feature=feature)
