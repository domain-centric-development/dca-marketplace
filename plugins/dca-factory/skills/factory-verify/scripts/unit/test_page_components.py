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

from dca_factory.web import page, page_core, page_style, page_tokens, page_ui, page_views

LEVELS = ("atoms", "molecules", "organisms", "templates")
BEM = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*(__[a-z0-9]+(-[a-z0-9]+)*)?(--[a-z0-9]+(-[a-z0-9]+)*)?$")
#: The words the factory names a state with: never a class, always `data-state`.
STATE_WORDS = {"done", "delivered", "running", "waiting", "queued", "draft", "approved", "stopped", "failed", "superseded",
               "ok", "wait", "bad", "mute", "open", "sel", "show", "up", "down", "stopping", "now", "ready", "pass", "fail"}
COLOUR = re.compile(r"#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(")
EXAMPLE = os.path.join(os.path.dirname(os.path.abspath(page.__file__)), "..", "..", "..", "templates", "theme",
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
        self.assertEqual({"formRow"}, callers)
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

    def test_side_by_side_stands_on_the_twelve_columns(self):
        for block in ("board", "lanes", "tiles"):
            rule = re.search(r"^\." + block + r" \{([^}]*)\}", page_style.STYLE, re.M).group(1)
            self.assertIn("repeat(var(--grid-columns), minmax(0, 1fr))", rule, block)
        self.assertIn("--grid-columns: 12;", page_tokens.TOKENS)

    def test_one_width_narrows_the_page_the_frame_by_the_window_a_component_by_its_place(self):
        widths = re.findall(r"@(media|container) \((?:max-width: |width < )([0-9]+px)\)", page_style.STYLE)
        self.assertEqual({page_style.NARROW}, {w for _kind, w in widths})
        self.assertEqual({"media", "container"}, {kind for kind, _w in widths})
        frame = re.search(r"@media \(max-width: [0-9]+px\) \{(.*?)\n\}", page_style.STYLE, re.S).group(1)
        blocks = {re.split(r"__|--", c)[0] for c in re.findall(r"\.([a-z][\w-]*)", frame)}
        self.assertLessEqual(blocks, set(page_style.FRAME_BLOCKS) | {"field"})

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
