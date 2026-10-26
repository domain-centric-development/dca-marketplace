"""A story's acceptance criteria as files hold them: the shape the gate checks, and the scenarios as a person reads them."""

from __future__ import annotations

import re
import typing

from .hand_over_patterns import CRITERION
from .....sharedkernel.adapter.outgoing.markdown.front_matter import GateError
from .story_layout import story_kind
from .stage_evidence_files import happy_paths
from .design_files import STEP
from .test_files import scenario_titles


SCENARIO_KEY = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def criteria_of(story_path: str, body: str, front: typing.Optional[typing.Mapping[str, typing.Any]] = None
                ) -> typing.List[typing.Tuple[str, str]]:
    """Acceptance criteria as (key, text) pairs, read from the `## Acceptance criteria` section — none for a task
    (`front` given), which has no criterion.

    Two forms, mixable. The line form: one `- <key>: <text>` line per criterion. The scenario form:
    `#### <key>` followed by `- Given / When / Then / And / But` steps, optionally grouped under
    `### Rule: <text>` headings — Gherkin's own shape. The key is a name, never a number, and is
    what the test stage binds. The shape is checked here, deterministically: a rule without a
    scenario, a scenario without exactly one trigger or without an outcome, a step outside a
    scenario, an unknown step and a repeated key are refused. Whether a scenario covers its rule
    is not a question a script can answer; the backlog skill asks it."""
    collecting = False
    found: typing.List[typing.Tuple[str, str]] = []
    keys: typing.Set[str] = set()
    rule: typing.Optional[str] = None
    rule_scenarios = 0
    scenario: typing.Optional[typing.Tuple[str, typing.List[typing.Tuple[str, str]]]] = None

    def refuse(message: str) -> typing.NoReturn:
        raise GateError(f"{story_path}: {message}")

    def close_scenario() -> None:
        nonlocal scenario
        if scenario is None:
            return
        key, steps = scenario
        triggers, outcome, phase = 0, False, None
        for word, _ in steps:
            if word in ("Given", "When", "Then"):
                phase = word
            if word == "When" or (word in ("And", "But") and phase == "When"):
                triggers += 1
            if word == "Then":
                outcome = True
        if not steps:
            refuse(f"scenario `{key}` has no steps — write `- Given / When / Then` lines under it")
        if triggers != 1:
            refuse(f"scenario `{key}` has {triggers} triggers — exactly one `When` (an `And` after it is "
                   f"a second trigger); two triggers are two scenarios")
        if not outcome:
            refuse(f"scenario `{key}` has no `Then` — a scenario states what is observed")
        found.append((key, "; ".join(f"{word} {text}".strip() for word, text in steps)))
        scenario = None

    def close_rule() -> None:
        if rule is not None and rule_scenarios == 0:
            refuse(f"rule `{rule}` has no scenario — every rule gets at least one `#### <key>` scenario")

    def add_key(key: str) -> None:
        if key in keys:
            refuse(f"acceptance criterion key `{key}` appears twice — a key names one behaviour")
        keys.add(key)

    for line in body.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("## acceptance criteria"):
            collecting = True
            continue
        if collecting and line.startswith("## "):
            break
        if not collecting or not stripped:
            continue
        if line.startswith("### "):
            close_scenario()
            close_rule()
            heading = line[4:].strip()
            if not heading.lower().startswith("rule:"):
                refuse(f"`### {heading}` — a third-level heading under the criteria is a `### Rule: <text>`")
            rule, rule_scenarios = heading[5:].strip(), 0
            continue
        if line.startswith("#### "):
            close_scenario()
            key = re.sub(r"\s*\(happy path\)$", "", line[5:].strip())
            if not SCENARIO_KEY.match(key):
                refuse(f"scenario heading `#### {key}` is not a key — lowercase and hyphenated, naming the behaviour")
            add_key(key)
            scenario = (key, [])
            if rule is not None:
                rule_scenarios += 1
            continue
        if line[:1].isspace() and not stripped.startswith(("-", "#")):
            # a Markdown continuation line: the step or line criterion above it goes on
            if scenario is not None and scenario[1]:
                word, text = scenario[1][-1]
                scenario[1][-1] = (word, f"{text} {stripped}")
                continue
            if scenario is None and found:
                key, text = found[-1]
                found[-1] = (key, f"{text} {stripped}")
                continue
        step = STEP.match(stripped)
        if step:
            if scenario is None:
                refuse(f"step {stripped!r} stands outside a scenario — put it under a `#### <key>` heading")
            scenario[1].append((step.group(1), step.group(2).strip()))
            continue
        if scenario is not None and stripped.startswith("-"):
            refuse(f"scenario `{scenario[0]}`: {stripped!r} is not a step — steps begin with Given, When, "
                   f"Then, And or But")
        match = CRITERION.match(stripped)
        if match:
            close_scenario()
            add_key(match.group(1))
            found.append((match.group(1), match.group(2).strip()))
        elif stripped.startswith("-"):
            refuse(f"acceptance criterion {stripped!r} has no key — write `- <key>: <criterion>` with a "
                   f"lowercase, hyphenated key that names the behaviour, or a `#### <key>` scenario")
    close_scenario()
    close_rule()
    if not found and story_kind(front or {}) == "task":
        return []
    if not found:
        raise GateError(
            f"{story_path}: no acceptance criteria — add a `## Acceptance criteria` "
            f"section with one `- <key>: <criterion>` line or one `#### <key>` scenario per criterion"
        )
    return found


def scenarios_of(body: str) -> typing.List[typing.Dict[str, typing.Any]]:
    """The criteria as a person reads them (WP-146), in the story's order: [{key, title, rule, happy, steps, text}] —
    `steps` the scenario's `[{word, text}]` (Given / When / Then / And / But), `text` the line form's criterion, `rule`
    the `### Rule:` it stands under, `happy` its happy-path mark. A reader for the views: it refuses nothing —
    `criteria_of` is the check."""
    section = body.split("## Acceptance criteria", 1)[-1].split("\n## ", 1)[0] if "## Acceptance criteria" in body else ""
    titles, happy = scenario_titles(body), set(happy_paths(body))
    found: typing.List[typing.Dict[str, typing.Any]] = []
    rule = ""
    current: typing.Optional[typing.Dict[str, typing.Any]] = None
    for line in section.splitlines():
        stripped = line.strip()
        if line.startswith("### "):
            title = line[4:].strip()
            rule, current = (title[5:].strip() if title.lower().startswith("rule:") else title), None
            continue
        heading = re.match(r"^####\s+([a-z0-9][a-z0-9-]*)", stripped)
        criterion = CRITERION.match(stripped)
        step = STEP.match(stripped)
        if heading:
            key = heading.group(1)
            current = dict(key=key, title=titles.get(key, key), rule=rule, happy=key in happy, steps=[], text="")
            found.append(current)
        elif step and current is not None:
            current["steps"].append(dict(word=step.group(1), text=step.group(2).strip()))
        elif stripped and line[:1].isspace() and found and (found[-1]["steps"] or found[-1]["text"]):
            # a Markdown continuation line: the step or line criterion above it goes on
            last = found[-1]["steps"][-1] if found[-1]["steps"] else found[-1]
            last["text"] = f"{last['text']} {stripped}"
        elif criterion:
            key = criterion.group(1)
            found.append(dict(key=key, title=titles.get(key, key), rule=rule, happy=key in happy, steps=[],
                              text=criterion.group(2).strip()))
            current = None
    return found
