"""One story as a person reads it: its words, criteria, stages, passes and tokens, as text or Markdown."""

from __future__ import annotations

import textwrap
import typing

from ....domain.model.usage import USAGE_FIELDS
from ....application.status.stage_ranks import stage_rank
from ....application.status.texts import stamp_text, took_text
from .terminal import (
    MARKS_MD, MARKS_TEXT, bold, decision_mark, heading, how_lines, how_md, next_md, next_text, paint, paragraph_lines,
    section, sections_md, sections_text, table_md, table_text, tokens_text, view_width,
)


#: What a story view says beside a shared process whose parts an older reading froze and whose stream is gone (0.90.1).
PARTS_INCOMPLETE = "parts incomplete — the stream was cleared before 0.90.1 could read it again"


def scenario_lines(model: typing.Mapping[str, typing.Any], indent: str = "    ") -> typing.List[str]:
    """A story's criteria as a person reads them: the title, then the steps, the rule they serve above them."""
    out, rule, width = [], None, view_width()
    wrap = lambda text, first, rest: textwrap.wrap(text, width, initial_indent=first, subsequent_indent=rest) or [first]
    for scenario in model["scenarios"]:
        if scenario["rule"] and scenario["rule"] != rule:
            out += [""] + wrap(f"Rule: {scenario['rule']}", indent, indent + "      ")
        rule = scenario["rule"]
        out += wrap(scenario["title"] + (" (happy path)" if scenario["happy"] else "") + f"  [{scenario['key']}]",
                    indent + "  ", indent + "    ")
        for step in scenario["steps"]:
            out += wrap(f"{step['word']} {step['text']}", indent + "    ", indent + "      ")
        if scenario["text"]:
            out += wrap(scenario["text"], indent + "    ", indent + "      ")
    return out


def token_cells(entry: typing.Mapping[str, typing.Any], measured: typing.Any) -> typing.List[str]:
    """The four token classes as Claude Code reports them (and ccusage shows them), and their total."""
    if not measured:
        return ["—", "—", "—", "—", "not measured"]
    return [f"{entry.get(k, 0):,}" for k in ("input", "output", "cache_write", "cache_read")] + [f"{entry['tokens']:,}"]


def stage_cells(
        model: typing.Mapping[str, typing.Any]
) -> typing.Tuple[typing.List[str], typing.List[typing.List[typing.Any]], typing.Set[int]]:
    """One row per stage and a total. A model column only where the stages ran on different models or a
    requested one did not reach a stage — otherwise the one model is named in the caption."""
    tools_used = {t for e in model["stages"].values() for t in e.get("tools", ())}
    per_stage = len(model["models"]) > 1 or bool(model["not_applied"]) or len(tools_used) > 1 \
        or any(e.get("efforts") for e in model["stages"].values())
    any_why = any(e.get("why") for e in model["stages"].values())
    rows = []
    for stage in sorted(model["stages"], key=stage_rank):
        e = model["stages"][stage]
        cells = [stage, e["runs"], took_text(e["seconds"])] + token_cells(e, e["measured"])
        if e.get("running"):
            cells[1] = f"{e['runs']} (running)"
            cells[3:3 + 5] = token_cells(e, True)
        elif e["measured"] < e["runs"]:
            cells[1] = f"{e['runs']} ({e['runs'] - e['measured']} not measured)"
        if model["priced"]:
            cells.append(f"{e['cost']:.2f}" if e["priced"] else "—")
        if per_stage:
            ran = ", ".join(sorted(e["models"])) or "—"
            if e["not_applied"]:
                ran += f" (requested {', '.join(sorted(e['requested']))}: not applied)"
            if len(tools_used) > 1 and e.get("tools"):
                ran += f" · {', '.join(sorted(e['tools']))}"
            if e.get("efforts"):
                ran += f" · effort {', '.join(sorted(e['efforts']))}"
            cells.append(ran)
        if any_why:
            cells.append(e.get("why", ""))
        rows.append(cells)
        for part in e.get("parts") or []:
            sub = [f"  · {part['stage']}", "", took_text(part["seconds"])] + token_cells(part, True)
            sub[4] = "≈" + sub[4]                     # the output column: split by what each part wrote
            if model["priced"]:
                sub.append(f"≈{part['cost']:.2f}" if part["cost"] is not None else "—")
            if per_stage:
                sub.append("")
            if any_why:
                sub.append(f"{part['denied']} denied" if part.get("denied") else "")
            rows.append(sub)
        if e.get("parts_incomplete"):
            rows.append([f"  · {PARTS_INCOMPLETE}"] + [""] * (len(cells) - 1))
    total = {k: sum(e.get(k, 0) for e in model["stages"].values())
             for k in ("runs", "seconds", "tokens", "measured", "cost") + USAGE_FIELDS}
    streaming = any(e.get("running") for e in model["stages"].values())
    cells = ["total", total["runs"], took_text(total["seconds"])] + token_cells(total, total["measured"] or streaming)
    if model["priced"]:
        cells.append(f"{total['cost']:.2f}")
    if per_stage:
        cells.append("")
    if any_why:
        cells.append("")
    rows.append(cells)
    headers = ["stage", "runs", "worked", "input", "output", "cache write", "cache read", "total"] \
        + (["cost $"] if model["priced"] else []) + (["model"] if per_stage else []) + (["notes"] if any_why else [])
    right = {1, 2, 3, 4, 5, 6, 7} | ({8} if model["priced"] else set())
    return headers, rows, right


def story_header(model: typing.Mapping[str, typing.Any]) -> typing.Tuple[str, typing.List[typing.Tuple[str, str]]]:
    """(title line, [(label, value)]): what the story is, where it stands, how often it ran."""
    row = model["row"]
    title = f"{model['story']} — {model['title']}" if model["title"] else model["story"]
    state = row["state"]
    if row["delivered"]:
        state = f"delivered {stamp_text(row['delivered'])} UTC"
    if model["accepted_by"]:
        state += " · accepted by a human"
    passes = model["passes"]
    corrections = sum(1 for p in passes[1:] if p["label"].startswith("correction"))
    again = len(passes) - 1 - corrections
    why = []
    if corrections:
        why.append("one correction" if corrections == 1 else f"{corrections} corrections")
    if again:
        why.append("planned again once" if again == 1 else f"planned again {again} times")
    pass_text = ("no journal — delivered before the pipeline measured"
                 if not model["row"].get("journal", True) and model["row"]["mark"] == "done"
                 else "not run yet") if not passes else "1 pass — the first delivery" if len(passes) == 1 else \
        f"{len(passes)} passes — the first delivery, then " + " and ".join(why)
    facts = [("Epic", model["epic"] or "—")]
    if model["context"]:
        facts.append(("Context", model["context"]))
    facts += [("Criteria", str(model["criteria"])), ("State", state), ("History", pass_text)]
    if row.get("flaky"):
        facts.append(("Flaky", ", ".join(row["flaky"]) + " — red in a whole suite, green on its own run; no round"))
    signals = model.get("signals") or {}
    if signals.get("asked") or signals.get("assumptions_open") or signals.get("assumptions_answered") \
            or signals.get("plan_open"):
        facts.append(("Questions", f"{signals['asked']} asked, {signals['answered']} answered · assumptions "
                                   f"{signals['assumptions_open']} open, {signals['assumptions_answered']} answered"
                                   + (f" · {signals['plan_open']} left open by the plan" if signals["plan_open"] else "")))
    if signals.get("rules"):
        order = ("red", "killed", "survived", "no-break", "unchecked")
        said = {"red": "red before the build", "killed": "killed by a break"}
        facts.append(("Rules", f"{sum(signals['rules'].values())} named — " + ", ".join(
            f"{signals['rules'][v]} {said.get(v, v)}" for v in order if signals["rules"].get(v))))
    if signals.get("findings"):
        facts.append(("Findings", ", ".join(f"{n} {p}" for p, n in sorted(signals["findings"].items()))
                      + (" · domain " + ", ".join(f"{n} {c[7:]}" for c, n in sorted(signals["domain"].items()))
                         if signals.get("domain") else "")))
    if signals.get("corrections"):
        facts.append(("Corrections", ", ".join(f"{n} {code}" for code, n in sorted(signals["corrections"].items()))))
    return title, facts


def stage_caption(model: typing.Mapping[str, typing.Any]) -> str:
    caption = "Stages"
    parts = []
    if len(model["models"]) == 1 and not model["not_applied"]:
        parts.append(model["models"][0])
    if model["not_applied"]:
        parts.append(f"requested {', '.join(model['not_applied'])}: not applied")
    if not model["priced"] and any(e["measured"] for e in model["stages"].values()):
        parts.append("no price in a session log")
    return caption + (" — " + " · ".join(parts) if parts else "")


def render_story_text(model: typing.Mapping[str, typing.Any], colour: bool = False) -> str:
    row = model["row"]
    title, facts = story_header(model)
    width = max(len(label) for label, _v in facts)
    out = [""] + heading(title, colour, "═") + [""]
    if model.get("situation"):
        out += [f"  {paint(model['situation'], row['mark'], colour)}", ""]
    for label, value in facts:
        if label == "State":
            value = paint(f"{MARKS_TEXT[row['mark']]} {value}", row["mark"], colour)
        out.append(f"  {bold(label.ljust(width), colour)}   {value}")
    for w in model["waiting"]:
        out += ["", "  " + paint(f"{MARKS_TEXT[w['mark']]} {w['what']}", w["mark"], colour)]
        out += how_lines(w["action"], colour, "      ")
    criteria = (section("Criteria", colour) + scenario_lines(model)[1 if model["scenarios"][0]["rule"] else 0:]
                if model.get("scenarios") else [])
    if "sections" in model:
        out += sections_text(model["sections"], model["criteria_at"], criteria, colour)
    else:
        out += (section("Story", colour) + paragraph_lines(model["description"], "    ")
                if model.get("description") else []) + criteria
    if model["passes"]:
        out += section("Passes", colour)
        out += table_text(["pass", "started (UTC)", "ended (UTC)", "worked", "waited before", "tokens"],
                          [[f"{i + 1}  {p['label']}", stamp_text(p["start"]), stamp_text(p["end"]),
                            took_text(p["seconds"]), took_text(p["waited"]), tokens_text(p["tokens"], p["measured"])]
                           for i, p in enumerate(model["passes"])], {3, 4, 5}, colour=colour, first_bold=True)
    if model["stages"]:
        headers, rows, right = stage_cells(model)
        out += section(stage_caption(model), colour) + table_text(headers, rows, right, total=True, colour=colour,
                                                                    first_bold=True)
    denials = denial_rows(model)
    if denials:
        out += section("Denied — calls the tool refused without asking, each a turn spent", colour)
        out += table_text(["stage", "tool", "call"], denials, colour=colour, first_bold=True)
    if model["decisions"]:
        out += section("Decisions", colour)
        out += table_text(["record", "state", "answer or question"],
                          [[d["id"], d["state"], d["text"]] for d in model["decisions"]], colour=colour,
                          marks=[decision_mark(d) for d in model["decisions"]], first_bold=True)
    out += ["", "─" * 72] + next_text(model, colour) + [""]
    return "\n".join(out)


def denial_rows(model: typing.Mapping[str, typing.Any]) -> typing.List[typing.List[str]]:
    """[stage, tool, call] for every call a stage was denied — a shared process's named with its stage inside."""
    return [[f"{stage} · {d['stage']}" if d["stage"] and d["stage"] != stage else stage, d["tool"], d["command"]]
            for stage in sorted(model["stages"], key=stage_rank) for d in model["stages"][stage].get("denials") or []]


def render_story_md(model: typing.Mapping[str, typing.Any]) -> str:
    title, facts = story_header(model)
    out = [f"**{title}**", ""] + ([f"*{model['situation']}*", ""] if model.get("situation") else [])
    out += [f"- **{label}:** " + (f"{MARKS_MD[model['row']['mark']]} " if label == "State" else "") + value
            for label, value in facts]
    for w in model["waiting"]:
        out += ["", f"{MARKS_MD[w['mark']]} **{w['what']}** — {how_md(w['action'])}"]
    criteria = []
    if model.get("scenarios"):
        criteria += ["", "**Criteria**"]
        rule = None
        for scenario in model["scenarios"]:
            if scenario["rule"] and scenario["rule"] != rule:
                criteria += ["", f"*Rule: {scenario['rule']}*"]
            rule = scenario["rule"]
            criteria += ["", f"- **{scenario['title']}**" + (" (happy path)" if scenario["happy"] else "") + f" `{scenario['key']}`"]
            criteria += [f"  - {step['word']} {step['text']}" for step in scenario["steps"]]
            if scenario["text"]:
                criteria.append(f"  - {scenario['text']}")
    out += sections_md(model["sections"], model["criteria_at"], criteria)
    if model["passes"]:
        out += ["", "**Passes**", ""]
        out += table_md(["pass", "started (UTC)", "ended (UTC)", "worked", "waited before", "tokens"],
                        [[f"{i + 1} {p['label']}", stamp_text(p["start"]), stamp_text(p["end"]),
                          took_text(p["seconds"]), took_text(p["waited"]), tokens_text(p["tokens"], p["measured"])]
                         for i, p in enumerate(model["passes"])], {3, 4, 5}, first_bold=True)
    if model["stages"]:
        headers, rows, right = stage_cells(model)
        rows = rows[:-1] + [[f"**{c}**" if str(c) else c for c in rows[-1]]]
        out += ["", f"**{stage_caption(model)}**", ""] + table_md(headers, rows, right, first_bold=True)
    denials = denial_rows(model)
    if denials:
        out += ["", "**Denied** — calls the tool refused without asking, each a turn spent", ""]
        out += table_md(["stage", "tool", "call"], [[a, b, f"`{c}`"] for a, b, c in denials], first_bold=True)
    if model["decisions"]:
        out += ["", "**Decisions**", ""]
        out += table_md(["", "record", "state", "answer or question"],
                        [[MARKS_MD[decision_mark(d)], f"**{d['id']}**", d["state"], d["text"]] for d in model["decisions"]])
    out += ["", next_md(model)]
    return "\n".join(out)
