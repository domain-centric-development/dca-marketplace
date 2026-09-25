#!/usr/bin/env python3
"""Every skill folder carries a SKILL.md with a name and a description in its front matter, and
`dca-craft` names no DCA artifact.

Two reasons the front matter is a check and not a convention. A skill whose front matter a tool
cannot read is not a broken skill, it is an *absent* one — the tool lists everything else and says
nothing. And the `name` has to match its directory, because that is the name a project writes into
a stack profile (`carrier.build:`, `review.<perspective>:`) and the one a slash command resolves.

The boundary is a check because the place a skill sits in attracts content: `dca-craft` holds what
works without the method's artifacts, and without the check its general skills drift back towards
rule ids, `dca-*` skills, marker names and the conventions overlay. `--self-test` runs only the
boundary check's own cases.
"""

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# The general plugin and the folders under it that the boundary check reads; its README may say
# what the plugin pairs with.
BOUNDARY_PLUGIN = "dca-craft"
BOUNDARY_FOLDERS = ("skills", "agents")

# The `dca-` names a general skill may use: the plugin's own name and the marketplace's.
ALLOWED_DCA_NAMES = {"dca-craft", "dca-marketplace"}

# Type names the building blocks and rules give that DDD has no word for — the list used where no
# `dca-java` checkout sits beside this one, and always merged with what that checkout declares.
FIXED_DCA_TYPES = {
    "BaseAggregateRoot", "ContextMapRenderer", "DomainGateway", "IntegrationEventType",
    "ReadInputPort", "TransactionBoundary", "UseCaseException", "WriteInputPort",
}
# Strategic markers that are DDD words as words and DCA's only in annotation or attribute form.
FIXED_DCA_ANNOTATIONS = {"ExternalUpstream", "OpenHostService", "Partnership", "SharedKernel", "Upstream"}

# Public types of `dca-java` that are DDD's or Hexagonal's own vocabulary: never matched as a word.
# `BoundedContext` stays general in every form — other libraries carry the same annotation.
GENERAL_WORDS = {
    "AggregateRoot", "BoundedContext", "DomainEvent", "DomainEventPublisher", "DomainException",
    "DomainService", "Entity", "Factory", "Id", "InputPort", "IntegrationEvent",
    "IntegrationEventPublisher", "OpenHostService", "OutputPort", "Partnership", "Repository",
    "SharedKernel", "Specification", "Store", "Upstream", "UseCase", "Value", "ValueObject",
}

# `dca-java`'s published modules whose public types count; samples and tests do not.
DCA_JAVA_MODULES = ("dca-building-blocks", "dca-archunit", "dca-archunit-spring-modulith", "dca-spring")
PUBLIC_TYPE = re.compile(
    r"^public\s+(?:(?:final|abstract|sealed|non-sealed|static)\s+)*(@interface|interface|class|record|enum)\s+([A-Z]\w*)",
    re.MULTILINE)

FIXED_PATTERNS = (
    (re.compile(r"DCA-[A-Z]{3}-"), "a DCA rule id"),
    (re.compile(r"\bdev\.domaincentric\b"), "the building blocks' Java namespace"),
    (re.compile(r"\bDomainCentric\."), "the building blocks' .NET namespace"),
    (re.compile(r"\.(?:agents|claude)/dca\b"), "the DCA conventions overlay"),
    (re.compile(r"\bDca[A-Z][A-Za-z]+"), "a DCA type"),
)
DCA_NAME = re.compile(r"(?<![\w-])dca-[a-z][a-z0-9]*(?:-[a-z0-9]+)*")


def front_matter(path):
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    if not text.startswith("---"):
        return {}
    block = text.split("---", 2)[1]
    data = {}
    for line in block.splitlines():
        if ":" in line and not line.startswith((" ", "\t", "-")):
            key, value = line.split(":", 1)
            data[key.strip()] = value.strip()
    return data


def dca_java_types(root):
    """The public type names of the sibling `dca-java` checkout: (types, annotations), or None."""
    checkout = os.path.join(os.path.dirname(root), "dca-java")
    if not os.path.isdir(checkout):
        return None
    types, annotations = set(), set()
    for module in DCA_JAVA_MODULES:
        sources = os.path.join(checkout, module, "src", "main")
        for folder, _, files in os.walk(sources):
            for name in files:
                if not name.endswith(".java"):
                    continue
                with open(os.path.join(folder, name), encoding="utf-8") as handle:
                    for kind, type_name in PUBLIC_TYPE.findall(handle.read()):
                        (annotations if kind == "@interface" else types).add(type_name)
    return types, annotations


def boundary_patterns(read=None):
    """What the boundary check matches: the fixed patterns, one per DCA-only type name, and the
    strategic markers in annotation (`@Upstream`) or attribute (`[Upstream(`) form."""
    types, annotations = set(FIXED_DCA_TYPES), set(FIXED_DCA_ANNOTATIONS)
    if read:
        types |= read[0] | read[1]
        annotations |= read[1]
    patterns = list(FIXED_PATTERNS)
    for name in sorted(types - GENERAL_WORDS):
        patterns.append((re.compile(r"\bI?" + name + r"\b"), f"the DCA type `{name}`"))
    for name in sorted(annotations - {"BoundedContext"}):
        patterns.append((re.compile(r"(?:@" + name + r"|\[" + name + r"[\](])"), f"the DCA marker `@{name}`"))
    return patterns


def boundary_findings(line, patterns):
    """The DCA artifacts one line names."""
    found = [f"{what} (`{match.group(0)}`)" for pattern, what in patterns for match in pattern.finditer(line)]
    found += [f"the DCA name `{match.group(0)}`" for match in DCA_NAME.finditer(line)
              if match.group(0) not in ALLOWED_DCA_NAMES]
    return found


def check_boundary(root, patterns):
    problems = []
    plugin = os.path.join(root, "plugins", BOUNDARY_PLUGIN)
    for sub in BOUNDARY_FOLDERS:
        for folder, _, files in os.walk(os.path.join(plugin, sub)):
            for name in sorted(files):
                path = os.path.join(folder, name)
                try:
                    with open(path, encoding="utf-8") as handle:
                        lines = handle.read().splitlines()
                except UnicodeDecodeError:
                    continue
                where = os.path.relpath(path, os.path.join(root, "plugins"))
                for number, line in enumerate(lines, 1):
                    for finding in boundary_findings(line, patterns):
                        problems.append(f"{where}:{number}: names {finding}")
    return problems


# Lines from the texts the boundary check was written against, and lines it must leave alone.
SELF_TEST_RED = (
    "  (`DCA-NET-006` — the boundary is `ITransactionBoundary`); an `async` member",
    "- An incoming adapter injecting a domain service (`DCA-HEX-012`) — the use",
    "a rule id in prose form such as DCA-HEX-* is still a rule id",
    "  and the real dependencies disagree, and `ContextMapRenderer` renders",
    "- **`/dca-bootstrap`** — The Subdomain column feeds module selection (\"By",
    "@Upstream(context = \"product\", translation = Upstream.Translation.ANTI_CORRUPTION_LAYER,",
    "[Upstream(\"Product\", Translation.AntiCorruptionLayer, Consumes.Api, Rationale = \"…\")]",
    "`.agents/dca/conventions.md`, `.claude/dca/conventions.md`, `AGENTS.md`, `CLAUDE.md`. Take from it:",
    "   (`skills/dca-knowledge/catalog/`: `guide/elements.md`, `guide/rules.md`,",
    "- **`/dca-discipline`** — When the user wants to bend a DCA rule (e.g.",
    "the project's `DcaLayout` from the architecture test",
    "The markers are the library's (`dev.domaincentric.dca.buildingblocks.…` / `DomainCentric.BuildingBlocks.…`).",
    "A DomainGateway exception needs an explicit rationale.",
    "`dca-archunit.properties`: rule sets switched off there",
)
SELF_TEST_GREEN = (
    "/plugin install dca-craft@dca-marketplace",
    "The general reviewers live in `dca-craft`.",
    "Is the aggregate root the **only entry point** to its children? A marker on an Entity or a Repository",
    "Shared Kernel use should be minimal; an Upstream context publishes, a Partnership coordinates.",
    "an Open Host Service publishes a stable API; `@BoundedContext` is another library's annotation too",
    "- [ ] Implements `AggregateRoot<T, ID>`, a `DomainEvent` record, a `ValueObject`, an `OutputPort`",
    "a `candidate-dca` suffix or `my-dca-thing` is not a dca name; `abcdca-core` neither",
)


def self_test(patterns):
    """The boundary check's own cases; returns the failures."""
    failures = [f"not flagged: {line}" for line in SELF_TEST_RED if not boundary_findings(line, patterns)]
    failures += [f"flagged: {line} -> {boundary_findings(line, patterns)}"
                 for line in SELF_TEST_GREEN if boundary_findings(line, patterns)]
    return failures


def main():
    read = dca_java_types(ROOT)
    patterns = boundary_patterns(read)
    failures = self_test(patterns) + self_test(boundary_patterns())
    for failure in failures:
        print(f"check-skills: self-test: {failure}", file=sys.stderr)
    if "--self-test" in sys.argv[1:]:
        print(f"check-skills: self-test {'failed' if failures else 'passed'} "
              f"({len(SELF_TEST_RED)} red and {len(SELF_TEST_GREEN)} green lines, "
              f"with and without the dca-java type list)")
        return 1 if failures else 0
    problems, counted = [], 0
    for plugin in sorted(os.listdir(os.path.join(ROOT, "plugins"))):
        skills = os.path.join(ROOT, "plugins", plugin, "skills")
        if not os.path.isdir(skills):
            continue
        for name in sorted(os.listdir(skills)):
            folder = os.path.join(skills, name)
            if not os.path.isdir(folder):
                continue
            path = os.path.join(folder, "SKILL.md")
            where = f"{plugin}/skills/{name}"
            if not os.path.isfile(path):
                problems.append(f"{where}: no SKILL.md")
                continue
            counted += 1
            front = front_matter(path)
            if not front.get("name"):
                problems.append(f"{where}: front matter has no `name`")
            elif front["name"] != name:
                problems.append(f"{where}: front matter says name `{front['name']}`")
            if not front.get("description"):
                problems.append(f"{where}: front matter has no `description`")
    for problem in problems:
        print(f"check-skills: {problem}", file=sys.stderr)
    print(f"check-skills: {counted - len(problems)}/{counted} skills carry a name and a description")
    boundary = check_boundary(ROOT, patterns)
    for problem in boundary:
        print(f"check-skills: {problem}", file=sys.stderr)
    source = "dca-java's public types" if read else "the fixed type list (no dca-java checkout)"
    print(f"check-skills: {BOUNDARY_PLUGIN} names {len(boundary)} DCA artifacts (types from {source})")
    return 1 if problems or boundary or failures else 0


if __name__ == "__main__":
    sys.exit(main())
