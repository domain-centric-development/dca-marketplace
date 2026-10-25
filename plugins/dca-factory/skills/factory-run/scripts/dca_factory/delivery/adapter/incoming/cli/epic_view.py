"""One epic as a person reads it: its fields, its text, its stories with their state, as text or Markdown."""

from __future__ import annotations

import typing

from ....application.status.texts import stamp_text
from .terminal import (
    MARKS_MD,
    MARKS_TEXT,
    bold,
    commands,
    dim,
    heading,
    next_md,
    next_text,
    section,
    sections_md,
    sections_text,
    table_md,
    table_text,
)
from .status_view import epic_summary


def epic_story_cells(model: typing.Mapping[str, typing.Any], marks: typing.Mapping[str, str]) -> typing.List[typing.List[str]]:
    """An epic's stories as its view lists them: the story with its mark, its state, when it was delivered, its title."""
    return [[f"{marks[r['mark']]} {r['story']}", r["state"], stamp_text(r["delivered"]), r["title"]] for r in model["rows"]]


def render_epic_text(model: typing.Mapping[str, typing.Any], colour: bool = False) -> str:
    title = f"{model['epic']} — {model['title']}" if model["title"] else model["epic"]
    facts = [(label, value) for label, value in (
        ("Intent", model["intent"]), ("Goal", model["goal"]), ("Outcome", model["metric"]),
        ("Domain", model["domain_contact"]), ("Discovery", model["discovery"]), ("Created", model["created"]),
        ("Stories", epic_summary(model) if model["rows"] else "no story yet"), ("File", model["path"])) if value]
    width = max(len(label) for label, _v in facts)
    out = [""] + heading(title, colour, "═") + [""]
    out += [f"  {model['situation']}", ""] if model.get("situation") else []
    out += [f"  {bold(label.ljust(width), colour)}   {value}" for label, value in facts]
    if model["rows"]:
        stories = section("Stories — newest first", colour) + table_text(
            ["story", "state", "delivered (UTC)", "title"], epic_story_cells(model, MARKS_TEXT),
            indent="    ", marks=[r["mark"] for r in model["rows"]], colour=colour)
    else:
        stories = ["", f"  no story yet — {commands('/factory-backlog stories ' + model['epic'], colour)}"]
    out += sections_text(model["sections"], model["stories_at"], stories, colour)
    if model["journey"]:
        out += ["", f"  {dim('journey', colour)}   {model['journey']['text']} — "
                    f"{commands(model['journey']['action']['skill'], colour)}"]
    return "\n".join(out + ["", "─" * 72] + next_text(model, colour) + [""])


def render_epic_md(model: typing.Mapping[str, typing.Any]) -> str:
    title = f"{model['epic']} — {model['title']}" if model["title"] else model["epic"]
    out = [f"**{title}**", ""] + ([f"*{model['situation']}*", ""] if model.get("situation") else [])
    out += [f"- **{label}:** {value}" for label, value in (
        ("Intent", model["intent"]), ("Goal", model["goal"]), ("Outcome", f"`{model['metric']}`" if model["metric"] else ""),
        ("Domain contact", model["domain_contact"]), ("Discovery", model["discovery"]), ("Created", model["created"]),
        ("Stories", epic_summary(model) if model["rows"] else "no story yet"), ("File", f"`{model['path']}`" if model["path"] else ""))
        if value]
    if model["rows"]:
        stories = ["", "**Stories** — newest first", ""] + table_md(["story", "state", "delivered (UTC)", "title"],
                                                                     epic_story_cells(model, MARKS_MD))
    else:
        stories = ["", f"No story yet — `/factory-backlog stories {model['epic']}`."]
    out += sections_md(model["sections"], model["stories_at"], stories)
    if model["journey"]:
        out += ["", f"*journey* — {model['journey']['text']} → `{model['journey']['action']['skill']}`"]
    return "\n".join(out + ["", next_md(model)])
