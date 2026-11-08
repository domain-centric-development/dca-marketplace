"""The page is built from components in atomic levels, one naming, its colours from tokens alone (WP-180).

What a person or an agent may change on the page without asking: a component's look in its block, a view's order. What
these tests hold, so that two hands building the same thing build it the same way: every class a BEM block of a
component (or of the frame) with its elements and variants; a factory state as `data-state`, never a class; a
component calling nothing above its level; the views and the core writing no class and no style of their own; every
field set through `ui.formRow`; every component in the pattern library; every colour a token; the public tokens and
the shipped `theme.example.css` the same list.
"""

import os
import re
import unittest

import support  # noqa: F401 — puts the package on the path

from dca_factory.delivery.adapter.incoming.web import page, page_core, page_style, page_tokens, page_ui, page_views

LEVELS = ("atoms", "molecules", "organisms", "templates")
BEM = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*(__[a-z0-9]+(-[a-z0-9]+)*)?(--[a-z0-9]+(-[a-z0-9]+)*)?$")
#: The words the factory names a state with: never a class, always `data-state`.
STATE_WORDS = {"done", "delivered", "running", "waiting", "queued", "draft", "approved", "stopped", "failed", "superseded",
               "ok", "wait", "bad", "mute", "open", "sel", "show", "up", "down", "stopping", "now", "ready", "pass", "fail"}
#: The base layer: a bare element styled alone, before any block — what a link, code or a focused control looks like.
BASE_TAGS = {"html", "body", "a", "code", "button", "input", "select", "textarea"}
#: A drawing's parts: an SVG has no classes of its own to give its shapes.
SVG_TAGS = {"svg", "circle", "path", "rect", "line", "polyline", "polygon", "g", "text"}
#: Where written text is shown as written — rendered Markdown, a document's sections —: its tags carry no classes.
CONTENT_ZONES = (".prose", ".document")
COLOUR = re.compile(r"#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(")
EXAMPLE = os.path.join(os.path.dirname(os.path.abspath(page.__file__)), *[".."] * 6, "templates", "theme",
                       "theme.example.css")


def kebab(name):
    return re.sub(r"(?<!^)([A-Z])", r"-\1", name).lower()


def components():
    """`{name: (level, body)}` — a component is its `ui.<name> = ` line and what follows, up to the next one."""
    found, level, name, body = {}, None, None, []
    for line in page_ui.SCRIPT_UI.splitlines():
        header = re.match(r"^// --- (\w+)", line)
        start = re.match(r"^ui\.(\w+) = ", line)
        if (header or start) and name:
            found[name] = (level, "\n".join(body))
            name, body = None, []
        if header:
            level = header.group(1)
        elif start:
            name, body = start.group(1), [line]
        elif name:
            body.append(line)
    if name:
        found[name] = (level, "\n".join(body))
    return found


def css_classes(style):
    """Every class a selector of the stylesheet names — outside the rules under `.flow`, whose classes are the
    factory's drawing."""
    names = set()
    for rule in re.findall(r"([^{}]+)\{[^{}]*\}", re.sub(r"/\*.*?\*/", "", style, flags=re.S)):
        for selector in rule.split(","):
            selector = selector.strip()
            if not selector or selector.startswith("@") or re.match(r"^\.flow\b(?!-)", selector) and " " in selector:
                continue
            names.update(re.findall(r"\.([A-Za-z_][\w-]*)", selector))
    return names


def selectors(style):
    """Every selector of the stylesheet, its comments gone — outside the rules under `.flow`, the factory's drawing."""
    found = []
    for rule in re.findall(r"([^{}]+)\{[^{}]*\}", re.sub(r"/\*.*?\*/", "", style, flags=re.S)):
        for selector in rule.split(","):
            selector = selector.strip()
            if not selector or selector.startswith(("@", "from", "to")) or re.fullmatch(r"\d+%", selector):
                continue
            if re.match(r"^\.flow\b(?!-)", selector) and " " in selector:
                continue
            found.append(selector)
    return found


def compounds(selector):
    """A selector's compounds — `.a > .b c` is `.a`, `.b`, `c` —, each without its pseudo-classes, pseudo-elements and
    attributes (whose arguments are selectors of their own, read apart)."""
    bare = re.sub(r"::?[\w-]+(\((?:[^()]|\([^()]*\))*\))?", "", selector)
    bare = re.sub(r"\[[^\]]*\]", "", bare)
    return [c for c in re.split(r"\s*[\s>+~]\s*", bare.strip()) if c]


def markup_classes(text):
    return {c for value in re.findall(r'class="([^"]*)"', text) for c in value.split() if "$" not in c}


class PageComponentsTest(unittest.TestCase):

    def setUp(self):
        self.ui = components()
        self.blocks = {kebab(n) for n in self.ui} | set(page_style.FRAME_BLOCKS)

    def test_every_component_sits_in_a_level(self):
        self.assertTrue(self.ui, "no component found")
        self.assertEqual({}, {n: lvl for n, (lvl, _b) in self.ui.items() if lvl not in LEVELS})

    def test_a_component_calls_nothing_above_its_level_and_an_atom_calls_none(self):
        rank = {lvl: i for i, lvl in enumerate(LEVELS)}
        wrong = []
        for name, (level, body) in self.ui.items():
            for called in set(re.findall(r"\bui\.(\w+)\b", body)) - {name}:
                if called not in self.ui:
                    wrong.append(f"{name} calls ui.{called}, no component")
                elif level == "atoms" or rank[self.ui[called][0]] > rank[level]:
                    wrong.append(f"{name} ({level}) calls {called} ({self.ui[called][0]})")
        self.assertEqual([], wrong)

    def test_every_class_is_bem_and_belongs_to_a_component_or_the_frame(self):
        used = css_classes(page_style.STYLE) | markup_classes(page_ui.SCRIPT_UI) | markup_classes(page.FRAME)
        self.assertEqual([], sorted(c for c in used if not BEM.match(c)), "not BEM")
        self.assertEqual([], sorted(c for c in used if re.split(r"__|--", c)[0] not in self.blocks), "no component's block")

    def test_a_block_styles_its_elements_by_class_never_by_tag(self):
        # a tag in a selector reaches markup the block does not name: a base rule for a bare element, a drawing's shape
        # and the content zones of written text are the named exceptions
        tagged = []
        for selector in selectors(page_style.STYLE):
            if selector.startswith(CONTENT_ZONES) or selector.startswith(":root") and " " not in selector:
                continue
            parts = compounds(selector)
            for part in parts:
                tag = re.match(r"^([a-z][a-z0-9]*)", part)
                if not tag or tag.group(1) in SVG_TAGS:
                    continue
                if len(parts) == 1 and part == tag.group(1) and tag.group(1) in BASE_TAGS:
                    continue
                tagged.append(selector)
                break
        self.assertEqual([], tagged)

    def test_a_block_never_reaches_into_another_blocks_elements(self):
        # a block may place another block, never restyle its elements: that is a variant of the other block
        reaching = []
        for selector in selectors(page_style.STYLE):
            parts = compounds(selector)
            if len(parts) < 2:
                continue
            target = re.findall(r"\.([a-z][\w-]*)", parts[-1])
            outer = {re.split(r"__|--", c)[0] for part in parts[:-1] for c in re.findall(r"\.([a-z][\w-]*)", part)}
            for name in target:
                block = re.split(r"__|--", name)[0]
                if "__" in name and outer - {block}:
                    reaching.append(selector)
                    break
        self.assertEqual([], reaching)

    def test_a_component_writes_its_own_block_around_its_elements(self):
        # an element stands inside its block: the component of that name writes the block, a part of it (`trailItem`)
        # stands in the block its whole writes, and the frame's own blocks are in the frame
        lonely = []
        for name, (_level, body) in self.ui.items():
            block = kebab(name)
            written = markup_classes(body) | set(re.findall(r'mods\("([a-z][\w-]*)"', body))
            for element in {c for c in written if "__" in c}:
                owner = element.split("__")[0]
                if owner == block and owner not in written and owner not in page_style.FRAME_BLOCKS:   # the frame writes those
                    lonely.append(f"ui.{name} writes {element} without {owner}")
        self.assertEqual([], lonely)

    def test_the_script_sets_no_class_a_state_is_an_attribute(self):
        script = page_ui.SCRIPT_UI + page_views.SCRIPT_VIEWS + page_views.SCRIPT_GALLERY + page_core.SCRIPT_CORE \
            + page_core.SCRIPT_START
        self.assertEqual([], re.findall(r"classList\.\w+\([^)]*\)|\bclassName\s*=", script))

    def test_a_view_writes_a_heading_only_in_written_text(self):
        # a heading the views write themselves has no class: it stands in a document's zone, else it is a component's
        bare = [line.strip()[:90] for line in page_views.SCRIPT_VIEWS.splitlines()
                if re.search(r"<h[1-6][ >]", line) and "ui.document(" not in line]
        self.assertEqual([], bare)

    def test_a_state_is_data_state_never_a_class(self):
        used = css_classes(page_style.STYLE) | markup_classes(page_ui.SCRIPT_UI) | markup_classes(page.FRAME)
        self.assertEqual([], sorted(c for c in used if c in STATE_WORDS or re.split(r"--", c)[-1] in STATE_WORDS))

    def test_the_views_and_the_core_write_no_class_and_no_style(self):
        for name, text in (("views", page_views.SCRIPT_VIEWS + page_views.SCRIPT_GALLERY),
                           ("core", page_core.SCRIPT_CORE + page_core.SCRIPT_START)):
            self.assertEqual([], re.findall(r"\b(?:class|style)=", text), name)

    def test_a_field_is_set_through_the_form_row_alone(self):
        fields = {n for n, (_l, body) in self.ui.items() if re.search(r"<(input|textarea|select)\b", body)}
        self.assertEqual({"field", "select"}, fields)
        callers = {n for n, (_l, body) in self.ui.items() if re.search(r"\bui\.(field|select)\(", body)}
        # a field comes with its label through the form row — but for the file picker, a hidden field the visible
        # "+ file" press opens, named by its own aria-label (WP-184)
        self.assertEqual({"formRow", "attach"}, callers)
        for name, text in (("views", page_views.SCRIPT_VIEWS + page_views.SCRIPT_GALLERY), ("core", page_core.SCRIPT_CORE)):
            self.assertEqual([], re.findall(r"ui\.(?:field|select)\(|<(?:input|textarea|select)\b", text), name)

    def test_every_component_is_in_the_pattern_library(self):
        # shown by itself, or inside a component that is — a field only ever inside its form row
        shown = set(re.findall(r"\bui\.(\w+)\b", page_views.SCRIPT_GALLERY)) & set(self.ui)
        while True:
            inside = {c for n in shown for c in re.findall(r"\bui\.(\w+)\b", self.ui[n][1]) if c in self.ui} - shown
            if not inside:
                break
            shown |= inside
        self.assertEqual([], sorted(set(self.ui) - shown))

    def test_no_colour_is_written_outside_the_tokens(self):
        for name, text in (("style", page_style.STYLE), ("ui", page_ui.SCRIPT_UI), ("views", page_views.SCRIPT_VIEWS),
                           ("gallery", page_views.SCRIPT_GALLERY), ("core", page_core.SCRIPT_CORE), ("frame", page.FRAME)):
            self.assertEqual([], COLOUR.findall(text), name)

    def test_a_state_takes_the_palette_never_the_brand(self):
        rules = re.findall(r"([^{}]*\[data-state[^{}]*)\{([^{}]*)\}", page_style.STYLE)
        self.assertTrue(rules)
        self.assertEqual([], [sel.strip() for sel, body in rules if "--brand" in body])
        for use, meaning in (("ok", "success"), ("pass", "success"), ("wait", "warning"), ("stop", "danger"),
                             ("fail", "danger"), ("run", "info")):
            self.assertIn(f"--{use}: var(--{meaning});", page_tokens.TOKENS)

    def test_space_type_and_corners_are_steps_of_their_scales(self):
        # a hairline (1 or 2 px), an em and the factory's drawing under `.flow` are the named exceptions (WP-181)
        raw = []
        for selector, body in re.findall(r"([^{}]*)\{([^{}]*)\}", page_style.STYLE):
            if re.match(r"\s*\.flow\b", selector.split(",")[0]) and " " in selector.strip():
                continue
            for declaration in body.split(";"):
                prop, _, value = declaration.partition(":")
                if re.fullmatch(r"(margin|padding)(-[a-z]+)?|gap|row-gap|column-gap|font|font-size|border-radius", prop.strip()):
                    raw += [f"{selector.strip()[:40]} {prop.strip()}: {px}" for px in re.findall(r"-?\d*\.?\d+px", value)
                            if abs(float(px[:-2])) > 2]
        self.assertEqual([], raw)

    def test_nothing_reads_below_twelve_pixels(self):
        # WP-183: the smallest step of the type scale, and the drawing's small text at the width it is drawn at
        steps = re.findall(r"--text-[a-z0-9]+: ([0-9.]+)px", page_tokens.TOKENS)
        self.assertTrue(steps)
        self.assertGreaterEqual(min(float(s) for s in steps), 12, "a step of the type scale")
        # 12 px is fine print alone (a column's head, a label in capitals, a count); the small words one reads are 14 px
        self.assertGreaterEqual(float(re.search(r"--text-sm: ([0-9.]+)px", page_tokens.TOKENS).group(1)), 14, "the small words one reads")
        # the drawing shrinks with its place down to the least width it states: there its small text is 12 px or more
        import tempfile
        from dca_factory.infrastructure.rulebook import show_rulebook
        from dca_factory.rulebook.application.show_rulebook import ShowRulebookQuery
        from dca_factory.rulebook.adapter.incoming.cli import flow_svg
        small = float(re.search(r"text\.small \{[^}]*font-size: ([0-9.]+)px", flow_svg.STYLE).group(1))
        self.assertIn("max-width: var(--flow-measure)", page_style.STYLE)
        for kind, flow in show_rulebook(tempfile.gettempdir()).execute(ShowRulebookQuery()).get("flow", {}).items():
            drawn = flow_svg.svg(flow["graph"], kind)
            units = float(re.search(r'viewBox="0 0 ([0-9.]+) ', drawn).group(1))
            least = float(re.search(r'min-width: ([0-9.]+)px', drawn).group(1))
            self.assertGreaterEqual(small * least / units, 11.95, f"the {kind} drawing's small text at its least width")

    def test_side_by_side_stands_on_the_twelve_columns(self):
        for block in ("board", "lanes", "tiles"):
            rule = re.search(r"^\." + block + r" \{([^}]*)\}", page_style.STYLE, re.M).group(1)
            self.assertIn("repeat(var(--grid-columns), minmax(0, 1fr))", rule, block)
        self.assertIn("--grid-columns: 12;", page_tokens.TOKENS)

    def test_two_named_widths_the_frame_by_the_window_a_component_by_its_place(self):
        # one narrow width and one wide (WP-183), each named once, and the reader's own; the script's wide width is the
        # stylesheet's
        widths = re.findall(r"@(media|container) \((?:max-width: |width < |width >= )([0-9]+px)\)", page_style.STYLE)
        self.assertEqual({page_style.NARROW, page_style.WIDE, page_style.READER}, {w for _kind, w in widths})
        self.assertIn(f"const WIDE_PX = {page_style.WIDE[:-2]};", page_core.SCRIPT_CORE)
        wide = re.search(rf"@container \(width >= {page_style.WIDE}\) \{{(.*?)\n\}}", page_style.STYLE, re.S).group(1)
        for template in ("split", "master"):
            self.assertIn(f".{template}", wide, template)
        reader = re.search(rf"@container \(width >= {page_style.READER}\) \{{(.*?)\n\}}", page_style.STYLE, re.S).group(1)
        self.assertEqual({"reader"}, {re.split(r"__|--", c)[0] for c in re.findall(r"\.([a-z][\w-]*)", reader)})
        self.assertIn("repeat(var(--grid-columns), minmax(0, 1fr))", wide)
        self.assertEqual({"media", "container"}, {kind for kind, _w in widths})
        frame = re.search(r"@media \(max-width: [0-9]+px\) \{(.*?)\n\}", page_style.STYLE, re.S).group(1)
        blocks = {re.split(r"__|--", c)[0] for c in re.findall(r"\.([a-z][\w-]*)", frame)}
        self.assertLessEqual(blocks, set(page_style.FRAME_BLOCKS) | {"field"})

    def test_the_stylesheet_parses_braces_and_parentheses_balanced_in_every_rule(self):
        # an open parenthesis in a selector swallows every rule after it — the browser drops them without a word
        style = re.sub(r"/\*.*?\*/", "", page_style.STYLE + page_tokens.TOKENS, flags=re.S)
        self.assertEqual(style.count("{"), style.count("}"))
        self.assertEqual(style.count("("), style.count(")"))
        for selector in re.findall(r"([^{}]+)\{[^{}]*\}", style):
            self.assertEqual(selector.count("("), selector.count(")"), selector.strip()[:80])

    def test_a_place_places_a_component_and_never_restyles_it(self):
        # where one block's selector reaches into another's, it may say where the other stands — its column, its
        # margin, how it aligns —, never how it looks: a look that differs is a variant of its own (`block--variant`)
        placing = re.compile(r"(grid-column|grid-row|grid-template-columns|display|margin(-[a-z]+)?|align-[a-z]+|"
                             r"justify-[a-z]+|flex(-[a-z]+)?|order|width|min-width|max-width|gap|column-gap|row-gap)$")
        restyled = []
        for selector, body in re.findall(r"([^{}]+)\{([^{}]*)\}", re.sub(r"/\*.*?\*/", "", page_style.STYLE, flags=re.S)):
            for one in selector.split(","):
                one = one.strip()
                if not one or one.startswith("@") or re.match(r"\.flow\b", one):
                    continue
                blocks = {re.split(r"__|--", c)[0] for c in re.findall(r"\.([a-z][\w-]*)", one)}
                if len(blocks) < 2:
                    continue
                props = [d.split(":")[0].strip() for d in body.split(";") if ":" in d]
                restyled += [f"{one} {{{p}}}" for p in props if not placing.match(p)]
        self.assertEqual([], restyled)

    def test_the_public_tokens_are_declared_and_listed_in_the_example(self):
        declared = set(re.findall(r"^\s*(--[a-z0-9-]+):", page_tokens.TOKENS, re.M))
        self.assertEqual([], sorted(set(page_tokens.PUBLIC) - declared))
        with open(EXAMPLE, encoding="utf-8") as handle:
            example = handle.read()
        listed = set(re.findall(r"(--[a-z0-9-]+):", example.split("A light bar")[0]))
        self.assertEqual(set(page_tokens.PUBLIC), listed)

    def test_the_mark_and_the_icon_take_the_brand(self):
        self.assertIn('fill="var(--brand)"', page.MARK)
        self.assertIn(page_tokens.ICON_BRAND, page.FAVICON)
        self.assertIn(f"--brand: {page_tokens.ICON_BRAND};", page_tokens.TOKENS)

    def test_the_page_links_the_theme_after_its_own_style(self):
        self.assertLess(page.PAGE.index("</style>"), page.PAGE.index('<link rel="stylesheet" href="/theme/theme.css">'))


if __name__ == "__main__":
    unittest.main()
