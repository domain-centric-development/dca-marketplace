"""A story's text split by scenario (WP-165): the scenarios the plan found holding on today's code, with their rules,
apart from the rest — the story repository's text work when the story's aggregate splits them off."""

from __future__ import annotations

import re
import typing


CRITERIA = re.compile(r"^##\s+acceptance criteria\s*$", re.I)
RULE = re.compile(r"^###\s")
SCENARIO = re.compile(r"^####\s+([a-z0-9][a-z0-9-]*)")


def split_off(lines: typing.List[str], keys: typing.Collection[str]
              ) -> typing.Tuple[typing.List[str], typing.List[str]]:
    """The story's lines without the scenarios `keys`, and those scenarios under their rules. A rule left without a
    scenario goes with them."""
    start = next((i for i, l in enumerate(lines) if CRITERIA.match(l.strip())), None)
    if start is None:
        return lines, []
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    # blocks: (rule heading index or None, scenario key or None, lines)
    kept: typing.List[str] = []
    moved: typing.List[str] = []
    rule: typing.List[str] = []
    rule_kept: typing.List[str] = []
    rule_moved: typing.List[str] = []
    current: typing.List[str] = []
    key: typing.Optional[str] = None

    def close_scenario() -> None:
        nonlocal current, key
        if key is not None:
            (rule_moved if key in keys else rule_kept).extend(current)
        else:
            rule.extend(current)
        current, key = [], None

    def close_rule() -> None:
        nonlocal rule, rule_kept, rule_moved
        close_scenario()
        if rule_kept or (rule and not rule_moved):
            kept.extend(rule + rule_kept)
        if rule_moved:
            moved.extend(rule + rule_moved)
        rule, rule_kept, rule_moved = [], [], []

    for line in lines[start + 1:end]:
        if RULE.match(line) and not SCENARIO.match(line):
            close_rule()
        found = SCENARIO.match(line)
        if found:
            close_scenario()
            key = found.group(1)
        current.append(line)
    close_rule()
    return lines[:start + 1] + kept + lines[end:], moved
