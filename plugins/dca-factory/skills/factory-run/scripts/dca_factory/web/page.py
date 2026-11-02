"""The page `factory.sh serve` shows (WP-91): one HTML file with its script inline, no dependency and no build step.

It draws the factory's own JSON views — status, decisions, discovery, requests, one story, a stage's output — in the
cycle's tabs, in the project's look (the mark, its colours and faces, a light and a dark theme). It decides nothing:
the order, the marks, the words, the figures and every action — its label, whether it is the one to press, the request
it writes and what the person still gives — come from the factory. A press writes that request, or starts and stops
the factory. Kept as a module so it ships, installs and is hashed with the package.
"""

import base64
import hashlib
import re

#: The mark in its text cut (under 44 px), its strokes in the colour of the text around it.
MARK = ('<svg viewBox="17.4 12 85.2 96" fill="none" aria-hidden="true"><polygon points="60,20 94.6,40 94.6,80 60,100 '
        '25.4,80 25.4,40" stroke="currentColor" stroke-width="7" stroke-linejoin="round"/>'
        + "".join(f'<circle cx="{x}" cy="{y}" r="8" fill="currentColor"/>'
                  for x, y in ((60, 20), (94.6, 40), (94.6, 80), (60, 100), (25.4, 80), (25.4, 40)))
        + '<circle cx="60" cy="60" r="12" fill="var(--teal)"/></svg>')

#: The tab's icon: the same drawing in ink, as the website's favicon.
FAVICON = MARK.replace('aria-hidden="true"', 'xmlns="http://www.w3.org/2000/svg" width="32" height="36"') \
    .replace("currentColor", "#1c2433").replace('stroke-width="7"', 'stroke-width="7.7"').replace("var(--teal)", "#148f96")

PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>Factory</title>
<link rel="icon" type="image/svg+xml" href="/favicon.svg">
<style>
@font-face { font-family: "Space Grotesk"; font-weight: 300 700; font-display: swap; src: url(/fonts/space-grotesk-latin.woff2) format("woff2"); }
@font-face { font-family: "Newsreader"; font-weight: 200 800; font-display: swap; src: url(/fonts/newsreader-latin.woff2) format("woff2"); }
@font-face { font-family: "JetBrains Mono"; font-weight: 100 800; font-display: swap; src: url(/fonts/jetbrains-mono-latin.woff2) format("woff2"); }
:root {
  --teal: #148f96; --deep: #171d29; --mist: #e8eaf0;
  --bg: #f7f6f3; --panel: #ffffff; --ink: #1c2433; --muted: #5b6472; --line: #dedbd3; --soft: #eef4f4; --group: #e4efef; --group-line: #cfe0e0; --code: #f0eee9;
  --accent: #0d6b70; --accent-hover: #0b5b60; --on-accent: #ffffff; --fill: #0d6b70; --fill-hover: #0b5b60;
  --done: #0d6b70; --wait: #93600f; --stop: #c96a5a; --run: #148f96; --shared: #4b47b8;
  --shadow: 0 6px 24px rgba(28, 36, 51, .10);
  --display: "Space Grotesk", "Avenir Next", "Trebuchet MS", sans-serif;
  --body: "Newsreader", Georgia, "Times New Roman", serif;
  --mono: "JetBrains Mono", "SF Mono", Menlo, Consolas, monospace;
  color-scheme: light;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg: #12171f; --panel: #1a2130; --ink: #e8eaf0; --muted: #9aa3b2; --line: #2b3445; --soft: #172a30; --group: #233d45; --group-line: #33545d; --code: #222a39;
    --accent: #3cbcc3; --accent-hover: #5fcdd3; --on-accent: #ffffff; --fill: #0d6b70; --fill-hover: #0b5b60;
    --done: #3cbcc3; --wait: #e2ab55; --stop: #d9826f; --run: #3cbcc3; --shared: #b3b0f2; --shadow: 0 6px 24px rgba(0, 0, 0, .35);
    color-scheme: dark;
  }
}
:root[data-theme="dark"] {
  --bg: #12171f; --panel: #1a2130; --ink: #e8eaf0; --muted: #9aa3b2; --line: #2b3445; --soft: #172a30; --group: #233d45; --group-line: #33545d; --code: #222a39;
  --accent: #3cbcc3; --accent-hover: #5fcdd3; --on-accent: #ffffff; --fill: #0d6b70; --fill-hover: #0b5b60;
  --done: #3cbcc3; --wait: #e2ab55; --stop: #d9826f; --run: #3cbcc3; --shared: #b3b0f2; --shadow: 0 6px 24px rgba(0, 0, 0, .35);
  color-scheme: dark;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body { background: var(--bg); color: var(--ink); font: 17px/1.55 var(--body); min-height: 100vh; }
a, .link { color: var(--accent); cursor: pointer; text-decoration: none; }
.link:hover { text-decoration: underline; }
.link:not(.title), .way-link { text-decoration: underline; text-decoration-thickness: 1px; text-underline-offset: 3px;
  text-decoration-color: color-mix(in srgb, var(--accent) 45%, transparent); }
button.link { background: none; border: 0; padding: 0; text-align: left; } button.link:not(.title) { font: inherit; }
button:focus-visible, a:focus-visible, textarea:focus-visible, select:focus-visible, input:focus-visible {
  outline: 3px solid var(--teal); outline-offset: 2px; border-radius: 4px; }
.wrap { max-width: 1100px; margin: 0 auto; padding: 0 24px; }
code, .mono { font-family: var(--mono); font-size: .78em; }
code { background: var(--code); padding: 1px 5px; border-radius: 4px; overflow-wrap: anywhere; }

/* the bar: the website's top bar, in either theme */
.topbar { position: sticky; top: 0; z-index: 20; background: var(--deep); color: var(--mist);
  border-bottom: 1px solid rgba(232, 234, 240, .08); }
.nav { display: flex; align-items: center; gap: 18px; padding: 12px 0; flex-wrap: wrap; }
.brand { display: flex; align-items: center; gap: 1ex; font: 700 19px var(--display); letter-spacing: -.3px; color: var(--mist); }
.brand svg { width: 2.13ex; height: 2.4ex; overflow: visible; transform: translateY(.1ex); }
.brand .tld { color: var(--teal); }
a.brand { text-decoration: none; border-radius: 6px; padding: 2px 6px; margin: -2px -6px; }
a.brand:hover > span:first-of-type { color: var(--teal); } a.brand:focus-visible { outline: 2px solid var(--teal); outline-offset: 2px; }
.brand .project { font: 400 13px var(--mono); color: rgba(232, 234, 240, .62); letter-spacing: .3px; margin-left: 4px; }
.tabs { display: flex; gap: 4px; margin-left: auto; overflow-x: auto; scrollbar-width: none; }
.tabs button { font: 400 13px var(--mono); letter-spacing: .4px; color: rgba(232, 234, 240, .72); background: none; border: 0;
  padding: 8px 10px; cursor: pointer; border-bottom: 2px solid transparent; white-space: nowrap; }
.tabs button:hover { color: var(--teal); }
.tabs button[aria-selected="true"] { color: var(--mist); border-bottom-color: var(--teal); }
.tabs button:focus-visible { outline: 2px solid var(--teal); outline-offset: -2px; }
/* the parts side by side, a hairline between them; the cycle's views joined by arrows */
.tabs { align-items: center; } .tgroup { display: flex; align-items: center; }
.tsep { flex: none; width: 1px; height: 16px; margin: 0 8px; background: rgba(232, 234, 240, .2); }
.tabs .arrow { color: rgba(232, 234, 240, .35); font: 400 12px var(--mono); }
/* the keys show while the bar is worked by keyboard, never for a mouse */
/* now: the cycle as four columns, the actions at their foot on one line */
.board { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); margin-top: 26px; align-items: stretch; }
.colw { display: flex; align-items: stretch; } .colw + .colw::before { content: "→"; align-self: center; padding: 0 6px; color: var(--muted); font: 400 18px var(--mono); }
.col { flex: 1; min-width: 0; display: flex; flex-direction: column; background: var(--panel); border: 1px solid var(--line); border-radius: 12px; padding: 16px; }
.col.hot { border-color: #c9922e; box-shadow: inset 0 3px 0 #c9922e; }
.col h3 { font: 700 17px var(--display); display: flex; justify-content: space-between; align-items: baseline; gap: 8px; }
.col h3 .link { font: inherit; color: inherit; text-decoration: none; } .col h3 .link:hover { color: var(--accent); }
.col .one .title { font: inherit; color: var(--text); text-decoration: none; } .col .one .title:hover { color: var(--accent); } .col h3 .c { font: 700 26px var(--display); } .col .of { font: 500 14px var(--mono); color: var(--muted); }
.col .sub2 { font: 400 12px/16px var(--mono); color: var(--muted); height: 16px; margin-top: 2px; }
.col .prog { display: flex; align-items: center; gap: 8px; } .col .prog .thin { flex: 1; height: 4px; border-radius: 2px; background: var(--soft); overflow: hidden; }
.col .prog .thin i { display: block; height: 100%; background: var(--done); }
.col .one { margin-top: 12px; font-size: 15px; } .col .one + .one { margin-top: 8px; } .col .one .id { display: block; font: 400 12px var(--mono); color: var(--muted); }
.col .acts { margin-top: auto; padding-top: 14px; flex-wrap: nowrap; align-items: center; } .col .acts .to { margin-left: auto; }
.btn.primary.nogo::after { content: none; }
.inflow { display: flex; gap: 14px; align-items: center; margin-top: 22px; }
.inflow .lab { font: 500 11px var(--mono); text-transform: uppercase; letter-spacing: .08em; color: var(--accent); white-space: nowrap; }
.list { list-style: none; margin-top: 12px; } .list li { display: flex; gap: 10px; align-items: baseline; padding: 8px 0; border-top: 1px solid var(--line); }
.list li:first-child { border-top: 0; } .list .what { flex: 1; min-width: 0; } .list .id { font: 400 12.5px var(--mono); color: var(--muted); display: block; }
.list .r { font: 400 13px var(--mono); color: var(--muted); white-space: nowrap; text-align: right; }
button.link.to { display: inline-block; margin-top: 12px; font: 500 13px var(--mono); color: var(--accent); text-decoration: none; }
.col button.link.to { margin-top: 0; } .quietline button.link { text-decoration: none; }
.quietline { margin-top: 14px; font: 400 13px var(--mono); color: var(--muted); } .quietline .link { font: inherit; color: var(--accent); }
/* the wish's trail: each wish in its state, what became of it */
.trail { list-style: none; margin-top: 14px; border-top: 1px solid var(--line); }
.trail li { display: grid; grid-template-columns: 1.4em minmax(0, 1fr) auto; gap: 4px 10px; align-items: baseline; padding: 10px 0; border-bottom: 1px solid var(--line); }
.trail li:last-child { border-bottom: 0; } .trail .g { color: var(--accent); } .trail .w { min-width: 0; } .trail q { font-style: italic; }
.trail .s { display: block; font: 400 12.5px var(--mono); color: var(--muted); margin-top: 2px; } .trail .s.ok { color: var(--done); }
.trail .s.ask { color: #b07a1e; } .trail .s.bad { color: var(--stop); } .trail .a { display: flex; gap: 6px; flex-wrap: wrap; justify-content: flex-end; }
.spin { display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: #c9922e; margin-right: 6px; animation: pulse 1.2s infinite; }
@keyframes pulse { 50% { opacity: .3; } }
@media (prefers-reduced-motion: reduce) { .spin { animation: none; } }
@media (max-width: 860px) {
  .board { grid-template-columns: 1fr; } .colw { flex-direction: column; }
  .colw + .colw::before { content: "↓"; padding: 4px 0; }
}
.tabs .key { display: none; margin-right: 6px; color: var(--teal); font-size: 11px; }
.tabs:has(:focus-visible) .key { display: inline; }
.tabs .n { display: inline-block; min-width: 18px; margin-left: 6px; padding: 0 5px; border-radius: 9px; background: var(--fill);
  color: #fff; font-size: 11px; text-align: center; }
.status { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; font: 400 13px var(--mono); color: rgba(232, 234, 240, .8); }
.dot { width: 9px; height: 9px; border-radius: 50%; background: #8a93a3; display: inline-block; margin-right: 6px; }
.dot.up { background: var(--teal); box-shadow: 0 0 0 3px rgba(20, 143, 150, .25); }
.dot.stopping { background: #c9922e; } .dot.down { background: #8a93a3; }
.bar-btn { font: 500 13px var(--display); color: var(--mist); background: none; border: 1px solid rgba(232, 234, 240, .35);
  border-radius: 6px; padding: 5px 12px; cursor: pointer; }
.bar-btn:hover { border-color: var(--teal); color: var(--teal); }
.bar-btn.primary { background: var(--fill); border-color: var(--fill); color: var(--on-accent); }
.by { font: 400 13px var(--mono); color: var(--mist); background: rgba(232, 234, 240, .06); border: 1px solid rgba(232, 234, 240, .2);
  border-radius: 6px; padding: 4px 8px; width: 170px; }
.theme { display: inline-flex; border: 1px solid rgba(232, 234, 240, .25); border-radius: 6px; overflow: hidden; }
.theme button { font: 400 12px var(--mono); color: rgba(232, 234, 240, .7); background: none; border: 0; padding: 4px 8px; cursor: pointer; }
.theme button[aria-pressed="true"] { background: rgba(232, 234, 240, .14); color: var(--mist); }

/* a tab: the eyebrow and heading of a website section, then its cards */
main.wrap { padding-top: 40px; padding-bottom: 72px; }
.eyebrow { font: 400 12.5px var(--mono); letter-spacing: 2.5px; text-transform: uppercase; color: var(--accent); margin-bottom: 10px; }
h1 { font: 700 clamp(28px, 4vw, 38px)/1.1 var(--display); letter-spacing: -1px; }
.lede { margin-top: 10px; color: var(--muted); max-width: 44em; font-size: 18px; }
.next { margin-top: 26px; display: flex; align-items: center; gap: 14px; flex-wrap: wrap; padding: 14px 18px;
  border: 1px solid var(--line); border-left: 4px solid var(--teal); border-radius: 10px; background: var(--panel); }
.next .text { flex: 1 1 280px; font: 500 16px var(--display); }
.next .arrow { color: var(--accent); margin-right: 6px; }
.next.ended { border-left-color: var(--stop); } .next.ended .arrow { color: var(--stop); }
.card { margin-top: 22px; background: var(--panel); border: 1px solid var(--line); border-radius: 12px; padding: 20px 22px; }
.card > h2 { font: 700 20px/1.25 var(--display); letter-spacing: -.3px; display: flex; gap: 10px; align-items: baseline; flex-wrap: wrap; }
.card > h2 .sub { font: 400 12.5px var(--mono); color: var(--muted); letter-spacing: .2px; }
.card > .about { color: var(--muted); margin-top: 6px; font-size: 16px; max-width: 48em; }
h3 { font: 600 15px var(--display); margin: 18px 0 6px; }
.drawer h2 { font: 600 16px var(--display); margin: 20px 0 6px; }
.drawer > .acts { margin: 16px 0 22px; }
.drawer > .ask { margin: 8px 0 24px; padding-bottom: 22px; border-bottom: 1px solid var(--line); }
.sr { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; border: 0; }
.prose { font-size: 16px; }
.prose p, .prose ul, .prose ol { margin: 0 0 8px; }
.prose table.md { width: auto; margin: 4px 0 10px; font-size: 15px; } .prose table.md td, .prose table.md th { padding: 5px 12px 5px 0; }
.prose pre.md { font: 12.5px/1.5 var(--mono); background: var(--code); border-radius: 6px; padding: 10px 12px; overflow-x: auto; margin: 4px 0 10px; }
.prose h4 { font: 600 14px var(--display); margin: 10px 0 4px; } .prose ul, .prose ol { padding-left: 1.3em; } .prose li { margin: 2px 0; }
.more { margin: 10px 0 6px; } .more summary { cursor: pointer; font: 500 14px var(--display); color: var(--accent); }
.more[open] summary { margin-bottom: 4px; }
.aside { margin-top: 18px; padding: 4px 14px 6px; border-left: 4px solid var(--wait); border-radius: 6px; background: var(--panel); }
.empty { color: var(--muted); font-style: italic; margin-top: 8px; }
.rec { color: var(--wait); font-size: 15px; margin-top: 4px; }

table { width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 16px; }
th { text-align: left; font: 500 11.5px var(--mono); letter-spacing: 1.2px; text-transform: uppercase; color: var(--muted);
  border-bottom: 1px solid var(--line); padding: 6px 8px; }
td { border-bottom: 1px solid var(--line); padding: 10px 8px; vertical-align: top; }
tr:last-child td { border-bottom: 0; }
.num { text-align: right; font-family: var(--mono); font-size: 13px; white-space: nowrap; font-variant-numeric: tabular-nums; }
.id { font: 400 12.5px var(--mono); color: var(--muted); margin-top: 2px; overflow-wrap: anywhere; }
.title { font: 500 16.5px var(--display); }
.mark { font: 700 15px var(--display); display: inline-block; width: 1.3em; text-align: center; }
.m-done { color: var(--done); } .m-look, .m-question { color: var(--wait); } .m-stopped { color: var(--stop); }
.m-running, .m-next { color: var(--run); } .m-none { color: var(--muted); }
.state { font: 400 12px var(--mono); padding: 2px 8px; border-radius: 999px; background: var(--code); white-space: nowrap; }
.st-queued { color: var(--accent); } .st-running { color: var(--run); } .st-waiting { color: var(--wait); } .st-failed { color: var(--stop); }

/* a control is pressed, a display is read: a control is a raised rectangle in the display face, a display flat, in the mono
   face, never with an edge — teal alone tells neither (the brand's controls and displays, branding/README.md) */
.btn { font: 600 14px var(--display); padding: 7px 14px; border-radius: 7px; border: 1px solid var(--line); background: var(--panel);
  color: var(--ink); cursor: pointer; white-space: nowrap; box-shadow: 0 1px 0 var(--line), 0 1px 3px rgba(28, 36, 51, .06); }
.btn:active:not(:disabled) { transform: translateY(1px); box-shadow: none; }
.btn:hover { border-color: var(--teal); color: var(--accent); }
.btn.primary { background: var(--fill); border-color: var(--fill); color: var(--on-accent);
  box-shadow: 0 1px 0 var(--fill-hover), 0 2px 6px color-mix(in srgb, var(--teal) 30%, transparent); }
.btn.primary::after { content: "→"; font-weight: 400; margin-left: 6px; }
.btn.primary:hover { background: var(--fill-hover); border-color: var(--fill-hover); color: var(--on-accent); }
.btn.danger:hover { border-color: var(--stop); color: var(--stop); }
.btn:disabled { opacity: .5; cursor: default; }
.btn.claude::before { content: "✦"; color: var(--accent); margin-right: 6px; font-weight: 400; } .btn.primary.claude::before { color: var(--on-accent); }
.seg { display: inline-flex; border: 1px solid var(--line); border-radius: 7px; overflow: hidden; background: var(--panel); }
.seg button { font: 500 13px var(--display); color: var(--ink); background: none; border: 0; padding: 5px 11px; cursor: pointer; white-space: nowrap; }
.seg button + button { border-left: 1px solid var(--line); } .seg button:hover { color: var(--accent); }
.seg button[aria-pressed="true"] { background: var(--ink); color: var(--bg); }
.seg .n { font: 400 11px var(--mono); margin-left: 4px; opacity: .7; }
.acts { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; align-items: center; }
td .acts { margin-top: 0; justify-content: flex-end; }
.ask { display: flex; gap: 10px; align-items: flex-start; flex-wrap: wrap; margin-top: 12px; }
.ask textarea { flex: 1 1 320px; min-height: 72px; resize: vertical; font: 17px/1.5 var(--body); color: var(--ink); background: var(--bg);
  border: 1px solid var(--line); border-radius: 8px; padding: 10px 12px; }
.ask select { font: 400 13px var(--mono); color: var(--ink); background: var(--bg); border: 1px solid var(--line); border-radius: 8px; padding: 8px; }
.option { display: flex; gap: 12px; align-items: baseline; padding: 8px 0; border-bottom: 1px solid var(--line); }
.option:last-child { border-bottom: 0; }
.option .btn { min-width: 2.6em; }
.nowrap { white-space: nowrap; }
.hint { font: 400 12.5px var(--mono); color: var(--muted); }
.kv { display: grid; grid-template-columns: max-content 1fr; gap: 4px 16px; margin-top: 12px; font-size: 16px; }
.kv dt { font: 400 12.5px var(--mono); color: var(--muted); padding-top: 3px; }
pre.out { font: 12.5px/1.5 var(--mono); background: #0f141d; color: #c9ced8; border-radius: 8px; padding: 12px; max-height: 460px; overflow: auto;
  white-space: pre-wrap; word-break: break-word; margin-top: 12px; }
pre.out:empty { display: none; }
.step b { font: 600 14px var(--display); color: var(--accent); margin-right: 6px; }

/* the flow, drawn by the factory: a way back shown on a hover, a step, a gate or an edge picked by a click */
.flowsvg { overflow-x: auto; margin-top: 12px; }
.flowsvg svg { display: block; width: 100%; min-width: 880px; height: auto; }
.flowsvg .f text { fill: var(--ink); } .flowsvg .f text.small { fill: var(--muted); stroke: var(--panel); }
.flowsvg .f .on-line { stroke: color-mix(in srgb, var(--muted) 70%, transparent); } .flowsvg .f .tip-on { fill: color-mix(in srgb, var(--muted) 70%, transparent); }
.flowsvg .f .gate circle, .flowsvg .f .tip-again { fill: var(--teal); } .flowsvg .f .way-again path.vis { stroke: var(--teal); }
.flowsvg .f .way-again text.small { fill: var(--teal); } .flowsvg .f .way-back path.vis { stroke: var(--ink); } .flowsvg .f .tip-back { fill: var(--ink); }
.flowsvg .f .mark-stop circle { fill: var(--stop); } .flowsvg .f .mark-waits circle { fill: var(--muted); } .flowsvg .f .done { stroke: var(--ink); }
.flowsvg .way, .flowsvg .gate { cursor: pointer; }
.flowsvg .way-back { opacity: 0; pointer-events: none; transition: opacity .15s; }
.flowsvg .way-back.show, .flowsvg .way-back.sel { opacity: 1; pointer-events: auto; }
/* what is picked stands out, the rest steps back: a band behind the picked way, a ring round the picked gate */
.flowsvg.has-pick .way:not(.sel):not(.way-back), .flowsvg.has-pick .gate:not(.sel), .flowsvg.has-pick [data-stage]:not(.sel) { opacity: .35; }
.flowsvg .way.sel path.vis { stroke-dasharray: none; stroke-width: 2.4; }
.flowsvg .way-again.sel path.hit { stroke: color-mix(in srgb, var(--teal) 22%, transparent); }
.flowsvg .way-back.sel path.hit { stroke: color-mix(in srgb, var(--ink) 14%, transparent); }
.flowsvg .way.sel text.small { font-weight: 700; }
.flowsvg .gate.sel circle { stroke: color-mix(in srgb, var(--teal) 30%, transparent); stroke-width: 10px; }
.flowsvg .mark.sel circle { stroke: color-mix(in srgb, var(--stop) 30%, transparent); stroke-width: 8px; }
.flowsvg [data-stage].sel { paint-order: stroke; stroke: color-mix(in srgb, var(--teal) 22%, transparent); stroke-width: 10px; stroke-linejoin: round; }
.flowsvg [data-stage].has-back:hover { fill: var(--teal); }
@media (prefers-reduced-motion: reduce) { .flowsvg .way-back { transition: none; } }

/* the domain: the open context's row as an ink head, a teal course with numbered nodes, the model as a profile, features as cards */
.dm { margin: 4px 0 8px; }
table.epics tr.epic-row.ink-open td, table.epics tr.epic-row.ink-open:hover td { background: var(--ink); color: var(--bg); border-bottom: 0;
  box-shadow: inset 0 4px 0 var(--teal); }
table.epics tr.ink-open td:first-child { border-radius: 4px 0 0 0; } table.epics tr.ink-open td:last-child { border-radius: 0 4px 0 0; }
table.epics tr.ink-open .id, table.epics tr.ink-open .hint, table.epics tr.ink-open .caret { color: color-mix(in srgb, var(--bg) 70%, transparent); }
table.epics tr.ink-open .title { font-weight: 700; }
.pill { font: 600 11px var(--mono); letter-spacing: .08em; text-transform: uppercase; padding: 2px 8px; border-radius: 999px; white-space: nowrap; }
.pill.core { background: color-mix(in srgb, var(--teal) 28%, transparent); box-shadow: inset 0 0 0 1.5px var(--teal); color: var(--teal); }
.pill.sup { box-shadow: inset 0 0 0 1.5px var(--teal); color: var(--teal); }
.pill.gen { box-shadow: inset 0 0 0 1.5px currentColor; opacity: .7; } .sd { margin: 4px 0 0 18px; }
.dm-track { border-left: 2px solid var(--line); margin: 10px 0 0 12px; padding-left: 20px; }
.dm-node { position: relative; margin: 16px 0 8px; font: 600 15px var(--display); }
.dm-node .n { position: absolute; left: -33px; top: -1px; width: 22px; height: 22px; border-radius: 50%; background: var(--teal); color: var(--on-accent); font: 600 12px var(--mono); display: grid; place-items: center; }
.dm-node .hint { font: 400 13px var(--body); margin-left: 6px; }
.dm-facts { display: grid; grid-template-columns: max-content 1fr; gap: 6px 12px; margin: 2px 0 0; }
.dm-facts dt { font: 600 11px var(--mono); color: var(--muted); text-transform: uppercase; letter-spacing: .06em; padding-top: 3px; }
.dm-facts dd { margin: 0; display: flex; flex-wrap: wrap; gap: 4px; }
.chip { font: 500 12px var(--mono); padding: 2px 8px; border-radius: 3px; background: color-mix(in srgb, var(--teal) 14%, transparent); color: var(--accent); white-space: nowrap; cursor: help; }
.chip.minor { background: transparent; color: var(--accent); box-shadow: inset 0 0 0 1px var(--teal); }
/* a term of the shared kernel, in a context or in the kernel's own block: indigo, never a context's teal */
.chip.shared { background: color-mix(in srgb, var(--shared) 14%, transparent); color: var(--shared); }
.chip.shared::before { content: "⇄ "; font-size: 10px; }
.dm-kernel { border: 1px solid color-mix(in srgb, var(--shared) 35%, var(--line)); border-top: 4px solid var(--shared); border-radius: 4px 4px 9px 9px;
  padding: 10px 14px 12px; margin: 12px 0 4px; background: color-mix(in srgb, var(--shared) 5%, var(--panel)); }
.dm-kernel .top { display: flex; gap: 10px; align-items: baseline; flex-wrap: wrap; margin-bottom: 8px; }
.dm-kernel .top b { font: 700 18px var(--display); color: var(--shared); }
details.dm-group { border: 1px solid var(--group-line); border-radius: 6px; margin-top: 6px; background: var(--panel); }
details.dm-group > summary { display: flex; justify-content: space-between; align-items: baseline; padding: 6px 10px; background: var(--group); border-radius: 6px; cursor: pointer; list-style: none; font: 600 15px var(--display); }
details.dm-group > summary::-webkit-details-marker { display: none; } details.dm-group > summary::before { content: "▸"; color: var(--muted); font: 400 12px var(--mono); margin-right: 8px; }
details.dm-group[open] > summary { border-radius: 6px 6px 0 0; } details.dm-group[open] > summary::before { content: "▾"; color: var(--accent); }
details.dm-group > summary span { font: 400 12px var(--mono); color: var(--muted); margin-left: auto; }
details.dm-group > summary { justify-content: flex-start; }
.dm-rule { padding: 8px 10px 2px; font: italic 500 14px var(--body); color: var(--muted); }
.dm-rule::before { content: "Rule · "; font: normal 600 11px var(--mono); color: var(--accent); letter-spacing: .06em; }
.dm .rrow { border-top: 0; } .dm .rrow + .rrow { border-top: 1px solid var(--line); }
.dm .rhead { padding: 5px 10px 5px 20px; }
.dm .rrow.open { box-shadow: inset 3px 0 0 var(--teal); background: color-mix(in srgb, var(--teal) 7%, transparent); }
.dm .spec-act { padding: 6px 10px 10px; }

/* displays every page shares: an outcome event, a state in its colour */
.event { font: 500 12px var(--mono); padding: 1px 9px 1px 7px; border-radius: 999px; background: color-mix(in srgb, var(--teal) 13%, transparent);
  color: var(--accent); white-space: nowrap; }
.event::before { content: "◆"; font-size: 8.5px; margin-right: 5px; vertical-align: 1px; }
.tone { font: 600 10.5px var(--mono); letter-spacing: .07em; text-transform: uppercase; padding: 2px 8px; border-radius: 999px; white-space: nowrap; }
.tone.ok { color: var(--accent); background: color-mix(in srgb, var(--teal) 13%, transparent); }
.tone.wait { color: var(--wait); background: color-mix(in srgb, var(--wait) 15%, transparent); }
.tone.bad { color: var(--stop); background: color-mix(in srgb, var(--stop) 15%, transparent); }
.tone.mute { color: var(--muted); box-shadow: inset 0 0 0 1px var(--line); }
.small-btn .btn, .btn.small { font-size: 12.5px; padding: 4px 9px; }

/* backlog: an epic as a strip of its stories, opened into lanes by where each stands */
.erows { display: grid; gap: 8px; margin-top: 12px; }
.erow { border-radius: 8px; background: var(--soft); }
.ehead { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 6px 12px; padding: 9px 12px; cursor: pointer; align-items: baseline; }
.ehead:focus-visible { outline: 2px solid var(--teal); outline-offset: 1px; border-radius: 8px; }
.ehead .name { display: flex; gap: 8px; align-items: baseline; flex-wrap: wrap; min-width: 0; }
.ehead .name b { font: 600 15.5px var(--display); } .ehead .caret { color: var(--muted); font: 400 12px var(--mono); }
.ehead .meta { display: flex; gap: 8px; align-items: center; font: 400 12.5px var(--mono); color: var(--muted); white-space: nowrap; }
.strip { display: flex; gap: 2px; grid-column: 1 / -1; } .strip i { flex: 1; height: 5px; border-radius: 1px; background: var(--line); }
.strip i.l-delivered, .legend i.l-delivered { background: var(--teal); } .strip i.l-running, .legend i.l-running { background: var(--wait); } .strip i.l-stopped, .legend i.l-stopped { background: var(--stop); }
.strip i.l-approved, .legend i.l-approved { background: color-mix(in srgb, var(--teal) 40%, var(--line)); }
.strip i.l-draft, .legend i.l-draft { background: transparent; box-shadow: inset 0 0 0 1px var(--muted); }
.strip i.l-superseded, .legend i.l-superseded { background: var(--line); }
/* the strip's key, said once above the epics */
.legend { display: flex; flex-wrap: wrap; gap: 4px 16px; font: 400 12px var(--mono); color: var(--muted); margin-top: 10px; }
.legend span { display: inline-flex; align-items: center; gap: 6px; }
.legend i { display: inline-block; width: 18px; height: 6px; border-radius: 1px; }
.ebody { padding: 0 12px 12px; } .ebody > .about { margin: 0 0 8px; }
.lanes { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; }
@media (max-width: 760px) { .lanes { grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); } }
.lane { background: var(--bg); border-radius: 8px; padding: 8px; min-width: 0; }
.lane h4 { font: 600 11px var(--mono); letter-spacing: .08em; text-transform: uppercase; color: var(--muted); display: flex; justify-content: space-between; margin-bottom: 6px; }
.scard { background: var(--panel); border: 1px solid var(--line); border-radius: 6px; padding: 6px 8px; margin-bottom: 6px; font-size: 14px; line-height: 1.35; }
.scard .link.title { font: 500 14px var(--display); } .scard .id { margin-top: 3px; }
/* a card's edge is its segment's colour in the strip above */
.scard.l-delivered { box-shadow: inset 3px 0 0 var(--teal); } .scard.l-running { box-shadow: inset 3px 0 0 var(--wait); }
.scard.l-stopped { box-shadow: inset 3px 0 0 var(--stop); } .scard.l-approved { box-shadow: inset 3px 0 0 color-mix(in srgb, var(--teal) 40%, var(--line)); }
.scard.l-superseded { box-shadow: inset 3px 0 0 var(--line); } .scard.l-draft { border-left: 2px dashed var(--muted); }
.scard .acts { margin-top: 6px; } .scard .btn { font-size: 12.5px; padding: 4px 9px; }
.lane details > summary { cursor: pointer; font: 500 12px var(--mono); color: var(--accent); }

/* run: what waits as tickets, a running story as its course of stages */
.queue { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; margin-top: 12px; }
.ticket { border: 1px dashed var(--line); border-radius: 7px; padding: 6px 10px; font-size: 14px; display: grid; gap: 4px; min-width: 0; }
.ticket .what { display: flex; gap: 8px; align-items: baseline; flex-wrap: wrap; }
.ticket .what b { font: 600 12px var(--mono); color: var(--accent); }
.ticket .acts { margin-top: 0; }
.live { border: 1px solid var(--line); border-radius: 9px; overflow: hidden; margin-top: 12px; }
.live .top { display: flex; justify-content: space-between; gap: 10px; padding: 9px 12px; align-items: baseline; flex-wrap: wrap; }
.live .top .right { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.stepper { display: grid; grid-auto-flow: column; grid-auto-columns: minmax(0, 1fr); gap: 3px; padding: 0 12px 10px; }
.st { text-align: center; font: 500 11px var(--mono); color: var(--muted); }
.st i { display: block; height: 8px; border-radius: 4px; background: var(--line); margin-bottom: 4px; }
.st.done i { background: var(--teal); } .st.stopped i { background: var(--stop); } .st.stopped { color: var(--stop); font-weight: 600; } .st.now i { background: var(--wait); animation: pulse 1.5s infinite; } .st.now { color: var(--ink); font-weight: 600; }
@keyframes pulse { 50% { opacity: .45; } } @media (prefers-reduced-motion: reduce) { .st.now i { animation: none; } }
.live .doing { padding: 6px 12px; font: 400 12.5px var(--mono); color: var(--muted); border-top: 1px solid var(--line); }

/* decide: the question on a tinted head, its answers as tiles, the recommended one framed */
.card.decision { padding: 0; overflow: hidden; }
.decision .q { padding: 12px 18px; background: color-mix(in srgb, var(--wait) 12%, var(--panel)); border-bottom: 1px solid var(--line); }
.decision.accept .q { background: color-mix(in srgb, var(--teal) 10%, var(--panel)); }
.decision .q b { font: 600 17px/1.3 var(--display); display: block; margin-top: 2px; }
.decision .dbody { padding: 10px 18px 16px; }
/* the options as rows, each its button first and what it means beside it — long words read across, not down */
.opts { display: grid; gap: 6px; margin-top: 10px; }
.opt { border: 1px solid var(--line); border-radius: 8px; padding: 9px 12px; font-size: 15px; display: grid;
  grid-template-columns: 64px minmax(0, 1fr); gap: 4px 12px; align-items: start; }
.opt > .pick-it { grid-row: 1 / span 2; } .opt .rec-word { grid-column: 2; }
.opt.advised { border-color: var(--teal); box-shadow: inset 0 0 0 1px var(--teal); }
.decision details.more > summary::before { content: "▸ "; color: var(--muted); } .decision details.more[open] > summary::before { content: "▾ "; }
.decision .id .link.title { font: inherit; }
.opt .rec-word { font: 600 10.5px var(--mono); color: var(--accent); text-transform: uppercase; letter-spacing: .07em; }

/* delivered: the figures as tiles, the deliveries as a line of days */
.tiles { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; margin-top: 12px; }
@media (max-width: 760px) { .tiles { grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); } }
.tile { border-radius: 9px; padding: 10px 12px; background: var(--soft); }
.tile b { font: 700 24px/1.1 var(--display); display: block; } .tile.lead b { color: var(--accent); }
.tile span { display: block; line-height: 1.4; margin-top: 4px; font: 500 11px/1.4 var(--mono); color: var(--muted); text-transform: uppercase; letter-spacing: .06em; }
.days { border-left: 2px solid var(--line); margin: 16px 0 0 6px; padding-left: 16px; display: grid; gap: 12px; }
.day { position: relative; } .day::before { content: ""; position: absolute; left: -22px; top: 5px; width: 10px; height: 10px; border-radius: 50%; background: var(--teal); }
.day h4 { font: 600 12px var(--mono); color: var(--muted); margin-bottom: 2px; }
/* a delivery a row of fixed columns: when, what, its epic, its outcome event, how long, what it cost — the figures
   right-aligned, a column never wider than its place */
.dl { display: grid; grid-template-columns: 44px minmax(0, 1fr) 150px 210px 76px 64px; gap: 4px 14px; align-items: start;
  padding: 5px 0; border-bottom: 1px solid var(--line); font-size: 15px; }
.dl .cut { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.dl .fig, .dl .at, .dl .epic { font: 400 12.5px var(--mono); color: var(--muted); font-variant-numeric: tabular-nums; white-space: nowrap; }
.dl .fig { text-align: right; }
.dl > :not(.what) { padding-top: 4px; }   /* a title is a button, its baseline its last line: the small cells meet its first */
@media (max-width: 760px) {
  .dl { grid-template-columns: 44px minmax(0, 1fr) auto; } .dl .epic { display: none; }
  .dl .ev { grid-column: 2 / -1; grid-row: 2; } .dl .fig + .fig { grid-column: 3; grid-row: 2; } }

/* delivered over time: two panels on one time axis — cost above, tokens below, never two scales on one axis */
.curve { position: relative; margin-top: 14px; }
.curve svg { display: block; width: 100%; height: auto; }
.curve .grid { stroke: var(--line); stroke-width: 1; }
.curve .axis { font: 400 11px var(--mono); fill: var(--muted); }
.curve .name { font: 600 11px var(--mono); fill: var(--muted); letter-spacing: .06em; text-transform: uppercase; }
.curve .end { font: 600 12px var(--mono); fill: var(--ink); }
.curve .area { fill: color-mix(in srgb, var(--teal) 12%, transparent); }
.curve .line { fill: none; stroke: var(--teal); stroke-width: 2; stroke-linejoin: round; }
.curve .cross { stroke: var(--muted); stroke-width: 1; stroke-dasharray: 3 3; }
.curve .dot { fill: var(--teal); stroke: var(--panel); stroke-width: 2; }
.curve .tip { position: absolute; pointer-events: none; background: var(--panel); border: 1px solid var(--line); border-radius: 8px;
  box-shadow: var(--shadow); padding: 8px 10px; font: 400 12.5px var(--mono); color: var(--ink); max-width: 320px; }
.curve .tip b { display: block; font: 600 13.5px var(--display); margin-bottom: 4px; }
.curve .tip .row { display: flex; justify-content: space-between; gap: 14px; color: var(--muted); } .curve .tip .row span:last-child { color: var(--ink); }

/* quality: what the stages asked, what the judge found, what a person corrected — counted, never rated */
.tiles.five { grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); }
.tile.bad b { color: var(--stop); } .tile small { display: block; font: 400 11.5px var(--mono); color: var(--muted); margin-top: 2px; }
.qbars { display: grid; grid-template-columns: max-content minmax(0, 1fr) max-content; gap: 6px 12px; align-items: center; margin-top: 8px; }
.qbars .lbl { font: 500 12.5px var(--mono); color: var(--ink); } .qbars .n { font: 500 12.5px var(--mono); color: var(--muted); text-align: right; font-variant-numeric: tabular-nums; }
.qbars .track { height: 8px; } .qbars .track i { display: block; height: 100%; border-radius: 0 4px 4px 0; background: var(--teal); min-width: 2px; }
.qline { display: flex; flex-wrap: wrap; gap: 4px 14px; font: 400 12.5px var(--mono); color: var(--muted); margin: 0 0 10px; }
.qline b { color: var(--ink); font-weight: 600; } .qline .bad { color: var(--stop); }

/* discover: the problem with an amber edge, the proposed epics as cards */
.proposals { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 8px; }
.proposal { border: 1px solid var(--line); border-radius: 8px; padding: 9px 11px; margin-bottom: 8px; display: grid; gap: 5px; }
.proposal > b { font: 600 15px var(--display); } .proposal .ev { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; font-size: 13px; color: var(--muted); }
.proposal .acts { margin-top: 2px; }

/* the rules: one detail under the drawing, a rule a row that opens where it stands */
.rgroup { margin-top: 14px; } .rgroup .lbl { font: 500 10.5px var(--mono); letter-spacing: 1px; text-transform: uppercase; color: var(--muted); margin-bottom: 4px; }
.rgroup .lbl .n { color: var(--ink); margin-left: 4px; }
.rrow { border-top: 1px solid var(--line); } .rrow:last-child { border-bottom: 1px solid var(--line); }
.rhead { display: grid; grid-template-columns: 14px minmax(0, 1fr) max-content; gap: 10px; align-items: baseline; width: 100%;
  background: none; border: 0; padding: 7px 2px; text-align: left; color: var(--ink); cursor: pointer; font: 400 14px var(--body); }
.rhead:hover .rid, .rhead:focus-visible .rid { color: var(--accent); } .rhead:focus-visible { outline: 2px solid var(--teal); outline-offset: 1px; }
.rhead .caret { color: var(--muted); font: 400 12px var(--mono); } .rhead .rid { font: 500 12.5px var(--mono); padding-left: 6px; }
.rhead .rid.e-gate { border-left: 3px solid var(--deep); } .rhead .rid.e-runner { border-left: 3px solid var(--run); } .rhead .rid.e-instructed { border-left: 3px solid var(--wait); }
.rhead .rid.f-pass { background: color-mix(in srgb, var(--done) 18%, transparent); } .rhead .rid.f-fail { background: color-mix(in srgb, var(--stop) 22%, transparent); }
.rhead .rgist { color: var(--ink); min-width: 0; font-size: 15px; } .rhead .rid { color: var(--muted); font-size: 11.5px; }
.rbody .why { font: 400 15px var(--body); color: var(--muted); margin: 2px 0 8px; }
.rbody .said { margin: 4px 0; font: 400 15px var(--body); line-height: 1.45; }
.rbody .said .kw { font: 600 12.5px var(--mono); color: var(--ink); margin-right: 6px; white-space: nowrap; }
.mk { width: 15px; height: 15px; vertical-align: -3px; margin-right: 2px; }
.mk circle { stroke: none; } .mk path { fill: none; stroke: #ffffff; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }
.mk-pass circle { fill: var(--teal); } .mk-fail circle { fill: var(--stop); } .mk-wait circle, .mk-ask circle { fill: var(--muted); }
.mk-minor path { stroke: var(--muted); }
.rbody .goes { font: 500 12.5px var(--mono); color: var(--accent); white-space: nowrap; }
.rbody details.src summary { cursor: pointer; font: 400 11.5px var(--mono); color: var(--muted); margin-top: 8px; }
.rbody { padding: 2px 4px 12px 26px; } .rbody .kv { margin-top: 0; }
.part { border-left: 2px solid var(--line); padding: 2px 0 6px 14px; margin-top: 14px; }
.part-head { font: 600 15px var(--display); display: flex; gap: 8px; align-items: baseline; }
.part-head .num { font: 600 12px var(--mono); color: var(--accent); } .part-head .hint { font: 400 13px var(--body); }
.part .rgroup:first-of-type { margin-top: 6px; } .then { margin: 6px 0 0; font: 400 14px var(--body); color: var(--muted); }
details.fold > summary { cursor: pointer; font: 500 12px var(--mono); color: var(--accent); margin-top: 6px; }
.storyline { font: 400 15px var(--body); margin: 12px 0 0; } .storyline .hint { display: block; }
.flowsvg.has-story [data-stage]:not(.ov-reached) { opacity: .35; }
.flowsvg [data-stage].ov-now { fill: var(--teal); text-decoration: underline; text-decoration-thickness: 2px; text-underline-offset: 4px; }
.flowsvg .gate.ov-failed circle { stroke: var(--stop); stroke-width: 4px; }
.flowsvg .ov-badge { font: 700 11px var(--mono); fill: var(--stop); }
table.epics tr.epic-row { cursor: pointer; } table.epics tr.epic-row:hover td { background: var(--soft); }
table.epics tr.epic-row:focus-visible { outline: 2px solid var(--teal); outline-offset: -2px; }
table.epics .caret { color: var(--muted); font: 400 12px var(--mono); }
table.epics tr.epic-body > td { padding-top: 0; } table.epics tr.epic-body table { margin-top: 4px; }
.bar { height: 6px; border-radius: 3px; background: var(--line); min-width: 80px; overflow: hidden; }
.bar i { display: block; height: 100%; background: var(--done); }
.show-s { display: none; } @media (max-width: 760px) { .show-s { display: block; } }
.spec-act { margin-top: 8px; } .spec-act .ask textarea { min-height: 64px; }
.terms { display: flex; flex-wrap: wrap; gap: 4px 6px; } .term { font: 400 12.5px var(--mono); padding: 2px 7px; border-radius: 3px; background: color-mix(in srgb, var(--teal) 14%, transparent); color: var(--accent); cursor: help; }
details.feature { border-top: 1px solid var(--line); padding: 6px 0; } details.feature > summary { cursor: pointer; font: 500 15px var(--display); }
details.feature > summary .hint { font: 400 13px var(--body); margin-left: 6px; }
.rule-head { font: 600 14px var(--display); margin: 10px 0 2px; }
.pend { font: 500 11.5px var(--mono); padding: 1px 6px; border-radius: 4px; white-space: nowrap; }
.pend.p-gone { background: color-mix(in srgb, var(--stop) 22%, transparent); }
.pend.p-changes { background: color-mix(in srgb, var(--wait) 22%, transparent); } .pend.p-adds { background: color-mix(in srgb, var(--teal) 18%, transparent); }
.way-link { background: none; border: 0; padding: 2px 0; font: 500 13px var(--mono); color: var(--accent); cursor: pointer; }
details.more > summary { cursor: pointer; list-style: none; } details.more > summary::-webkit-details-marker { display: none; }
details.more > summary h2::before { content: "▸ "; color: var(--muted); } details.more[open] > summary h2::before { content: "▾ "; }
.flowsvg [data-stage] { cursor: pointer; } .flowsvg [data-stage].sel { fill: var(--teal); }

.rid .x { font-weight: 700; color: var(--stop); margin-left: 3px; }
.back { font: 400 11.5px var(--mono); color: var(--muted); }
.pick { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; margin-top: 12px; }
.pick select { font: 400 13px var(--mono); color: var(--ink); background: var(--bg); border: 1px solid var(--line); border-radius: 8px; padding: 6px; }
.outcome { margin: 4px 0; } .outcome b { font: 600 13px var(--mono); margin-right: 6px; }
.banner { display: none; background: var(--deep); color: var(--mist); border-bottom: 3px solid var(--stop); font: 500 14px var(--display); padding: 8px 0; }
#toasts { position: fixed; right: 16px; bottom: 16px; z-index: 40; display: flex; flex-direction: column; gap: 8px; max-width: min(440px, calc(100% - 32px)); }
.toast { background: var(--panel); color: var(--ink); border: 1px solid var(--line); border-left: 4px solid var(--teal); border-radius: 8px;
  padding: 10px 14px; box-shadow: var(--shadow); font-size: 15px; white-space: pre-wrap; }
.toast.err { border-left-color: var(--stop); }
.drawer { position: fixed; inset: var(--bar, 0px) 0 0 auto; width: min(760px, 100%); z-index: 15; background: var(--bg); border-left: 1px solid var(--line);
  box-shadow: var(--shadow); overflow-y: auto; padding: 24px; }
.drawer .close { float: right; }
@media (max-width: 760px) {
  .wrap { padding: 0 16px; }
  .tabs { order: 3; width: 100%; margin-left: 0; }
  .hide-s { display: none; }
  td, th { padding: 8px 4px; }
  .by { width: 100px; }
  /* a row with buttons: its cells side by side, the buttons on a line of their own beneath */
  tr:has(> td.act) { display: grid; grid-template-columns: auto 1fr fit-content(40%); border-bottom: 1px solid var(--line); }
  tr:has(> td.act) > td { border-bottom: 0; } tr:has(> td.act) > td.hide-s { display: none; }
  td.act { grid-column: 1 / -1; padding-top: 0; } td.act:has(> .acts:empty) { display: none; } td.act .acts { justify-content: flex-start; }
  table:has(td.act) tr:has(> th) { display: none; }
}
</style>
</head>
<body>
<header class="topbar" id="topbar">
  <div class="wrap nav">
    <a class="brand" id="home" href="#now" data-tab="now" aria-label="now — where the factory stands" title="now — where the factory stands">__MARK__<span>factory<span class="tld">.</span></span><span class="project" id="project"></span></a>
    <nav class="tabs" id="tabs" role="tablist" aria-label="the factory's views"></nav>
    <div class="status">
      <span id="worker"><span class="dot"></span>…</span>
      <button class="bar-btn primary" data-call="up" id="up" title="work the released stories off, one after the other — factory.sh up" hidden>▶ start the backlog</button>
      <button class="bar-btn" data-call="down" id="down" title="no next story from the backlog; what runs ends its stage — factory.sh down" hidden>■ stop the backlog</button>
      <label>as <input class="by" id="by" type="text" autocomplete="name" aria-label="your name"></label>
      <span class="theme" role="group" aria-label="theme">
        <button data-pick="light" aria-pressed="false">light</button><button data-pick="auto" aria-pressed="false">auto</button><button data-pick="dark" aria-pressed="false">dark</button>
      </span>
    </div>
  </div>
</header>
<div class="banner" id="banner" role="alert"><div class="wrap" id="banner-text"></div></div>
<main class="wrap" id="main" role="tabpanel"></main>
<div id="toasts" aria-live="polite"></div>
<aside class="drawer" id="drawer" aria-label="story" tabindex="-1" hidden></aside>
<script>
"use strict";
const TOKEN = new URLSearchParams(location.search).get("t") || "";
// the views in the order of their keys (0 … 6, the cockpit's); which part each sits in — once, inflow, the cycle, to look
// up — comes from the factory (`help`'s parts)
const TABS = [
  ["describe", "The project description", "What is built, how, and in which domain — and in each context what holds today. You write the description; what holds changes by a story the gate delivers."],
  ["discover", "Discovery", "Which problem is worth solving — a report with its sources and the epics it proposes."],
  ["backlog", "Backlog", "Epics and their stories, newest first — from a discovery, a wish, a judge's finding or a delivered epic's journey. A story runs once released."],
  ["run", "The factory at work", "Your requests at once, while this page is open; the backlog's stories while it is started — one stage after the other, a gate between them."],
  ["decide", "Waiting for you", "A question a stage may not decide alone, or a result to look at."],
  ["delivered", "Delivered", "What the factory delivered, the newest first."],
  ["rules", "The rules", "What the gate checks, what the runner decides and what each stage is told — per stage of a story, the gates between them. Pick a rule to read it; pick a story to see which fired."]];
const NOW = ["now", "Where it stands", "The cycle a story turns through — how many stand where, and the one that matters most in each."];
const MARKS = {look: "!", question: "?", stopped: "✗", running: "▶", done: "✓", none: "·", next: "→"};
const S = {tab: "now", help: null, status: null, decisions: null, discover: null, requests: null, follow: null, followSource: null,
           followLines: [], drawer: null, opener: null, drafts: {}, folded: {},
           rules: null, rulesFor: null, ruleKind: "story", rule: null, ruleStory: "", flowPick: null};
const stored = key => { try { return localStorage.getItem(key) || ""; } catch (e) { return ""; } };
const store = (key, value) => { try { localStorage.setItem(key, value); } catch (e) {} };
// the page opens where it stands; a link to a view opens that view
const known = id => id === "now" || TABS.some(([t]) => t === id);
if (known(location.hash.slice(1))) S.tab = location.hash.slice(1);
if (location.hash === "#spec" || S.tab === "spec") S.tab = "describe";                // what holds is part of the description
// `#rules:<story>[:<rule>]` opens the rules with that story's gate runs marked, and the rule read
if (location.hash.startsWith("#rules:")) {
  const [story, rule] = decodeURIComponent(location.hash.slice(7)).split(":");
  [S.tab, S.ruleStory, S.rule] = ["rules", story || "", rule || null];
}

// --- helpers -------------------------------------------------------------------------------------------------------
const $ = id => document.getElementById(id);
const esc = v => String(v == null ? "" : v).replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
const mark = m => `<span class="mark m-${esc(m)}" aria-hidden="true">${esc(MARKS[m] || "·")}</span>`;
// a section's markdown as the website sets it: paragraphs, lists, `code` and **strong** — escaped first
// code first, as markdown reads it — `x`, and ``x`` that may hold a backtick —, bold only outside it
const inline = text => String(text == null ? "" : text).split(/(``.+?``|`[^`]+`)/).map((part, i) => i % 2
  ? `<code>${esc(part.startsWith("``") ? part.slice(2, -2).trim() : part.slice(1, -1))}</code>`
  : esc(part).replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")).join("");
function prose(text) {
  // the markdown a person writes in a description, a record or a story: paragraphs, lists, tables, code, headings
  const out = [];
  let para = [], list = null, table = null, code = null;
  const endPara = () => { if (para.length) out.push(`<p>${inline(para.join(" "))}</p>`); para = []; };
  const endList = () => { if (list) out.push(`<${list.tag}>${list.items.map(i => `<li>${inline(i)}</li>`).join("")}</${list.tag}>`); list = null; };
  const cells = row => row.trim().replace(/^\||\|$/g, "").split("|").map(c => c.trim());
  const endTable = () => {
    if (!table) return;
    const [head, ...rows] = table.filter(r => !/^\s*\|?\s*:?-{2,}/.test(r));
    out.push(`<table class="md"><tr>${cells(head).map(c => `<th>${inline(c)}</th>`).join("")}</tr>`
      + rows.map(r => `<tr>${cells(r).map(c => `<td>${inline(c)}</td>`).join("")}</tr>`).join("") + `</table>`);
    table = null;
  };
  const endAll = () => { endPara(); endList(); endTable(); };
  for (const line of String(text || "").split("\n")) {
    if (code) { if (/^\s*```/.test(line)) { out.push(`<pre class="md">${esc(code.join("\n"))}</pre>`); code = null; } else code.push(line); continue; }
    if (/^\s*```/.test(line)) { endAll(); code = []; continue; }
    if (/^\s*\|/.test(line)) { endPara(); endList(); (table = table || []).push(line); continue; }
    endTable();
    const heading = line.match(/^#{3,6}\s+(.*)$/);
    const item = line.match(/^\s*(?:([-*])|\d+\.)\s+(.*)$/);
    if (heading) { endAll(); out.push(`<h4>${inline(heading[1])}</h4>`); }
    else if (item) {
      endPara();
      const tag = item[1] ? "ul" : "ol";
      if (list && list.tag !== tag) endList();
      list = list || {tag, items: []};
      list.items.push(item[2]);
    } else if (!line.trim()) { endPara(); endList(); }
    else if (list && /^\s/.test(line)) list.items[list.items.length - 1] += " " + line.trim();
    else { endList(); para.push(line.trim()); }
  }
  if (code) out.push(`<pre class="md">${esc(code.join("\n"))}</pre>`);
  endAll();
  return `<div class="prose">${out.join("")}</div>`;
}
// one of the factory's sections; one with a kind (why a story is not built) set apart in the wait colour
const section = (s, h = 3) => s.kind ? `<div class="aside"><h${h}>${esc(s.heading || s.kind)}</h${h}>${prose(s.text)}</div>`
  : `${s.heading ? `<h${h}>${esc(s.heading)}</h${h}>` : ""}${prose(s.text)}`;
const story = (id, title) => `<button type="button" class="link title" data-story="${esc(id)}">${esc(title || id)}</button>`;
const by = () => $("by").value.trim();

async function api(path, body) {
  const options = {headers: {"X-Factory-Token": TOKEN}};
  if (body !== undefined) Object.assign(options, {method: "POST", body: JSON.stringify(body),
    headers: {"X-Factory-Token": TOKEN, "Content-Type": "application/json"}});
  const response = await fetch(path, options);
  let data = {};
  try { data = await response.json(); } catch (e) { data = {error: "no JSON from " + path}; }
  if (!response.ok) throw new Error(data.error || data.output || "HTTP " + response.status);
  return data;
}

function toast(text, isError) {
  const node = document.createElement("div");
  node.className = "toast" + (isError ? " err" : "");
  node.textContent = text;
  $("toasts").appendChild(node);
  setTimeout(() => node.remove(), isError ? 9000 : 4500);
}

function banner(text) {
  $("banner-text").textContent = text || "";
  $("banner").style.display = text ? "block" : "none";
}

// --- actions: the factory's, drawn as given ------------------------------------------------------------------------
// An action carries its label, whether it is the one to press, and the request it writes; `open` says what the person
// still gives — their words (a form), or an answer under Decide; one whose request is written already says so
// (`queued`). One without a request is no press on this page.
const ACTIONS = {};
let actionCount = 0;
function act(action, scope) {
  if (!action || !action.request) return "";
  if (action.waits_on) return "";                       // another choice of the same record is on its way
  if (action.queued) return `<span class="state st-queued" title="request ${esc(action.queued)}">${esc(action.label)} — ${esc(action.queued_text || "queued")}</span>`;
  const id = `${scope || "m"}${++actionCount}`;
  ACTIONS[id] = action;
  // a press that has an agent write something new says so before it is pressed: ✦ on the button, words in its title
  const r = action.request, cls = `btn${action.primary ? " primary" : ""}${action.creates ? " claude" : ""}`;
  const said = [action.creates ? "an agent writes this, in the factory's queue" : "", action.text].filter(Boolean).join(" — ");
  if (r.open === "words") {
    const choices = (r.choices || []).length ? `<select aria-label="why"><option value="">why? (optional)</option>${r.choices.map(c => `<option>${esc(c)}</option>`).join("")}</select>` : "";
    // what the person typed outlives a redraw: kept by the action's command, until its request is written
    const draft = r.draft || action.skill;
    return `<div class="ask" data-ask="${id}"><textarea data-draft="${esc(draft)}" placeholder="${esc(action.text)}" aria-label="${esc(action.label)}">${esc(S.drafts[draft] || "")}</textarea>${choices}
      <button class="${cls}" data-press="${id}" title="${esc(said)}">${esc(action.label)}</button></div>`;
  }
  if (r.open === "record") return `<button class="${cls}" data-tab="decide">${esc(action.label)}</button>`;
  return `<button class="${cls}" data-press="${id}" title="${esc(said)}">${esc(action.label)}</button>`;
}
const acts = (list, scope) => (list || []).map(a => act(a, scope)).join("");
function forget(scope) { for (const key of Object.keys(ACTIONS)) if (key[0] === scope) delete ACTIONS[key]; }

async function press(button) {
  const action = ACTIONS[button.dataset.press];
  if (!action) return;
  const r = action.request, box = button.closest("[data-ask]"), fields = Object.assign({}, r.fields);
  let words = r.words || "";
  if (box) {
    words = box.querySelector("textarea").value.trim();
    const pick = box.querySelector("select");
    if (pick && pick.value) fields.option = pick.value;
    if (!words) { toast(`${action.label}: ${action.text}`, true); return; }
    if (r.prefix) words = `${r.prefix}\n\n${words}`;
  }
  try {
    const data = await api("/api/request", Object.assign({kind: r.kind, words, by: by()}, fields));
    toast(data.duplicate ? `queued already: ${data.id}`
      : r.kind === "wish" ? "✦ your wish is being written as a draft — it shows below the field" : `request written: ${data.id}`);
    if (box) { box.querySelector("textarea").value = ""; delete S.drafts[r.draft || action.skill]; }
    refresh();
    if (S.drawer) openStory(S.drawer);
  } catch (e) { toast(e.message, true); }
}
document.addEventListener("input", event => {
  if (event.target.dataset && event.target.dataset.draft !== undefined) S.drafts[event.target.dataset.draft] = event.target.value;
});
document.addEventListener("change", event => {
  if (!event.target.dataset || event.target.dataset.overlay === undefined) return;
  S.ruleStory = event.target.value;
  event.target.blur();                                   // a focused select holds the redraw back
  loadRules();
});

// what the page itself calls: the backlog started and stopped, a request taken back or queued again, an output followed
const CALLS = {
  async up() { const d = await api("/api/up", {by: by()}); toast(d.output || "up"); },
  async down(node) {
    const now = node.dataset.now === "1";
    if (now && !confirm("Interrupt the running stage too? Its work so far stays; the stage runs again later.")) return;
    const d = await api("/api/down", {by: by(), now}); toast(d.output || "stopping");
  },
  async drop(node) {
    if (!confirm(`Take request ${node.dataset.id} back?`)) return;
    await api("/api/requests/drop", {id: node.dataset.id}); toast("taken back");
  },
  async retry(node) { await api("/api/requests/retry", {id: node.dataset.id}); toast("queued again"); },
  async hide(node) { await api("/api/requests/drop", {id: node.dataset.id}); toast("hidden — the draft stays in the backlog"); },
  async follow(node) { follow(node.dataset.kind, node.dataset.id); },
  async unfollow() { follow(null); },
  async close() { S.drawer = null; $("drawer").hidden = true; forget("d"); if (S.opener && document.contains(S.opener)) S.opener.focus(); S.opener = null; },
};

document.addEventListener("click", async event => {
  const target = event.target.closest("[data-press],[data-call],[data-story],[data-tab],[data-pick],[data-rule],[data-flow]");
  if (!target) return;
  if (target.dataset.rule) {
    S.rule = S.rule === target.dataset.rule ? null : target.dataset.rule;
    render();
    const read = $("rule-detail");
    if (read) read.scrollIntoView({block: "nearest", behavior: "smooth"});
    return;
  }
  if (target.dataset.flow) { S.ruleKind = target.dataset.flow; return render(); }
  if (target.dataset.pick) return theme(target.dataset.pick);
  if (target.dataset.tab) return show(target.dataset.tab);
  if (target.dataset.story) return openStory(target.dataset.story);
  target.disabled = true;
  try {
    if (target.dataset.press) await press(target);
    else { await CALLS[target.dataset.call](target); refresh(); }
  } catch (e) { toast(e.message, true); }
  finally { target.disabled = false; }
});

// --- the theme: the person's choice over the system's ----------------------------------------------------------------
function theme(choice) {
  store("factory.theme", choice);
  if (choice === "auto") document.documentElement.removeAttribute("data-theme");
  else document.documentElement.setAttribute("data-theme", choice);
  document.querySelectorAll(".theme button").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.pick === choice)));
}

// --- loading -------------------------------------------------------------------------------------------------------
async function load(name, path) {
  try { S[name] = await api(path); return true; }
  catch (e) { banner(`${name}: ${e.message}`); return false; }
}

let refreshing = false, lastSlow = 0;
async function refresh() {
  if (refreshing) return;
  refreshing = true;
  try {
    const slow = Date.now() - lastSlow > 15000 || ["decide", "discover", "describe"].includes(S.tab);
    const jobs = [load("status", "/api/view/status"), load("requests", "/api/view/requests")];
    if (slow || !S.decisions) jobs.push(load("decisions", "/api/view/decisions"));
    if (slow || !S.discover) jobs.push(load("discover", "/api/view/discover"));
    if ((await Promise.all(jobs)).every(Boolean)) banner("");
    if (slow) lastSlow = Date.now();
    render();
  } finally { refreshing = false; }
}

// --- the frame -----------------------------------------------------------------------------------------------------
function show(tab) {
  if (S.drawer) CALLS.close();
  S.tab = tab;
  store("factory.tab", tab);
  history.replaceState(null, "", "#" + tab);
  render();
  window.scrollTo(0, 0);
}

function renderFrame() {
  const st = S.status || {}, w = st.worker, counts = (S.requests || {}).counts || {};
  $("project").textContent = st.project || "";
  document.title = (st.project ? st.project + " — " : "") + "factory";
  // the dot is the backlog's, the one thing a person switches here: a person's requests are worked while this page is
  // open, and that goes without saying (WP-177)
  const backlog = backlogOn(st);
  const dot = !backlog ? "down" : w.stopping ? "stopping" : "up";
  const queued = (S.requests || {}).counts_text;
  $("worker").innerHTML = `<span class="dot ${dot}"></span>${esc(st.worker_text || "…")}${queued ? ` · ${esc(queued)}` : ""}`;
  $("worker").title = w ? `${w.owner} since ${w.since_text}` : "nobody holds the checkout";
  $("up").hidden = backlog;
  $("down").hidden = !backlog || w.stopping;
  // a record waits where it is answered: a discovery's on discover, the description's on describe, the rest decide
  const asking = place => (st.waiting || []).filter(w => (w.place || "decide") === place).length;
  const tab = id => {
    const n = ["decide", "discover", "describe"].includes(id) ? asking(id) : id === "run" ? (counts.failed || 0) : 0;
    const key = TABS.findIndex(([t]) => t === id), on = S.tab === id, first = S.tab === "now" && key === 0;
    return `<button role="tab" id="tab-${id}" data-tab="${id}" aria-selected="${on}" tabindex="${on || first ? 0 : -1}" aria-controls="main" aria-keyshortcuts="${key}"><span class="key" aria-hidden="true">${key}</span>${esc(id)}${n ? `<span class="n">${n}</span>` : ""}</button>`;
  };
  // the parts side by side, the cycle's views with an arrow between them: the order a story turns through
  const parts = (S.help || {}).parts || [{tabs: TABS.map(([id]) => id)}];
  morph($("tabs"), parts.map(p => `<span class="tgroup" role="presentation">${p.tabs.map((id, i) =>
    (i && p.ordered ? `<span class="arrow" aria-hidden="true">→</span>` : "") + tab(id)).join("")}</span>`)
    .join(`<span class="tsep" aria-hidden="true"></span>`));
  $("main").setAttribute("aria-labelledby", S.tab === "now" ? "home" : "tab-" + S.tab);
}
const partOf = id => ((S.help || {}).parts || []).find(p => p.tabs.includes(id));

// --- drawing: the new page is matched against the one on screen, never put in its place -------------------------------
// An element that stays the same element keeps what the browser holds for the person — where a box is scrolled, what
// has the focus, a caret, a selection —, so nothing of it has to be remembered and put back. An element with a key
// (`id`, `data-fold`, `data-epic`, `data-context`, `data-story`) is found again by it, wherever it moved; a fold's
// `open` and a text field's words are the person's, and the match leaves them alone.
const keyOf = node => node.nodeType === 1 ? node.id || node.dataset.fold || node.dataset.epic || node.dataset.context
  || node.dataset.topic
  || (node.tagName === "BUTTON" ? "" : node.dataset.story) || "" : "";
const PERSONS = {DETAILS: ["open"], TEXTAREA: ["value"], INPUT: ["value"], SELECT: ["value"]};
function morphNode(old, want) {
  if (old.nodeType !== 1) { if (old.nodeValue !== want.nodeValue) old.nodeValue = want.nodeValue; return; }
  const keep = PERSONS[old.tagName] || [];
  for (const {name} of [...old.attributes]) if (!want.hasAttribute(name) && !keep.includes(name)) old.removeAttribute(name);
  for (const {name, value} of [...want.attributes]) if (!keep.includes(name) && old.getAttribute(name) !== value) old.setAttribute(name, value);
  // a text field's words are the person's, and what the page fills in itself (`data-own`) is the page's
  if (old.tagName !== "TEXTAREA" && !old.hasAttribute("data-own")) morphChildren(old, want);
}
function morphChildren(from, to) {
  const keyed = new Map([...from.childNodes].filter(keyOf).map(n => [keyOf(n), n]));
  let cur = from.firstChild;
  for (const want of [...to.childNodes]) {
    const key = keyOf(want);
    const match = key ? keyed.get(key)
      : cur && !keyOf(cur) && cur.nodeType === want.nodeType && cur.nodeName === want.nodeName ? cur : null;
    if (!match) { from.insertBefore(want, cur); continue; }
    if (key) keyed.delete(key);
    if (match === cur) cur = cur.nextSibling; else from.insertBefore(match, cur);
    morphNode(match, want);
  }
  while (cur) { const next = cur.nextSibling; cur.remove(); cur = next; }
}
function morph(target, html) {
  if (target.dataset.drawn === html) return;            // nothing changed: nothing is touched
  const fresh = document.createElement("template");
  fresh.innerHTML = html;
  morphChildren(target, fresh.content);
  target.dataset.drawn = html;
}

function render() {
  renderFrame();
  const editing = document.activeElement && ["TEXTAREA", "SELECT"].includes(document.activeElement.tagName)
    && $("main").contains(document.activeElement);
  if (editing) return;                                   // a person typing is not redrawn under their hands
  forget("m"); forget("s");
  const [, title, lede] = S.tab === "now" ? NOW : TABS.find(([id]) => id === S.tab) || NOW;
  const eyebrow = S.tab === "now" ? "Now" : (partOf(S.tab) || {}).eyebrow || "";
  const view = {now, describe, discover, backlog, run, decide, delivered, rules: rulesTab}[S.tab] || now;
  morph($("main"), `<div class="eyebrow">${esc(eyebrow)}</div><h1>${esc(title)}</h1><p class="lede">${esc(lede)}</p>`
    + (S.status ? endedLine(S.status) + view(S.status) : `<section class="card"><p class="empty">Reading the factory…</p></section>`));
  if (S.tab === "run") paintFollow();
  if (S.tab === "rules") paintFlow();
}

// --- the rules: the factory's rulebook, drawn as it says it ------------------------------------------------------------
async function loadRules() {
  const want = S.ruleStory || "";
  if (S.rules && S.rulesFor === want) return;
  S.rulesFor = want;
  if (await load("rules", "/api/view/rules" + (want ? `?id=${encodeURIComponent(want)}` : ""))) render();
}

// one place for what is picked in the drawing: a step, a gate or an edge; each rule a row that opens where it stands
const pickedRules = () => S.openRules || (S.openRules = new Set(S.rule ? [S.rule] : []));

// a rule read as sentences: its title, why, when, and each outcome after its keyword, where it sends the story
// the marks are the drawing's: a gate's check for a pass, a stop's cross for a fail, a pause where a person answers
const MARK = {
  pass: '<path d="M6 10.4l2.7 2.7L14.2 7.6"/>', fail: '<path d="M6.6 6.6l6.8 6.8M13.4 6.6l-6.8 6.8"/>',
  wait: '<path d="M8 6.5v7M12 6.5v7"/>', ask: '<path d="M7.6 7.6a2.5 2.5 0 1 1 3.4 2.3c-.7.3-1 .8-1 1.5v.6M10 14.4v.1"/>'};
const icon = state => MARK[state] ? `<svg class="mk mk-${state}" viewBox="0 0 20 20" aria-hidden="true"><circle cx="10" cy="10" r="10"/>${MARK[state]}</svg>`
  : `<svg class="mk mk-minor" viewBox="0 0 20 20" aria-hidden="true"><path d="M6 10h8"/></svg>`;
const SAYS = {pass: "Passes when", fail: "Fails when", skip: "Skips when", note: "Notes when", wait: "Waits when", ask: "Asks when"};
const sentence = t => { const s = String(t || "").trim(); return s ? s[0].toUpperCase() + s.slice(1) + (/[.!?)]$/.test(s) ? "" : ".") : ""; };
const clause = t => { const s = String(t || "").trim(); return s + (/[.!?)]$/.test(s) ? "" : "."); };
const going = goes => (goes || []).length ? ` <span class="goes">→ ${goes.map(g => g === "stop" ? "stop" : g === "again" ? "once more" : "back to " + g).map(esc).join(" or ")}</span>` : "";

function ruleRow(id, rules, story, stage) {
  const r = rules[id] || {id, enforcement: "", outcomes: []}, open = pickedRules().has(id);
  const fired = story && story.fired[id] ? story.fired[id].filter(f => !stage || f.stage === stage) : [];
  const state = fired.some(f => f.state === "fail") ? "fail" : fired.length ? fired[fired.length - 1].state : "";
  const refused = story && story.refused[id];
  const head = r.title ? sentence(r.title).replace(/\.$/, "") : r.text ? r.text.replace(/\s+/g, " ").slice(0, 140) + (r.text.length > 140 ? "…" : "") : sentence(r.why || r.when);
  const body = !open ? "" : `<div class="rbody">` + (r.text
      ? `<p class="said"><span class="kw">Where</span> ${inline(clause(r.when))}</p>${prose(r.text)}`
      : (r.why ? `<p class="why">${inline(sentence(r.why))}</p>` : "")
        + `<p class="said"><span class="kw">When</span> ${inline(clause(r.when))}</p>`
        + (r.outcomes || []).map(o => `<p class="said s-${esc(o.state)}"><span class="kw">${icon(o.state)} ${esc(SAYS[o.state] || o.state)}</span> ${inline(clause(o.said))}${going(o.goes)}</p>`).join(""))
    + (fired.length ? `<p class="rec">this story: ${esc(fired.map(f => `${f.stage}: ${f.state}`).join(" · "))}${refused ? ` · refused ${refused}×` : ""}</p>` : "")
    + `<details class="src" data-fold="src:${esc(id)}"${foldOpen("src:" + id)}><summary>source</summary><p class="hint">${esc(r.source || "")}${r.bound ? (r.part === "instruction" ? " · placed in " : " · bound in ") + esc(r.bound) : ""}</p></details></div>`;
  return `<div class="rrow${open ? " open" : ""}"><button type="button" class="rhead" data-open-rule="${esc(id)}" aria-expanded="${open}">
    <span class="caret" aria-hidden="true">${open ? "▾" : "▸"}</span><span class="rgist">${inline(head)}</span>
    <span class="rid e-${esc(r.enforcement)}${state ? " f-" + esc(state) : ""}">${esc(id)}${refused ? `<span class="x">×${refused}</span>` : ""}</span></button>${body}</div>`;
}

function ruleGroup(label, ids, rules, story, stage) {
  if (!ids || !ids.length) return "";
  return `<div class="rgroup">${label ? `<div class="lbl">${esc(label)} <span class="n">${ids.length}</span></div>` : ""}${ids.map(id => ruleRow(id, rules, story, stage)).join("")}</div>`;
}

function waysLine(edges, title, rules) {
  if (!edges.length) return "";
  const named = id => (rules && rules[id] && rules[id].title) || id;
  return `<div class="rgroup"><div class="lbl">${esc(title)}</div>${edges.map(e => `<button type="button" class="way-link" data-edge="${esc(e.source)}>${esc(e.target)}>${esc(e.way)}">
    ${esc(e.source)} → ${esc(e.target)}</button> <span class="hint">${esc([...new Set(e.rules.map(r => named(r.rule)))].join(" · "))}</span>`).join("<br>")}</div>`;
}

function picked(flow, rules, story) {
  const graph = flow.graph || {edges: [], every_gate: [], anywhere: []}, p = S.flowPick;
  const ids = es => [...new Set(es.flatMap(e => e.rules.map(r => r.rule)))];
  if (!p) {
    return card("", "", `<p class="empty">Pick a step, a gate or a way in the drawing — its rules show here.</p>
      <p class="hint"><b>Four kinds of rule.</b> A <b>check</b> (GATE-…) is a question a gate asks after a stage — it passes or refuses. A <b>decision</b> (RUN-…) says where the story goes then: on, once more, back, or stop. A <b>pass</b> rule says what a passing gate does. What a stage is <b>told</b> (STAGE-…) is its instruction; no gate asks it directly.</p>
      <p class="hint">A teal dot is a gate: the checks between two steps. A dashed arc above is a round — a refused gate sends the story back into its step, three times at most. A way back appears below while the pointer is on its step. A red mark stops the run; a grey one waits for a person.</p>`);
  }
  if (p.type === "stage") {
    // a stage told as it runs: what it is told, the gate that asks, what a pass does, where a refusal sends it
    const step = flow.steps.find(s => s.stage === p.stage) || {gate_before: [], told: [], gate_after: [], passed: [], decided: []};
    const at = flow.steps.findIndex(s => s.stage === p.stage), next = (flow.steps[at + 1] || {}).stage || "delivered";
    const own = e => e.source === p.stage;
    const round = graph.edges.find(e => own(e) && e.way === "again"), on = graph.edges.find(e => own(e) && e.way === "on" && e.rules.length);
    const out = graph.edges.filter(e => own(e) && e.way === "back"), into = graph.edges.filter(e => e.target === p.stage && e.way === "back");
    const stops = graph.edges.filter(e => own(e) && (e.way === "stop" || e.way === "waits"));
    const named = new Set([round, on, ...out, ...stops].filter(Boolean).flatMap(e => e.rules.map(r => r.rule)));
    const rest = (step.decided || []).filter(id => !named.has(id));
    let n = 0;
    const part = (title, body) => body ? `<div class="part"><div class="part-head"><span class="num">${++n}</span>${title}</div>${body}</div>` : "";
    return card(esc(p.stage), (step.window || "") + (step.gate === "none" ? " · decides with its verdict, no gate" : ""),
      part("Before it — the gate before the stage asks; a refusal keeps it from starting", ruleGroup("", step.gate_before, rules, story, p.stage))
      + part(`It is told <span class="hint">— ${(step.told || []).length} instructions</span>`, foldGroup(`told:${p.stage}`, "show what it is told", step.told, rules, story, p.stage))
      + part(`The gate after it asks <span class="hint">— ${(step.gate_after || []).length} checks, each can refuse</span>`, foldGroup(`checks:${p.stage}`, "show the checks", step.gate_after, rules, story, p.stage))
      + part(step.gate === "none" ? "Its verdict decides" : "When the gate passes",
          ruleGroup("", [...(step.passed || []), ...(on ? on.rules.map(r => r.rule) : [])], rules, story, p.stage)
          + `<p class="then">→ on to <b>${esc(next)}</b></p>`)
      + part(step.gate === "none" ? "When it asks for changes" : "When a check refuses",
          (round ? ruleGroup("once more into this stage", ids([round]), rules, story, p.stage) : "")
          + waysLine(out, "back to an earlier stage", rules) + (stops.length ? ruleGroup("stop, or wait for a person", ids(stops), rules, story, p.stage) : ""))
      + part("The runner also decides here", ruleGroup("", rest, rules, story, p.stage))
      + (into.length ? `<div class="part">${waysLine(into, "ways back to this stage", rules)}</div>` : ""));
  }
  if (p.type === "gate") {
    const [where, stage] = p.gate.split(":"), step = flow.steps.find(s => s.stage === stage) || {};
    const round = graph.edges.find(e => e.source === stage && e.target === stage && e.way === "again");
    return card(`gate ${esc(where === "gate-before" ? "before" : "after")} ${esc(stage)}`,
      where === "gate-before" ? "a refused check keeps the stage from starting" : "a refused check sends the story once more into its step",
      ruleGroup("1 · its checks — each can refuse", (where === "gate-before" ? step.gate_before : step.gate_after) || [], rules, story, stage)
      + (where === "gate-after" && round ? ruleGroup("2 · when one refuses — what decides where the story goes", ids([round]), rules, story, stage) : "")
      + ruleGroup("also at every gate", flow.every_gate, rules, story, stage));
  }
  const edge = graph.edges.concat(graph.every_gate || [], graph.anywhere || []).find(e => `${e.source}>${e.target}>${e.way}` === p.key);
  if (p.way === "again") {
    const step = flow.steps.find(s => s.stage === p.source) || {};
    return card(`${esc(p.source)} once more`, step.gate === "after" ? "a refused check of its gate sends the story back into it" : "the stage runs again",
      ruleGroup("what sends it once more", edge ? ids([edge]) : [], rules, story, p.source)
      + (step.gate === "after" ? ruleGroup(`the checks of the gate after ${p.source} — each can refuse`, step.gate_after, rules, story, p.source) : ""));
  }
  return card(`${esc(p.source)} → ${esc(p.target)}`, esc(p.way), ruleGroup("the rules that take it", edge ? ids([edge]) : [], rules, story, p.source));
}

// a folded part stays as the person left it: the page draws itself again on every refresh
const folds = () => S.folds || (S.folds = new Set());
const foldOpen = key => folds().has(key) ? " open" : "";
document.addEventListener("toggle", event => {
  const at = event.target;
  if (!at.dataset || !at.dataset.fold) return;
  if (at.open) folds().add(at.dataset.fold); else folds().delete(at.dataset.fold);
}, true);

function foldGroup(key, label, ids, rules, story, stage) {
  if (!ids || !ids.length) return "";
  return `<details class="fold" data-fold="${esc(key)}"${foldOpen(key)}><summary>${esc(label)} (${ids.length})</summary>${ruleGroup("", ids, rules, story, stage)}</details>`;
}

function folded(title, sub, ids, rules, story) {
  if (!ids || !ids.length) return "";
  return `<details class="card more" data-fold="${esc(title)}"${foldOpen(title)}><summary><h2>${esc(title)} <span class="sub">${ids.length} rules — ${esc(sub)}</span></h2></summary>`
    + ruleGroup("", ids, rules, story) + `</details>`;
}

// a story laid over the drawing: the steps its gates ran at, where it stands, which gate refused it and how often
function storyMarks(flow, story) {
  if (!story) return null;
  // the steps run in order: every step before the last one the story's gates ran at was reached too (a judge has none)
  const ran = new Set(Object.values(story.fired).flat().map(f => f.stage));
  const last = Math.max(-1, ...flow.steps.map((s, i) => ran.has(s.stage) ? i : -1));
  const reached = new Set([...ran, ...flow.steps.slice(0, last + 1).map(s => s.stage)]);
  const at = story.refused_at || {};
  const gates = flow.steps.filter(s => s.gate === "after").map(s => {
    const refused = Object.values(at[s.stage] || {}).reduce((n, k) => n + k, 0);
    const failed = (s.gate_after || []).some(id => (story.fired[id] || []).some(f => f.stage === s.stage && f.state === "fail"));
    return {stage: s.stage, refused, failed};
  });
  return {reached, gates};
}

function storyLine(st, flow, story) {
  if (!story) return "";
  const row = (st.rows || []).find(r => r.story === story.id) || {};
  const marks = storyMarks(flow, story), refused = marks.gates.filter(g => g.refused);
  const other = [...marks.reached].filter(name => !flow.steps.some(s => s.stage === name));
  return `<p class="storyline"><b>${esc(story.id)}</b> — ${esc(row.state || "")}${row.stage && row.stage !== "—" ? `, now at <b>${esc(row.stage)}</b>` : ""}.
    ${refused.length ? "Refused: " + refused.map(g => `${esc(g.stage)} ×${g.refused}`).join(", ") + "." : "No gate refused it."}
    ${other.length ? `<span class="hint">It also ran ${esc(other.join(", "))} — another kind's steps; pick that kind to see them.</span>` : ""}</p>`;
}

function rulesTab(st) {
  if (!S.rules) { loadRules(); return card("", "", `<p class="empty">Reading the rules…</p>`); }
  const v = S.rules, rules = Object.fromEntries((v.rules || []).map(r => [r.id, r]));
  const story = v.story || null;
  const kinds = Object.keys(v.flow || {});
  if (story && S.kindFor !== story.id) {
    S.kindFor = story.id;
    const ran = new Set(Object.values(story.fired).flat().map(f => f.stage));
    const fits = kinds.filter(k => [...ran].every(st => v.flow[k].steps.some(s => s.stage === st)))
      .sort((a, b) => v.flow[a].steps.length - v.flow[b].steps.length);
    if (fits.length) S.ruleKind = fits[0];
  }
  const kind = kinds.includes(S.ruleKind) ? S.ruleKind : kinds[0];
  const flow = (v.flow || {})[kind] || {steps: [], edges: [], every_gate: []};
  const stories = (st.rows || []).map(r => r.story);
  const picks = `<div class="pick"><span class="seg">${kinds.map(k => `<button aria-pressed="${k === kind}" data-flow="${esc(k)}">${esc(k)}</button>`).join("")}</span>
    <select data-overlay aria-label="a story's gate runs"><option value="">no story</option>${stories.map(id => `<option${id === S.ruleStory ? " selected" : ""}>${esc(id)}</option>`).join("")}</select></div>`;
  return card(`${esc(kind)}`, `${(v.rules || []).length} rules`, picks + storyLine(st, flow, story) + (flow.svg_one_at_a_time ? `<div class="flowsvg">${flow.svg_one_at_a_time}</div>` : ""))
    + picked(flow, rules, story)
    + folded("At every gate", "the checks each gate of this flow runs as well", flow.every_gate, rules, story)
    + folded("Anywhere in a run", "what stops a run or waits for a person at any step",
             [...new Set(((flow.graph || {}).anywhere || []).flatMap(e => e.rules.map(r => r.rule)))], rules, story)
    + `<details class="card more" data-fold="outside"${foldOpen("outside")}><summary><h2>Outside the stages <span class="sub">${(v.outside || []).length} rules — the whole run, the commit hook, every stage alike</span></h2></summary>`
    + ruleGroup("", v.outside || [], rules, story) + `</details>`
    + ((v.problems || []).length ? card("Problems", "the rulebook itself", `<ul>${v.problems.map(p => `<li>${esc(p)}</li>`).join("")}</ul>`) : "");
}

// the drawing: a way back shows while its step is hovered; what is picked stays marked
function showBacks(test) {
  document.querySelectorAll(".flowsvg .way-back").forEach(g => g.classList.toggle("show", test(g)));
}
// a gate after a step and its round are one thing: the gate, and where a refusal of it sends the story
const gated = stage => { const f = S.rules && S.rules.flow && S.rules.flow[S.ruleKind]; const s = f && f.steps.find(x => x.stage === stage); return !!s && s.gate === "after"; };
const flowKey = g => g.dataset.gate ? "gate:" + g.dataset.gate : g.dataset.stage && !g.dataset.way ? "stage:" + g.dataset.stage
  : g.dataset.way === "again" && gated(g.dataset.source) ? "gate:gate-after:" + g.dataset.source
  : `${g.dataset.source}>${g.dataset.target}>${g.dataset.way}`;
function paintFlow() {
  const backs = new Set([...document.querySelectorAll(".flowsvg .way-back")].map(g => g.dataset.source));
  document.querySelectorAll(".flowsvg [data-stage]").forEach(t => t.classList.toggle("has-back", backs.has(t.dataset.stage)));
  const key = S.flowPick ? S.flowPick.key : "";
  document.querySelectorAll(".flowsvg").forEach(f => f.classList.toggle("has-pick", !!key));
  document.querySelectorAll(".flowsvg .way, .flowsvg .gate, .flowsvg [data-stage]").forEach(g => g.classList.toggle("sel", !!key && flowKey(g) === key));
  const v = S.rules, flow = v && v.flow && v.flow[S.ruleKind], marks = flow ? storyMarks(flow, v.story) : null;
  const row = marks && S.status ? (S.status.rows || []).find(r => r.story === v.story.id) : null;
  document.querySelectorAll(".flowsvg").forEach(f => f.classList.toggle("has-story", !!marks));
  document.querySelectorAll(".flowsvg .ov-badge").forEach(t => t.remove());
  document.querySelectorAll(".flowsvg [data-stage]").forEach(t => {
    t.classList.toggle("ov-reached", !!marks && marks.reached.has(t.dataset.stage));
    t.classList.toggle("ov-now", !!row && row.stage === t.dataset.stage);
  });
  document.querySelectorAll(".flowsvg .gate").forEach(g => {
    const [, stage] = (g.dataset.gate || "").split(":"), at = marks ? marks.gates.find(x => x.stage === stage) : null;
    g.classList.toggle("ov-failed", !!at && at.failed);
    if (at && at.refused) {
      const c = g.querySelector("circle"), t = document.createElementNS("http://www.w3.org/2000/svg", "text");
      t.setAttribute("x", +c.getAttribute("cx") + 14); t.setAttribute("y", +c.getAttribute("cy") - 12);
      t.setAttribute("class", "ov-badge"); t.textContent = `×${at.refused}`; g.appendChild(t);
    }
  });
  if (S.flowPick && S.flowPick.type === "stage") showBacks(g => g.dataset.source === S.flowPick.stage);
  else if (S.flowPick && S.flowPick.way === "back") showBacks(g => flowKey(g) === S.flowPick.key);
}
document.addEventListener("mouseover", event => {
  const at = event.target.closest && event.target.closest(".flowsvg [data-stage]");
  if (at) showBacks(g => g.dataset.source === at.dataset.stage);
});
document.addEventListener("mouseout", event => {
  const at = event.target.closest && event.target.closest(".flowsvg [data-stage]");
  if (at) { showBacks(() => false); paintFlow(); }
});
function pickInFlow(at) {
  const key = flowKey(at);
  if (S.flowPick && S.flowPick.key === key) S.flowPick = null;
  else if (at.dataset.gate) S.flowPick = {key, type: "gate", gate: at.dataset.gate};
  else if (key.startsWith("gate:")) S.flowPick = {key, type: "gate", gate: key.slice(5)};
  else if (at.dataset.stage && !at.dataset.way) S.flowPick = {key, type: "stage", stage: at.dataset.stage};
  else S.flowPick = {key, type: "edge", source: at.dataset.source, target: at.dataset.target, way: at.dataset.way};
  render();
}
document.addEventListener("click", event => {
  const rule = event.target.closest && event.target.closest("[data-open-rule]");
  if (rule) {
    event.stopPropagation();
    const id = rule.dataset.openRule, open = pickedRules();
    if (open.has(id)) open.delete(id); else open.add(id);
    return render();
  }
  const edge = event.target.closest && event.target.closest("[data-edge]");
  if (edge) {
    event.stopPropagation();
    const [source, target, way] = edge.dataset.edge.split(">");
    S.flowPick = {key: edge.dataset.edge, type: "edge", source, target, way};
    return render();
  }
  const at = event.target.closest && event.target.closest(".flowsvg [data-rules], .flowsvg [data-stage]");
  if (!at) return;
  event.stopPropagation();
  pickInFlow(at);
}, true);

// --- the spec: what holds, per context — its domain model, its features, rules and scenarios ---------------------------
async function loadSpec() {
  if (S.spec || S.specLoading) return;
  S.specLoading = true;
  if (await load("spec", "/api/view/spec")) render();
  S.specLoading = false;
}

// a scenario's step as a sentence: its Gherkin keyword set apart
const step = line => { const m = String(line).match(/^\s*-\s*(Given|When|Then|And|But)\b\s*(.*)$/);
  return m ? `<p class="said"><span class="kw">${esc(m[1])}</span> ${inline(m[2])}</p>` : `<p class="said">${inline(String(line).replace(/^\s*-\s*/, ""))}</p>`; };

function scenario(item) {
  const open = (S.openScenarios || (S.openScenarios = new Set())).has(item.key);
  const heading = item.form === "line" ? item.lines.join(" ").replace(/\s+/g, " ").replace(/^-\s*[a-z0-9-]+:\s*/, "") : item.key.replace(/-/g, " ");
  const h = item.health || null;
  const proof = !h ? "" : h.proof === "orphaned" ? `<span class="pend p-gone" title="${esc(h.missing.join(", "))}">test gone</span>`
    : h.proof === "untested" ? `<span class="pend p-gone">no test</span>` : "";
  const changes = proof + item.changed_by.map(c => `<span class="pend p-${esc(c.verdict)}" title="${esc(c.title)} (${esc(c.status)})">${esc(c.verdict)} by ${esc(c.story)}</span>`).join(" ");
  const body = !open ? "" : `<div class="rbody">${item.form === "scenario" ? item.lines.slice(1).map(step).join("") : ""}
    <p class="hint">${item.tests.length ? "test: " + item.tests.map(t => esc(t) + (h && h.missing.includes(t) ? " <b>— not in the code</b>" : "")).join(", ") : "no test named"} · <code>${esc(item.key)}</code>
      · ${h && h.delivered_by ? `delivered by ${esc(h.delivered_by.story)}${h.delivered_by.how ? " (" + esc(h.delivered_by.how) + ")" : ""}` : "no delivered story brought it"}</p>
    ${item.fix ? `<div class="spec-act">${act(item.fix, "s")}</div>` : ""}
    ${item.change ? `<div class="spec-act">${act(item.change, "s")}</div>` : ""}</div>`;
  return `<div class="rrow${open ? " open" : ""}"><button type="button" class="rhead" data-open-scenario="${esc(item.key)}" aria-expanded="${open}">
    <span class="caret" aria-hidden="true">${open ? "▾" : "▸"}</span><span class="rgist">${inline(heading)}</span><span>${changes}</span></button>${body}</div>`;
}

// a context as the designed domain and the spec hold it: an ink head with its numbers, then its course — 1 its model
// as a profile by kind, 2 its features as cards, each rule a line above its criteria
const KIND_LABEL = {"aggregate": "aggregate", "entity": "entities", "identity": "ids", "value object": "values", "domain event": "events",
  "domain service": "services", "domain gateway": "gateways", "specification": "specifications", "factory": "factories",
  "read model": "read models", "failure": "failures", "concept": "concepts", "other": "other"};
const subdomainClass = sd => /core/i.test(sd) ? "core" : /generic/i.test(sd) ? "gen" : "sup";

function specContext(c) {
  const facts = modelFacts(c.model);
  const features = c.features.map(f => {
    const key = `feature:${c.context}:${f.feature}`, count = f.rules.reduce((n, r) => n + r.criteria.length, 0);
    const pending = f.rules.reduce((n, r) => n + r.criteria.filter(x => x.changed_by.length).length, 0);
    return `<details class="dm-group" data-fold="${esc(key)}"${foldOpen(key)}><summary><b>${esc(f.feature || "the context itself")}</b>
      <span>${count}${pending ? ` · ${pending} changed` : ""}</span></summary>`
      + f.rules.map(r => (r.rule ? `<div class="dm-rule">${inline(r.rule)}</div>` : "") + r.criteria.map(scenario).join("")).join("")
      + (f.add ? `<div class="spec-act">${act(f.add, "s")}</div>` : "") + `</details>`;
  }).join("");
  const coming = c.coming.length ? `<div class="rgroup"><div class="lbl">coming — new criteria of open stories</div>${c.coming.map(s =>
    `<p class="said"><span class="pend p-adds">${esc(s.status)}</span> ${story(s.story)} — ${s.keys.map(k => `<code>${esc(k.key)}</code>`).join(", ")}</p>`).join("")}</div>` : "";
  return `<div class="dm"><div class="dm-track">
    <div class="dm-node"><span class="n">1</span>Domain model<span class="hint">from its glossary</span></div>
    ${facts ? `<dl class="dm-facts">${facts}</dl>` : `<p class="hint">The glossary names no term of a model.</p>`}
    <div class="dm-node"><span class="n">2</span>Features<span class="hint">what holds, by rule</span></div>
    ${features || `<p class="hint">No criterion holds yet.</p>`}${coming}
    ${c.add ? `<details class="fold" data-fold="addfeature:${esc(c.context)}"${foldOpen("addfeature:" + c.context)}><summary>add a feature</summary><div class="spec-act">${act(c.add, "s")}</div></details>` : ""}
  </div></div>`;
}

// how a context stands over the whole of it: tests gone or missing, criteria no delivered story brought
function healthCell(h) {
  if (!h) return "";
  const bad = [h.orphaned ? `<span class="pend p-gone">${h.orphaned} test gone</span>` : "", h.untested ? `<span class="pend p-gone">${h.untested} no test</span>` : ""].filter(Boolean);
  return (bad.length ? bad.join(" ") : `<span class="hint">all tested</span>`) + (h.undelivered ? ` <span class="hint" title="adopted, delivered by hand without a story, or written before the factory">· ${h.undelivered} not from a story</span>` : "");
}

// a model as its kinds, each a row of chips; a shared term in the kernel's colour, saying who uses it
const modelFacts = model => model.map(g => `<dt>${esc(KIND_LABEL[g.kind] || g.kind)}</dt><dd>${g.terms.map(t =>
  `<span class="chip${t.shared ? " shared" : ["concept", "other"].includes(g.kind) ? " minor" : ""}" title="${esc([t.meaning, t.shared ? "shared kernel" : "", (t.used_by || []).length ? "used by " + t.used_by.join(", ") : ""].filter(Boolean).join(" — "))}">${esc(t.name)}</span>`).join("")}</dd>`).join("");
function kernelBlock(k) {
  if (!k) return "";
  return `<div class="dm-kernel"><div class="top"><b>Shared kernel</b><span class="hint">what every context shares, the same in each — no context of its own</span></div>
    <dl class="dm-facts">${modelFacts(k.model)}</dl></div>`;
}

function domainCard() {
  if (!S.spec) { loadSpec(); return card("Domain", "", `<p class="empty">Reading the contexts…</p>`); }
  const open = S.openContexts || (S.openContexts = new Set());
  const rows = (S.spec.contexts || []).map(c => {
    const isOpen = open.has(c.context), pending = c.features.reduce((n, f) => n + f.rules.reduce((m, r) => m + r.criteria.filter(x => x.changed_by.length).length, 0), 0) + c.coming.length;
    return `<tr class="epic-row ctx-row${isOpen ? " open ink-open" : ""}" data-context="${esc(c.context)}" tabindex="0" aria-expanded="${isOpen}">
      <td><span class="caret" aria-hidden="true">${isOpen ? "▾" : "▸"}</span> <span class="title">${esc(c.context)}</span>${c.subdomain ? `<div class="sd"><span class="pill ${subdomainClass(c.subdomain)}">${esc(c.subdomain)}</span></div>` : ""}</td>
      <td class="hide-s">${esc(c.purpose)}</td><td class="num">${c.features.length}</td><td class="num">${c.criteria}</td>
      <td class="num">${pending ? `<span class="pend p-changes">${pending}</span>` : "—"}</td>
      <td class="hide-s">${healthCell(c.health)}</td></tr>`
      + (isOpen ? `<tr class="epic-body"><td colspan="6">${specContext(c)}</td></tr>` : "");
  }).join("");
  return card("Domain", "the contexts as designed, and what holds in each — the model from its glossary, the features as the gate delivered them",
    kernelBlock(S.spec.shared_kernel) + (rows ? `<table class="epics"><tr><th>context</th><th class="hide-s">what it is for</th><th class="num">features</th><th class="num">criteria</th><th class="num">open changes</th><th class="hide-s">health</th></tr>${rows}</table>`
      : `<p class="empty">No spec yet — what holds is written by the stories the gate delivers.</p>`));
}
document.addEventListener("click", event => {
  const row = event.target.closest && event.target.closest("tr.ctx-row");
  if (row && !event.target.closest("button, a")) {
    event.stopPropagation();
    const open = S.openContexts || (S.openContexts = new Set()), id = row.dataset.context;
    if (open.has(id)) open.delete(id); else open.add(id);
    return render();
  }
  const sc = event.target.closest && event.target.closest("[data-open-scenario]");
  if (sc) {
    event.stopPropagation();
    const open = S.openScenarios || (S.openScenarios = new Set()), id = sc.dataset.openScenario;
    if (open.has(id)) open.delete(id); else open.add(id);
    render();
  }
}, true);

// on every tab: the factory that ended on its own, and why
function endedLine(st) {
  const gone = st.ended;
  return gone ? `<div class="next ended"><div class="text"><span class="arrow">!</span>${esc(gone.text)}${gone.log ? ` <span class="hint">${esc(gone.log)}</span>` : ""}</div>
    <button class="btn primary nogo" data-call="up">▶ start the backlog</button></div>` : "";
}

// whether the backlog runs: a runner from a terminal or a session's, or the factory's worker with the backlog on
const backlogOn = st => { const w = st.worker; return !!(w && w.alive && (w.how !== "up" || w.backlog)); };

function card(title, sub, body) {
  const head = title ? `<h2>${title}${sub ? ` <span class="sub">${sub}</span>` : ""}</h2>` : "";
  return `<section class="card">${head}${body}</section>`;
}

// --- now: where it stands --------------------------------------------------------------------------------------------
// The cycle as four columns, each as the factory says it: its count, one line, the one item that matters most there and
// the one action at its foot. Then the inflow — the wish part —, the last deliveries and what may wait.
const when = text => {
  const day = String(text || "").slice(0, 10), today = new Date().toISOString().slice(0, 10);
  return !day ? "" : day === today ? `today ${String(text).slice(11)}` : day;
};
function column(c) {
  const count = c.column === "delivered" ? `${c.count}<small class="of"> / ${c.total}</small>` : `${c.count}`;
  const line = c.column === "delivered"
    ? `<div class="sub2 prog" role="img" aria-label="${c.count} of ${c.total} stories delivered, ${c.percent} percent"><span class="thin"><i style="width:${c.percent}%"></i></span>${esc(c.line)}</div>`
    : `<div class="sub2">${esc(c.line)}</div>`;
  const item = c.title ? `<div class="one">${c.story ? story(c.story, c.title) : esc(c.title)}${c.sub ? `<span class="id">${esc(c.sub)}</span>` : ""}</div>` : "";
  const last = c.last_text ? `<div class="one">last ${esc(when(c.last_text))}</div>` : "";
  const press = !c.action ? "" : c.action.call ? `<button class="btn primary nogo" data-call="${esc(c.action.call)}">${esc(c.action.label)}</button>` : act(c.action);
  const all = c.column === "delivered" ? `<button class="link to" data-tab="delivered">all →</button>` : "";
  return `<div class="colw"><div class="col${c.hot ? " hot" : ""}"><h3><button class="link" data-tab="${esc(c.column)}">${esc(c.column)}</button><span class="c">${count}</span></h3>
    ${line}${last}${item}<div class="acts">${press}${all}</div></div></div>`;
}
function now(st) {
  const rows = Object.fromEntries((st.rows || []).map(r => [r.story, r]));
  const recent = (st.delivered_order || []).slice(0, 3).map(id => rows[id]).filter(Boolean).map(r => `<li><span class="mark m-done" aria-hidden="true">✓</span>
    <span class="what">${story(r.story, r.title)}<span class="id">${esc(r.epic)}</span></span><span class="r">${esc(when(r.delivered_text))}<br>${esc(r.cost_text || "")}</span></li>`).join("");
  const sums = [st.cost_text, st.seconds_text].filter(Boolean).join(" · ");
  const findings = (st.findings || []).length;
  return `<div class="board">${(st.now || []).map(column).join("")}</div>`
    + `<div class="inflow"><span class="lab">Inflow →</span><span class="hint">a wish, a discovery, a finding, an epic's journey fill the backlog</span></div>`
    + wishCard(st, true)
    + (recent ? card("Last delivered", sums ? `${esc(sums)} in all` : "", `<ul class="list">${recent}</ul><button class="link to" data-tab="delivered">delivered →</button>`) : "")
    + (findings ? `<p class="quietline">Beside that: <button class="link" data-tab="backlog">${findings} open finding${findings > 1 ? "s" : ""} beside their stories →</button></p>` : "");
}

// --- the wish: one part wherever it stands, the field and the trail of what became of each wish ------------------------
function wishCard(st, tight) {
  const trail = ((S.requests || {}).wishes || []).map(w => {
    const since = w.state === "running" && w.started ? ` — ${Math.max(0, Math.round((Date.now() - Date.parse(w.started)) / 1000))} s` : "";
    const ops = (w.operations || []).map(op => `<button class="btn small${op.name === "drop" ? " danger" : ""}" data-call="${esc(op.name)}" data-kind="request" data-id="${esc(w.id)}"${op.name === "hide" ? ` title="hide it here; the draft stays in the backlog" aria-label="hide"` : ""}>${esc(op.label)}</button>`).join("");
    const answer = w.state === "waiting" ? `<button class="btn small primary" data-tab="${esc(w.place)}">answer</button>` : "";
    const open = (w.made || []).slice(0, 1).map(m => `<button class="btn small" data-story="${esc(m.id)}">open</button>`).join("");
    const glyph = {ok: "✓ ", ask: "? ", bad: "✗ "}[w.tone] || "";
    return `<li><span class="g" aria-hidden="true">✦</span><span class="w"><q>${esc(w.words)}</q>
      <span class="s ${esc(w.tone)}">${w.tone === "wait" ? `<span class="spin" aria-hidden="true"></span>` : ""}${esc(glyph + w.text + since)}${w.by ? ` · ${esc(w.by)}` : ""}</span></span>
      <span class="a">${answer}${acts(w.actions, "s")}${open}${ops}</span></li>`;
  }).join("");
  return `<section class="card wish"${tight ? ` style="margin-top:12px"` : ""}><h2>A wish <span class="sub">your words become a story, a task or a finding settled — a draft until you release it</span></h2>`
    + act((st.entries || {}).wish) + (trail ? `<ul class="trail" aria-label="the wishes">${trail}</ul>` : "") + `</section>`;
}

// --- 0 describe ----------------------------------------------------------------------------------------------------
// a part of the description opens in place and reads as written, section by section
async function loadPart(name) {
  try { S.partText[name] = await api(`/api/view/part?id=${encodeURIComponent(name)}`); }
  catch (e) { S.partText[name] = {error: e.message}; }
  render();
}
function partBody(name) {
  const v = S.partText[name];
  if (!v || v.loading) {          // one read at a time, whatever redraws meanwhile
    if (!v) { S.partText[name] = {loading: true}; loadPart(name); }
    return `<p class="empty">Reading ${esc(name)}…</p>`;
  }
  if (v.error) return `<p class="m-stopped">${esc(v.error)}</p>`;
  return v.sections.length ? v.sections.map(sec => `<h3>${esc(sec.heading)}</h3><div class="prose">${prose(sec.text) || `<p class="empty">empty</p>`}</div>`).join("")
    : `<p class="empty">${esc(v.path)} is missing.</p>`;
}

function describe(st) {
  const open = S.openParts || (S.openParts = new Set());
  S.partText = S.partText || {};
  const parts = (st.description || []).map(p => {
    const isOpen = open.has(p.part);
    return `<tr class="epic-row part-row${isOpen ? " open" : ""}" data-part="${esc(p.part)}" tabindex="0" aria-expanded="${isOpen}"><td>${mark(p.mark)}</td>
    <td><span class="caret" aria-hidden="true">${isOpen ? "▾" : "▸"}</span> <span class="title">${esc(p.part)}</span><div class="id">${esc(p.path)}</div></td>
    <td>${p.present ? esc((p.sections || []).join(" · ")) : `<span class="empty">missing</span>`}
    ${(p.missing || []).length ? `<div class="rec">missing: ${esc(p.missing.join(", "))}</div>` : ""}
    ${(p.empty || []).length ? `<div class="rec">empty: ${esc(p.empty.join(", "))}</div>` : ""}</td></tr>`
      + (isOpen ? `<tr class="epic-body"><td></td><td colspan="2">${partBody(p.part)}</td></tr>` : "");
  }).join("");
  return card("The parts", "written by you, through the description — what is built, how, and in which domain; open one to read it", `<table class="epics"><tr><th><span class="sr">state</span></th><th>part</th><th>sections</th></tr>${parts}</table>`)
    + domainCard()
    + card("Change the description", "", `<p class="about">In your words — <code>&lt;part&gt;: &lt;change&gt;</code> where it is one part. Where it needs a decision of yours, it asks here.</p>${act((st.entries || {}).describe)}`)
    + ((S.decisions || {}).records || []).filter(r => (r.actions || []).length && r.place === "describe").map(recordCard).join("");
}
document.addEventListener("click", event => {
  const row = event.target.closest && event.target.closest("tr.part-row");
  if (!row || event.target.closest("button, a")) return;
  const open = S.openParts || (S.openParts = new Set()), name = row.dataset.part;
  if (open.has(name)) open.delete(name); else { open.add(name); delete (S.partText || {})[name]; }
  render();
});

// --- 1 discover ----------------------------------------------------------------------------------------------------
// a discovery opens in place like a context: its report, what it proposes, and words that continue it
function discoveryBody(t) {
  const proposals = t.proposals.map(p => `<div class="proposal"><b>${esc(p.goal || p.intent || p.id)}</b>
      ${p.goal && p.intent ? `<span>${esc(p.intent)}</span>` : ""}
      <div class="ev">${p.metric ? `<span class="event">${esc(p.metric)}</span>` : ""}${p.domain_contact ? `<span>asks ${esc(p.domain_contact)}</span>` : ""}<span class="id">${esc(p.id)}</span></div>
      ${p.epic ? `<div><span class="tone ok">epic ${esc(p.epic)}</span></div>` : `<div class="acts">${acts(p.actions)}</div>`}</div>`).join("");
  const changes = t.description_changes.map(c => `<tr><td><div class="title">${esc(c.target)}</div></td>
      <td>${esc(c.change)}<div class="id">${esc(c.why)}</div></td><td class="act"><div class="acts">${acts(c.actions)}</div></td></tr>`).join("");
  const report = (t.sections || []).filter(sec => !/^proposed /i.test(sec.heading))
    .map(sec => `<h3>${esc(sec.heading)}</h3>${prose(sec.text)}`).join("");
  return `<div class="dm"><div class="dm-track">
    <div class="dm-node"><span class="n">1</span>The report<span class="hint">${esc(t.report)}</span></div>
    ${report || `<p class="empty">The report says nothing beyond what it proposes.</p>`}
    <div class="dm-node"><span class="n">2</span>Proposed epics<span class="hint">${t.proposals.length}, each an epic once you make it one</span></div>
    ${proposals ? `<div class="proposals">${proposals}</div>` : `<p class="empty">No proposed work.</p>`}
    ${changes ? `<div class="dm-node"><span class="n">3</span>Changes to the description<span class="hint">applied one by one, through the description</span></div><table>${changes}</table>` : ""}
    <div class="dm-node"><span class="n">${changes ? 4 : 3}</span>Continue this discovery<span class="hint">a question, a document, a wish — the report grows</span></div>
    ${acts(t.actions, "s")}
  </div></div>`;
}

function discover(st) {
  const topics = (S.discover || {}).topics || [], open = S.openTopics || (S.openTopics = new Set());
  const rows = topics.map(t => {
    const isOpen = open.has(t.topic), made = t.proposals.filter(p => p.epic).length;
    return `<tr class="epic-row topic-row${isOpen ? " open ink-open" : ""}" data-topic="${esc(t.topic)}" tabindex="0" aria-expanded="${isOpen}">
      <td><span class="caret" aria-hidden="true">${isOpen ? "▾" : "▸"}</span> <span class="title">${esc(t.title)}</span><div class="id">${esc(t.topic)}</div></td>
      <td class="num">${t.proposals.length}</td><td class="num">${made}</td><td class="num hide-s">${t.description_changes.length}</td></tr>`
      + (isOpen ? `<tr class="epic-body"><td colspan="4">${discoveryBody(t)}</td></tr>` : "");
  }).join("");
  // a discovery on its way: where it stands and its output, until its report stands below
  const tone = {queued: "mute", running: "wait", waiting: "wait"};
  const working = ((S.discover || {}).working || []).map(r => `<div class="ticket"><div class="what"><b>${esc(r.topic || "new")}</b>
      <span class="tone ${tone[r.state] || "mute"}">${esc(r.state === "waiting" ? "asks you" : r.state)}</span><span>${esc(r.words)}</span></div>
      <div class="acts"><button class="btn small" data-call="follow" data-kind="request" data-id="${esc(r.id)}">follow</button></div></div>`).join("");
  // what a discovery asks back is answered where the discovery stands — the same record Decide lists
  const records = ((S.decisions || {}).records || []).filter(rec => (rec.actions || []).length);
  const asking = ((S.discover || {}).working || []).map(r => records.find(rec => r.record && rec.path === r.record))
    .filter(Boolean).map(recordCard).join("");
  return card("A new discovery", "a problem worth solving, or what should exist — the report and the epics it proposes", act((st.entries || {}).discover)
      + (working ? `<h3>In progress</h3><div class="queue">${working}</div>` : "") + asking)
    + card("Discoveries", "each topic with its report — open one to read it, act on what it proposes, or continue it",
      rows ? `<table class="epics"><tr><th>topic</th><th class="num">proposed</th><th class="num">epics made</th><th class="num hide-s">description changes</th></tr>${rows}</table>`
        : `<p class="empty">No discovery yet — it goes to ${esc((S.discover || {}).store || "")}.</p>`);
}
document.addEventListener("click", event => {
  const row = event.target.closest && event.target.closest("tr.topic-row");
  if (!row || event.target.closest("button, a")) return;
  const open = S.openTopics || (S.openTopics = new Set()), topic = row.dataset.topic;
  if (open.has(topic)) open.delete(topic); else open.add(topic);
  render();
});

// --- 2 backlog -----------------------------------------------------------------------------------------------------
function storyRow(r) {
  return `<tr><td>${mark(r.mark)}</td><td>${story(r.story, r.title)}<div class="id">${esc(r.story)}</div></td>
    <td>${esc(r.state)}</td><td class="hide-s">${esc(r.stage === "—" ? "" : r.stage)}</td>
    <td class="num hide-s">${esc(r.tokens_text)}</td><td class="act"><div class="acts">${acts(r.actions)}</div></td></tr>`;
}

// where a story stands, as a lane of its epic — the factory's `lane`
const LANES = ["draft", "approved", "running", "delivered"];
const laneOf = r => r.lane || "approved";
function storyCard(r) {
  const stage = r.stage && r.stage !== "—" ? ` · ${r.stage}` : "";
  return `<div class="scard l-${segment(r)}">${story(r.story, r.title)}<div class="id">${esc(r.state)}${esc(stage)}${r.delivered_text ? ` · ${esc(r.delivered_text)}` : ""}</div>
    ${(r.actions || []).length ? `<div class="acts">${acts(r.actions)}</div>` : ""}</div>`;
}
function lane(name, rows, order, epic) {
  if (name === "delivered") rows = rows.slice().sort((a, b) => order.indexOf(a.story) - order.indexOf(b.story));
  const shown = name === "delivered" ? rows.slice(0, 3) : rows, rest = rows.slice(shown.length);
  return `<div class="lane"><h4>${name} <span>${rows.length}</span></h4>${shown.map(storyCard).join("")}
    ${rest.length ? `<details data-fold="lane:${esc(epic)}:${name}"${foldOpen(`lane:${epic}:${name}`)}><summary>${rest.length} more</summary>${rest.map(storyCard).join("")}</details>` : ""}</div>`;
}
// a segment a story, in the lanes' order from left to right — draft, released, on its way, delivered —, the superseded
// last: the strip reads as the lanes beneath it
const STRIP = ["draft", "approved", "running", "stopped", "delivered", "superseded"];
const segment = r => r.mark === "stopped" ? "stopped" : laneOf(r);
const stripOf = rows => rows.map(segment).sort((a, b) => STRIP.indexOf(a) - STRIP.indexOf(b)).map(l => `<i class="l-${l}"></i>`).join("");
const STRIP_KEY = `<div class="legend"><span><i class="strip-key l-draft"></i>draft</span><span><i class="strip-key l-approved"></i>released</span>
  <span><i class="strip-key l-running"></i>on its way</span><span><i class="strip-key l-stopped"></i>stopped</span><span><i class="strip-key l-delivered"></i>delivered</span><span><i class="strip-key l-superseded"></i>superseded</span></div>`;
// what an epic needs first, in one word: stopped, waiting for a person, running, a draft to release, ready, done
function epicTone(e) {
  const n = m => e.rows.filter(r => r.mark === m && laneOf(r) !== "draft").length;
  const drafts = e.rows.filter(r => laneOf(r) === "draft").length, ready = e.rows.filter(r => r.state === "ready").length;
  if (n("stopped")) return `<span class="tone bad">${n("stopped")} stopped</span>`;
  if (n("look") + n("question")) return `<span class="tone wait">${n("look") + n("question")} waits for you</span>`;
  if (n("running")) return `<span class="tone wait">running</span>`;
  if (drafts) return `<span class="tone mute">${drafts} draft${drafts === 1 ? "" : "s"}</span>`;
  if (e.total && e.delivered === e.total) return `<span class="tone ok">delivered</span>`;
  return ready ? `<span class="tone mute">${ready} ready</span>` : "";
}

function backlog(st) {
  // the epics as one list, as the cockpit shows them; an epic opens its stories in place, and stays open on a redraw
  const open = S.openEpics || (S.openEpics = new Set()), filter = S.backlogFilter || "all", order = st.delivered_order || [];
  const keep = r => filter === "all" || (filter === "drafts" ? r.lane === "draft" : !["delivered", "superseded"].includes(r.lane));
  const shown = (st.epics || []).map(e => Object.assign({}, e, {rows: e.rows.filter(keep)}))
    .filter(e => filter === "all" || e.rows.length);
  const counts = {all: (st.epics || []).length,
    open: (st.epics || []).filter(e => e.rows.some(r => !["delivered", "superseded"].includes(r.lane))).length,
    drafts: (st.epics || []).filter(e => e.rows.some(r => r.lane === "draft")).length};
  const filters = `<div class="pick"><span class="seg">${["all", "open", "drafts"].map(f => `<button aria-pressed="${f === filter}" data-filter="${f}">${f}<span class="n">${counts[f]}</span></button>`).join("")}</span></div>`;
  const epics = shown.map(e => {
    const isOpen = open.has(e.epic) !== (filter !== "all"), full = (st.epics || []).find(x => x.epic === e.epic) || e;
    const head = `<div class="ehead" data-epic="${esc(e.epic)}" tabindex="0" role="button" aria-expanded="${isOpen}">
      <div class="name"><span class="caret" aria-hidden="true">${isOpen ? "▾" : "▸"}</span><b>${esc(e.title || e.epic)}</b><span class="id">${esc(e.epic)}</span>${e.metric ? `<span class="event">${esc(e.metric)}</span>` : ""}</div>
      <div class="meta">${epicTone(full)}<span>${full.delivered}/${full.total}</span></div>
      <div class="strip" title="${full.delivered} of ${full.total} delivered">${stripOf(full.rows)}</div></div>`;
    const body = !isOpen ? "" : `<div class="ebody">`
      + (e.goal ? `<p class="about">${esc(e.goal)}</p>` : "")
      + qualityLine(full.signals)
      + (e.rows.length ? `<div class="lanes">${LANES.map(name => lane(name, e.rows.filter(r => laneOf(r) === name || (name === "delivered" && laneOf(r) === "superseded")), order, e.epic)).join("")}</div>` : `<p class="empty">No story yet.</p>`)
      // the epic's own buttons, and beside them why one is offered — a delivered epic without its journey
      + `<div class="acts">${acts(e.actions)}${(st.journeys || []).filter(j => j.epic === e.epic).map(j => `<span class="hint">${esc(j.text)}</span>`).join("")}</div></div>`;
    return `<div class="erow">${head}${body}</div>`;
  }).join("");
  const findings = (st.findings || []).map(f => `<tr><td><span class="state">${esc(f.severity)}</span></td>
    <td>${esc(f.plain || f.defect)}<div class="id">${esc(f.row)} · ${esc(f.where)}</div></td><td class="act"><div class="acts">${act(f.action)}</div></td></tr>`).join("");
  return wishCard(st)
    + (epics || filter !== "all" ? card("Epics", filter === "all" ? "newest first — open one to see its stories by where they stand" : filter === "drafts" ? "the drafts, waiting for your release" : "what is not delivered yet",
        filters + STRIP_KEY + (epics ? `<div class="erows">${epics}</div>` : `<p class="empty">Nothing here.</p>`))
      : card("", "", `<p class="empty">The backlog is empty.</p>`))
    + (findings ? `<details class="card more" data-fold="findings"${foldOpen("findings")}><summary><h2>Findings <span class="sub">${(st.findings || []).length} the judge kept open — each to the backlog or done</span></h2></summary><table>${findings}</table></details>` : "");
}
document.addEventListener("click", event => {
  const row = event.target.closest && event.target.closest(".ehead");
  if (!row || event.target.closest("button, a")) return;
  const open = S.openEpics || (S.openEpics = new Set()), id = row.dataset.epic;
  if (open.has(id)) open.delete(id); else open.add(id);
  render();
});
document.addEventListener("click", event => {
  const f = event.target.closest && event.target.closest("[data-filter]");
  if (!f) return;
  S.backlogFilter = f.dataset.filter; S.openEpics = new Set(); render();
});
document.addEventListener("keydown", event => {
  const row = event.target.closest && event.target.closest("tr.epic-row, .ehead");
  if (row && (event.key === "Enter" || event.key === " ")) { event.preventDefault(); row.click(); }
});

// --- 3 run ---------------------------------------------------------------------------------------------------------
function run(st) {
  const w = st.worker, reqs = (S.requests || {}).requests || [];
  // the backlog is the one thing switched here: a person's requests are worked while this page is open (WP-177)
  const factory = (backlogOn(st) ? (w.stopping ? `<p class="about">Stopping after the running stage.</p>`
      : `<div class="acts"><button class="btn" data-call="down">■ stop the backlog — after the running stage</button>
      <button class="btn danger" data-call="down" data-now="1">■ stop now</button></div>`)
    : `<div class="acts"><button class="btn primary nogo" data-call="up">▶ start the backlog</button></div>`)
    + (w ? `<details class="more" data-fold="worker"${foldOpen("worker")}><summary class="hint">the worker</summary><dl class="kv"><dt>worker</dt><dd>${esc(w.owner)}</dd>
      <dt>since</dt><dd>${esc(w.since_text)}</dd>${w.log ? `<dt>log</dt><dd><code>${esc(w.log)}</code></dd>` : ""}</dl></details>` : "");
  const ops = r => (r.operations || []).map(op => `<button class="btn small${op.name === "drop" ? " danger" : ""}" data-call="${esc(op.name)}"
    data-kind="request" data-id="${esc(r.id)}">${esc(op.label)}</button>`).join("");
  const tone = {queued: "mute", running: "wait", waiting: "wait", failed: "bad"};
  const tickets = reqs.map(r => `<div class="ticket"><div class="what"><b>${esc(r.kind)}</b><span>${esc(r.target)}</span><span class="tone ${tone[r.state] || "mute"}">${esc(r.state)}</span></div>
    <div class="id">${esc(r.id)} · ${esc(r.by)}</div>
    ${r.error ? `<div class="m-stopped">${esc(r.error)}</div>` : ""}
    ${r.record ? `<div class="rec">asks: <code>${esc(r.record)}</code> — answer it under Decide</div>` : ""}
    ${ops(r) ? `<div class="acts">${ops(r)}</div>` : ""}</div>`).join("");
  const titles = Object.fromEntries((st.rows || []).map(r => [r.story, r.title]));
  // a story in flight as its course: running, or stopped where it goes on from, with why and what goes on
  const course = (id, tone, label, extra, acts) => `<div class="live"><div class="top"><div>${story(id, titles[id])}<div class="id">${esc(id)}</div></div>
      <div class="right"><span class="tone ${tone}">${esc(label)}</span>${acts}</div></div>
      ${extra.course && extra.course.length ? `<div class="stepper">${extra.course.map(c => `<div class="st ${c.state}"><i></i>${esc(c.stage)}</div>`).join("")}</div>` : ""}
      ${extra.doing ? `<div class="doing">${esc(extra.doing)}</div>` : ""}</div>`;
  const follows = id => `<button class="btn small" data-call="follow" data-kind="story" data-id="${esc(id)}">follow</button>`;
  const live = (st.running || []).map(r => course(r.story, r.interrupted ? "bad" : "wait",
      r.interrupted ? "interrupted" : `${r.part || r.stage}${r.round > 1 ? ` · round ${r.round}` : ""}`,
      {course: r.course, doing: r.activity}, `<span class="hint">${esc(r.ago || "")}</span>${follows(r.story)}`)).join("")
    + (st.waiting || []).filter(w => w.mark === "stopped" && !(st.running || []).some(r => r.story === w.story))
      .map(w => course(w.story, "bad", "stopped", {course: w.course, doing: (w.action && w.action.text) || w.what},
        `${act(w.action)}${follows(w.story)}`)).join("");
  const ready = (st.rows || []).filter(r => st.queue && st.queue.ready.includes(r.story)).map(storyRow).join("");
  return card("The backlog", backlogOn(st) ? "on — the released stories one after the other"
        : `off — ${(st.queue || {ready: []}).ready.length} released stories would run`, factory)
    + wishCard(st)
    + card("Running", "a story's course through its stages — running, or stopped where it goes on", live || `<p class="empty">No stage runs.</p>`)
    + card("Output", `<span id="follow-title" data-own></span>`, `<div class="acts" id="follow-acts" data-own></div><pre class="out" id="follow-out" data-own></pre>`)
    + card("Requests", "everything asked of the factory, oldest first", tickets ? `<div class="queue">${tickets}</div>` : `<p class="empty">No request waits.</p>`)
    + (ready ? card("Next in line", "ready, in the order the factory takes them", `<table>${ready}</table>`) : "");
}

function follow(kind, id) {
  if (S.followSource) { S.followSource.close(); S.followSource = null; }
  S.follow = kind ? {kind, id} : null;
  S.followLines = [];
  if (kind) {
    const source = new EventSource(`/api/follow?${kind}=${encodeURIComponent(id)}&t=${encodeURIComponent(TOKEN)}`);
    source.onmessage = event => {
      try { S.followLines.push(JSON.parse(event.data)); } catch (e) { S.followLines.push(event.data); }
      if (S.followLines.length > 1500) S.followLines.splice(0, S.followLines.length - 1500);
      paintFollow();
    };
    source.addEventListener("end", () => { S.followLines.push("— the output ended —"); paintFollow(); source.close(); });
    S.followSource = source;
  }
  // the output is a card of the run page: the story's drawer would hide it, so it closes, and the card comes into view
  if (S.drawer) CALLS.close();
  if (S.tab !== "run") show("run"); else paintFollow();
  if (kind) requestAnimationFrame(() => { const out = $("follow-out"); if (out) out.closest(".card").scrollIntoView({behavior: "smooth", block: "start"}); });
}

function paintFollow() {
  const out = $("follow-out");
  if (!out) return;
  $("follow-title").textContent = S.follow ? `${S.follow.kind} ${S.follow.id}` : "follow a running stage or request";
  $("follow-acts").innerHTML = S.follow ? `<button class="btn" data-call="unfollow">stop following</button>` : "";
  const atEnd = out.scrollTop + out.clientHeight >= out.scrollHeight - 20;   // at the end it follows the newest line
  const text = S.followLines.join("\n") || (S.follow ? "waiting for output…" : "");
  if (out.textContent !== text) out.textContent = text;
  if (atEnd) out.scrollTop = out.scrollHeight;
}

// --- 4 decide ------------------------------------------------------------------------------------------------------
function recordCard(r) {
  const offered = (r.actions || []).filter(a => !a.waits_on), accept = r.kind === "acceptance";
  const options = offered.filter(a => a.request.open !== "words" && !accept);
  const words = offered.filter(a => a.request.open === "words");
  const head = `<div class="q"><span class="hint">${accept ? "acceptance" : "question"} · ${esc(r.id)}${r.story ? ` · ${esc(r.stage)}` : ""}</span><b>${inline(r.text)}</b></div>`;
  // what to look at is the acceptance itself and stands open; a question's full text folds under its answers
  const isOpen = r.id in S.folded ? !S.folded[r.id] : accept;
  const full = (r.sections || []).length ? `<details class="more" data-more="${esc(r.id)}"${isOpen ? " open" : ""}><summary>${accept ? "what to look at" : "the question in full"}</summary>${r.sections.map(one => section(one)).join("")}</details>` : "";
  const body = (accept ? full : "")
    + (accept
      ? `<div class="acts">${acts(offered.filter(a => a.request.open !== "words"))}</div>`
      : options.length ? `<div class="opts">${options.map(a => `<div class="opt${a.primary ? " advised" : ""}"><div class="pick-it">${act(a)}</div>${a.primary ? `<span class="rec-word">recommended</span>` : ""}
          <span>${inline(a.text)}${a.note ? ` <span class="hint">— ${esc(a.note)}</span>` : ""}</span></div>`).join("")}</div>` : "")
    + words.map(a => `<h3>${accept ? "or correct it" : options.length ? "or in your words" : "your answer"}</h3>${act(a)}`).join("")
    + (accept ? "" : full)
    + `<p class="id" style="margin-top:10px">${r.story ? `${story(r.story, r.story)} · ` : ""}${esc(r.path)}</p>`;
  return `<section class="card decision${accept ? " accept" : ""}">${head}<div class="dbody">${body}</div></section>`;
}

function decide(st) {
  const records = ((S.decisions || {}).records || []).filter(r => (r.actions || []).length && (r.place || "decide") === "decide");
  // a waiting story whose record is open stands above as that record; the others — a draft, a stopped story — here
  const others = (st.waiting || []).filter(w => !w.record).map(w => `<tr><td>${mark(w.mark)}</td>
    <td>${story(w.story)}</td><td>${esc(w.what)}</td>
    <td class="act"><div class="acts">${act(w.action) || `<span class="hint">${esc(w.action.text || w.action.skill || w.action.shell || "")}</span>`}</div></td></tr>`).join("");
  return records.map(recordCard).join("")
    + (others ? card(records.length ? "Also waiting for you" : "", "", `<table>${others}</table>`) : "")
    + (!records.length && !others ? card("", "", `<p class="empty">Nothing waits for you.</p>`) : "");
}

// --- 5 delivered ---------------------------------------------------------------------------------------------------
// --- the delivered curve: what all deliveries up to a day cost together, as the factory sums it --------------------
const CURVE = {w: 1000, left: 64, right: 96, top: 26, panel: 120, gap: 44, bottom: 24};
const money = n => n >= 1000 ? `$${(n / 1000).toFixed(1)}k` : `$${Math.round(n)}`;
const count = n => n >= 1e9 ? `${(n / 1e9).toFixed(1)} G` : n >= 1e6 ? `${(n / 1e6).toFixed(0)} M` : n >= 1e3 ? `${(n / 1e3).toFixed(0)} k` : `${n}`;
function niceMax(v) { const p = Math.pow(10, Math.floor(Math.log10(v || 1))); return [1, 2, 2.5, 5, 10].map(m => m * p).find(m => m >= v) || v; }
function curveSvg(curve) {
  const {w, left, right, top, panel, gap, bottom} = CURVE, h = top + panel * 2 + gap + bottom;
  const t = curve.map(c => Date.parse(c.at)), t0 = t[0], t1 = t[t.length - 1] === t0 ? t0 + 864e5 : t[t.length - 1];
  const x = v => left + (v - t0) / (t1 - t0) * (w - left - right);
  const panels = [{name: "cost, cumulative", key: "cost_total", fmt: money, y0: top},
                  {name: "tokens, cumulative", key: "tokens_total", fmt: count, y0: top + panel + gap}];
  let out = `<svg viewBox="0 0 ${w} ${h}" role="img" aria-label="cost and tokens of every delivery so far, over time">`;
  for (const p of panels) {
    const max = niceMax(curve[curve.length - 1][p.key]), y = v => p.y0 + panel - v / max * panel;
    p.y = y;
    for (const f of [0, .5, 1]) out += `<line class="grid" x1="${left}" x2="${w - right}" y1="${y(max * f)}" y2="${y(max * f)}"/>`
      + `<text class="axis" x="${left - 8}" y="${y(max * f) + 4}" text-anchor="end">${esc(p.fmt(max * f))}</text>`;
    // a sum holds until the next delivery: a step, not a slope
    let d = `M${x(t[0])},${y(0)}`;
    curve.forEach((c, i) => { d += ` V${y(c[p.key])}` + (i + 1 < curve.length ? ` H${x(t[i + 1])}` : ""); });
    out += `<path class="area" d="${d} V${y(0)} Z"/><path class="line" d="${d}"/>`
      + `<text class="name" x="${left}" y="${p.y0 - 10}">${esc(p.name)}</text>`
      + `<text class="end" x="${x(t[t.length - 1]) + 8}" y="${y(curve[curve.length - 1][p.key]) + 4}">${esc(p.fmt(curve[curve.length - 1][p.key]))}</text>`;
  }
  const ticks = 6, axisY = top + panel * 2 + gap + 18;
  for (let i = 0; i <= ticks; i++) {
    const v = t0 + (t1 - t0) * i / ticks, day = new Date(v).toISOString().slice(5, 10);
    out += `<text class="axis" x="${x(v)}" y="${axisY}" text-anchor="middle">${day}</text>`;
  }
  out += `<line class="cross" id="curve-cross" x1="0" x2="0" y1="${top}" y2="${top + panel * 2 + gap}" visibility="hidden"/>`
    + panels.map((p, n) => `<circle class="dot" id="curve-dot-${n}" r="4.5" cx="0" cy="0" visibility="hidden"/>`).join("")
    + `<rect id="curve-hit" x="${left}" y="${top}" width="${w - left - right}" height="${panel * 2 + gap}" fill="transparent"/></svg>`;
  S.curvePanels = panels.map(p => ({key: p.key, y: p.y}));
  S.curveX = {t0, t1, x0: left, x1: w - right};
  return out;
}
function curveCard(st) {
  const curve = st.delivered_curve || [];
  if (curve.length < 2) return "";
  S.curve = curve;
  const last = curve[curve.length - 1], unpriced = curve.length - last.priced_total;
  return `<div class="curve" id="curve">${curveSvg(curve)}<div class="tip" id="curve-tip" hidden></div></div>`
    + (unpriced ? `<p class="hint">${unpriced} deliver${unpriced === 1 ? "y carries" : "ies carry"} no price and add nothing to the cost.</p>` : "");
}
document.addEventListener("mousemove", event => {
  const hit = event.target.closest && event.target.closest("#curve-hit"), tip = $("curve-tip");
  const marks = ["curve-cross", "curve-dot-0", "curve-dot-1"].map(id => $(id));
  if (!hit || !S.curve) { if (tip) tip.hidden = true; marks.forEach(m => m && m.setAttribute("visibility", "hidden")); return; }
  const svg = hit.ownerSVGElement, box = svg.getBoundingClientRect(), scale = CURVE.w / box.width;
  const vx = (event.clientX - box.left) * scale, {t0, t1, x0, x1} = S.curveX;
  const at = t0 + (vx - x0) / (x1 - x0) * (t1 - t0);
  let i = 0; while (i + 1 < S.curve.length && Date.parse(S.curve[i + 1].at) <= at) i++;
  const c = S.curve[i], cx = x0 + (Date.parse(c.at) - t0) / (t1 - t0) * (x1 - x0);
  marks[0].setAttribute("x1", cx); marks[0].setAttribute("x2", cx); marks[0].setAttribute("visibility", "visible");
  S.curvePanels.forEach((p, n) => { marks[n + 1].setAttribute("cx", cx); marks[n + 1].setAttribute("cy", p.y(c[p.key])); marks[n + 1].setAttribute("visibility", "visible"); });
  tip.innerHTML = `<b>${esc(c.title || c.story)}</b><div class="row"><span>delivered</span><span>${esc(c.at.replace("T", " ").slice(0, 16))}</span></div>`
    + `<div class="row"><span>cost so far</span><span>$${c.cost_total.toFixed(2)}</span></div><div class="row"><span>tokens so far</span><span>${c.tokens_total.toLocaleString("en")}</span></div>`
    + `<div class="row"><span>this one</span><span>${c.cost == null ? "unpriced" : "$" + c.cost.toFixed(2)} · ${count(c.tokens)}</span></div>`;
  tip.hidden = false;
  const left = cx / scale + 14, room = box.width - tip.offsetWidth - 8;
  tip.style.left = `${Math.min(left, room)}px`; tip.style.top = `${(event.clientY - box.top) - tip.offsetHeight - 12}px`;
});

// --- quality: the signals the factory counts per story, summed — shown as counted, never rated -------------------
const sum = o => Object.values(o || {}).reduce((n, v) => n + v, 0);
const domainWords = o => Object.entries(o || {}).sort((a, b) => b[1] - a[1]).map(([c, n]) => `${n} ${c.replace(/^domain-/, "")}`).join(" · ");
function qualityCard(q) {
  if (!q || !q.stories) return "";
  const domain = sum(q.domain), corrected = sum(q.corrections);
  const tiles = [
    [`${q.answered}/${q.asked}`, "questions answered", "a stage asked, a person answered", ""],
    [`${q.assumptions_answered}`, "assumptions answered", `${q.assumptions_open} still open`, q.assumptions_open ? "bad" : ""],
    [`${q.plan_open}`, "left open by plans", "what a plan named and did not decide", ""],
    [`${domain}`, "domain findings", domain ? domainWords(q.domain) : "none confirmed", domain ? "bad" : ""],
    [`${corrected}`, "corrections at acceptance", corrected ? domainWords(q.corrections) : "none", corrected ? "bad" : ""],
  ].map(([n, label, said, cls]) => `<div class="tile ${cls}"><b>${esc(n)}</b><span>${esc(label)}</span><small>${esc(said)}</small></div>`).join("");
  const found = Object.entries(q.findings || {}).sort((a, b) => b[1] - a[1]), most = found.length ? found[0][1] : 1;
  const bars = found.map(([name, n]) => `<span class="lbl">${esc(name)}</span><span class="track"><i style="width:${Math.round(100 * n / most)}%"></i></span><span class="n">${n}</span>`).join("");
  // the rules a broken implementation was tried against: one tile, the count by kind on hover
  const counted = `killed ${q.killed} · red ${q.red} · survived ${q.survived} · no-break ${q["no-break"]} — of ${q.stories} stories: ${q.measured} measured, ${q.not_measured} tested before rules were recorded, ${q.without_test || 0} without a test stage, ${q.open || 0} not delivered`;
  const ruleTile = `<div class="tile${q.survived ? " bad" : ""}" title="${esc(counted)}"><b>${q.named ? `${q.killed}/${q.named}` : "–"}</b><span>rules caught when broken</span><small>${q.measured} of ${q.stories} stories measured</small></div>`;
  return card("Quality", "what the stages asked, what the judge confirmed, what a person corrected — counted over every story, never rated",
    `<div class="tiles five">${tiles}${ruleTile}</div>`
    + (bars ? `<h3>Findings the judge confirmed, by perspective</h3><div class="qbars">${bars}</div>` : ""));
}
// the same figures in one line, for an epic
function qualityLine(q) {
  if (!q || !q.stories) return "";
  const domain = sum(q.domain), found = Object.entries(q.findings || {}).sort((a, b) => b[1] - a[1]);
  return `<div class="qline"><span>questions <b>${q.answered}/${q.asked}</b></span><span>assumptions <b>${q.assumptions_answered}</b>${q.assumptions_open ? ` <span class="bad">${q.assumptions_open} open</span>` : ""}</span>`
    + `<span>left open by plans <b>${q.plan_open}</b></span>`
    + (found.length ? `<span>findings ${found.map(([n, c]) => `${esc(n)} <b>${c}</b>`).join(" · ")}</span>` : "")
    + `<span>domain <b class="${domain ? "bad" : ""}">${domain ? esc(domainWords(q.domain)) : "0"}</b></span>`
    + (q.named ? `<span>rules caught when broken <b class="${q.survived ? "bad" : ""}">${q.killed}/${q.named}</b></span>` : "") + `</div>`;
}

function delivered(st) {
  const rows = Object.fromEntries((st.rows || []).map(r => [r.story, r])), events = Object.fromEntries((st.epics || []).map(e => [e.epic, e.metric]));
  const tiles = [[`${st.delivered}`, `of ${st.total} stories delivered`, "lead"], [st.seconds_text, "worked"], [st.tokens_text, "tokens"], [st.cost_text, "cost"]]
    .filter(([n]) => n).map(([n, label, cls]) => `<div class="tile ${cls || ""}"><b>${esc(n)}</b><span>${esc(label)}</span></div>`).join("");
  const days = [];
  for (const r of (st.delivered_order || []).map(id => rows[id]).filter(Boolean)) {
    const day = (r.delivered_text || "").slice(0, 10) || "undated";
    if (!days.length || days[days.length - 1].day !== day) days.push({day, rows: []});
    days[days.length - 1].rows.push(r);
  }
  const line = r => `<div class="dl"><div class="at">${esc((r.delivered_text || "").slice(11))}</div><div class="what">${story(r.story, r.title)}</div>
    <div class="epic cut" title="${esc(r.epic)}">${esc(r.epic)}</div>
    <div class="ev cut">${events[r.epic] ? `<span class="event" title="${esc(events[r.epic])}">${esc(events[r.epic])}</span>` : ""}</div>
    <div class="fig">${esc(r.seconds_text || "")}</div><div class="fig">${esc(r.cost_text || "")}</div></div>`;
  return card("Delivered", "what is delivered, and what it cost as it summed up",
    `<div class="tiles">${tiles}</div>` + curveCard(st))
    + qualityCard(st.signals)
    + card("By day", "each delivery with the outcome event its epic is measured by", (days.length ? `<div class="days">${days.map(d => `<div class="day"><h4>${esc(d.day)}</h4>${d.rows.map(line).join("")}</div>`).join("")}</div>` : `<p class="empty">Nothing delivered yet.</p>`));
}

// --- one story -----------------------------------------------------------------------------------------------------
async function openStory(id) {
  if (!S.drawer) S.opener = document.activeElement;
  S.drawer = id;
  // below the bar, so the tabs and the factory's state stay in reach
  document.documentElement.style.setProperty("--bar", $("topbar").getBoundingClientRect().height + "px");
  const node = $("drawer"), close = `<button class="btn close" data-call="close">close</button>`;
  node.hidden = false;
  node.innerHTML = `${close}<p class="empty">Reading ${esc(id)}…</p>`;
  node.focus();
  let v;
  try { v = await api(`/api/view/story?id=${encodeURIComponent(id)}`); }
  catch (e) { node.innerHTML = `${close}<p class="m-stopped">${esc(e.message)}</p>`; return; }
  if (S.drawer !== id) return;
  forget("d");
  const row = v.row || {};
  // the factory's sections in its order, the scenarios where its criteria stood
  const scenarios = (v.scenarios || []).map(c => `<h3>${esc(c.title || c.key)}</h3>${c.rule ? `<p class="hint">${esc(c.rule)}</p>` : ""}
    ${(c.steps || []).map(s => `<div class="step"><b>${esc(s.word)}</b>${esc(s.text)}</div>`).join("")}`).join("");
  const list = v.sections || [], at = v.criteria_at == null ? list.length : v.criteria_at;
  const sections = list.slice(0, at).map(one => section(one, 2)).join("") + (scenarios ? `<h2>Scenarios</h2>${scenarios}` : "")
    + list.slice(at).map(one => section(one, 2)).join("");
  const stages = Object.entries(v.stages || {}).map(([name, e]) => `<tr><td>${esc(name)}</td><td class="num">${e.runs || ""}</td>
    <td class="num">${esc(e.seconds_text)}</td><td class="num">${esc(e.tokens_text)}</td><td class="num hide-s">${esc(e.cost_text)}</td><td class="id">${esc(e.why || "")}</td></tr>`).join("");
  node.innerHTML = `${close}<div class="eyebrow">${esc(v.epic)}</div><h1>${esc(v.title || id)}</h1>
    <dl class="kv"><dt>story</dt><dd class="mono">${esc(id)}</dd><dt>state</dt><dd>${esc(row.state || v.situation || "")}</dd>
      ${v.context ? `<dt>context</dt><dd>${esc(v.context)}</dd>` : ""}<dt>file</dt><dd><code>${esc(v.path)}</code></dd>
      ${row.tokens_text ? `<dt>tokens</dt><dd>${esc(row.tokens_text)}${row.cost_text ? " · " + esc(row.cost_text) : ""}</dd>` : ""}</dl>
    <div class="acts">${acts((v.actions || []).filter(a => a.request.open !== "words"), "d")}${Object.keys(v.stages || {}).length || row.mark === "running" ? `<button class="btn" data-call="follow" data-kind="story" data-id="${esc(id)}">output</button>` : ""}</div>
    ${(v.actions || []).filter(a => a.request.open === "words" && !a.waits_on).map(a => `<h2>${esc(a.label)}</h2>${act(a, "d")}`).join("")}
    ${sections}
    ${stages ? `<h2>Processes</h2><table><tr><th>process</th><th class="num">runs</th><th class="num">time</th><th class="num">tokens</th><th class="num hide-s">cost</th><th>why</th></tr>${stages}</table>` : ""}`;
}

// --- start ---------------------------------------------------------------------------------------------------------
// a record's text folded by the person stays folded through the next redraw
document.addEventListener("toggle", event => {
  const more = event.target.closest && event.target.closest("[data-more]");
  if (more) S.folded[more.dataset.more] = !more.open;
}, true);

// The tab bar by keyboard (WAI-ARIA tabs): while a tab has the focus, the arrows, Home and End move between the views
// and a digit jumps to its view — the cockpit's keys, shown as hints then. Outside the bar a digit is a digit
// (WCAG 2.1.4: a one-key shortcut acts only where its element has the focus).
document.addEventListener("keydown", event => {
  if (event.target.closest("textarea, input, select")) return;
  if (event.key === "Escape") return CALLS.close();
  const at = event.target.closest('[role="tab"]');
  if (!at) return;
  const ids = [...$("tabs").querySelectorAll('[role="tab"]')].map(b => b.dataset.tab), i = ids.indexOf(at.dataset.tab);
  const to = /^[0-9]$/.test(event.key) ? (TABS[+event.key] || [])[0]
    : {ArrowRight: ids[(i + 1) % ids.length], ArrowLeft: ids[(i - 1 + ids.length) % ids.length],
       Home: ids[0], End: ids[ids.length - 1]}[event.key];
  if (!to) return;
  event.preventDefault();
  if (to !== S.tab) show(to);
  $("tab-" + to).focus();
});
window.addEventListener("hashchange", () => {
  const tab = location.hash.slice(1);
  if (tab !== S.tab && known(tab)) show(tab);
});
theme(stored("factory.theme") || "auto");
(async () => {
  if (!TOKEN) { banner("This page needs the token `factory.sh serve` printed — open that URL."); return; }
  try { $("by").value = stored("factory.by") || (await api("/api/meta")).by || ""; } catch (e) { banner(e.message); }
  $("by").addEventListener("change", () => store("factory.by", by()));
  load("help", "/api/view/help").then(ok => ok && render());   // the parts: once, inflow, the cycle, to look up
  await refresh();
  setInterval(() => { if (!document.hidden) refresh(); }, 5000);
})();
</script>
</body>
</html>
""".replace("__MARK__", MARK)


#: The page's one script as its Content-Security-Policy names it: no other script runs, an injected one included.
SCRIPT_HASH = "sha256-" + base64.b64encode(hashlib.sha256(
    re.search(r"<script>(.*?)</script>", PAGE, re.S).group(1).encode("utf-8")).digest()).decode("ascii")
