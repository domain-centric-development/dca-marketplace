"""How a view shows on a terminal and in Markdown: marks, colour, tables, headings, the next step."""

from __future__ import annotations

import os
import re
import shutil
import sys
import textwrap
import typing
from datetime import datetime, timezone
from ....domain.model.decision_record import WAITING_WORDS


MARKS_TEXT = {"look": "!", "question": "?", "stopped": "✗", "running": "▶", "done": "✓", "none": "·", "next": "→"}


MARKS_MD = {"look": "👀", "question": "❓", "stopped": "⛔", "running": "⏳", "done": "✅", "none": "➖", "next": "👉"}


COLOURS = {"look": "33", "question": "33", "stopped": "31", "running": "34", "done": "32", "none": "2", "next": "36"}


def tokens_text(tokens: int, measured: bool = True) -> str:
    return f"{tokens:,}" if measured and tokens else "not measured"


def paint(text: str, mark: str, colour: bool) -> str:
    return f"\x1b[{COLOURS[mark]}m{text}\x1b[0m" if colour and mark in COLOURS else text


def bold(text: str, colour: bool) -> str:
    return f"\x1b[1m{text}\x1b[0m" if colour else text


def dim(text: str, colour: bool) -> str:
    return f"\x1b[2m{text}\x1b[0m" if colour else text


COMMAND = re.compile(r"(/(?:factory|dca)-[a-z-]+(?: [A-Za-z0-9][\w.-]*)?)")


def commands(text: str, colour: bool, md: bool = False) -> str:
    """The skills a line names, set apart: cyan on a terminal, `code` in Markdown."""
    if md:
        return COMMAND.sub(r"`\1`", text)
    return COMMAND.sub(lambda m: f"\x1b[36m{m.group(1)}\x1b[0m", text) if colour else text


def how_lines(act: typing.Mapping[str, typing.Any], colour: bool, indent: str) -> typing.List[str]:
    """The action as labelled lines: look at it, in an agent session, in a shell."""
    lines: typing.List[str] = []
    if act.get("text"):
        lines.append(f"{indent}{act['text']}")
    rows: typing.List[typing.Tuple[str, str]] = []
    if act.get("look"):
        rows.append(("look at it", act["look"]))
    if act.get("skill"):
        rows.append(("agent", commands(act["skill"], colour)))
        rows.append(("shell", act["shell"] if act.get("shell") else dim("— needs an agent session", colour)))
    for label, value in rows:
        lines.append(f"{indent}{dim(label.ljust(10), colour)}   {value}")
    return lines


def how_md(act: typing.Mapping[str, typing.Any]) -> str:
    parts: typing.List[str] = []
    if act.get("text"):
        parts.append(act["text"])
    if act.get("look"):
        parts.append(f"look at it: `{act['look']}`")
    if act.get("skill"):
        parts.append(f"`{act['skill']}`" + (f" (in a shell: {act['shell']})" if act.get("shell") else ""))
    return " · ".join(parts)


def next_text(model: typing.Mapping[str, typing.Any], colour: bool) -> typing.List[str]:
    nxt = model["next"]
    return [f"  {bold('Next', colour)}   {nxt['text']}"] + how_lines(nxt["action"], colour, "         ")


def next_md(model: typing.Mapping[str, typing.Any]) -> str:
    """The session's form: the skill to use; the shell's command beside it where there is one."""
    nxt, act = model["next"], model["next"]["action"]
    line = f"**Next:** {nxt['text']}"
    if act.get("skill"):
        line += f" → `{act['skill']}`" + (f" (in a shell: `{act['shell']}`)" if act.get("shell") else "")
    return line


def table_text(headers: typing.Sequence[typing.Any], rows: typing.Sequence[typing.Sequence[typing.Any]],
               right: typing.Container[int] = (), indent: str = "    ",
               marks: typing.Optional[typing.Sequence[typing.Optional[str]]] = None, colour: bool = False,
               widths: typing.Optional[typing.Sequence[int]] = None, total: bool = False,
               first_bold: bool = False, painted: int = 2) -> typing.List[str]:
    """Aligned columns with a rule under the header; `marks[i]` colours row i's first `painted` cells.
    `widths` makes several tables line up — the backlog's, one per epic; `total` sets the last row
    apart with a rule of its own."""
    widths = list(widths or column_widths(headers, rows))
    # The last column wraps inside its own column rather than being cut: nothing a reader needs is lost.
    # The width is the terminal's where there is one, else a fixed 120 — the same text in a pipe.
    room = view_width() - len(indent) - sum(widths[:-1]) - 3 * (len(widths) - 1)
    wrap_last = len(widths) > 1 and (len(widths) - 1) not in right and widths[-1] > max(room, 30)
    if wrap_last:
        widths[-1] = max(room, 30)
    fmt = lambda cells: "   ".join((str(c).rjust(widths[i]) if i in right else str(c).ljust(widths[i]))
                                   for i, c in enumerate(cells)).rstrip()
    if wrap_last:
        wrapped: typing.List[typing.List[typing.Any]] = []
        for row in rows:
            pieces = textwrap.wrap(str(row[-1]), widths[-1]) or [""]
            wrapped.append(list(row[:-1]) + [pieces[0]])
            wrapped += [[""] * (len(row) - 1) + [piece] for piece in pieces[1:]]
        if marks is not None:
            expanded: typing.List[typing.Optional[str]] = []
            for mark, row in zip(marks, rows):
                expanded += [mark] + [None] * (len(textwrap.wrap(str(row[-1]), widths[-1]) or [""]) - 1)
            marks = expanded
        rows = wrapped
    lines = [indent + (bold(fmt(headers), True) if colour else fmt(headers)),
             indent + "   ".join("─" * w for w in widths)]
    for n, row in enumerate(rows):
        is_total = total and n == len(rows) - 1
        if is_total:
            lines.append(indent + "   ".join("─" * w for w in widths))
        line = bold(fmt(row), colour) if is_total else fmt(row)
        if first_bold and colour and not is_total:
            first = str(row[0]).ljust(widths[0])
            line = bold(first, True) + line[len(first):]
        row_mark = marks[n] if marks else None
        if row_mark and colour:
            head = "   ".join(str(c).ljust(widths[i]) for i, c in enumerate(row[:painted]))
            line = paint(head, row_mark, True) + line[len(head):]
        lines.append(indent + line)
    return lines


def view_width() -> int:
    return shutil.get_terminal_size((120, 24)).columns if sys.stdout.isatty() else 120


def column_widths(headers: typing.Sequence[typing.Any],
                  rows: typing.Sequence[typing.Sequence[typing.Any]]) -> typing.List[int]:
    return [max([len(str(h))] + [len(str(r[i])) for r in rows]) for i, h in enumerate(headers)]


def table_md(headers: typing.Sequence[typing.Any], rows: typing.Sequence[typing.Sequence[typing.Any]],
             right: typing.Container[int] = (), first_bold: bool = False) -> typing.List[str]:
    """A Markdown table with its headers in bold; `first_bold` sets the first column apart too."""
    strong = lambda c: f"**{c}**" if str(c) and not str(c).startswith("**") else str(c)
    rows = [[strong(r[0])] + list(r[1:]) for r in rows] if first_bold else rows
    lines = ["| " + " | ".join(strong(h) for h in headers) + " |",
             "|" + "|".join("--:" if i in right else "---" for i in range(len(headers))) + "|"]
    lines += ["| " + " | ".join(str(c).replace("|", "\\|") for c in row) + " |" for row in rows]
    return lines


def heading(text: str, colour: bool, underline: str = "─") -> typing.List[str]:
    """A title the eye finds: bold where there is colour, underlined always."""
    return [bold(text, colour), underline * len(text)]


def section(text: str, colour: bool) -> typing.List[str]:
    return ["", "  " + bold(text, colour), ""]


def decision_mark(decision: typing.Mapping[str, typing.Any]) -> str:
    """Open or a draft needs you; answered waits for the stage that applies it; applied is done — and
    an answered acceptance is done too: it was applied by the gate or by the re-plan."""
    if decision["state"] in WAITING_WORDS:
        return "question"
    if decision["state"] == "applied" or decision["kind"] == "acceptance":
        return "done"
    return "running"


def sections_text(sections: typing.List[typing.Any], at: typing.Optional[int], block: typing.List[str],
                  colour: bool) -> typing.List[str]:
    """A story's or an epic's sections as the terminal shows them, in the order given — the block of its own (the
    criteria, the stories) where its section stood, else after them; why a story is not built painted as a wait."""
    out: typing.List[str] = []
    for index, one in enumerate(sections + [None]):
        if index == (len(sections) if at is None else at):
            out += block
        if one is None:
            break
        heading = one["heading"] or "Text"
        out += (section(paint(heading, "look", colour) if one["kind"] else heading, colour)
                + paragraph_lines(one["text"], "    "))
    return out


def sections_md(sections: typing.List[typing.Any], at: typing.Optional[int],
                block: typing.List[str]) -> typing.List[str]:
    """The same for a session: each section under its heading in bold, its Markdown as written."""
    out: typing.List[str] = []
    for index, one in enumerate(sections + [None]):
        if index == (len(sections) if at is None else at):
            out += block
        if one is None:
            break
        heading = f"**{one['heading'] or 'Text'}**"
        out += ["", f"⚠ {heading}" if one["kind"] else heading, "", one["text"]]
    return out


def paragraph_lines(text: str, indent: str) -> typing.List[str]:
    """Prose wrapped to the view's width, its paragraphs kept apart; a heading, a list item or a table row stands on
    its own line as written, a line wrapped under a list item joined to it."""
    out: typing.List[str] = []
    for paragraph in text.split("\n\n"):
        lines: typing.List[str] = []
        for line in paragraph.splitlines():
            if lines and line[:1].isspace() and line.strip() and not line.lstrip().startswith(("-", "*", "|", ">", "#")):
                lines[-1] += " " + line.strip()
            else:
                lines.append(line)
        if any(l.lstrip().startswith(("#", "-", "*", "|", ">")) for l in lines):
            wrapped = [w for l in lines for w in (textwrap.wrap(l.strip(), view_width(), initial_indent=indent,
                                                                subsequent_indent=indent + "  ") or [""])]
        else:
            wrapped = textwrap.wrap(" ".join(paragraph.split()), view_width(), initial_indent=indent,
                                    subsequent_indent=indent)
        out += ([""] if out else []) + wrapped
    return out


def json_ready(value: typing.Any) -> typing.Any:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if isinstance(value, set):
        return sorted(value)
    if isinstance(value, dict):
        return {k: json_ready(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_ready(v) for v in value]
    return value


def use_colour(choice: typing.Optional[str]) -> bool:
    if choice == "always":
        return True
    if choice == "never" or os.environ.get("NO_COLOR"):
        return False
    return sys.stdout.isatty()
