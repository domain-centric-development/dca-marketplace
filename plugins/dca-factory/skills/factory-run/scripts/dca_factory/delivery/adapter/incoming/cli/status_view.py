"""The status as a person reads it: short, or the whole backlog by epic, as text or Markdown."""

from __future__ import annotations

import typing

from ....application.status.texts import signals_line, stamp_text, took_text
from ....application.status.show_epic import epic_mark
from .terminal import (
    MARKS_MD, MARKS_TEXT, bold, column_widths, commands, dim, heading, how_lines, how_md, next_md, next_text, paint,
    section, table_md, table_text, tokens_text,
)



def epic_summary(item: typing.Mapping[str, typing.Any]) -> str:
    parts = [f"{item['delivered']} of {item['total']} delivered",
             tokens_text(item["tokens"], item["measured"]) + (" tokens" if item["measured"] else "")]
    if item["seconds"]:
        parts.append(took_text(item["seconds"]))
    return " · ".join(parts)


def backlog_columns(model: typing.Mapping[str, typing.Any]) -> typing.Tuple[typing.List[str], typing.Set[int]]:
    headers = ["story", "state", "stage", "passes", "started (UTC)", "delivered (UTC)", "worked"]
    return headers, {3, 6}


def backlog_cells(
        row: typing.Mapping[str, typing.Any], model: typing.Mapping[str, typing.Any], marks: typing.Mapping[str, str]
) -> typing.List[str]:
    if not row.get("journal", True) and row["mark"] == "done":
        # delivered before the pipeline kept a journal: said once, not in five empty cells
        return [f"{marks[row['mark']]} {row['story']}", row["state"], "", "", "no journal",
                stamp_text(row["delivered"]), ""]
    return [f"{marks[row['mark']]} {row['story']}", row["state"], row["stage"], row["passes"] or "—",
            stamp_text(row["started"]), stamp_text(row["delivered"]), took_text(row["seconds"])]


def token_rows(
        model: typing.Mapping[str, typing.Any]
) -> typing.Tuple[typing.List[str], typing.List[typing.List[typing.Any]], typing.List[str], typing.Set[int]]:
    """The tokens per story, grouped by epic with a subtotal each and the total over every story — the
    four classes as the tool reports them."""
    classes = ("input", "output", "cache_write", "cache_read")
    def cells(label: str, item: typing.Mapping[str, typing.Any], runs: typing.Any) -> typing.List[typing.Any]:
        if not item["measured"]:
            return [label, runs or "—", "—", "—", "—", "—", "not measured"] + (["—"] if model["priced"] else [])
        row = [label, runs] + [f"{item.get(k, 0):,}" for k in classes] + [f"{item['tokens']:,}"]
        return row + ([f"{item.get('cost', 0):.2f}" if item.get("priced") else "—"] if model["priced"] else [])
    rows, kinds = [], []
    for epic in (e for e in model["epics"] if e["rows"]):
        subtotal = {k: sum(r.get(k, 0) for r in epic["rows"]) for k in classes + ("tokens", "measured", "runs", "cost", "priced")}
        rows.append(cells(epic["epic"] or "(no epic)", subtotal, subtotal["runs"]))
        kinds.append("epic")
        for r in epic["rows"]:
            rows.append(cells("  ↳ " + r["story"], r, r["runs"]))
            kinds.append("story")
    grand = {k: sum(r.get(k, 0) for r in model["rows"]) for k in classes + ("tokens", "measured", "runs", "cost", "priced")}
    rows.append(cells("total", grand, grand["runs"]))
    kinds.append("total")
    headers = ["epic / story", "runs", "input", "output", "cache write", "cache read", "total"] \
        + (["cost $"] if model["priced"] else [])
    return headers, rows, kinds, set(range(1, len(headers)))


#: How many of the stories that can run the short view names; the rest it counts.
QUEUE_SHOWN = 5


#: Where the short view points for more — the same words in the terminal and in a session.
MORE_FORMS = (("every story", "status --all"), ("one story", "status --story <id>"), ("one epic", "status --epic <id>"))


def short_model(model: typing.Mapping[str, typing.Any]) -> typing.Dict[str, typing.Any]:
    """What the short view shows, decided once for the terminal and the session: the running stages with their round,
    what waits for a person (the drafts in one line), the next stories in the schedule's order — the first few, the
    rest counted — and the totals."""
    queue = model.get("queue") or dict(ready=[], blocked=0, drafts=0)
    by_id = {r["story"]: r for r in model["rows"]}
    shown_ids = queue["ready"][:QUEUE_SHOWN]
    rest = []
    if len(queue["ready"]) > len(shown_ids):
        rest.append(f"{len(queue['ready']) - len(shown_ids)} more ready")
    if queue["blocked"]:
        rest.append(f"{queue['blocked']} blocked")
    totals = [f"{model['delivered']} of {model['total']} delivered", f"{len(queue['ready'])} ready"] if model["total"] \
        else ["no story yet"]
    totals += [f"{queue['blocked']} blocked"] if queue["blocked"] else []
    totals += [f"{queue['drafts']} draft" + ("s" if queue["drafts"] != 1 else "")] if queue["drafts"] else []
    if model["measured"]:
        totals.append(f"{tokens_short(model['tokens'])} tokens")
    if model["seconds"]:
        totals.append(f"{took_text(model['seconds'])} worked")
    if model.get("findings"):
        totals.append(f"{len(model['findings'])} open finding" + ("s" if len(model["findings"]) != 1 else ""))
    return dict(running=model["running"], waiting=[w for w in model["waiting"] if not w.get("draft")],
                drafts=[w["story"] for w in model["waiting"] if w.get("draft")],
                queue=[by_id[i] for i in shown_ids if i in by_id], rest=" · ".join(rest), totals=" · ".join(totals))


def running_words(entry: typing.Mapping[str, typing.Any]) -> str:
    """A running stage as the short view says it: the stage (and the part of a shared one), its round after the
    first, since when."""
    stage = f"{entry['stage']} · {entry['part']}" if entry.get("part") else entry["stage"]
    if entry.get("round", 1) > 1:
        stage += f" · round {entry['round']}"
    line = f"{stage}   since {stamp_text(entry['since'])} UTC"
    if entry.get("interrupted"):
        line += " · never ended — possibly interrupted"
    if entry.get("ago"):
        line += f" · {entry['ago']}"
    return line


def tokens_short(count: int) -> str:
    """A token count at a glance: `481.7 M`, `12.3 k`."""
    return f"{count / 1e6:.1f} M" if count >= 1e6 else f"{count / 1e3:.1f} k" if count >= 1e3 else str(count)


def render_short_text(model: typing.Mapping[str, typing.Any], colour: bool = False) -> str:
    short = short_model(model)
    section = lambda title, colour: ["", "  " + bold(title, colour)]   # the short view: no blank line under a heading
    out = [""] + heading(f"Factory — {model['project']}", colour, "═")
    out += section("Running", colour)
    for r in short["running"]:
        mark = "stopped" if r.get("interrupted") else "running"
        out.append("    " + paint(f"{MARKS_TEXT[mark]} {r['story']}   {running_words(r)}", mark, colour))
        if r.get("activity"):
            out.append(f"        activity: {r['activity']}")
    if not short["running"]:
        out.append("    Nothing is running.")
    out += section("Waiting for you", colour)
    for n, w in enumerate(short["waiting"]):
        head = f"{MARKS_TEXT[w['mark']]} {w['story']}   {w['what']}" + (f"   {w['record']}" if w.get("record") else "")
        out += ([""] if n else []) + ["    " + paint(head, w["mark"], colour)]
        out += how_lines(w["action"], colour, "        ")
    if short["drafts"]:
        ids = " ".join(short["drafts"])
        out += ([""] if short["waiting"] else []) + [
            "    " + paint(f"{MARKS_TEXT['question']} {len(short['drafts'])} draft(s) wait for your release: {ids}",
                           "question", colour),
            f"        {dim('agent'.ljust(10), colour)}   {commands('/factory-backlog release ' + ids, colour)}"]
    if not short["waiting"] and not short["drafts"]:
        out.append("    Nothing waits for you.")
    out += section("Next in line", colour)
    if short["queue"]:
        cells = [[f"{MARKS_TEXT[r['mark']]} {r['story']}", r["state"], r["title"]] for r in short["queue"]]
        out += table_text(["story", "state", "title"], cells, indent="    ",
                          marks=[r["mark"] for r in short["queue"]], colour=colour)
    else:
        out.append("    Nothing is ready to run.")
    if short["rest"]:
        out.append(f"    … {short['rest']}")
    out += ["", "  " + short["totals"]]
    out += ["", "─" * 72] + next_text(model, colour)
    out.append(f"  {bold('More', colour)}   " + " · ".join(f"{what}: {form}" for what, form in MORE_FORMS))
    if model["extra"]:
        out += [""] + ["  " + line for line in model["extra"]]
    if model["hint"]:
        out += ["", f"  layout: {model['hint']}"]
    return "\n".join(out + [""])


def render_short_md(model: typing.Mapping[str, typing.Any]) -> str:
    short = short_model(model)
    out = [f"### Factory — {model['project']}", "", "**Running**", ""]
    if short["running"]:
        out += [f"- {MARKS_MD['stopped' if r.get('interrupted') else 'running']} **{r['story']}** {running_words(r)}"
                + (f" — {r['activity']}" if r.get("activity") else "") for r in short["running"]]
    else:
        out.append("Nothing is running.")
    out += ["", "**Waiting for you**", ""]
    if short["waiting"]:
        out += table_md(["", "story", "what", "how"],
                        [[MARKS_MD[w["mark"]], w["story"], w["what"] + (f" — `{w['record']}`" if w.get("record") else ""),
                          how_md(w["action"])] for w in short["waiting"]])
    if short["drafts"]:
        ids = " ".join(short["drafts"])
        out += ([""] if short["waiting"] else []) + [
            f"{MARKS_MD['question']} {len(short['drafts'])} draft(s) wait for your release: {ids} → `/factory-backlog release {ids}`"]
    if not short["waiting"] and not short["drafts"]:
        out.append("Nothing waits for you.")
    out += ["", "**Next in line**", ""]
    if short["queue"]:
        out += table_md(["", "story", "state", "title"],
                        [[MARKS_MD[r["mark"]], r["story"], r["state"], r["title"]] for r in short["queue"]])
    else:
        out.append("Nothing is ready to run.")
    if short["rest"]:
        out += ["", f"… {short['rest']}"]
    out += ["", short["totals"], "", next_md(model), "",
            "More — " + " · ".join(f"{what}: `{form}`" for what, form in MORE_FORMS)]
    if model["extra"]:
        out += [""] + [f"- {line}" for line in model["extra"]]
    return "\n".join(out)


def render_status_text(model: typing.Mapping[str, typing.Any], colour: bool = False) -> str:
    only_backlog = model.get("part") == "backlog"
    out = [""] + heading(f"{'Backlog' if only_backlog else 'Factory'} — {model['project']}", colour, "═")
    if not only_backlog:
        out += waiting_running_text(model, colour)
    return "\n".join(out + backlog_text(model, colour, heading_line=not only_backlog) + [""])


def waiting_running_text(model: typing.Mapping[str, typing.Any], colour: bool) -> typing.List[str]:
    out = section("Waiting for you", colour)
    if model["waiting"]:
        width = max(len(w["story"]) for w in model["waiting"])
        what = max(len(w["what"]) for w in model["waiting"])
        for n, w in enumerate(model["waiting"]):
            head = f"{MARKS_TEXT[w['mark']]} {w['story'].ljust(width)}   {w['what']}"
            out += ([""] if n else []) + ["    " + paint(head, w["mark"], colour)]
            out += how_lines(w["action"], colour, "        ")
    else:
        out.append("    Nothing waits for you.")
    out += section("Running", colour)
    if model["running"]:
        for r in model["running"]:
            mark = "stopped" if r.get("interrupted") else "running"
            stage = f"{r['stage']} · {r['part']}" if r.get("part") else r["stage"]
            line = f"{MARKS_TEXT[mark]} {r['story']}   {stage}   since {stamp_text(r['since'])} UTC"
            if r.get("interrupted"):
                line += " · never ended — possibly interrupted"
            if r.get("ago"):
                line += f" · {r['ago']}"
            out.append("    " + paint(line, mark, colour))
            if r.get("activity"):
                out.append(f"        activity: {r['activity']}")
    else:
        out.append("    Nothing is running.")
    return out


def backlog_text(model: typing.Mapping[str, typing.Any], colour: bool, heading_line: bool = True) -> typing.List[str]:
    whole = epic_mark({"rows": model["rows"]})
    summary = paint(f"{MARKS_TEXT[whole]} {epic_summary(model)}", whole, colour) if model["rows"] else ""
    out = section("Backlog" + (f" — {epic_summary(model)}" if model["rows"] else ""), colour) if heading_line \
        else ["", "  " + summary, ""]
    if not model["rows"]:
        out.append("    No story yet.")
    headers, right = backlog_columns(model)
    widths = column_widths(headers, [backlog_cells(r, model, MARKS_TEXT) for r in model["rows"]])
    for n, epic in enumerate(model["epics"]):
        mark = epic_mark(epic)
        out += ([""] if n else []) + ["    " + paint(bold(f"{MARKS_TEXT[mark]} {epic['epic'] or '(no epic)'}", colour), mark, colour)
                                      + (f"   {dim(epic_summary(epic), colour)}" if epic["rows"] else "")]
        if not epic["rows"]:
            out.append(f"      no story yet — {commands('/factory-backlog stories ' + epic['epic'], colour)}")
            continue
        cells = [backlog_cells(r, model, MARKS_TEXT) for r in epic["rows"]]
        out += table_text(headers, cells, right, indent="      ", marks=[r["mark"] for r in epic["rows"]],
                          colour=colour, widths=widths)
    for hint in model.get("journeys", []):
        out += ["", f"    {dim('journey', colour)}   {hint['epic']}: {hint['text']} — {commands(hint['action']['skill'], colour)}"]
    for row in model["rows"]:
        if row.get("flaky"):
            out += ["", f"    {dim('flaky', colour)}   {row['story']}: {', '.join(row['flaky'])} — red in a whole suite, "
                        f"green on its own run; no round counted"]
    if model["rows"]:
        headers, rows, kinds, right = token_rows(model)
        caption = "Tokens" + ("" if model["priced"] or not model["measured"] else " — no price in a session log")
        out += section(caption, colour)
        lines = table_text(headers, rows, right, total=True, colour=colour)
        # epic rows and the total in bold: the sums stand out
        for n, kind in enumerate(kinds):
            index = 2 + n + (1 if kind == "total" else 0)
            if kind == "epic" and colour:
                lines[index] = bold(lines[index], True)
        out += lines
    figures = [(e["epic"] or "(no epic)", signals_line(e.get("signals") or {})) for e in model["epics"] if e["rows"]]
    if model["rows"] and signals_line(model.get("signals") or {}):
        out += section("Signals — " + signals_line(model["signals"]), colour)
        width = max(len(name) for name, _l in figures)
        out += [f"    {name.ljust(width)}   {line}" for name, line in figures if line]
    out += ["", "─" * 72] + next_text(model, colour)
    if model["extra"]:
        out += [""] + ["  " + line for line in model["extra"]]
    if model["hint"]:
        out += ["", f"  layout: {model['hint']}"]
    return out


def render_status_md(model: typing.Mapping[str, typing.Any]) -> str:
    if model.get("part") == "backlog":
        return render_backlog_md(model)
    out = [f"### Factory — {model['project']}", "", "**Waiting for you**", ""]
    if model["waiting"]:
        out += table_md(["", "story", "what", "how"],
                        [[MARKS_MD[w["mark"]], w["story"], w["what"], how_md(w["action"])] for w in model["waiting"]])
    else:
        out.append("Nothing waits for you.")
    out += ["", "**Running**", ""]
    if model["running"]:
        out += table_md(["", "story", "stage", "since"] + (["activity"] if any(r.get("activity") for r in model["running"]) else []),
                        [[MARKS_MD["stopped" if r.get("interrupted") else "running"], r["story"], r["stage"],
                          stamp_text(r["since"]) + " UTC" + (" · never ended — possibly interrupted" if r.get("interrupted") else "")
                          + (f" · {r['ago']}" if r.get("ago") else "")]
                         + ([r.get("activity", "")] if any(x.get("activity") for x in model["running"]) else [])
                         for r in model["running"]])
    else:
        out.append("Nothing is running.")
    return "\n".join(out + backlog_md_lines(model))


def render_backlog_md(model: typing.Mapping[str, typing.Any]) -> str:
    return "\n".join([f"### Backlog — {model['project']}"] + backlog_md_lines(model))


def backlog_md_lines(model: typing.Mapping[str, typing.Any]) -> typing.List[str]:
    out = ["", "**Backlog**" + (f" — {epic_summary(model)}" if model["rows"] else "")]
    if not model["rows"]:
        out += ["", "No story yet."]
    headers, right = backlog_columns(model)
    for epic in model["epics"]:
        out += ["", f"{MARKS_MD[epic_mark(epic)]} *{epic['epic'] or '(no epic)'}* — {epic_summary(epic)}", ""]
        if not epic["rows"]:
            out.append(f"No story yet — `/factory-backlog stories {epic['epic']}`.")
            continue
        out += table_md(headers, [backlog_cells(r, model, MARKS_MD) for r in epic["rows"]], right)
    for hint in model.get("journeys", []):
        out += ["", f"*journey* — {hint['epic']}: {hint['text']} → `{hint['action']['skill']}`"]
    for row in model["rows"]:
        if row.get("flaky"):
            out += ["", f"*flaky* — {row['story']}: {', '.join(f'`{t}`' for t in row['flaky'])} — red in a whole suite, "
                        f"green on its own run; no round counted"]
    if model["rows"]:
        headers, rows, kinds, right = token_rows(model)
        rows = [[f"**{c}**" if kind in ("epic", "total") and str(c) else c for c in row] if kind != "story"
                else [row[0].strip()] + row[1:] for row, kind in zip(rows, kinds)]  # "↳ story" in Markdown
        caption = "Tokens" + ("" if model["priced"] or not model["measured"] else " — no price in a session log")
        out += ["", f"**{caption}**", ""] + table_md(headers, rows, right)
    out += ["", next_md(model)]
    if model["extra"]:
        out += [""] + [f"- {line}" for line in model["extra"]]
    return out
