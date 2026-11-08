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
GAP = 30                # between two things on the line
DOT = 11                # a gate's radius
MARK = 7                # a stop's or a wait's radius
CHAR = 13.4             # a step's name, per character, in the display face at 22 px
SMALL = 15              # the small text's size: a label, a count, a rule in the legend
SMALL_CHAR = 7.5        # the small text, per character, in the mono face at SMALL
LEAST = 12              # the size the small text never goes below where the drawing is shown — so its least width
ROW = 22                # a line of the legend
LEGEND = 204            # where the legend's rules start, clear of its longest label at SMALL

STYLE = """
.f text { font-family: 'Space Grotesk', 'Avenir Next', 'Trebuchet MS', sans-serif; fill: #1c2433; }
.f .step { font-size: 22px; font-weight: 700; }
.f text.small { font-family: 'JetBrains Mono', ui-monospace, Menlo, monospace; font-size: __SMALL__px; fill: #5b6472;
  paint-order: stroke; stroke: #ffffff; stroke-width: 5px; stroke-linejoin: round; }
.f .on-line { stroke: #a7adb8; stroke-width: 2; fill: none; }
.f [class^="tip-"] { fill: none; stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; }
.f .tip-on { stroke: #a7adb8; } .f .tip-again { stroke: #148f96; } .f .tip-back { stroke: #1c2433; }
.f .way path.hit { stroke: transparent; stroke-width: 14; fill: none; }
.f .way-again path.vis { stroke: #148f96; stroke-width: 2; stroke-dasharray: 5 4; fill: none; }
.f .way-again text.small { fill: #148f96; }
.f .way-name { font-weight: 700; }
.f .way-back path.vis { stroke: #1c2433; stroke-width: 1.6; fill: none; }
.f .gate circle { fill: #148f96; }
.f .gate path, .f .mark path { stroke: #ffffff; stroke-width: 2; fill: none; stroke-linecap: round; stroke-linejoin: round; }
.f .mark-stop circle { fill: #c96a5a; }
.f .mark-waits circle { fill: #5b6472; }
.f .done { fill: none; stroke: #1c2433; stroke-width: 2; }
@media (prefers-color-scheme: dark) {
  .f text { fill: #e8eaf0; } .f text.small { fill: #9aa3b2; stroke: #0d1117; } .f .on-line, .f .tip-on { stroke: #8a93a3; }
  .f .gate circle { fill: #3bb3b9; } .f .tip-again, .f .way-again path.vis { stroke: #3bb3b9; } .f .way-again text.small { fill: #3bb3b9; }
  .f .way-back path.vis, .f .tip-back { stroke: #e8eaf0; } .f .done { stroke: #e8eaf0; }
  .f .mark-stop circle { fill: #d9826f; } .f .mark-waits circle { fill: #9aa3b2; }
}
""".replace("__SMALL__", str(SMALL))


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
    return at, line, x + 9 + 45      # room for the end's word, centred under it


def gate(x: float, name: str, checks: typing.List[str]) -> str:
    return (f'<g class="gate" data-gate="{esc(name)}" data-rules="{esc(" ".join(checks))}"><title>{esc(name)}: '
            f'{len(checks)} checks</title><circle cx="{x:.1f}" cy="{Y}" r="{DOT}"/>'
            f'<path d="M{x - 4.5:.1f},{Y + .5} l3,3 l6,-6.5"/></g>')


def sign(x: float, y: float, way: str) -> str:
    """A stop's cross or a wait's bars in a circle."""
    inner = (f"M{x - 2.6:.1f},{y - 2.6:.1f} l5.2,5.2 M{x + 2.6:.1f},{y - 2.6:.1f} l-5.2,5.2" if way == "stop"
             else f"M{x - 1.8:.1f},{y - 3:.1f} v6 M{x + 1.8:.1f},{y - 3:.1f} v6")
    return f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{MARK}"/><path d="{inner}"/>'


def mark(x: float, y: float, way: str, edge: Model, source: str) -> str:
    return (f'<g class="way mark mark-{way}" data-source="{esc(source)}" data-target="{way}" data-way="{way}" '
            f'data-rules="{esc(ruled(edge))}"><title>{esc(source)} → {way}: {esc(said(edge))}</title>'
            f'{sign(x, y, way)}</g>')


def svg(graph: Model, kind: str, titles: typing.Optional[typing.Mapping[str, str]] = None) -> str:
    """The kind's flow; `graph` as the rulebook's json view gives it (`flow.<kind>.graph`); `titles` names a rule
    by its title where a way back is labelled — its id where it has none."""
    titles = titles or {}
    steps = graph["steps"]
    at, line, width = placed(steps)
    gated = {s["stage"]: s for s in steps}
    edges = graph["edges"]
    backs = sorted((e for e in edges if e["way"] == "back"),
                   key=lambda e: (abs(at[e["source"]].x - at[e["target"]].x), at[e["source"]].x))
    named = [list(dict.fromkeys(titles.get(r["rule"]) or r["rule"] for r in e["rules"])) for e in backs]
    depths: typing.List[float] = []          # each lane below the label of the one above it
    below: typing.Dict[str, float] = {}
    for edge, names in zip(backs, named):
        nest = ""
        depths.append(below.get(nest, 26.0))
        below[nest] = depths[-1] + 22 + 15 * (len(names) + 1)
    depth = max(below.values(), default=26.0)
    legend = []                              # a rule a line, with each way it takes (a rule may stop or wait)
    for source, label in (("every_gate", "at every gate"), ("anywhere", "anywhere in a run")):
        ways: typing.Dict[str, typing.List[str]] = {}
        for edge in (e for e in graph[source] if e["way"] in ("stop", "waits")):
            for rule in dict.fromkeys(r["rule"] for r in edge["rules"]):
                ways.setdefault(rule, []).append(edge["way"])
        legend.append((source, label, list(ways.items())))
    legend = [group for group in legend if group[2]]
    rows = sum((len(lines) + 1) // 2 for _, _, lines in legend)
    height = Y + 54 + depth + ROW * rows + 12 * len(legend) + 10
    # it shrinks with its place down to the width its small text still reads at LEAST px; narrower, it scrolls
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" class="f" viewBox="0 0 __WIDTH__ {height:.0f}" style="min-width: __LEAST__px" '
           f'role="img" aria-label="the {esc(kind)} flow: its steps, gates, rounds and ways back">',
           f"<style>{STYLE}</style>",
           '<defs>' + "".join(
               f'<marker id="a-{n}" viewBox="0 0 10 10" refX="7.2" refY="5" markerWidth="11" markerHeight="11" '
               f'markerUnits="userSpaceOnUse" orient="auto-start-reverse"><path class="tip-{n}" d="M2.2,1.4 L8.6,5 L2.2,8.6"/></marker>'
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
                out.append(f'<text class="small" x="{place.x:.1f}" y="{Y + 53}" text-anchor="middle">decides, '
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
    # the ways back, nested: the shortest closest to the line, each labelled beneath its lowest point — the way, then
    # the title of each rule that takes it, one a line
    for lane, edge in enumerate(backs):
        a, b = at[edge["source"]], at[edge["target"]]
        top, low = Y + 54, Y + 54 + depths[lane]
        bend = top + (low - top) / .75           # a cubic with both handles here bottoms out at `low`
        lean = (a.x - b.x) * .12                  # the last handle off to the source's side: the point leans into its way
        d = f"M{a.x:.1f},{top} C{a.x:.1f},{bend:.1f} {b.x + lean:.1f},{bend:.1f} {b.x:.1f},{top + 4}"
        mid = (a.x + b.x) / 2
        out.append(f'<g class="way way-back" data-source="{esc(edge["source"])}" data-target="{esc(edge["target"])}" '
                   f'data-way="back" data-rules="{esc(ruled(edge))}"><title>{esc(edge["source"])} → '
                   f'{esc(edge["target"])}: {esc(said(edge))}</title><path class="hit" d="{d}"/>'
                   f'<path class="vis" d="{d}" marker-end="url(#a-back)"/>'
                   f'<text class="small" x="{mid:.1f}" y="{low + 14:.1f}" text-anchor="middle">'
                   f'<tspan class="way-name">{esc(edge["source"])} → {esc(edge["target"])}</tspan>'
                   + "".join(f'<tspan x="{mid:.1f}" dy="15">{esc(name)}</tspan>' for name in named[lane])
                   + '</text></g>')
    # a stop and a wait, marked under the step they leave from
    for edge in (e for e in edges if e["way"] in ("stop", "waits")):
        step = at[edge["source"]]
        offset = -9 if edge["way"] == "stop" else 9
        out.append(mark(step.x + offset, Y + 30, edge["way"], edge, edge["source"]))
    # what every gate and the whole run share, said once: a rule a line, by its title, in two columns
    y, column = Y + 54 + depth + 8, max((width - LEGEND) / 2, 300.0)
    for source, label, lines in legend:
        out.append(f'<text class="small" x="24" y="{y + 4}">{label}</text>')
        for n, (rule, taken) in enumerate(lines):
            half = (len(lines) + 1) // 2      # down the first column, then the second
            x, row = LEGEND + column * (n // half), y + ROW * (n % half)
            words = titles.get(rule) or rule
            fits = int((column - 30) / SMALL_CHAR)
            shown = words if len(words) <= fits else words[:fits - 1].rstrip() + "…"
            out.append(f'<g class="way mark" data-source="{source.replace("_", "-")}" '
                       f'data-target="{taken[0]}" data-way="{taken[0]}" data-rules="{esc(rule)}">'
                       f'<title>{esc(rule)}: {esc(words)}</title>'
                       + "".join(f'<g class="mark-{way}">{sign(x + 16 * i, row, way)}</g>' for i, way in enumerate(taken))
                       + f'<text class="small" x="{x + 14 + 16 * (len(taken) - 1)}" y="{row + 4}">{esc(shown)}</text></g>')
        y += ROW * ((len(lines) + 1) // 2) + 12
    out.append("</svg>")
    return "\n".join(out).replace("__WIDTH__", f"{width:.0f}").replace("__LEAST__", f"{width * LEAST / SMALL:.0f}") + "\n"
