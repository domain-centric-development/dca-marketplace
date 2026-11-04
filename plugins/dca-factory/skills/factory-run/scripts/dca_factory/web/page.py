"""The page `factory.sh serve` shows (WP-91): one HTML file with its script inline, no dependency and no build step.

It draws the factory's own JSON views — status, decisions, discovery, requests, one story, a stage's output — in the
cycle's tabs, in the project's look (the mark, its colours and faces, a light and a dark scheme). It decides nothing:
the order, the marks, the words, the figures and every action — its label, whether it is the one to press, the request
it writes and what the person still gives — come from the factory. A press writes that request, or starts and stops
the factory. Kept as modules so it ships, installs and is hashed with the package.

Since WP-180 it is put together from its levels: the tokens (`page_tokens.py`), the stylesheet (`page_style.py`), the
components (`page_ui.py`), the script's core (`page_core.py`) and the views (`page_views.py`). A project gives it a
look of its own with `.dca-factory/theme/theme.css`, linked after the page's own style so a plain `:root { … }`
overrides the public tokens; the service serves that folder at `/theme/`.
"""

import base64
import hashlib
import re

from .page_core import SCRIPT_CORE, SCRIPT_START
from .page_style import STYLE
from .page_tokens import ICON_BRAND, ICON_INK, TOKENS
from .page_ui import SCRIPT_UI
from .page_views import SCRIPT_GALLERY, SCRIPT_VIEWS

#: The mark in its text cut (under 44 px), its strokes in the colour of the text around it, its core the brand's.
MARK = ('<svg viewBox="17.4 12 85.2 96" fill="none" aria-hidden="true"><polygon points="60,20 94.6,40 94.6,80 60,100 '
        '25.4,80 25.4,40" stroke="currentColor" stroke-width="7" stroke-linejoin="round"/>'
        + "".join(f'<circle cx="{x}" cy="{y}" r="8" fill="currentColor"/>'
                  for x, y in ((60, 20), (94.6, 40), (94.6, 80), (60, 100), (25.4, 80), (25.4, 40)))
        + '<circle cx="60" cy="60" r="12" fill="var(--brand)"/></svg>')


def icon(ink=ICON_INK, brand=ICON_BRAND):
    """The tab's icon: the same drawing in the light scheme's ink and brand, the border 10 % stronger on paper."""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="32" height="36" viewBox="17.4 12 85.2 96" fill="none">'
            f'<polygon points="60,20 94.6,40 94.6,80 60,100 25.4,80 25.4,40" stroke="{ink}" stroke-width="7.7" '
            f'stroke-linejoin="round"/>'
            + "".join(f'<circle cx="{x}" cy="{y}" r="8" fill="{ink}"/>'
                      for x, y in ((60, 20), (94.6, 40), (94.6, 80), (60, 100), (25.4, 80), (25.4, 40)))
            + f'<circle cx="60" cy="60" r="12" fill="{brand}"/></svg>')


FAVICON = icon()

FACES = """
@font-face { font-family: "Space Grotesk"; font-weight: 300 700; font-display: swap; src: url(/fonts/space-grotesk-latin.woff2) format("woff2"); }
@font-face { font-family: "Newsreader"; font-weight: 200 800; font-display: swap; src: url(/fonts/newsreader-latin.woff2) format("woff2"); }
@font-face { font-family: "JetBrains Mono"; font-weight: 100 800; font-display: swap; src: url(/fonts/jetbrains-mono-latin.woff2) format("woff2"); }
"""

#: The page's frame: the bar, the main region, the drawer — the one markup not drawn by a component.
FRAME = """<header class="topbar" id="topbar">
  <div class="wrap topbar__app">
    <a class="brand" id="home" href="#now" data-tab="now" aria-label="now — where the factory stands" title="now — where the factory stands"><span class="brand__logo" aria-hidden="true">__MARK__</span><span class="brand__name">factory<span class="brand__dot">.</span></span><span class="brand__project" id="project"></span></a>
    <div class="topbar__tools">
      <div id="run"></div>
      <div class="menu menu--bar" data-menu-box="me">
        <button type="button" class="menu__toggle" aria-expanded="false" aria-controls="menu-me" data-menu="me" title="who acts here, and the colour scheme"><span id="initials">you</span><span class="menu__chev" aria-hidden="true">▾</span></button>
        <div class="menu__panel" id="menu-me" hidden>
          <div class="form-row"><label class="label label--quiet" for="by">you act as</label><input class="field" id="by" type="text" autocomplete="name"></div>
          <div class="form-row"><span class="label label--quiet">colour scheme</span><span class="switch" role="group" aria-label="colour scheme"><button type="button" class="switch__opt" data-pick="light" aria-pressed="false">light</button><button type="button" class="switch__opt" data-pick="auto" aria-pressed="false">auto</button><button type="button" class="switch__opt" data-pick="dark" aria-pressed="false">dark</button></span></div>
        </div>
      </div>
    </div>
  </div>
  <div class="topbar__nav"><nav class="wrap tabs" id="tabs" role="tablist" aria-label="the factory's views"></nav></div>
</header>
<div class="banner" id="banner" role="alert" hidden><div class="wrap" id="banner-text"></div></div>
<main class="wrap main" id="main" role="tabpanel"></main>
<div class="toasts" id="toasts" aria-live="polite"></div>
<aside class="drawer" id="drawer" aria-label="story" tabindex="-1" hidden></aside>""".replace("__MARK__", MARK)

#: The page's one script, its parts in the order they run.
SCRIPT = SCRIPT_CORE + SCRIPT_UI + SCRIPT_VIEWS + SCRIPT_GALLERY + SCRIPT_START

PAGE = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>Factory</title>
<link rel="icon" type="image/svg+xml" href="/favicon.svg">
<style>{FACES}{TOKENS}{STYLE}</style>
<link rel="stylesheet" href="/theme/theme.css">
</head>
<body>
{FRAME}
<script>{SCRIPT}</script>
</body>
</html>
"""


#: The page's one script as its Content-Security-Policy names it: no other script runs, an injected one included.
SCRIPT_HASH = "sha256-" + base64.b64encode(hashlib.sha256(
    re.search(r"<script>(.*?)</script>", PAGE, re.S).group(1).encode("utf-8")).digest()).decode("ascii")
