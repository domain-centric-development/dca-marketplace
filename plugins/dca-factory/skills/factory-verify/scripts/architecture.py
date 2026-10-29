"""The factory's own architecture, checked over its package's source — DCA's rules in a third language, over `ast`.

The package is built in DCA layers (WP-152): `building_blocks.py` outside every context, the bounded contexts
`discovery/`, `delivery/` and `spec/` each with `domain/`, `application/` and `adapter/{incoming,outgoing}/`, the
shared kernel `sharedkernel/`, the web host `web/` and the composition root `infrastructure/`. At the top of the
package sits the version stamp `contract.py` alone, read by name by every installed release.

    place_findings(package)   a module at the top of the package, outside every layer
    layer_findings(package)   an import against the direction of the layers, with the DCA rule id it breaks
    value_findings(package)   a bare primitive or time type in a domain field or a domain signature
    marker_findings(package)  a dataclass decorator on a value, an identifier or a domain event — their base makes them
    port_findings(package)    an output port unmarked, in the domain, unimplemented, or implemented inside the core
    cycle_findings(package)   an import cycle between two modules of the package

Each returns its findings as lines `<module>:<line> <what>`; none means the package holds. Exempt: `web/fonts.py`,
generated data.
"""

import ast
import os

CONTEXTS = ("discovery", "delivery", "spec")
#: The one module at the package's top besides the building blocks: the version stamp, which `factory.sh` and an
#: installed copy of any release read by its name.
STAMP = "contract"
EXEMPT = ("web/fonts.py",)

#: What a domain module may import from the standard library: types, data classes, enums, patterns — nothing that
#: reads a file, starts a process, asks the clock or the network (DCA-ONI-002).
PURE_STDLIB = frozenset((
    "__future__", "abc", "collections", "collections.abc", "dataclasses", "enum", "functools", "itertools",
    "re", "typing",
))

#: An application module takes the same, and `datetime` to compute with times a read model shows — the clock itself
#: it asks through an output port; everything else outside it reaches through its ports alone (DCA-LAY-003).
APPLICATION_STDLIB = PURE_STDLIB | {"datetime"}

#: A primitive or a time type: in the domain, each is wrapped in a value object (`value` its one field).
PRIMITIVES = frozenset(("str", "int", "float", "bool", "datetime", "date", "time"))


def modules(package):
    """Every module of the package: {path below the package with `/`: dotted name below it}, `__init__` as its
    package's name."""
    found = {}
    for top, dirs, files in os.walk(package):
        dirs[:] = sorted(d for d in dirs if d != "__pycache__")
        below = os.path.relpath(top, package).replace(os.sep, "/")
        for name in sorted(files):
            if not name.endswith(".py"):
                continue
            rel = name if below == "." else f"{below}/{name}"
            if rel in EXEMPT:
                continue
            dotted = rel[:-3].replace("/", ".")
            found[rel] = dotted[: -len(".__init__")] if dotted.endswith(".__init__") else \
                ("" if dotted == "__init__" else dotted)
    return found


def place_of(dotted):
    """(owner, layer) of a module: a context's or the shared kernel's `domain`, `application`, `incoming`,
    `outgoing`; `blocks`, `web`, `root`; `top` for a module at the package's top."""
    parts = dotted.split(".") if dotted else []
    if not parts:
        return ("package", "top")
    if parts[0] == "building_blocks":
        return ("blocks", "blocks")
    if parts[0] in CONTEXTS + ("sharedkernel",):
        if len(parts) > 1 and parts[1] in ("domain", "application"):
            return (parts[0], parts[1])
        if len(parts) > 2 and parts[1] == "adapter" and parts[2] in ("incoming", "outgoing"):
            return (parts[0], parts[2])
        return (parts[0], "package")
    if parts[0] == "web":
        return ("web", "web")
    if parts[0] == "infrastructure":
        return ("infrastructure", "root")
    return (parts[0], "top")


def imports_of(tree, dotted, is_package, known):
    """[(line, target)] for each import at the module's top level (not inside a function): a target inside the
    package is its dotted name below it, one outside it the module's full name prefixed with `!`."""
    found = []
    base = dotted.split(".") if dotted else []
    if not is_package:
        base = base[:-1]
    for node in tree.body:
        nodes = [node]
        if isinstance(node, (ast.If, ast.Try)):
            nodes = [n for n in ast.walk(node) if isinstance(n, (ast.Import, ast.ImportFrom))]
        for item in nodes:
            if isinstance(item, ast.Import):
                for alias in item.names:
                    if alias.name.split(".")[0] == "dca_factory":
                        found.append((item.lineno, alias.name.split(".", 1)[1] if "." in alias.name else ""))
                    else:
                        found.append((item.lineno, "!" + alias.name))
            elif isinstance(item, ast.ImportFrom):
                if item.level:
                    anchor = base[: len(base) - (item.level - 1)] if item.level > 1 else base
                    target = ".".join(anchor + ([item.module] if item.module else []))
                elif (item.module or "").split(".")[0] == "dca_factory":
                    target = item.module.split(".", 1)[1] if "." in item.module else ""
                else:
                    found.append((item.lineno, "!" + (item.module or "")))
                    continue
                named = [f"{target}.{a.name}" if target else a.name for a in item.names]
                subs = [n for n in named if n in known]
                found += [(item.lineno, n) for n in subs] or [(item.lineno, target)]
    return found


def place_findings(package):
    """Every module outside the layers: at the package's top, and neither the building blocks nor the version stamp.
    DCA has no rule id for it — the libraries place every class by its package."""
    return [f"{rel}:1 outside every layer — a module belongs to a context, the shared kernel, the web host or the root"
            for rel, dotted in sorted(modules(package).items())
            if dotted and place_of(dotted)[1] == "top" and dotted != STAMP]


def parsed(package):
    """{dotted: (rel, tree)} for every module."""
    out = {}
    for rel, dotted in modules(package).items():
        with open(os.path.join(package, rel), encoding="utf-8") as handle:
            out[dotted] = (rel, ast.parse(handle.read(), rel))
    return out


def layer_findings(package):
    """Every import against the layers. Rules, by DCA's ids:

    - DCA-ONI-001  a domain imports no application;
    - DCA-HEX-001  a domain imports no adapter (nor a module at the top, the web host or the root);
    - DCA-HEX-002  an application imports no adapter (nor a module at the top, the web host or the root);
    - DCA-HEX-006  an incoming adapter imports no outgoing adapter of its own context;
    - DCA-STR-002  the shared kernel imports no bounded context, nor a module that belongs to one;
    - DCA-STR-003  a context's application imports no other context's application;
    - DCA-STR-004  a context's domain or application imports no other context's domain;
    - DCA-STR-006  an adapter or the open host service of a context reaches another context through its `api` alone;
    - DCA-ONI-002  a domain imports nothing from outside the package but the pure standard library;
    - DCA-LAY-003  an application reaches the outside through its ports: the pure standard library, nothing else.
    """
    found = []
    trees = parsed(package)
    known = set(trees)
    for dotted, (rel, tree) in sorted(trees.items()):
        owner, layer = place_of(dotted)
        for line, target in imports_of(tree, dotted, rel.endswith("__init__.py"), known):
            where = f"{rel}:{line}"
            if target.startswith("!"):
                name = target[1:]
                if layer == "domain" and name not in PURE_STDLIB:
                    found.append(f"{where} DCA-ONI-002 the domain imports {name}")
                elif layer == "application" and name not in APPLICATION_STDLIB:
                    found.append(f"{where} DCA-LAY-003 the application imports {name} — an output port reaches it")
                continue
            to_owner, to_layer = place_of(target)
            if owner == "sharedkernel" and (to_owner in CONTEXTS or to_layer in ("top", "web", "root")):
                found.append(f"{where} DCA-STR-002 the shared kernel imports {target}")
                continue
            if to_owner in ("blocks", "package"):
                continue
            if layer == "domain":
                if to_layer == "application":
                    found.append(f"{where} DCA-ONI-001 the domain imports the application {target}")
                elif to_layer != "domain":
                    found.append(f"{where} DCA-HEX-001 the domain imports {target}")
                elif to_owner not in (owner, "sharedkernel"):
                    found.append(f"{where} DCA-STR-004 the domain of {owner} imports the domain of {to_owner}")
            elif layer == "application":
                if to_layer not in ("domain", "application"):
                    found.append(f"{where} DCA-HEX-002 the application imports {target}")
                elif to_owner not in (owner, "sharedkernel"):
                    rule = "DCA-STR-003" if to_layer == "application" else "DCA-STR-004"
                    found.append(f"{where} {rule} the application of {owner} imports the {to_layer} of {to_owner}")
            elif owner in CONTEXTS and to_owner in CONTEXTS and to_owner != owner \
                    and not (target == f"{to_owner}.api" or target.startswith(f"{to_owner}.api.")):
                found.append(f"{where} DCA-STR-006 {owner} reaches {target} — another context through its api alone")
            elif layer == "incoming" and to_owner == owner and to_layer == "outgoing":
                found.append(f"{where} DCA-HEX-006 the incoming adapter imports the outgoing adapter {target}")
    return found


def annotation_names(node):
    """Every name an annotation mentions — `typing.Optional[str]` gives Optional and str; a quoted one is read."""
    if node is None:
        return []
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        try:
            node = ast.parse(node.value, mode="eval").body
        except SyntaxError:
            return []
    names = []
    for item in ast.walk(node):
        if isinstance(item, ast.Name):
            names.append(item.id)
        elif isinstance(item, ast.Attribute):
            names.append(item.attr)
    return names


#: The building blocks whose subclasses are frozen dataclasses by their base (`building_blocks.py`).
FROZEN_MARKERS = frozenset(("Value", "Id", "DomainEvent"))


def marker_bases(cls):
    """The building blocks among a class's direct bases that make it a frozen dataclass — `Value`, `bb.Value`;
    a name inside a base's brackets (`Entity[Id]`) is no base."""
    names = set()
    for base in cls.bases:
        base = base.value if isinstance(base, ast.Subscript) else base
        names.add(getattr(base, "attr", getattr(base, "id", "")))
    return FROZEN_MARKERS & names


def is_wrapper(cls):
    """A value object around one primitive: a `Value` or an `Id` whose one field is `value`."""
    fields = [n for n in cls.body if isinstance(n, ast.AnnAssign) and "ClassVar" not in annotation_names(n.annotation)]
    return bool(marker_bases(cls) - {"DomainEvent"}) and len(fields) == 1 \
        and getattr(fields[0].target, "id", "") == "value"


def value_findings(package):
    """Every bare primitive (`str`, `int`, `float`, `bool`) or time type (`datetime`, `date`, `time`) in a domain
    field — an annotated class attribute that is no `ClassVar` — or a domain signature, a parameter's or a return's
    (DCA-TAC-025). Exempt: the one `value` field of a frozen dataclass that wraps it, the dunder methods, and a
    return of `bool` alone — a predicate, a question to the object."""
    found = []
    for dotted, (rel, tree) in sorted(parsed(package).items()):
        if place_of(dotted)[1] != "domain":
            continue

        def signature(function, where):
            if function.name.startswith("__") and function.name.endswith("__"):
                return
            arguments = function.args.posonlyargs + function.args.args + function.args.kwonlyargs \
                + [a for a in (function.args.vararg, function.args.kwarg) if a]
            for argument in arguments:
                if argument.arg in ("self", "cls"):
                    continue
                bare = sorted(PRIMITIVES & set(annotation_names(argument.annotation)))
                if bare:
                    found.append(f"{rel}:{argument.lineno} {where}{function.name}({argument.arg}) takes {', '.join(bare)}")
            bare = sorted(PRIMITIVES & set(annotation_names(function.returns)))
            if bare == ["bool"]:     # a predicate: a question to the object, not a value without a name
                bare = []
            if bare:
                found.append(f"{rel}:{function.lineno} {where}{function.name} returns {', '.join(bare)}")

        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                signature(node, "")
            if not isinstance(node, ast.ClassDef):
                continue
            wrapper = is_wrapper(node)
            for item in node.body:
                if isinstance(item, ast.AnnAssign):
                    names = annotation_names(item.annotation)
                    if "ClassVar" in names or (wrapper and getattr(item.target, "id", "") == "value"):
                        continue
                    bare = sorted(PRIMITIVES & set(names))
                    if bare:
                        found.append(f"{rel}:{item.lineno} {node.name}.{getattr(item.target, 'id', '?')} is "
                                     f"{', '.join(bare)}")
                elif isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    signature(item, f"{node.name}.")
    return found


def marker_findings(package):
    """Every value, identifier or domain event that carries a dataclass decorator of its own: its base already makes it
    a frozen dataclass, and a second decorator either fails at import or quietly changes what the base set."""
    found = []
    for dotted, (rel, tree) in sorted(parsed(package).items()):
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef) or not marker_bases(node):
                continue
            for decorator in node.decorator_list:
                target = decorator.func if isinstance(decorator, ast.Call) else decorator
                if getattr(target, "attr", getattr(target, "id", "")) == "dataclass":
                    found.append(f"{rel}:{decorator.lineno} {node.name} is a "
                                 f"{', '.join(sorted(marker_bases(node)))} — a frozen dataclass by its base, "
                                 f"without a decorator")
    return found


#: The building blocks that make a protocol an output port, and the ones that make it something else on purpose.
PORT_MARKERS = frozenset(("OutputPort", "Repository", "Store"))
OTHER_MARKERS = frozenset(("InputPort", "UseCase", "DomainGateway"))


def class_bases(cls):
    """The names of a class's direct bases — `OutputPort`, `bb.Store`, `Repository[Story, StoryId]` by its name."""
    return {getattr(b.value if isinstance(b, ast.Subscript) else b, "attr",
                    getattr(b.value if isinstance(b, ast.Subscript) else b, "id", "")) for b in cls.bases}


def public_methods(cls):
    """{name: parameter names without `self`} of the methods a class declares itself, the private ones left out."""
    return {item.name: tuple(a.arg for a in item.args.posonlyargs + item.args.args + item.args.kwonlyargs
                             if a.arg not in ("self", "cls"))
            for item in cls.body if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
            and not item.name.startswith("_")}


def drives_an_input_port(cls):
    """Whether a class drives a use case — names an input port or calls `execute` — the bridge that hands an output
    port a second use case."""
    return any((isinstance(n, (ast.Name, ast.Attribute)) and getattr(n, "id", getattr(n, "attr", "")).endswith("InputPort"))
               or (isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "execute") for n in ast.walk(cls))


def port_findings(package):
    """Every output port that is not one, has no implementation, or has one in the wrong place. Python's ports are
    protocols: an adapter fits a port by its shape and never names it, so the type checker sees a fit only where an
    adapter is assigned to the port — that a port is marked, implemented, and implemented outside the core is checked
    here. A class implements a port when it declares each of the port's methods (its own and its port bases') with
    the same parameter names. By DCA's ids:

    - DCA-HEX-009  a protocol in an application's `shared` package extends `OutputPort`, `Repository` or `Store`
      (`InputPort`, `UseCase` and a domain's `DomainGateway` are what they say);
    - DCA-HEX-010  an output port is declared in no domain;
    - DCA-TAC-015  a repository is implemented in an outgoing adapter alone;
    - DCA-TAC-020  a store is implemented in an outgoing adapter alone;
    - DCA-HEX-019  any other output port too — in the composition root only the bridge that names an input port.

    Without a rule id, as the libraries have none: a protocol elsewhere in an application that is no port, and an
    output port no class implements."""
    trees = parsed(package)
    classes = [(dotted, rel, node) for dotted, (rel, tree) in sorted(trees.items())
               for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
    blocks = {node.name: node for dotted, _rel, node in classes if dotted == "building_blocks"}
    found = []
    ports = {}
    kinds = dict.fromkeys(PORT_MARKERS)
    grown = True
    while grown:
        grown = False
        for dotted, rel, node in classes:
            kind = next((kinds[b] or b for b in sorted(class_bases(node)) if b in kinds), None)
            if dotted != "building_blocks" and kind and node.name not in ports:
                ports[node.name] = (dotted, rel, node, kind)
                kinds[node.name] = kind
                grown = True
    for dotted, rel, node in classes:
        layer = place_of(dotted)[1]
        bases = class_bases(node)
        if layer == "application" and "Protocol" in bases and not bases & (set(kinds) | OTHER_MARKERS):
            shared = ".shared." in f".{dotted}." or dotted.endswith(".shared")
            found.append(f"{rel}:{node.lineno} {'DCA-HEX-009 ' if shared else ''}{node.name} is a protocol of the "
                         f"application but no port — it extends OutputPort, Repository or Store")

    def wanted(node):
        methods = {}
        for base in sorted(class_bases(node)):
            source = ports[base][2] if base in ports else blocks.get(base)
            if source is not None and source is not node:
                methods.update(wanted(source))
        methods.update(public_methods(node))
        return methods

    for name, (dotted, rel, node, kind) in sorted(ports.items()):
        if place_of(dotted)[1] == "domain":
            found.append(f"{rel}:{node.lineno} DCA-HEX-010 the output port {name} is declared in the domain")
        methods = wanted(node)
        if not methods:
            continue
        implementations = [(d, r, c) for d, r, c in classes
                           if d != "building_blocks" and c.name not in ports and "Protocol" not in class_bases(c)
                           and all(public_methods(c).get(m) == p for m, p in methods.items())]
        if not implementations:
            found.append(f"{rel}:{node.lineno} the output port {name} has no implementation")
        for d, r, c in implementations:
            layer = place_of(d)[1]
            if layer == "root" and not drives_an_input_port(c):
                layer = "root without an input port"
            if kind in ("Repository", "Store") and layer != "outgoing":
                rule = "DCA-TAC-015" if kind == "Repository" else "DCA-TAC-020"
                found.append(f"{r}:{c.lineno} {rule} {c.name} implements the {kind.lower()} {name} outside the "
                             f"outgoing adapters")
            elif layer not in ("outgoing", "root"):
                found.append(f"{r}:{c.lineno} DCA-HEX-019 {c.name} implements the output port {name} outside the "
                             f"outgoing adapters — in the composition root only a bridge to an input port")
    return found


def cycle_findings(package):
    """Every import cycle among the package's modules, at their top level — each once, from its first module."""
    trees = parsed(package)
    known = set(trees)
    graph = {}
    for dotted, (rel, tree) in trees.items():
        graph[dotted] = sorted({t for _l, t in imports_of(tree, dotted, rel.endswith("__init__.py"), known)
                                if not t.startswith("!") and t in known and t != dotted})
    found, seen = [], set()
    for start in sorted(graph):
        stack = [(start, [start])]
        while stack:
            node, path = stack.pop()
            for nxt in graph.get(node, ()):
                if nxt == start:
                    cycle = frozenset(path)
                    if cycle not in seen:
                        seen.add(cycle)
                        found.append(" → ".join(path + [start]))
                elif nxt not in path and nxt > start:
                    stack.append((nxt, path + [nxt]))
    return found
