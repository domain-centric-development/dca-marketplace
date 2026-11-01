"""A kind's flow drawn as SVG, from the rulebook's graph alone: the steps on one line with their gates between them,
the rounds above, the ways back below, a stop and a wait marked at the step they leave from. The same drawing serves
a page (`serve`, which shows the ways back on hover and reads a rule on a click — the groups carry what they stand
for in `data-` attributes) and a document (the guide's figure, every way back drawn)."""

from __future__ import annotations

import html
import typing

Model = typing.Dict[str, typing.Any]

Y = 130                 # the line the steps stand on
TOP = 64                # the height a round rises above the line
GAP = 36                # between two things on the line
DOT = 11                # a gate's radius
MARK = 7                # a stop's or a wait's radius
CHAR = 13.4             # a step's name, per character, in the display face at 22 px
LANE = 44               # between two ways back, below the line

STYLE = """
.f text { font-family: 'Space Grotesk', 'Avenir Next', 'Trebuchet MS', sans-serif; fill: #1c2433; }
.f .step { font-size: 22px; font-weight: 700; }
.f text.small { font-family: 'JetBrains Mono', ui-monospace, Menlo, monospace; font-size: 11px; fill: #5b6472;
  paint-order: stroke; stroke: #ffffff; stroke-width: 5px; stroke-linejoin: round; }
.f .on-line { stroke: #a7adb8; stroke-width: 2; fill: none; }
.f .tip-on { fill: #a7adb8; } .f .tip-again { fill: #148f96; } .f .tip-back { fill: #1c2433; }
.f .way path.hit { stroke: transparent; stroke-width: 14; fill: none; }
.f .way-again path.vis { stroke: #148f96; stroke-width: 2; stroke-dasharray: 5 4; fill: none; }
.f .way-again text.small { fill: #148f96; }
.f .way-back path.vis { stroke: #1c2433; stroke-width: 1.6; fill: none; }
.f .gate circle { fill: #148f96; }
.f .gate path, .f .mark path { stroke: #ffffff; stroke-width: 2; fill: none; stroke-linecap: round; stroke-linejoin: round; }
.f .mark-stop circle { fill: #b2453a; }
.f .mark-waits circle { fill: #5b6472; }
.f .done { fill: none; stroke: #1c2433; stroke-width: 2; }
@media (prefers-color-scheme: dark) {
  .f text { fill: #e8eaf0; } .f text.small { fill: #9aa3b2; stroke: #0d1117; } .f .on-line { stroke: #5b6472; } .f .tip-on { fill: #5b6472; }
  .f .tip-again, .f .gate circle { fill: #3bb3b9; } .f .way-again path.vis { stroke: #3bb3b9; } .f .way-again text.small { fill: #3bb3b9; }
  .f .way-back path.vis { stroke: #e8eaf0; } .f .tip-back { fill: #e8eaf0; } .f .done { stroke: #e8eaf0; }
  .f .mark-stop circle { fill: #d4604f; } .f .mark-waits circle { fill: #9aa3b2; }
}
"""


def esc(value: typing.Any) -> str:
    return html.escape(str(value), quote=True)


def ruled(edge: Model) -> str:
    return " ".join(f"{r['rule']}:{r['state']}" for r in edge["rules"])


def said(edge: Model) -> str:
    return ", ".join(f"{r['rule']} {r['state']}" for r in edge["rules"])


class Place(typing.NamedTuple):
    x: float
    half: float


def placed(steps: typing.List[Model]) -> typing.Tuple[typing.Dict[str, Place], typing.List[typing.Tuple[str, Place]],
                                                       float]:
    """Each step's centre, each gate's, and the end of the line — from left to right, a gate before or after its
    step as the step says."""
    x, at, line = 24.0, {}, []
    for step in steps:
        if step["gate"] == "before":
            x += DOT
            line.append(("gate-before:" + step["stage"], Place(x, DOT)))
            x += DOT + GAP
        half = len(step["stage"]) * CHAR / 2
        x += half
        at[step["stage"]] = Place(x, half)
        line.append((step["stage"], at[step["stage"]]))
        x += half + GAP
        if step["gate"] == "after":
            x += DOT
            line.append(("gate-after:" + step["stage"], Place(x, DOT)))
            x += DOT + GAP
    x += 9
    line.append(("delivered", Place(x, 9)))
    return at, line, x + 9 + 70


def gate(x: float, name: str, checks: typing.List[str]) -> str:
    return (f'<g class="gate" data-gate="{esc(name)}" data-rules="{esc(" ".join(checks))}"><title>{esc(name)}: '
            f'{len(checks)} checks</title><circle cx="{x:.1f}" cy="{Y}" r="{DOT}"/>'
            f'<path d="M{x - 4.5:.1f},{Y + .5} l3,3 l6,-6.5"/></g>')


def mark(x: float, y: float, way: str, edge: Model, source: str) -> str:
    sign = (f"M{x - 2.6:.1f},{y - 2.6:.1f} l5.2,5.2 M{x + 2.6:.1f},{y - 2.6:.1f} l-5.2,5.2" if way == "stop"
            else f"M{x - 1.8:.1f},{y - 3:.1f} v6 M{x + 1.8:.1f},{y - 3:.1f} v6")
    return (f'<g class="way mark mark-{way}" data-source="{esc(source)}" data-target="{way}" data-way="{way}" '
            f'data-rules="{esc(ruled(edge))}"><title>{esc(source)} → {way}: {esc(said(edge))}</title>'
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{MARK}"/><path d="{sign}"/></g>')


def svg(graph: Model, kind: str) -> str:
    """The kind's flow; `graph` as the rulebook's json view gives it (`flow.<kind>.graph`)."""
    steps = graph["steps"]
    at, line, width = placed(steps)
    gated = {s["stage"]: s for s in steps}
    edges = graph["edges"]
    backs = sorted((e for e in edges if e["way"] == "back"),
                   key=lambda e: (abs(at[e["source"]].x - at[e["target"]].x), at[e["source"]].x))
    height = Y + 66 + LANE * len(backs) + 24 * 2 + 20
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" class="f" viewBox="0 0 __WIDTH__ {height:.0f}" '
           f'role="img" aria-label="the {esc(kind)} flow: its steps, gates, rounds and ways back">',
           f"<style>{STYLE}</style>",
           '<defs>' + "".join(
               f'<marker id="a-{n}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
               f'orient="auto-start-reverse"><path class="tip-{n}" d="M0,0 L10,5 L0,10 z"/></marker>'
               for n in ("on", "again", "back")) + "</defs>"]
    # the line: a plain arrow from one thing to the next, an edge on (judge → document) carrying its rules
    on = {(e["source"], e["target"]): e for e in edges if e["way"] == "on"}
    for (name, a), (following, b) in zip(line, line[1:]):
        step_from = name.split(":")[-1]
        step_to = following.split(":")[-1]
        edge = on.get((step_from, step_to)) if not name.startswith("gate-before") else None
        title = f"<title>{esc(step_from)} → {esc(step_to)}: {esc(said(edge))}</title>" if edge and edge["rules"] else ""
        out.append(f'<path class="on-line" d="M{a.x + a.half + 6:.1f},{Y} L{b.x - b.half - 6:.1f},{Y}" '
                   f'marker-end="url(#a-on)">{title}</path>')
    for name, place in line:
        if name.startswith("gate-"):
            step = gated[name.split(":")[1]]
            out.append(gate(place.x, name, step["gate_before"] if name.startswith("gate-before") else step["gate_after"]))
        elif name == "delivered":
            out.append(f'<circle class="done" cx="{place.x:.1f}" cy="{Y}" r="9"><title>delivered</title></circle>'
                       f'<text class="small" x="{place.x:.1f}" y="{Y + 30}" text-anchor="middle">delivered</text>')
        else:
            out.append(f'<text class="step" data-stage="{esc(name)}" x="{place.x:.1f}" y="{Y + 8}" '
                       f'text-anchor="middle">{esc(name)}</text>')
            if gated[name]["gate"] == "none":
                out.append(f'<text class="small" x="{place.x:.1f}" y="{Y + 56}" text-anchor="middle">decides, '
                           f'no gate</text>')
    # the rounds: from the gate after a step (or the step) up and back into it
    for edge in (e for e in edges if e["way"] == "again"):
        step = at[edge["source"]]
        after = next((p for n, p in line if n == "gate-after:" + edge["source"]), None)
        start = after.x if after else step.x + step.half
        top = Y - TOP
        checks = len(gated[edge["source"]]["gate_after"])
        label = f"{checks} checks" if after else "again"
        d = f"M{start:.1f},{Y - 13} C{start:.1f},{top} {step.x:.1f},{top} {step.x:.1f},{Y - 24}"
        mid = (start + step.x) / 2
        out.append(f'<g class="way way-again" data-source="{esc(edge["source"])}" data-target="{esc(edge["target"])}" '
                   f'data-way="again" data-rules="{esc(ruled(edge))}"><title>{esc(edge["source"])} again: '
                   f'{esc(said(edge))}</title><path class="hit" d="{d}"/><path class="vis" d="{d}" '
                   f'marker-end="url(#a-again)"/><text class="small" x="{mid:.1f}" y="{top + 2}" '
                   f'text-anchor="middle">{esc(label)}</text></g>')
    # the ways back, nested: the shortest closest to the line
    for lane, edge in enumerate(backs, start=1):
        a, b = at[edge["source"]], at[edge["target"]]
        top, bottom = Y + 66, Y + 66 + LANE * lane
        d = f"M{a.x:.1f},{top} C{a.x:.1f},{bottom} {b.x:.1f},{bottom} {b.x:.1f},{top + 4}"
        mid, low = (a.x + b.x) / 2, top + (bottom - top) * .75
        rules = " · ".join(dict.fromkeys(r["rule"] for r in edge["rules"]))
        out.append(f'<g class="way way-back" data-source="{esc(edge["source"])}" data-target="{esc(edge["target"])}" '
                   f'data-way="back" data-rules="{esc(ruled(edge))}"><title>{esc(edge["source"])} → '
                   f'{esc(edge["target"])}: {esc(said(edge))}</title><path class="hit" d="{d}"/>'
                   f'<path class="vis" d="{d}" marker-end="url(#a-back)"/>'
                   f'<text class="small" x="{mid:.1f}" y="{low + 4:.1f}" text-anchor="middle">'
                   f'{esc(edge["source"])} → {esc(edge["target"])}  {esc(rules)}</text></g>')
    # a stop and a wait, marked under the step they leave from
    for edge in (e for e in edges if e["way"] in ("stop", "waits")):
        step = at[edge["source"]]
        offset = -9 if edge["way"] == "stop" else 9
        out.append(mark(step.x + offset, Y + 30, edge["way"], edge, edge["source"]))
    # what every gate and the whole run share, said once
    y, footer = height - 24 * 2 + 4, 0.0
    for source, label in (("every_gate", "at every gate"), ("anywhere", "anywhere in a run")):
        shared = [e for e in graph[source] if e["way"] in ("stop", "waits")]
        if not shared:
            continue
        x = 24.0
        out.append(f'<text class="small" x="{x}" y="{y + 4}">{label}</text>')
        x += 140
        for edge in shared:
            out.append(mark(x, y, edge["way"], edge, source.replace("_", "-")))
            words = ", ".join(dict.fromkeys(r["rule"] for r in edge["rules"]))
            out.append(f'<text class="small" x="{x + 14}" y="{y + 4}">{esc(words)}</text>')
            x += 28 + len(words) * 6.7
        footer = max(footer, x + 16)
        y += 24
    out.append("</svg>")
    return "\n".join(out).replace("__WIDTH__", f"{max(width, footer):.0f}") + "\n"
