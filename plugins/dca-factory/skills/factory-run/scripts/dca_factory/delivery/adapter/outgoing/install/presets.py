"""Detection: what a build tool looks like, and which commands it gets, is data — one flat `key: value` file per
detection case in `templates/presets/`, applied at setup and compared by `setup --check`. The factory knows no build
tool. A preset is never read at run time — the profile is the only contract there.

One program for every use of the presets, so detection, the first profile, the check and the write cannot disagree
about what was found:

    detect                         the detected keys, one `key<TAB>value` per line; `#governance` when found
    new <template> <profile>       write a first profile from the template and what was detected
    check <profile> [brief]        what detection proposes against the profile; exit 1 on a missing key
    write <profile> [<key>]        add the missing keys; with <key>, take the detected value for that one
"""

from __future__ import annotations

import os
import re
import sys
import typing

Values = typing.Dict[str, str]

#: The roles a method skill fills, and what the role needs: the architecture governance a preset detects
#: (`governance`), a browser surface (`frontend`), or nothing (`-`). A line is written only where the skill is
#: installed beside the pipeline — a named carrier that is missing stops a run — and stays commented out otherwise, so
#: resolution by description applies.
CARRIERS = (
    ("knowledge", "dca-knowledge", "governance"),
    ("carrier.plan", "dca-modelling", "governance"),
    ("carrier.build", "dca-modelling", "governance"),
    ("carrier.guard", "dca-discipline", "governance"),
    ("review.ddd", "review-ddd", "-"),
    ("review.hexagonal", "review-hexagonal", "-"),
    ("review.clean-code", "review-clean-code", "-"),
    ("carrier.glossary", "ubiquitous-language", "-"),
    ("carrier.domain", "context-map", "-"),
    ("carrier.test", "e2e-testing", "-"),
    ("carrier.discover", "product-discovery", "-"),
    ("carrier.frontend", "frontend", "frontend"),
)
#: The order presets apply in; a later kind's value replaces an earlier one's, an empty value takes it back.
KINDS = ("stack", "browser", "format", "governance", "stub", "integration", "unit")
#: Folders no detection looks into: build output, dependencies, tool state. Bounded in depth as well, so a detection
#: never walks a whole disk from a mistaken directory.
PRUNED = {".git", ".gradle", ".idea", ".vs", "build", "bin", "obj", "target", "dist", "out",
          "node_modules", ".venv", "venv", "__pycache__", ".agents", ".claude", ".codex", ".opencode", ".dca-factory"}
DEPTH = 4
#: The project description's default places — the gate's defaults, so no key is needed for them.
LOCATIONS = {"product": "product/overview.md", "tech": "product/tech.md", "domain": "product/domain.md"}
#: Which check or stage a profile key switches on — what `--check` says beside a proposed line.
SWITCHES = {
    "knowledge": "every stage cites that catalog instead of recalling",
    "knowledge.read": "a stage reads these catalog nodes once before it writes code",
    "compile": "the test, build and tidy gates compile the tests",
    "test": "single tests and the required suites run with it",
    "e2eTest": "the criteria's end-user tests run with it",
    "filterFlag": "single tests are selected by it",
    "filterFormat": "single tests are selected by it",
    "architecture": "the build, tidy and document gates run it",
    "format": "the build and tidy gates run it",
    "formatFix": "the test, build and tidy stages correct formatting with it",
    "browser": "the plan takes browser tests for a page",
    "guarded": "a stage changes these only where its plan announces it; the acceptance shows the diff",
}
#: What decides whether a gate is green, beside the profile itself — proposed as `guarded:`. The commit hook's
#: folders; the architecture suite's rule-selection files — by name, or a project file that carries the suite's
#: section —; and the test classes that run the suite, by what each language's base or entry looks like.
HOOK_FOLDERS = (".githooks", ".husky")
RULE_SELECTION = "**/dca-archunit.properties"
RULE_SECTIONS = (("pyproject.toml", re.compile(r"^\[tool\.dca\]", re.M)),)
SUITE_SOURCES = (".java", ".kt", ".cs", ".py", ".rs")
SUITE_ENTRY = re.compile(r"\bextends\s+DcaArchitectureTest\b|:\s*DcaArchitectureTest\b|\barchitecture_tests\(|"
                         r"\bdca_tests!\s*\(")
#: How deep the walk for the suite's test classes goes — a Java package path is deeper than a preset looks.
SUITE_DEPTH = 12
#: Files that make a browser surface: templates, stylesheets, component files.
SURFACE = ("**/*.css **/*.scss **/*.sass **/*.less **/*.html **/*.pug **/*.jade **/*.cshtml **/*.razor **/*.jsx "
           "**/*.tsx **/*.vue **/*.svelte **/*.erb **/*.twig **/*.hbs **/*.njk **/*.jinja **/*.j2")


class PresetError(Exception):
    """A preset the detection cannot read, or a request it cannot answer — said in one line, exit 1."""


def conventions_file() -> str:
    """The method's configuration: `dca.profile.yaml` at the root; the conventions file of an older install until
    `factory.sh update` or `dca-init` moves it there."""
    for candidate in ("dca.profile.yaml", ".agents/dca/conventions.md", ".claude/dca/conventions.md"):
        if os.path.isfile(candidate):
            return candidate
    return ""


class Detection:
    """One detection over the project in the working directory, with the presets in <directory>."""

    def __init__(self, directory: str, python: str, conventions: str, skills: typing.Iterable[str]) -> None:
        self.directory = directory
        #: A project uv manages runs its own interpreter, with its own dependencies: the project's tools (pytest, the
        #: rule suite, the type checker) are installed there, not beside the pipeline's Python.
        self.python = "uv run python" if os.path.isfile("uv.lock") else python
        self.conventions = conventions
        self.skills = set(skills)
        self.tree: typing.Optional[typing.List[str]] = None

    def files(self) -> typing.List[str]:
        found: typing.List[str] = []
        for root, dirs, names in os.walk("."):
            depth = 0 if root == "." else root.count(os.sep)
            dirs[:] = sorted(d for d in dirs if d not in PRUNED and depth < DEPTH)
            rel = "" if root == "." else root[2:].replace(os.sep, "/") + "/"
            found += [rel + name for name in sorted(names)]
        return found

    def matches(self, globs: str) -> typing.List[str]:
        if self.tree is None:
            self.tree = self.files()
        patterns = [glob_re(g) for g in globs.split()]
        return [f for f in self.tree if any(p.match(f) for p in patterns)]

    def holds(self, key: str, value: str) -> typing.List[str]:
        """The files one detection line matched — empty when it does not hold."""
        if key == "detect.exists":
            return self.matches(value)
        if key == "detect.contains":
            globs, _, pattern = value.partition(" :: ")
            wanted = re.compile(pattern, re.M)
            hits = []
            for path in self.matches(globs):
                try:
                    if os.path.getsize(path) < 2_000_000 and wanted.search(read(path, "ignore")):
                        hits.append(path)
                except OSError:
                    pass
            return hits
        raise PresetError(f"factory: unknown detection `{key}` — a preset has detect.exists and detect.contains only")

    def guarded(self) -> str:
        """What decides whether a gate is green, found in this project: the commit hook's folder, the rule-selection
        files and the test classes that run the architecture suite — as globs from the root, the hook's folder
        whole. Empty where the project has none of them: the profile itself is guarded without a key."""
        found = [f"{folder}/**" for folder in HOOK_FOLDERS if os.path.isdir(folder)]
        found += self.matches(RULE_SELECTION)
        for name, section in RULE_SECTIONS:
            if os.path.isfile(name) and section.search(read(name, "ignore")):
                found.append(name)
        for root, dirs, names in os.walk("."):
            depth = 0 if root == "." else root.count(os.sep)
            dirs[:] = sorted(d for d in dirs if d not in PRUNED and depth < SUITE_DEPTH)
            rel = "" if root == "." else root[2:].replace(os.sep, "/") + "/"
            for name in sorted(names):
                if not name.endswith(SUITE_SOURCES):
                    continue
                try:
                    if os.path.getsize(os.path.join(root, name)) < 500_000 \
                            and SUITE_ENTRY.search(read(os.path.join(root, name), "ignore")):
                        found.append(rel + name)
                except OSError:
                    pass
        return " ".join(dict.fromkeys(found))

    def frontend_default(self, values: Values) -> bool:
        """Whether the frontend craft is the project's: it has a browser surface — a browser runner or the files of a
        page. The craft follows the method the technical description chose, so a project with rules of its own gets
        it too."""
        return values.get("browser", "none") not in ("", "none") or bool(self.matches(SURFACE))

    def detect(self) -> typing.Tuple[Values, typing.List[str], bool]:
        presets = []
        names = sorted(os.listdir(self.directory)) if os.path.isdir(self.directory) else []
        for name in names:
            if name.endswith(".preset"):
                entries = read_preset(os.path.join(self.directory, name))
                fields = dict(entries)
                if fields.get("kind") not in KINDS:
                    raise PresetError(f"factory: {name} has no `kind:` of {', '.join(KINDS)}")
                presets.append((KINDS.index(fields["kind"]), int(fields.get("order", 50)), name[:-7], entries))
        presets.sort()
        values: Values = {}
        applied: typing.List[str] = []
        governance = False
        stack: typing.Optional[str] = None
        derived: Values = {}
        for kind, _order, name, entries in presets:
            if kind == 0 and stack is not None:
                continue                                   # the first stack that holds wins
            match: typing.Optional[str] = None
            held = True
            for key, value in entries:
                if key.startswith("detect."):
                    hit = self.holds(key, value)
                    if not hit:
                        held = False
                        break
                    match = hit[0]
            if not held:
                continue
            applied.append(name)
            if kind == 0:
                stack = name
            if kind == 3:
                governance = True
            for key, value in entries:
                if key in ("kind", "order") or key.startswith("detect."):
                    continue
                if key.startswith("conventions."):
                    derived[key[len("conventions."):]] = value
                    continue
                values[key] = value.replace("{match_dir}", os.path.dirname(match or "") or ".") \
                    .replace("{match}", match or "").replace("{python}", self.python)
        values = {key: value for key, value in values.items() if value}
        # A command the method's configuration states wins over the preset's, so the profile is not a second truth:
        # the first value there (or backticked command, in an older conventions file) the preset's pattern matches.
        conventions = self.conventions
        if conventions and os.path.isfile(conventions) and derived:
            text = read(conventions)
            stated = re.findall(r"`([^`\n]+)`", text) + [line.split(":", 1)[1].strip().strip("`")
                                                         for line in text.splitlines()
                                                         if ":" in line and not line.lstrip().startswith("#")]
            for key, pattern in derived.items():
                said = next((s for s in stated if re.search(pattern, s, re.I)), "")
                if said:
                    values[key] = said
        # What depends on the installed method skills: a carrier line only for a skill that is there.
        needed = {"-": True, "governance": governance, "frontend": self.frontend_default(values)}
        for key, skill, needs in CARRIERS:
            if skill in self.skills and needed.get(needs, False):
                values[key] = skill
                # the three built-in perspectives always run; `reviews:` lists only those added to them
                if key.startswith("review.") and key not in ("review.ddd", "review.hexagonal", "review.clean-code"):
                    values["reviews"] = ", ".join(filter(None, [values.get("reviews", ""), key[len("review."):]]))
        # What a stage reads once before it writes code, from the method's conventions file (its API node) — the file
        # is the source, the profile the factory's view of it; the runner reads only the profile.
        if values.get("knowledge") and conventions and os.path.isfile(conventions):
            found = re.search(r"^building_blocks_api:[^`\n]*`([^`\n]+)`", read(conventions), re.M)
            if found:
                values["knowledge.read"] = found.group(1)
        guarded = self.guarded()
        if guarded:
            values["guarded"] = guarded
        # What the method's configuration already gives — the architecture command — is not proposed for the
        # factory's profile: it reads it from there, and a copy would be a second truth.
        if os.path.isfile("dca.profile.yaml"):
            method = {line.split(":", 1)[0].strip(): line.split(":", 1)[1].strip().strip("`")
                      for line in read("dca.profile.yaml").splitlines(True)
                      if ":" in line and not line.lstrip().startswith("#")}
            if method.get("verify_command") and values.get("architecture", "").strip() == method["verify_command"]:
                values.pop("architecture")
        return values, applied, governance


def read(path: str, errors: str = "strict") -> str:
    with open(path, encoding="utf-8", errors=errors) as handle:
        return handle.read()


def glob_re(pattern: str) -> typing.Pattern[str]:
    out, i = "", 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out, i = out + "(?:.*/)?", i + 3
        elif pattern[i] == "*":
            out, i = out + "[^/]*", i + 1
        elif pattern[i] == "?":
            out, i = out + "[^/]", i + 1
        else:
            out, i = out + re.escape(pattern[i]), i + 1
    return re.compile(out + r"\Z")


def read_preset(path: str) -> typing.List[typing.Tuple[str, str]]:
    entries = []
    for raw in read(path).splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and ":" in line:
            key, value = line.split(":", 1)
            entries.append((key.strip(), value.strip()))
    return entries


def norm(value: str) -> str:
    return value.strip().strip('"').strip("'").strip()


def active(path: str) -> Values:
    keys: Values = {}
    for raw in read(path).splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and ":" in line:
            key, value = line.split(":", 1)
            keys.setdefault(key.strip(), value.strip())
    return keys


def proposals(values: Values, profile: Values) -> typing.Tuple[typing.List[typing.Tuple[str, str]],
                                                               typing.List[typing.Tuple[str, str, str]]]:
    """(missing, differing): what detection finds that the profile lacks, and where it says otherwise. A key that
    qualifies another (`covers.test` for `test`) is proposed only while the qualified key holds the detected value —
    it describes that command, not the person's."""
    missing, differing = [], []
    for key, value in values.items():
        if key.startswith("covers."):
            base = key[len("covers."):]
            if base in profile and norm(profile[base]) != norm(values.get(base, "")):
                continue
        if key not in profile:
            missing.append((key, value))
        elif norm(profile[key]) != norm(value):
            differing.append((key, profile[key], value))
    return missing, differing


def switch(key: str) -> str:
    if key.startswith("test."):
        key = "test"
    if key.startswith("covers."):
        return f"says which tests `{key[len('covers.'):]}:` runs"
    if key.startswith("carrier."):
        return f"the {key[len('carrier.'):]} role is carried by that skill"
    if key.startswith("review."):
        return f"the judge's {key[len('review.'):]} perspective is carried by that skill"
    if key == "reviews":
        return "the judge covers these perspectives as well"
    if key in LOCATIONS:
        return "the stages read it there"
    return SWITCHES.get(key, "")


def run(detection: Detection, mode: str, rest: typing.Sequence[str]) -> int:
    """One use of the presets (the module's modes); its exit. What it cannot do is said on stderr, exit 1."""
    try:
        return modes(detection, mode, list(rest))
    except PresetError as failed:
        sys.stdout.flush()
        print(str(failed), file=sys.stderr, flush=True)
        return 1


def modes(detection: Detection, mode: str, rest: typing.List[str]) -> int:
    values, applied, governance = detection.detect()
    if mode == "detect":
        for key, value in values.items():
            print(f"{key}\t{value}")
        print("#applied\t" + " ".join(applied))
        if governance:
            print("#governance\tfound")
        return 0
    if mode == "new":
        return new_profile(values, applied, rest[0], rest[1])
    if mode == "check":
        return check_profile(values, applied, rest)
    if mode == "write":
        return write_profile(values, rest[0], rest[1] if len(rest) > 1 else "")
    raise PresetError(f"factory: unknown presets mode {mode}")


def new_profile(values: Values, applied: typing.List[str], template: str, target: str) -> int:
    out = []
    for line in read(template).splitlines():
        key = line.split(":", 1)[0].strip()
        if "{{" in line:
            # An undetected command is left out, not left as a placeholder: the gate skips and names what the profile
            # does not declare, but it would try to run a placeholder.
            if values.get(key):
                out.append(f"{key}: {values[key]}")
            continue
        out.append(line)
    written = {l.split(":", 1)[0].strip() for l in out if l and not l.startswith("#") and ":" in l}
    for key, value in values.items():
        if key in written:
            continue
        # a commented line of the template is the key's place; otherwise it goes at the end
        slot = next((i for i, line in enumerate(out) if re.match(rf"#\s*{re.escape(key)}\s*:", line)), None)
        if slot is None:
            out.append(f"{key}: {value}")
        else:
            out[slot] = f"{key}: {value}"
    with open(target, "w", encoding="utf-8") as handle:
        handle.write("\n".join(out) + "\n")
    print(f"factory: wrote {target} from {', '.join(applied) or 'no preset (nothing detected)'} — check the")
    print("factory:   commands, then add knowledge:, carrier.<role>: and review.<perspective>: where the project has them")
    return 0


def check_profile(values: Values, applied: typing.List[str], rest: typing.List[str]) -> int:
    profile = active(rest[0])
    missing, differing = proposals(values, profile)
    # Every scenario but a story's happy path runs at the integration level (contract 9), so a profile without one
    # stops the first plan. Nothing detects a decision, so it is named until it is taken.
    no_level = not any(k.startswith("test.") for k in list(profile) + list(values)) and "integration" not in profile
    # A browser suite outside `required:` never runs whole at a gate: each story runs its own tests, so a test that
    # depends on another's data or on the order passes every gate and fails the first full run.
    browser = str(profile.get("e2eTest", "")).strip()
    required = profile.get("required", "").split()
    browser_out = bool(browser) and browser != "none" and bool(required) and "e2eTest" not in required
    if rest[1:] == ["brief"]:
        if missing:
            print(f"factory: profile — detection finds {', '.join(k for k, _ in missing)} the profile does not declare "
                  "(factory.sh setup --check)")
        if no_level:
            print("factory: profile — no integration level (`test.<name>:`, or `integration: none`); the first "
                  "story's plan stops on it (/factory-setup)")
        if browser_out:
            print("factory: profile — the browser suite (e2eTest) is not in `required:`, so no gate runs it whole "
                  "(factory.sh setup --check)")
        return 0
    # The same view as the status: a table, marks, and what to do in an agent and in a shell.
    colour = sys.stdout.isatty() and not os.environ.get("NO_COLOR")

    def paint(text: str, code: str) -> str:
        return f"\x1b[{code}m{text}\x1b[0m" if colour else text

    title = f"Profile — {os.path.basename(os.getcwd())}"
    print("\n" + paint(title, "1") + "\n" + "═" * len(title) + "\n")
    print(f"  detected   {', '.join(applied) or 'nothing a preset knows'}\n")

    def label(text: str) -> str:
        return paint(text.ljust(12), "2")

    for key, value in missing:
        print("    " + paint(f"? {key}", "33") + "   missing" + (f" — {switch(key)}" if switch(key) else ""))
        print(f"        {label('detected')}   {norm(value)}\n")
    for key, have, value in differing:
        print("    " + paint(f"· {key}", "2") + "   differs — kept: the profile's value is a person's decision")
        print(f"        {label('the profile')}   {norm(have)}")
        print(f"        {label('detected')}   {norm(value)}")
        print(f"        {label('to take it')}   bash .agents/factory/factory.sh setup --write --replace {key}\n")
    if no_level:
        print("    " + paint("? integration level", "33") + "   none — every scenario but a story's happy path runs there")
        print(f"        {label('set one up')}   the method's integration-test capability (in a DCA project "
              f"`dca-add integration-tests`), then setup --write")
        print(f"        {label('or decide')}   `integration: none` in the profile — the scenarios then take the next "
              "level the project has\n")
    if browser_out:
        print("    " + paint("? e2eTest in required", "33") + "   the browser suite runs only story by story — no gate "
              "runs it whole")
        print(f"        {label('why')}   a test that depends on another's data or on the order passes every gate and "
              "fails the first full run")
        print(f"        {label('to add it')}   `required: {' '.join(required + ['e2eTest'])}` — where the suite starts "
              "the application itself;")
        print(f"        {label('')}   one that needs a system started by hand stays out and runs in CI\n")
    if not missing and not differing:
        print("    The profile declares everything detection finds.\n")
    print("─" * 72)
    if missing:
        print(f"  {paint('Next', '1')}   add the {len(missing)} missing key(s).")
        print(f"         {paint('agent'.ljust(10), '2')}   {paint('/factory-setup', '36')}")
        print(f"         {paint('shell'.ljust(10), '2')}   bash .agents/factory/factory.sh setup --write")
        print()
        return 1
    if no_level:
        print(f"  {paint('Next', '1')}   decide the integration level.")
        print(f"         {paint('agent'.ljust(10), '2')}   {paint('/factory-setup', '36')}")
        print()
        return 0
    print(f"  {paint('Next', '1')}   Nothing to add." + (" The notes are yours to keep." if differing else ""))
    print()
    return 0


def write_profile(values: Values, path: str, replace: str) -> int:
    if replace and replace not in values:
        raise PresetError(f"factory: detection finds no `{replace}:` — nothing to replace")
    profile = active(path)
    missing, _ = proposals(values, profile)
    lines = read(path).splitlines()
    changed = []
    if replace and replace in profile:
        for i, line in enumerate(lines):
            if not line.lstrip().startswith("#") and line.split(":", 1)[0].strip() == replace:
                lines[i] = f"{replace}: {values[replace]}"
                changed.append(f"{replace} (replaced)")
                break
    for key, value in missing:
        slot = next((i for i, line in enumerate(lines) if re.match(rf"#\s*{re.escape(key)}\s*:", line)), None)
        if slot is None:
            lines.append(f"{key}: {value}")
        else:
            lines[slot] = f"{key}: {value}"
        changed.append(key)
    if changed:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")
        print(f"factory: {path} — wrote {', '.join(changed)}; every other line is as it was")
    else:
        print(f"factory: {path} already declares everything detection finds — nothing written")
    return 0
