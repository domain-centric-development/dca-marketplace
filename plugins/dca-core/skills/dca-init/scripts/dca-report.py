#!/usr/bin/env python3
"""The report `dca-new project` and `dca-init` end with — read from the disk, so it is the same every time.

The sections and fields are fixed: Stack · Generator · DCA part · Formatter · Browser runner · Proof ·
Git · Open. Every field is present; `—` stands where the disk holds nothing for it. Two facts the disk
cannot tell come from the caller: which generator made the skeleton (`--generator`) and the proof the
skill ran (`--proof start=passed`, repeated). The skill shows the output as it is.

    dca-report.py --mode new|init [--root <dir>] [--generator <text>] [--proof <check>=<result>]…
                  [--format md|text|json]
    dca-report.py --self-test
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile

SKIP_DIRS = {".git", "build", "bin", "obj", "target", "node_modules", ".gradle", ".idea", ".vs", "out"}
SECTIONS = ("Stack", "Generator", "DCA part", "Formatter", "Browser runner", "Proof", "Git", "Open")
PROOF_CHECKS = {"new": ("start", "suites", "smoke"), "init": ("architecture",)}
PROOF_WORDS = {"start": "starts, `/` answers", "suites": "every suite green",
               "smoke": "the smoke test red with an empty title", "architecture": "the architecture test"}
NONE = "—"


def files(root, suffixes=None, names=None):
    """Every file below root outside the build outputs, sorted — the order is part of the report."""
    found = []
    for base, dirs, entries in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for entry in sorted(entries):
            if (suffixes and entry.endswith(suffixes)) or (names and entry in names):
                found.append(os.path.join(base, entry))
    return found


def read(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            return handle.read()
    except OSError:
        return ""


def rel(root, path):
    return os.path.relpath(path, root).replace(os.sep, "/")


def first(pattern, text, group=1):
    match = re.search(pattern, text, re.MULTILINE)
    return match.group(group) if match else ""


def git(root, *args):
    try:
        done = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout if done.returncode == 0 else None


def agents_lines(root):
    """The `- key: `value`` lines of AGENTS.md: the description's places, the conventions file, the skills by role."""
    text = read(os.path.join(root, "AGENTS.md"))
    lines = {}
    for key, value in re.findall(r"^- ([a-z][a-z ]*): `([^`]+)`", text, re.MULTILINE):
        lines.setdefault(key, value)
    return text, lines


def conventions(root, lines):
    for path in (lines.get("conventions"), ".agents/dca/conventions.md", ".claude/dca/conventions.md"):
        if path and os.path.isfile(os.path.join(root, path)):
            text = read(os.path.join(root, path))
            keys = dict(re.findall(r"^([A-Za-z_]+):[ \t]*(.*?)[ \t]*$", text, re.MULTILINE))
            return path, {k: v.strip("`") for k, v in keys.items() if v}
    return "", {}


def stack(root):
    gradle = next((p for p in (os.path.join(root, n) for n in ("build.gradle.kts", "build.gradle")) if os.path.isfile(p)), "")
    pom = os.path.join(root, "pom.xml") if os.path.isfile(os.path.join(root, "pom.xml")) else ""
    solutions = [p for p in files(root, (".sln", ".slnx")) if os.path.dirname(p) == root]
    projects = files(root, (".csproj",))
    if gradle or pom:
        build = read(gradle or pom)
        builds = " ".join(read(p) for p in files(root, (".gradle", ".gradle.kts"), names={"pom.xml"})
                          + [read(os.path.join(root, "gradle", "libs.versions.toml"))])
        boot = first(r"org\.springframework\.boot['\"]?\)?\s+version\s+['\"]([^'\"]+)", build) \
            or first(r"<artifactId>spring-boot-starter-parent</artifactId>\s*<version>([^<]+)", build)
        java = first(r"JavaLanguageVersion\.of\((\d+)\)", builds) or first(r"<java\.version>([^<]+)", builds) \
            or first(r"sourceCompatibility\s*=\s*['\"]?(?:JavaVersion\.VERSION_)?([\d_.]+)", builds)
        tool = ("Gradle, Kotlin DSL" if gradle.endswith(".kts") else "Gradle") if gradle else "Maven"
        return dict(kind="java", fields=[
            ("language", f"Java {java}" if java else "Java"),
            ("build", tool),
            ("framework", f"Spring Boot {boot}" if boot else ("Spring Boot" if "spring-boot" in builds else NONE)),
            ("modules", str(java_modules(root, build)))], builds=builds)
    if solutions or projects:
        props = files(root, (".props", ".targets"))
        texts = " ".join(read(p) for p in projects + props)
        # a version held in an MSBuild property is read where the property is set
        for name, value in re.findall(r"<(\w+)>([\w.\-]+)</\1>", " ".join(read(p) for p in props)):
            texts = texts.replace(f"$({name})", value)
        tfm = sorted(set(re.findall(r"<TargetFrameworks?>([^<]+)<", texts)))
        web = "Microsoft.NET.Sdk.Web" in texts
        return dict(kind="dotnet", fields=[
            ("language", "C#"),
            ("build", ".NET SDK" + (f", {rel(root, solutions[0])}" if solutions else "")),
            ("framework", ("ASP.NET Core" if web else ".NET") + (f", {', '.join(tfm)}" if tfm else "")),
            ("modules", str(len(projects)))], builds=texts)
    return dict(kind="", fields=[("language", NONE), ("build", "no build file"), ("framework", NONE), ("modules", NONE)],
                builds="")


def java_modules(root, pom):
    """The Gradle subprojects or Maven modules; a build without any is one module."""
    settings = read(os.path.join(root, "settings.gradle.kts")) or read(os.path.join(root, "settings.gradle"))
    included = re.findall(r"""['"]:?([\w\-/:]+)['"]""", " ".join(re.findall(r"^\s*include\b(.*)$", settings, re.MULTILINE)))
    modules = re.findall(r"<module>([^<]+)</module>", pom)
    return len(included) or len(modules) or 1


JAVA_PACKAGES = ("dca-building-blocks", "dca-spring", "dca-archunit", "dca-archunit-spring-modulith")
DOTNET_PACKAGES = ("DomainCentric.BuildingBlocks", "DomainCentric.ArchRules.Xunit", "DomainCentric.ArchRules")


def packages(root, kind, builds):
    found = []
    if kind == "java":
        catalog = read(os.path.join(root, "gradle", "libs.versions.toml"))
        for name in JAVA_PACKAGES:
            version = first(rf"dev\.domaincentric:{re.escape(name)}:([\w.\-]+)['\"]", builds) \
                or first(rf"<artifactId>{re.escape(name)}</artifactId>\s*<version>([^<]+)", builds) \
                or first(rf"module\s*=\s*\"dev\.domaincentric:{re.escape(name)}\"[^\n]*version\s*=\s*\"([^\"]+)", catalog)
            if version or re.search(rf"dev\.domaincentric:{re.escape(name)}['\":]", builds):
                found.append(f"{name} {version}".strip())
    elif kind == "dotnet":
        central = " ".join(read(p) for p in files(root, names={"Directory.Packages.props"}))
        for name in DOTNET_PACKAGES:
            version = first(rf'<Package(?:Reference|Version)\s+Include="{re.escape(name)}"\s+Version="([^"$]+)"', builds + " " + central)
            if re.search(rf'<PackageReference\s+Include="{re.escape(name)}"', builds):
                found.append(f"{name} {version}".strip())
    return found


def dca_part(root, kind, builds, lines, conv_path):
    sources = files(root, (".java", ".cs"))
    texts = {p: read(p) for p in sources}
    arch = [rel(root, p) for p, t in texts.items() if re.search(r"(extends|:)\s*DcaArchitectureTest\b", t)]
    props = next((p for p in files(root, names={"dca-archunit.properties"})), "")
    ptext = read(props)
    sets = first(r"^dca\.rules\.sets\s*=\s*(.+)$", ptext).strip()
    warn = first(r"^dca\.rules\.warn\s*=\s*(.+)$", ptext).strip()
    off = first(r"^dca\.rules\.off\s*=\s*(.+)$", ptext).strip()
    rules = (sets or "the whole catalog") if props else ("the whole catalog (no dca-archunit.properties)" if arch else NONE)
    if props and warn:
        rules += f"; on warn: {warn}"
    if props and off:
        rules += f"; off: {off}"
    contexts = sorted(set(re.findall(r"BoundedContext\(\s*(?:name\s*[:=]\s*)?\"([^\"]+)\"", " ".join(texts.values()))))
    kernel = any(re.search(r"[@\[]SharedKernel\b", t) for t in texts.values())
    extras = [name for name, pattern in (("ContextMapDocumentationTest", r"class\s+ContextMapDocumentationTest\b"),
                                         ("ModulithTest", r"(extends|:)\s*DcaSpringModulithTest\b"))
              if any(re.search(pattern, t) for t in texts.values())]
    agents, _lines = agents_lines(root)
    section = "<!-- dca-core: start -->" in agents
    roles = [f"{k} `{v}`" for k, v in lines.items() if k not in ("conventions", "product", "tech", "domain")] if section else []
    return [("packages", ", ".join(packages(root, kind, builds)) or NONE),
            ("architecture test", ", ".join(arch) or NONE),
            ("rule sets", rules),
            ("contexts declared", f"{len(contexts)}: {', '.join(contexts)}" if contexts else "0"),
            ("shared kernel", "yes" if kernel else "no"),
            ("extra tests", ", ".join(extras) or NONE),
            ("conventions file", conv_path or NONE),
            ("AGENTS.md section", "present" if section else "missing"),
            ("skills by role", ", ".join(roles) or NONE)], dict(arch=arch, warn=warn, contexts=contexts, extras=extras,
                                                            section=section)


def formatter(root, kind, builds, conv):
    style = first(r"\b(googleJavaFormat|palantirJavaFormat|eclipse)\(", builds) if kind == "java" else ""
    if kind == "java" and ("com.diffplug.spotless" in builds or "spotless-maven-plugin" in builds):
        tool = "Spotless" + (f", {style}()" if style else "")
    elif kind == "dotnet" and os.path.isfile(os.path.join(root, ".editorconfig")):
        tool = "dotnet format, .editorconfig"
    else:
        tool = NONE
    return [("tool", tool), ("check", conv.get("format", NONE)), ("fix", conv.get("formatFix", NONE))], tool != NONE


def browser(root, kind, builds, conv):
    runner = conv.get("browser", "")
    if not runner and ("com.microsoft.playwright" in builds or "Microsoft.Playwright" in builds):
        runner = "Playwright"
    smoke = [rel(root, p) for p in files(root, (".java", ".cs", ".ts", ".js")) if re.search(r"smoke", os.path.basename(p), re.I)]
    pages = any(os.path.isdir(os.path.join(root, d)) for d in ("src/main/resources/templates", "src/main/resources/static")) \
        or bool(files(root, (".cshtml", ".razor")))
    return [("runner", runner or NONE), ("selector attribute", conv.get("selector", NONE)),
            ("application", conv.get("appStart", NONE)), ("smoke test", ", ".join(smoke) or NONE)], bool(runner), pages


def git_part(root):
    inside = git(root, "rev-parse", "--is-inside-work-tree")
    if not inside or inside.strip() != "true":
        return [("repository", "none"), ("branch", NONE), ("commits", NONE), ("uncommitted", NONE)], None
    branch = (git(root, "symbolic-ref", "--short", "HEAD") or "").strip() or NONE
    count = git(root, "rev-list", "--count", "HEAD")
    commits = count.strip() if count else "0"
    status = [l for l in (git(root, "status", "--porcelain", "--untracked-files=all") or "").splitlines() if l]
    return [("repository", "yes"), ("branch", branch), ("commits", commits),
            ("uncommitted", f"{len(status)} files" if status else "nothing")], dict(commits=commits, status=status)


def report(root, mode, generator="", proof=None):
    root = os.path.abspath(root)
    proof = proof or {}
    agents, lines = agents_lines(root)
    conv_path, conv = conventions(root, lines)
    st = stack(root)
    kind, builds = st["kind"], st["builds"]
    dca, facts = dca_part(root, kind, builds, lines, conv_path)
    fmt, has_formatter = formatter(root, kind, builds, conv)
    brw, has_runner, pages = browser(root, kind, builds, conv)
    gitf, gitfacts = git_part(root)
    checks = PROOF_CHECKS[mode]
    proofs = [(PROOF_WORDS[c], proof.get(c, NONE)) for c in checks]
    open_items = []
    described = [k for k in ("product", "tech") if os.path.isfile(os.path.join(root, lines.get(k, f"project/{k}.md")))]
    if len(described) < 2:
        open_items.append("no project description — /dca-describe")
    if not kind:
        open_items.append("no build file — /dca-new project")
    elif not facts["arch"]:
        open_items.append("no architecture test — /dca-init")
    if kind and not has_formatter:
        open_items.append("no formatter — /dca-add formatter")
    if kind and pages and not has_runner:
        open_items.append("pages without a browser runner — /dca-add browser")
    if "DCA-STR-012" in facts["warn"]:
        open_items.append("DCA-STR-012 on warn until the first layered module — /dca-new context")
    if kind and not facts["contexts"]:
        open_items.append("no bounded context declared — /dca-new context")
    claude = read(os.path.join(root, "CLAUDE.md"))
    if claude and "@AGENTS.md" not in claude:
        open_items.append("CLAUDE.md does not import AGENTS.md — add the line `@AGENTS.md`")
    if gitfacts is None:
        open_items.append("no git repository — git init")
    else:
        mapped = "docs/architecture/context-map.md"
        if "ContextMapDocumentationTest" in facts["extras"] and any(l[3:] == mapped for l in gitfacts["status"]):
            open_items.append(f"{mapped} generated, not committed yet")
        if gitfacts["commits"] == "0":
            open_items.append("nothing committed — the first commit is yours")
    open_items += [f"proof not shown: {PROOF_WORDS[c]}" for c in checks if proof.get(c, NONE) == NONE]
    title = {"new": "New DCA project", "init": "DCA added"}[mode]
    sections = [("Stack", st["fields"]),
                ("Generator", [("generator", generator or (NONE if mode == "new" else "— (an existing project)"))]),
                ("DCA part", dca), ("Formatter", fmt), ("Browser runner", brw), ("Proof", proofs),
                ("Git", gitf), ("Open", [(str(n + 1), item) for n, item in enumerate(open_items)] or [("", NONE)])]
    return dict(title=title, project=os.path.basename(root), mode=mode, sections=[dict(name=n, fields=f) for n, f in sections])


def render_md(model):
    out = [f"### {model['title']} — {model['project']}", "", "| **section** | **field** | **value** |", "|---|---|---|"]
    for section in model["sections"]:
        for n, (field, value) in enumerate(section["fields"]):
            name = f"**{section['name']}**" if n == 0 else ""
            cell = str(value).replace("|", "\\|")
            out.append(f"| {name} | {field} | {cell} |")
    return "\n".join(out)


def render_text(model):
    width = max(len(f) for s in model["sections"] for f, _v in s["fields"])
    title = f"{model['title']} — {model['project']}"
    out = [title, "═" * len(title)]
    for section in model["sections"]:
        out += ["", f"  {section['name']}"]
        out += [f"    {field.ljust(width)}   {value}" for field, value in section["fields"]]
    return "\n".join(out)


def self_test():
    def project(files_):
        root = tempfile.mkdtemp()
        for path, text in files_.items():
            os.makedirs(os.path.dirname(os.path.join(root, path)) or root, exist_ok=True)
            with open(os.path.join(root, path), "w", encoding="utf-8") as handle:
                handle.write(text)
        return root
    failures = []
    def check(name, condition):
        if not condition:
            failures.append(name)
    def field(model, section, name):
        return dict(next(s for s in model["sections"] if s["name"] == section)["fields"]).get(name)

    empty = project({})
    model = report(empty, "new")
    check("every section present, in order", [s["name"] for s in model["sections"]] == list(SECTIONS))
    check("an empty directory has no build file", field(model, "Stack", "build") == "no build file")
    check("an empty directory names what is open", "no project description — /dca-describe" in dict(field(model, "Open", "1") and model["sections"][-1]["fields"]).values())

    java = project({
        "build.gradle.kts": 'plugins { id("org.springframework.boot") version "4.0.1"\n id("com.diffplug.spotless") version "8.0.0" }\n'
                            'java { toolchain { languageVersion = JavaLanguageVersion.of(25) } }\n'
                            'dependencies { implementation("dev.domaincentric:dca-building-blocks:0.2.0")\n'
                            ' testArchitectureImplementation("dev.domaincentric:dca-archunit:0.6.0")\n'
                            ' testImplementation("com.microsoft.playwright:playwright:1.55.0") }\n'
                            'spotless { java { palantirJavaFormat() } }\n',
        "AGENTS.md": "<!-- dca-core: start -->\n- conventions: `.agents/dca/conventions.md`\n- build: `dca-modelling`\n<!-- dca-core: end -->\n"
                     "<!-- dca-describe: start -->\n- product: `project/product.md`\n- tech: `project/tech.md`\n<!-- dca-describe: end -->\n",
        "project/product.md": "# P\n", "project/tech.md": "# T\n",
        ".agents/dca/conventions.md": "format: ./gradlew spotlessCheck\nformatFix: ./gradlew spotlessApply\nselector: data-test\n",
        "src/test-architecture/java/a/ArchitectureTest.java": "class ArchitectureTest extends DcaArchitectureTest {}\n",
        "src/test-architecture/resources/dca-archunit.properties": "dca.rules.warn=DCA-STR-012\n",
        "src/main/java/a/cart/package-info.java": '@BoundedContext(name = "Cart")\npackage a.cart;\n',
        "src/main/resources/templates/index.html": "<title>x</title>",
        "src/test-e2e/java/a/SmokeTest.java": "class SmokeTest {}\n",
    })
    one = report(java, "new", "start.spring.io", {"start": "passed"})
    two = report(java, "new", "start.spring.io", {"start": "passed"})
    check("the same disk gives the same report", render_md(one) == render_md(two) and render_text(one) == render_text(two))
    check("Java and the build read", field(one, "Stack", "language") == "Java 25" and field(one, "Stack", "build") == "Gradle, Kotlin DSL")
    check("Spring Boot version read", field(one, "Stack", "framework") == "Spring Boot 4.0.1")
    check("packages with versions", field(one, "DCA part", "packages") == "dca-building-blocks 0.2.0, dca-archunit 0.6.0")
    check("the whole catalog with a warn entry", field(one, "DCA part", "rule sets") == "the whole catalog; on warn: DCA-STR-012")
    check("contexts named", field(one, "DCA part", "contexts declared") == "1: Cart")
    check("formatter style read", field(one, "Formatter", "tool") == "Spotless, palantirJavaFormat()")
    check("formatter commands from the conventions file", field(one, "Formatter", "fix") == "./gradlew spotlessApply")
    check("browser runner and selector", field(one, "Browser runner", "runner") == "Playwright"
          and field(one, "Browser runner", "selector attribute") == "data-test")
    check("generator and proof from the caller", field(one, "Generator", "generator") == "start.spring.io"
          and field(one, "Proof", "starts, `/` answers") == "passed")
    opens = [v for _k, v in next(s for s in one["sections"] if s["name"] == "Open")["fields"]]
    check("STR-012 named as open", any("DCA-STR-012" in v for v in opens))
    check("missing proof named as open", "proof not shown: every suite green" in opens)
    check("no git named as open", "no git repository — git init" in opens)
    check("a pipe in a value does not break the table", "\\|" in render_md(dict(title="t", project="p", sections=[dict(name="s", fields=[("f", "a|b")])])))

    dotnet = project({
        "Shop.slnx": "<Solution />",
        "src/Shop.Web/Shop.Web.csproj": '<Project Sdk="Microsoft.NET.Sdk.Web"><PropertyGroup><TargetFramework>net10.0</TargetFramework></PropertyGroup>'
                                        '<ItemGroup><PackageReference Include="DomainCentric.BuildingBlocks" Version="0.1.1" /></ItemGroup></Project>',
        "tests/Shop.ArchitectureTests/Shop.ArchitectureTests.csproj": '<Project Sdk="Microsoft.NET.Sdk"><ItemGroup>'
                                        '<PackageReference Include="DomainCentric.ArchRules.Xunit" Version="0.4.0" /></ItemGroup></Project>',
        "tests/Shop.ArchitectureTests/ArchitectureTest.cs": "public class ArchitectureTest : DcaArchitectureTest {}",
        "src/Shop.Web/Cart/CartContext.cs": '[BoundedContext("Cart")] public sealed class CartContext {}',
        "src/Shop.Web/SharedKernel/SharedKernelContext.cs": "[SharedKernel] public sealed class SharedKernelContext {}",
        "src/Shop.Web/Pages/Index.cshtml": "<title>x</title>",
        ".editorconfig": "root = true\n",
    })
    net = report(dotnet, "init", proof={"architecture": "green"})
    check(".NET read", field(net, "Stack", "framework") == "ASP.NET Core, net10.0")
    check(".NET packages", field(net, "DCA part", "packages") == "DomainCentric.BuildingBlocks 0.1.1, DomainCentric.ArchRules.Xunit 0.4.0")
    check("shared kernel found", field(net, "DCA part", "shared kernel") == "yes")
    check(".NET formatter", field(net, "Formatter", "tool") == "dotnet format, .editorconfig")
    check("pages without a runner named", any("browser runner" in v for _k, v in net["sections"][-1]["fields"]))
    check("init names an existing project", field(net, "Generator", "generator") == "— (an existing project)")
    names = lambda m: [(x["name"], [f for f, _v in x["fields"] if x["name"] != "Open"]) for x in m["sections"]]
    check("the same fields in Java and .NET, and on an empty directory",
          names(report(java, "init")) == names(net) == names(report(empty, "init")))
    check("json round-trips", json.loads(json.dumps(net))["sections"][0]["name"] == "Stack")

    for name in failures:
        print(f"dca-report self-test: FAIL {name}")
    print(f"dca-report self-test: {'failed' if failures else 'passed'}")
    return 1 if failures else 0


def main(argv):
    parser = argparse.ArgumentParser(description="The fixed report of dca-new project and dca-init, from the disk.")
    parser.add_argument("--mode", choices=("new", "init"))
    parser.add_argument("--root", default=".")
    parser.add_argument("--generator", default="")
    parser.add_argument("--proof", action="append", default=[], metavar="CHECK=RESULT")
    parser.add_argument("--format", choices=("md", "text", "json"), default="md")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args(argv)
    if args.self_test:
        return self_test()
    if not args.mode:
        parser.error("--mode new|init is required")
    proof = {}
    for item in args.proof:
        check, _, result = item.partition("=")
        if check not in PROOF_CHECKS[args.mode] or not result:
            parser.error(f"--proof takes {'|'.join(PROOF_CHECKS[args.mode])}=<result> in mode {args.mode}")
        proof[check] = result
    model = report(args.root, args.mode, args.generator, proof)
    print(json.dumps(model, indent=2, ensure_ascii=False) if args.format == "json"
          else render_md(model) if args.format == "md" else render_text(model))
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv[1:]))
