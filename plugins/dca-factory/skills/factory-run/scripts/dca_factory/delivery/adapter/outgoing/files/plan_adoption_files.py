"""The plan gate's write where the plan found scenarios that hold on today's code alone (WP-165): the whole story
becomes `status: adopted`, or those scenarios move into an adopted story of their own beside it. A gate's write,
never a stage's — the story is the person's file, and the runner reads the changed kind on its next pass."""

from __future__ import annotations

import os
import re
import time
import typing

from .....sharedkernel.adapter.outgoing.markdown.front_matter import read_front_matter
from .owned_files import write_answered, write_story_fields
from .story_layout import STORY_FILE

#: The record id the gate's `answered:` line cites: no decision record, the plan's own `## Adopt`.
PLAN_ADOPT = "plan-adopt"

CRITERIA = re.compile(r"^##\s+acceptance criteria\s*$", re.I)
RULE = re.compile(r"^###\s")
SCENARIO = re.compile(r"^####\s+([a-z0-9][a-z0-9-]*)")


def adopt_whole(runs: str, story_path: str, held: typing.Sequence[typing.Tuple[str, str]]) -> None:
    write_story_fields(story_path, status="adopted")
    write_answered(story_path, runs, PLAN_ADOPT, "every scenario holds on today's code, and no delivered story "
                   "carries it — the plan adopted the story: " + ", ".join(f"{k} ({t})" for k, t in held))


def split_off(lines: typing.List[str], keys: typing.Collection[str]
              ) -> typing.Tuple[typing.List[str], typing.List[str]]:
    """The story's lines without the scenarios `keys`, and those scenarios under their rules. A rule left without a
    scenario goes with them."""
    start = next((i for i, l in enumerate(lines) if CRITERIA.match(l.strip())), None)
    if start is None:
        return lines, []
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    # blocks: (rule heading index or None, scenario key or None, lines)
    kept, moved, rule, rule_kept, rule_moved = [], [], [], [], []
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


def adopt_split(runs: str, story_path: str, story_id: str, held: typing.Sequence[typing.Tuple[str, str]]) -> str:
    """The scenarios that hold move into `<story>-holds`, an adopted story in the same epic; returns its id."""
    front, _body = read_front_matter(story_path)
    with open(story_path, encoding="utf-8", newline="") as handle:
        text = handle.read()
    newline = "\r\n" if "\r\n" in text else "\n"
    rest, moved = split_off(text.split(newline), {k for k, _t in held})
    new_id = f"{story_id}-holds"
    folder = os.path.join(os.path.dirname(os.path.dirname(story_path)), new_id)
    title = str(front.get("title") or story_id).strip()
    fields = [f"id: {new_id}"] + [f"{k}: {front[k]}" for k in ("epic", "context", "feature") if front.get(k)] + [
        "status: adopted", f"created: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}",
        f"title: {title} — what holds today"]
    body = ["---", *fields, "---", "", f"# {title} — what holds today", "", "## Story", "",
            f"Split from story `{story_id}` by its plan: these scenarios hold on today's code, and no delivered story "
            "carries them.", "", "## Acceptance criteria", "", *[l for l in moved], "",
            "## Assumptions", "",
            f"- answered: split from `{story_id}` — " + ", ".join(f"{k} ({t})" for k, t in held)
            + f" ({PLAN_ADOPT})", ""]
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, STORY_FILE), "w", encoding="utf-8", newline="") as handle:
        handle.write(newline.join(re.sub(r"\s*\(happy path\)\s*$", "", l) for l in body))
    with open(story_path, "w", encoding="utf-8", newline="") as handle:
        handle.write(newline.join(rest))
    write_answered(story_path, runs, PLAN_ADOPT, f"{', '.join(k for k, _t in held)} hold on today's code, and no "
                   f"delivered story carries them — the plan split them into the adopted story `{new_id}`")
    return new_id
