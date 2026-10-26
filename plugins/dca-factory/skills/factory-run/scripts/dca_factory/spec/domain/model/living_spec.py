"""The rules of the living spec (WP-98, WP-105): what a story's criteria are to what holds, what is wrong with a
delta, and what holds after the story — the delta merged.

The plan derives the delta: what is added, changed, removed, and which rule is renamed. What follows from comparing
the story with the spec — a key the spec lacks is added, one it holds word for word holds already, one it holds
otherwise is changed — is derived here; a removal and a renamed rule only the plan can say. Every change and removal
of what holds is backed by a sentence of a person.
"""

from __future__ import annotations

import re
import typing

from ....building_blocks import DomainService
from .criterion import Criterion, CriterionKey, FeatureName, Line, RuleText, Selector
from .delta import Delta, Move, Problem, Verdict

Criteria = typing.Sequence[Criterion]

#: A rule's text as a person quotes it: straight, typographic or German quotation marks.
QUOTED = re.compile(r'"([^"]+)"|“([^”]+)”|„([^“”]+)[“”]')


class LivingSpec(DomainService):
    """What the spec makes of a story's criteria and a plan's delta. Stateless: it takes the criteria the spec holds
    and the story's, and returns verdicts, problems and what holds after."""

    @staticmethod
    def derived(story: Criteria, spec: Criteria) -> typing.Dict[CriterionKey, Verdict]:
        """What follows from comparing the story's criteria with the spec."""
        held = {item.key: item for item in spec}
        return {item.key: Verdict.ADDS if item.key not in held
                else Verdict.HOLDS if item.wording() == held[item.key].wording() else Verdict.CHANGES
                for item in story}

    @classmethod
    def delta_problems(cls, story: Criteria, spec: Criteria, delta: Delta) -> typing.List[Problem]:
        """What is wrong with a delta against the story and the spec."""
        problems = []
        held = {item.key: item for item in spec}
        found = cls.derived(story, spec)
        renamed = {rename.old for rename in delta.renames}
        for verdict in (Verdict.ADDS, Verdict.CHANGES, Verdict.HOLDS):
            verb = verdict.value
            for key in sorted(delta.named(verdict), key=lambda k: k.value):
                name = key.value
                if key not in found and verdict is Verdict.HOLDS and key in held and held[key].rule in renamed:
                    continue                 # it follows its rule's new text without being one of the story's (#164)
                if key not in found:
                    problems.append(Problem(f"`{verb} {name}` — the story has no criterion `{name}`"))
                elif found[key] is not verdict and not (verdict is Verdict.ADDS and found[key] is Verdict.HOLDS):
                    problems.append(Problem(
                        f"`{verb} {name}` — the spec {'has no' if key not in held else 'holds'} `{name}`"
                        + ("" if key not in held else
                           " word for word" if found[key] is Verdict.HOLDS else " otherwise")
                        + f": it is `{found[key].value} {name}`"))
        for key in sorted(delta.removes, key=lambda k: k.value):
            if key not in held:
                problems.append(Problem(f"`removes {key.value}` — the spec has no `{key.value}`"))
            elif key in found:
                problems.append(Problem(f"`removes {key.value}` — the story still has `{key.value}` as a criterion"))
        rules = {item.rule for item in spec}
        for rename in delta.renames:
            if rename.old not in rules:
                problems.append(Problem(f'rule "{rename.old.value}" — the spec has no such rule'))
        return problems

    @staticmethod
    def renamed_rules(spec: Criteria, delta: Delta) -> typing.Dict[RuleText, typing.List[CriterionKey]]:
        """The criteria the spec holds under each rule the delta renames, which follow its new text."""
        return {rename.old: [item.key for item in spec if item.rule == rename.old and item.key not in delta.removes]
                for rename in delta.renames}

    @staticmethod
    def rule_problems(changed: typing.Sequence[Line], story: Criteria, spec: Criteria,
                      delta: Delta) -> typing.List[Problem]:
        """A rule `## Changed expectations` quotes word for word, while the story no longer writes it and the delta
        neither renames it nor takes all of it away — a rewording the spec would not see: the old rule would keep its
        criteria and the story's new text would stand beside it as a second rule (#164)."""
        rules = {item.rule for item in spec if item.rule}
        kept = {item.rule for item in story}
        renamed = {rename.old for rename in delta.renames}
        problems: typing.List[Problem] = []
        for line in changed:
            for match in QUOTED.finditer(line.value):
                rule = RuleText(" ".join(next(g for g in match.groups() if g).split()))
                if rule not in rules or rule in kept or rule in renamed:
                    continue
                left = [item.key.value for item in spec if item.rule == rule and item.key not in delta.removes]
                if left:
                    problems.append(Problem(
                        f'`## Changed expectations` names the rule "{rule.value}", which the story no longer writes '
                        f'— `rule "{rule.value}" → "<its new text>"` where it is reworded ({", ".join(left)} follow '
                        f"it), or `removes` what it takes away"))
        return list(dict.fromkeys(problems))

    @staticmethod
    def placement(story: Criteria, held: Criteria, feature: FeatureName,
                  features: typing.AbstractSet[FeatureName]) -> Delta:
        """Where the story's criteria go (WP-105), as the delta says it: a criterion the context holds under another
        feature moves to the story's, and the story's feature is born where the context does not have it yet."""
        where = {item.key: item.feature for item in held}
        moves = {item.key: Move(where[item.key].place(), feature.place()) for item in story
                 if item.key in where and where[item.key] != feature}
        born = frozenset((feature,)) if feature.value and story and feature not in features else frozenset()
        return Delta(moves=moves, features=born)

    @staticmethod
    def placement_problems(story: Criteria, held: Criteria, delta: Delta, feature: FeatureName,
                           features: typing.AbstractSet[FeatureName]) -> typing.List[Problem]:
        """What is wrong with where the story's criteria go (WP-105): a criterion the context holds under another
        feature moves — the delta says `moves <key>: <from> → <to>` —, a move names what the spec and the story say,
        and a feature the context does not have yet is born with `adds feature <name>`. <held> is the context's
        criteria with their feature, <features> the context's feature folders."""
        problems, keys = [], {item.key for item in story}
        where = {item.key: item.feature for item in held}
        target = feature
        placed = LivingSpec.placement(story, held, feature, features)
        for key, move in placed.moves.items():
            if key not in delta.moves:
                problems.append(Problem(
                    f"`{key.value}` stands under {move.source.value} and the story puts it under "
                    f"{move.destination.value} — `moves {key.value}: {move.source.value} → {move.destination.value}`"))
        for key, move in sorted(delta.moves.items(), key=lambda pair: pair[0].value):
            if key not in where:
                problems.append(Problem(f"`moves {key.value}` — the spec has no `{key.value}`"))
            elif key not in keys:
                problems.append(Problem(f"`moves {key.value}` — the story has no criterion `{key.value}`"))
            elif move.source != where[key].place() or move.destination != target.place():
                problems.append(Problem(
                    f"`moves {key.value}: {move.source.value} → {move.destination.value}` — it stands under "
                    f"{where[key].place().value}, and the story's feature is {target.place().value}"))
        if target in placed.features and target not in delta.features:
            problems.append(Problem(f"feature `{target.value}` is new to the context — `adds feature {target.value}`"))
        for name in sorted(delta.features, key=lambda f: f.value):
            if name in features:
                problems.append(Problem(f"`adds feature {name.value}` — the context has it already"))
            elif name != target:
                problems.append(Problem(f"`adds feature {name.value}` — the story's feature is {target.place().value}"))
        return problems

    @classmethod
    def touches(cls, story: Criteria, spec: Criteria, delta: Delta) -> typing.List[CriterionKey]:
        """The keys whose behaviour the story changes or takes away — what a person's sentence has to back."""
        found = cls.derived(story, spec)
        return sorted([key for key, verdict in found.items() if verdict is Verdict.CHANGES] + list(delta.removes),
                      key=lambda k: k.value)

    @staticmethod
    def merge(spec: Criteria, story: Criteria, delta: Delta,
              tests: typing.Mapping[CriterionKey, typing.Tuple[Selector, ...]]) -> typing.List[Criterion]:
        """The spec after the story: a removed criterion gone, a renamed rule renamed, and the story's criteria of
        each rule standing together in the order the story lists them, held ones included (#136) — where the first
        of them stood under that rule, or at the rule's end when none stood there (a new rule appended). So a rule's
        order follows the story that delivered it last, not the order its criteria happened to arrive in; a criterion
        the story does not list keeps its place, and a criterion that moves to another rule leaves its old one.
        <tests> is the story's mapping; a criterion that holds keeps its test line unless the mapping names one."""
        renamed = {rename.old: rename.new for rename in delta.renames}
        merged: typing.List[typing.Optional[Criterion]] = []
        for item in spec:
            if item.key in delta.removes:
                continue
            merged.append(item.under(renamed[item.rule]) if item.rule in renamed else item)
        held = {item.key: item for item in merged if item is not None}
        rules: typing.List[typing.Optional[RuleText]] = []
        for item in story:
            if item.rule not in rules:
                rules.append(item.rule)
        for rule in rules:
            block = []
            for item in story:
                if item.rule == rule:
                    proven = tests.get(item.key) or ()
                    block.append(item.proven_by(proven or (held[item.key].tests if item.key in held else ())))
            keys = {item.key for item in block}
            anchor = next((position for position, other in enumerate(merged)
                           if other is not None and other.key in keys and other.rule == rule), None)
            if anchor is not None:
                merged[anchor] = None
            merged = [other for other in merged if other is None or other.key not in keys]
            if anchor is not None:
                at = merged.index(None)
                merged[at:at + 1] = block
                continue
            last = max((position for position, other in enumerate(merged)
                        if other is not None and other.rule == rule), default=None)
            if last is None:
                merged.extend(block)
            else:
                merged[last + 1:last + 1] = block
        return [item for item in merged if item is not None]

    @classmethod
    def merge_context(cls, held: Criteria, story: Criteria, delta: Delta,
                      tests: typing.Mapping[CriterionKey, typing.Tuple[Selector, ...]],
                      feature: FeatureName) -> typing.Dict[FeatureName, typing.List[Criterion]]:
        """Every file of the context after the story: a removed criterion gone wherever it stood, a moved one out of
        its old file, a renamed rule renamed everywhere, the story's criteria merged into the file of its feature. A
        file left without a criterion maps to []."""
        leaving = set(delta.moves) | {item.key for item in story}
        files: typing.Dict[FeatureName, typing.List[Criterion]] = {}
        for item in held:
            files.setdefault(item.feature, []).append(item)
        files.setdefault(feature, [])
        merged = {}
        for name, entries in files.items():
            if name == feature:
                merged[name] = cls.merge(entries, story, delta, tests)
            else:
                kept = [item for item in entries if item.key not in leaving]
                merged[name] = cls.merge(kept, [], delta, {})
        return merged
