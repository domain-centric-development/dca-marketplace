"""The factory explained: the flow, the commands, the marks, the files, as text or Markdown."""

from __future__ import annotations

import typing

from .terminal import (
    MARKS_MD,
    MARKS_TEXT,
    commands,
    dim,
    heading,
    next_md,
    next_text,
    section,
    table_md,
    table_text,
)


SHELL_NAME = "factory.sh"          # the help's tables name the runner short; the view says its full path once


#: The two parts of the flow: the foundation is written once and changed when things move; the cycle recurs.
PART_WORDS = {"foundation": "once", "cycle": "↻ cycle"}


NOW_WORDS = {"done": "done", "next": "you are here", "look": "waits for your look", "question": "waits for your answer",
             "running": "running"}


def shell_form(command: typing.Optional[str]) -> str:
    return f"{SHELL_NAME} {command}" if command else ""


def render_help_text(model: typing.Mapping[str, typing.Any], colour: bool = False) -> str:
    out = [""] + heading(f"Factory help — {model['project']}", colour, "═")
    out += section("The flow — a foundation once, then the cycle — and where this project is now", colour)
    rows = [[f"{f['number']}  {f['step']}", PART_WORDS[f["part"]], NOW_WORDS.get(f["mark"], ""), f["skill"],
             shell_form(f["shell"]) or "— needs an agent session", f["what"]] for f in model["flow"]]
    out += table_text(["step", "part", "now", "agent", "shell", "what it is"], rows,
                      marks=[f["mark"] if f["mark"] != "none" else None for f in model["flow"]], colour=colour, painted=3)
    out += section("Commands", colour)
    out += table_text(["to see", "agent", "shell", "what it shows"],
                      [[c["name"], c["skill"], shell_form(c["shell"]) or "— needs an agent session", c["what"]]
                       for c in model["commands"]],
                      colour=colour, first_bold=True)
    note = f"{SHELL_NAME} is {model['runner']}, in a terminal of its own; a session uses the agent form."
    out += ["", "    " + dim(note, colour)]
    out += section("Marks", colour)
    out += table_text(["mark", "means"], [[MARKS_TEXT[m["mark"]], m["meaning"]] for m in model["marks"]],
                      marks=[m["mark"] for m in model["marks"]], colour=colour, painted=1)
    out += section("Files", colour)
    out += table_text(["what", "where", "holds"], [[f["name"], f["where"], f["holds"]] for f in model["files"]],
                      colour=colour, first_bold=True)
    return "\n".join(out + ["", "─" * 72] + next_text(model, colour) + [""])


def render_help_md(model: typing.Mapping[str, typing.Any]) -> str:
    out = [f"### Factory help — {model['project']}", "",
           "**The flow — a foundation once, then the cycle — and where this project is now**", ""]
    out += table_md(["step", "part", "now", "agent", "shell", "what it is"],
                    [[f"{f['number']} {f['step']}", PART_WORDS[f["part"]], f"**{NOW_WORDS[f['mark']]}**" if f["mark"] in NOW_WORDS else "",
                      f"`{f['skill']}`",
                      f"`{shell_form(f['shell'])}`" if f["shell"] else "— needs an agent session", commands(f["what"], False, md=True)]
                     for f in model["flow"]])
    out += ["", "**Commands**", ""]
    out += table_md(["to see", "agent", "shell", "what it shows"],
                    [[c["name"], f"`{c['skill']}`", f"`{shell_form(c['shell'])}`" if c["shell"] else "— needs an agent session",
                      c["what"]] for c in model["commands"]],
                    first_bold=True)
    out += ["", f"`{SHELL_NAME}` is `{model['runner']}`, in a terminal of its own; a session uses the agent form.",
            "", "**Marks**", ""]
    out += table_md(["session", "terminal", "means"], [[MARKS_MD[m["mark"]], f"`{MARKS_TEXT[m['mark']]}`", m["meaning"]]
                                                      for m in model["marks"]])
    out += ["", "**Files**", ""]
    out += table_md(["what", "where", "holds"], [[f["name"], f"`{f['where']}`", f["holds"]] for f in model["files"]],
                    first_bold=True)
    return "\n".join(out + ["", next_md(model)])
