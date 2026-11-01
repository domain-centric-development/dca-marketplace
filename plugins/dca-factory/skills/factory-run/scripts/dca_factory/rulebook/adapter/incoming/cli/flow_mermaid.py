"""A kind's flow as a Mermaid flowchart, from the rulebook's graph alone — for a document that draws its diagrams in
Mermaid: the steps left to right with their gates, the rounds from a gate back into its step, the ways back with the
rules that take them. What stops a run or waits for a person is said beside it, not drawn."""

from __future__ import annotations

import typing

Model = typing.Dict[str, typing.Any]


def node(name: str) -> str:
    return name.replace("-", "_")


def rules(edge: Model, titles: typing.Mapping[str, str]) -> str:
    return "<br>".join(dict.fromkeys(titles.get(r["rule"]) or r["rule"] for r in edge["rules"]))


def mermaid(graph: Model, kind: str, titles: typing.Optional[typing.Mapping[str, str]] = None) -> str:
    titles = titles or {}
    steps = graph["steps"]
    lines = ["flowchart LR"]
    chain: typing.List[str] = []
    for step in steps:
        name = step["stage"]
        if step["gate"] == "before":
            lines.append(f'  {node("gate_before_" + name)}(("✓")):::gate')
            chain.append(node("gate_before_" + name))
        lines.append(f'  {node(name)}["{name}"]:::step')
        chain.append(node(name))
        if step["gate"] == "after":
            lines.append(f'  {node("gate_after_" + name)}(("✓")):::gate')
            chain.append(node("gate_after_" + name))
    lines.append('  delivered(("delivered")):::done')
    chain.append("delivered")
    on = {(e["source"], e["target"]): e for e in graph["edges"] if e["way"] == "on" and e["rules"]}
    for here, there in zip(chain, chain[1:]):
        edge = on.get((here.replace("gate_after_", ""), there))
        lines.append(f'  {here} -- "{rules(edge, titles)}" --> {there}' if edge else f"  {here} --> {there}")
    gated = {s["stage"]: s for s in steps}
    for edge in graph["edges"]:
        source, target = edge["source"], edge["target"]
        if edge["way"] == "again":
            start = node("gate_after_" + source) if gated[source]["gate"] == "after" else node(source)
            label = f'again · {len(gated[source]["gate_after"])} checks' if gated[source]["gate"] == "after" else "again"
            lines.append(f'  {start} -. "{label}" .-> {node(target)}')
        elif edge["way"] == "back":
            lines.append(f'  {node(source)} -. "{rules(edge, titles)}" .-> {node(target)}')
    lines += ["  classDef step fill:none,stroke:none,font-weight:bold",
              "  classDef gate fill:#148f96,stroke:#148f96,color:#ffffff",
              "  classDef done fill:none,stroke:#1c2433"]
    return "\n".join(lines) + "\n"
